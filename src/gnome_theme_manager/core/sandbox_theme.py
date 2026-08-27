# SPDX-License-Identifier: GPL-3.0-or-later

"""System-wide theme preview session module with automatic safety rollback (Task 1.5).

Enables live system-wide preview of GNOME theme components with:
- Full system application (GSettings/dconf, GTK4 symlinks, sandboxes).
- Explicit Commit (permanent apply) and Cancel (instant rollback).
- Safety auto-rollback on application shutdown or modal dismissal.
"""

import atexit
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import ApplyResult, ThemeSet

# Protected PyGObject imports
try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gdk, Gio, Gtk

    _GTK_AVAILABLE = True
except (ImportError, ValueError, AttributeError):
    Gdk = None
    Gio = None
    Gtk = None
    _GTK_AVAILABLE = False

logger = logging.getLogger("gnome_theme_manager.core.sandbox_theme")

# CSS Provider priority: High enough to override default application styles, below user inspector
GTK_PREVIEW_PRIORITY: int = 800  # Gtk.STYLE_PROVIDER_PRIORITY_USER


def _is_loadable_gtk_css(css_file: Path) -> bool:
    """Check if CSS stylesheet can be loaded cleanly by GTK4 without missing GTK3 gresource errors."""
    if not css_file.is_file():
        return False
    try:
        content = css_file.read_text(encoding="utf-8", errors="ignore")
        # GTK3 Adwaita stubs reference /org/gtk/libgtk/theme/Adwaita/ which does not exist in GTK4
        return "org/gtk/libgtk/theme/Adwaita" not in content
    except Exception:
        return False


def resolve_gtk_theme_css_file(theme_path: Path) -> Path | None:
    """Resolve the primary CSS stylesheet file for a GTK theme directory."""
    gtk4_css = theme_path / "gtk-4.0" / "gtk.css"
    if _is_loadable_gtk_css(gtk4_css):
        return gtk4_css

    gtk4_dark = theme_path / "gtk-4.0" / "gtk-dark.css"
    if _is_loadable_gtk_css(gtk4_dark):
        return gtk4_dark

    gtk3_css = theme_path / "gtk-3.0" / "gtk.css"
    if _is_loadable_gtk_css(gtk3_css):
        return gtk3_css

    gtk3_dark = theme_path / "gtk-3.0" / "gtk-dark.css"
    if _is_loadable_gtk_css(gtk3_dark):
        return gtk3_dark

    root_css = theme_path / "gtk.css"
    if _is_loadable_gtk_css(root_css):
        return root_css

    return None


