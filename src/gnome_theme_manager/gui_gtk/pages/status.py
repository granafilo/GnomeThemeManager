# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Current Status' page and system diagnostics.

Implements presentation logic for theme status and GNOME system diagnostics
consuming exclusively the public API of `ThemeManager`.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ...core.errors import GnomeThemeManagerError, GSettingsUnavailableError
from ...core.gsettings import Gtk4OverrideStatus
from ...core.models import SystemStatus, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.status")

UI_FILE = Path(__file__).parent.parent / "ui" / "status_page.ui"


@dataclass(frozen=True)
class StatusSnapshot:
    """Immutable snapshot for UI diagnostics and themes presentation."""

    themes: ThemeSet
    system_status: SystemStatus
    gtk_path: str | None = None
    icon_path: str | None = None
    cursor_path: str | None = None
    shell_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def format_optional_value(value: str | None, default: str | None = None) -> str:
    """Format optional text value."""
    if default is None:
        default = _("Not set")
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def format_boolean(
    value: bool | None,
    true_label: str | None = None,
    false_label: str | None = None,
    default: str | None = None,
) -> str:
    """Format boolean value into descriptive user string."""
    if true_label is None:
        true_label = _("Yes")
    if false_label is None:
        false_label = _("No")
    if default is None:
        default = _("Not available")
    if value is None:
        return default
    return true_label if value else false_label


def format_path(path: Path | str | None, default: str | None = None) -> str:
    """Format filesystem path for UI display."""
    if default is None:
        default = _("Not available")
    if path is None:
        return default
    return str(path)


def format_color_scheme(scheme: str | None) -> str:
    """Format GNOME color scheme (light/dark)."""
    if not scheme or scheme == "default":
        return _("Default (Light)")
    elif scheme == "prefer-dark":
        return _("Dark (Prefer dark)")
    elif scheme == "prefer-light":
        return _("Light (Prefer light)")
    return str(scheme)


def format_shell_theme(shell_theme: str | None, is_supported: bool) -> str:
    """Format GNOME Shell theme status considering User Themes extension."""
    if not is_supported:
        return _("Not managed ('User Themes' extension inactive)")
    if not shell_theme:
        return _("System Default")
    return shell_theme


def format_sandbox_status(
    available: bool,
    active_or_installed: bool,
    active_label: str,
    inactive_label: str,
) -> str:
    """Format status of sandbox runtime (Snap or Flatpak)."""
    if not available:
        return _("Not available (not installed)")
    if active_or_installed:
        return f"{_('Available')} ({active_label})"
    return f"{_('Available')} ({inactive_label})"


class StatusPage:
    """Controller for current status and system diagnostics page."""

    PAGE_ID: str = "status"
    ICON_NAME: str = "preferences-desktop-theme-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize controller loading status_page.ui template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Current Status")
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.banner_warning: Adw.Banner = self.builder.get_object("banner_warning")

        self.row_gtk_theme: Adw.ActionRow = self.builder.get_object("row_gtk_theme")
        self.row_icon_theme: Adw.ActionRow = self.builder.get_object("row_icon_theme")
        self.row_cursor_theme: Adw.ActionRow = self.builder.get_object("row_cursor_theme")
        self.row_shell_theme: Adw.ActionRow = self.builder.get_object("row_shell_theme")
        self.row_color_scheme: Adw.ActionRow = self.builder.get_object("row_color_scheme")
        self.row_gtk4_override: Adw.ActionRow = self.builder.get_object("row_gtk4_override")
        self.row_gsettings_status: Adw.ActionRow = self.builder.get_object("row_gsettings_status")
        self.row_user_themes_path: Adw.ActionRow = self.builder.get_object("row_user_themes_path")
        self.row_user_icons_path: Adw.ActionRow = self.builder.get_object("row_user_icons_path")
        self.row_flatpak_status: Adw.ActionRow = self.builder.get_object("row_flatpak_status")
        self.row_snap_status: Adw.ActionRow = self.builder.get_object("row_snap_status")

        self.error_page: Adw.StatusPage = self.builder.get_object("error_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")
        self.empty_retry_button: Gtk.Button = self.builder.get_object("empty_retry_button")

        self.error_retry_button.connect("clicked", lambda _: self.refresh())
        self.empty_retry_button.connect("clicked", lambda _: self.refresh())

        self._is_loading: bool = False
        self._generation_id: int = 0
        self.on_loading_changed: Callable[[bool], None] | None = None
        self._last_snapshot: StatusSnapshot | None = None

    def get_widget(self) -> Gtk.Widget:
        """Return root widget for embedding into window Gtk.Stack."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indicate whether a refresh is currently running."""
        return self._is_loading

    @property
    def current_snapshot(self) -> StatusSnapshot | None:
        """Return last successfully loaded snapshot."""
        return self._last_snapshot

    def refresh(self, sync: bool = False) -> None:
        """Refresh diagnostics and theme data from backend."""
        if self._is_loading and not sync:
            logger.debug("Refresh already in progress: request ignored.")
            return

        self._is_loading = True
        self._generation_id += 1
        current_generation = self._generation_id

        if self.on_loading_changed:
            self.on_loading_changed(True)
        self.widget.set_visible_child_name("loading")

        def worker_fetch() -> tuple[StatusSnapshot | None, Exception | None]:
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError(_("ThemeManager unavailable or not initialized."))

                themes = self.manager.get_current_themes()
                system_status = self.manager.get_system_status()

                gtk_path: str | None = None
                if themes.gtk_theme:
                    found = self.manager.find_theme(themes.gtk_theme, ThemeType.GTK)
                    if found:
                        gtk_path = str(found.path)

                icon_path: str | None = None
                if themes.icon_theme:
                    found = self.manager.find_theme(themes.icon_theme, ThemeType.ICON)
                    if found:
                        icon_path = str(found.path)

                cursor_path: str | None = None
                if themes.cursor_theme:
                    found = self.manager.find_theme(themes.cursor_theme, ThemeType.CURSOR)
                    if found:
                        cursor_path = str(found.path)

                shell_path: str | None = None
                if themes.shell_theme:
                    found = self.manager.find_theme(themes.shell_theme, ThemeType.SHELL)
                    if found:
                        shell_path = str(found.path)

                warnings: list[str] = []
                if not system_status.gsettings_available:
                    warnings.append(_("GSettings is unavailable in this environment."))
                if not system_status.shell_theme_supported:
                    warnings.append(_("GNOME Shell 'User Themes' extension is inactive."))
                if system_status.sandbox_status:
                    sb = system_status.sandbox_status
                    if sb.snap_available and not sb.snap_gtk_common_themes_installed:
                        warnings.append(_("Snap: 'gtk-common-themes' is not installed."))
                    if sb.flatpak_available and not sb.flatpak_filesystem_override_active:
                        warnings.append(_("Flatpak: user themes filesystem override is inactive."))

                snapshot = StatusSnapshot(
                    themes=themes,
                    system_status=system_status,
                    gtk_path=gtk_path,
                    icon_path=icon_path,
                    cursor_path=cursor_path,
                    shell_path=shell_path,
                    warnings=warnings,
                )
                return snapshot, None
            except Exception as err:
                return None, err

        def on_fetch_completed(result: tuple[StatusSnapshot | None, Exception | None]) -> bool:
            if current_generation != self._generation_id:
                logger.debug(
                    "Late callback discarded: gen %d != %d",
                    current_generation,
                    self._generation_id,
                )
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            if self.on_loading_changed:
                self.on_loading_changed(False)

            snapshot, error = result

            if error is not None:
                logger.error("Error retrieving status: %s", error)
                self._handle_error(error)
            elif snapshot is not None:
                self._apply_snapshot(snapshot)
            else:
                self.widget.set_visible_child_name("empty")

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_fetch()
            on_fetch_completed(res)
        else:

            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            thread = threading.Thread(target=thread_target, daemon=True)
            thread.start()

    def _apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Apply snapshot data to ready view widgets."""
        self._last_snapshot = snapshot

        if snapshot.themes.is_empty() and not snapshot.system_status.gsettings_available:
            self.widget.set_visible_child_name("empty")
            return

        t = snapshot.themes
        s = snapshot.system_status

        self.row_gtk_theme.set_subtitle(
            f"{format_optional_value(t.gtk_theme)} ({snapshot.gtk_path})"
            if snapshot.gtk_path
            else format_optional_value(t.gtk_theme)
        )
        self.row_icon_theme.set_subtitle(
            f"{format_optional_value(t.icon_theme)} ({snapshot.icon_path})"
            if snapshot.icon_path
            else format_optional_value(t.icon_theme)
        )
        self.row_cursor_theme.set_subtitle(
            f"{format_optional_value(t.cursor_theme)} ({snapshot.cursor_path})"
            if snapshot.cursor_path
            else format_optional_value(t.cursor_theme)
        )
        self.row_shell_theme.set_subtitle(
            format_shell_theme(t.shell_theme, s.shell_theme_supported)
        )
        self.row_color_scheme.set_subtitle(format_color_scheme(t.color_scheme))

        if s.gtk4_override_status == Gtk4OverrideStatus.ACTIVE:
            self.row_gtk4_override.set_subtitle(_("Active"))
        else:
            self.row_gtk4_override.set_subtitle(_("Inactive"))

        self.row_gsettings_status.set_subtitle(
            format_boolean(s.gsettings_available, _("Available"), _("Not available"))
        )
        self.row_user_themes_path.set_subtitle(format_path(s.user_themes_path))
        self.row_user_icons_path.set_subtitle(format_path(s.user_icons_path))

        if s.sandbox_status is not None:
            sb = s.sandbox_status
            self.row_flatpak_status.set_subtitle(
                format_sandbox_status(
                    available=sb.flatpak_available,
                    active_or_installed=sb.flatpak_filesystem_override_active,
                    active_label=_("Filesystem override active"),
                    inactive_label=_("Override inactive"),
                )
            )
            self.row_snap_status.set_subtitle(
                format_sandbox_status(
                    available=sb.snap_available,
                    active_or_installed=sb.snap_gtk_common_themes_installed,
                    active_label=_("gtk-common-themes installed"),
                    inactive_label=_("gtk-common-themes not installed"),
                )
            )
        else:
            self.row_flatpak_status.set_subtitle(_("Not available"))
            self.row_snap_status.set_subtitle(_("Not available"))

        if snapshot.warnings:
            self.banner_warning.set_title(_("Warnings: ") + " • ".join(snapshot.warnings))
            self.banner_warning.set_revealed(True)
        else:
            self.banner_warning.set_revealed(False)

        self.widget.set_visible_child_name("ready")

    def _handle_error(self, error: Exception) -> None:
        """Handle errors setting the error view."""
        if isinstance(error, GSettingsUnavailableError):
            user_msg = _(
                "GSettings is not available on this system. Ensure you are running in a "
                "GNOME environment and PyGObject (Gio) is installed."
            )
        elif isinstance(error, GnomeThemeManagerError):
            user_msg = f"{_('Theme manager error:')} {error}"
        else:
            user_msg = f"{_('An error occurred while reading status:')} {error}"

        self.error_page.set_description(user_msg)
        self.widget.set_visible_child_name("error")