class SystemThemePreviewSession:
    """Manages transactional system-wide theme preview sessions with auto-rollback."""

    def __init__(
        self,
        get_current_themes_fn: Callable[[], ThemeSet],
        apply_themes_fn: Callable[..., ApplyResult],
    ) -> None:
        """Initialize the preview session controller.

        Args:
            get_current_themes_fn: Callable returning the current active system ThemeSet.
            apply_themes_fn: Callable executing theme application to the system.
        """
        self._get_current_themes_fn = get_current_themes_fn
        self._apply_themes_fn = apply_themes_fn

        self._snapshot_themes: ThemeSet | None = None
        self._active_preview_set: ThemeSet | None = None
        self._in_app_provider: Any | None = None
        self._in_app_resource: Any | None = None
        self._is_active: bool = False

        # Register safety cleanup hook to guarantee rollback if process terminates unexpectedly
        atexit.register(self._atexit_cleanup)

    @property
    def is_preview_active(self) -> bool:
        """Return True if a system-wide preview session is currently active."""
        return self._is_active

    @property
    def active_preview_set(self) -> ThemeSet | None:
        """Return target ThemeSet currently under preview, if any."""
        return self._active_preview_set

    @property
    def snapshot_themes(self) -> ThemeSet | None:
        """Return original ThemeSet snapshot captured before preview started."""
        return self._snapshot_themes

    def _apply_in_app_live_styles(
        self, gtk_theme_path: Path | None, icon_theme: str | None = None
    ) -> None:
        """Apply CSS provider and GtkSettings inside the running process for instant feedback."""
        self._remove_in_app_live_styles()

        if not _GTK_AVAILABLE or Gtk is None or Gdk is None:
            return

        try:
            if icon_theme:
                settings = Gtk.Settings.get_default()
                if settings is not None:
                    settings.set_property("gtk-icon-theme-name", icon_theme)

            if gtk_theme_path is None or not gtk_theme_path.is_dir():
                return

            css_file = resolve_gtk_theme_css_file(gtk_theme_path)
            if css_file is None or not css_file.is_file():
                return

            gres_candidates = [
                css_file.parent / "gtk.gresource",
                gtk_theme_path / "gtk-4.0" / "gtk.gresource",
                gtk_theme_path / "gtk-3.0" / "gtk.gresource",
            ]
            for gres_path in gres_candidates:
                if gres_path.is_file() and Gio is not None:
                    try:
                        res = Gio.Resource.load(str(gres_path))
                        Gio.Resource._register(res)
                        self._in_app_resource = res
                        break
                    except Exception as ex:
                        logger.debug("Could not load GResource from '%s': %s", gres_path, ex)

            provider = Gtk.CssProvider.new()
            provider.load_from_path(str(css_file))

            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(display, provider, GTK_PREVIEW_PRIORITY)
            self._in_app_provider = provider
        except Exception as e:
            logger.debug("In-app live style injection error: %s", e)

    def _remove_in_app_live_styles(self) -> None:
        """Remove in-app live CSS provider and GResource."""
        try:
            if (
                self._in_app_provider is not None
                and _GTK_AVAILABLE
                and Gtk is not None
                and Gdk is not None
            ):
                display = Gdk.Display.get_default()
                if display is not None:
                    Gtk.StyleContext.remove_provider_for_display(display, self._in_app_provider)
        except Exception as e:
            logger.debug("Error removing live provider: %s", e)

        try:
            if self._in_app_resource is not None and Gio is not None:
                Gio.Resource._unregister(self._in_app_resource)
        except Exception as e:
            logger.debug("Error unregistering live GResource: %s", e)
        finally:
            self._in_app_provider = None
            self._in_app_resource = None

    def start_preview(
        self,
        theme_set: ThemeSet,
        theme_path: Path | None = None,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
        force: bool = True,
    ) -> bool:
        """Start a system-wide preview session by snapshotting current state and applying new theme.

        Args:
            theme_set: New ThemeSet to preview on the system.
            theme_path: Optional filesystem path of the theme for in-process CSS reload.
            apply_gtk4_override: Whether to apply GTK4 symlink override.
            propagate_sandbox: Whether to propagate to Flatpak and Snap sandboxes.
            force: Whether to bypass structural validator blocks for preview.

        Returns:
            True if preview was successfully applied, False otherwise.
        """
        if not self._is_active:
            try:
                self._snapshot_themes = self._get_current_themes_fn()
            except Exception as e:
                logger.error("Failed to capture system theme snapshot for preview: %s", e)
                return False

        try:
            result = self._apply_themes_fn(
                theme_set,
                apply_gtk4_override=apply_gtk4_override,
                propagate_sandbox=propagate_sandbox,
                force=force,
            )
            if isinstance(result, ApplyResult):
                self._active_preview_set = theme_set
                self._is_active = True

                # Inject in-process live reload so the running app window immediately updates
                self._apply_in_app_live_styles(theme_path, icon_theme=theme_set.icon_theme)

                logger.info("System-wide theme preview active for: %s", theme_set)
                return True
            else:
                logger.warning(
                    "Theme application for preview did not return ApplyResult: %s", result
                )
                if not self._is_active:
                    self._snapshot_themes = None
                return False
        except Exception as e:
            logger.error("Exception occurred while starting theme preview: %s", e)
            if not self._is_active:
                self._snapshot_themes = None
            return False

    def commit_preview(self) -> bool:
        """Permanently commit the currently previewed theme, keeping system changes.

        Returns:
            True if active preview was committed, False if no preview was active.
        """
        if not self._is_active:
            return False

        logger.info("Committed system-wide theme preview permanently.")
        self._remove_in_app_live_styles()
        self._snapshot_themes = None
        self._active_preview_set = None
        self._is_active = False
        return True

    def cancel_preview(self, snapshot_theme_path: Path | None = None) -> bool:
        """Cancel preview and immediately restore the previous system theme snapshot.

        Returns:
            True if preview was cancelled and restored, False if no preview was active.
        """
        if not self._is_active or self._snapshot_themes is None:
            return False

        snapshot = self._snapshot_themes
        logger.info(
            "Cancelling system-wide preview. Restoring original system themes: %s", snapshot
        )

        self._remove_in_app_live_styles()

        try:
            self._apply_themes_fn(
                snapshot,
                apply_gtk4_override=True,
                propagate_sandbox=True,
                force=True,
            )
            if snapshot_theme_path:
                self._apply_in_app_live_styles(snapshot_theme_path, icon_theme=snapshot.icon_theme)
            return True
        except Exception as e:
            logger.error("Failed to restore original themes upon preview cancellation: %s", e)
            return False
        finally:
            self._snapshot_themes = None
            self._active_preview_set = None
            self._is_active = False

    def _atexit_cleanup(self) -> None:
        """Safety cleanup invoked automatically if Python process terminates."""
        if self._is_active:
            logger.warning(
                "Application terminating with active theme preview. Rolling back system theme..."
            )
            self.cancel_preview()


# Backward compatibility alias
ThemeSandboxPreview = Any
