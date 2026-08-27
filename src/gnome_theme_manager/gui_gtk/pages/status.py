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
from typing import TYPE_CHECKING, Any

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
    fallback_gtk_opts: list[str] = field(default_factory=list)
    fallback_shell_opts: list[str] = field(default_factory=list)
    fallback_icon_opts: list[str] = field(default_factory=list)
    fallback_cursor_opts: list[str] = field(default_factory=list)
    fallback_cfg_gtk3: str | None = None
    fallback_cfg_gtk4: str | None = None
    fallback_cfg_shell: str | None = None
    fallback_cfg_icons: str | None = None
    fallback_cfg_cursors: str | None = None
    auto_enable_user_theme: bool = False


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
        self.row_color_scheme: Adw.ComboRow = self.builder.get_object("row_color_scheme")
        self.row_gtk4_override: Adw.ActionRow = self.builder.get_object("row_gtk4_override")
        self.row_gsettings_status: Adw.ActionRow = self.builder.get_object("row_gsettings_status")
        self.row_user_themes_path: Adw.ActionRow = self.builder.get_object("row_user_themes_path")
        self.row_user_icons_path: Adw.ActionRow = self.builder.get_object("row_user_icons_path")
        self.group_sandbox: Adw.PreferencesGroup | None = self.builder.get_object("group_sandbox")
        self.row_flatpak_status: Adw.ActionRow = self.builder.get_object("row_flatpak_status")
        self.row_snap_status: Adw.ActionRow = self.builder.get_object("row_snap_status")

        self.on_notify_message: Callable[[str, bool], None] | None = None

        self._color_scheme_options: list[tuple[str, str]] = [
            ("default", _("Default (Light)")),
            ("prefer-dark", _("Dark")),
            ("prefer-light", _("Light")),
        ]
        self._color_scheme_values: list[str] = [v for v, _ in self._color_scheme_options]
        self._color_scheme_model = Gtk.StringList()
        for _v, label in self._color_scheme_options:
            self._color_scheme_model.append(label)

        self._updating_color_scheme: bool = False
        if self.row_color_scheme is not None:
            self.row_color_scheme.set_model(self._color_scheme_model)
            self.row_color_scheme.connect("notify::selected", self._on_color_scheme_changed)

        # Fallback Dropdowns (Task 3.1 - AdwComboRow)
        self.dropdown_fallback_gtk3: Adw.ComboRow = self.builder.get_object(
            "dropdown_fallback_gtk3"
        )
        self.dropdown_fallback_gtk4: Adw.ComboRow = self.builder.get_object(
            "dropdown_fallback_gtk4"
        )
        self.dropdown_fallback_shell: Adw.ComboRow = self.builder.get_object(
            "dropdown_fallback_shell"
        )
        self.dropdown_fallback_icons: Adw.ComboRow = self.builder.get_object(
            "dropdown_fallback_icons"
        )
        self.dropdown_fallback_cursors: Adw.ComboRow = self.builder.get_object(
            "dropdown_fallback_cursors"
        )

        self._fallback_models: dict[str, Gtk.StringList] = {
            "gtk3": Gtk.StringList.new([]),
            "gtk4": Gtk.StringList.new([]),
            "shell": Gtk.StringList.new([]),
            "icons": Gtk.StringList.new([]),
            "cursors": Gtk.StringList.new([]),
        }
        if self.dropdown_fallback_gtk3 is not None:
            self.dropdown_fallback_gtk3.set_model(self._fallback_models["gtk3"])
            self.dropdown_fallback_gtk3.connect(
                "notify::selected-item", lambda *_: self._on_fallback_changed("gtk3")
            )
        if self.dropdown_fallback_gtk4 is not None:
            self.dropdown_fallback_gtk4.set_model(self._fallback_models["gtk4"])
            self.dropdown_fallback_gtk4.connect(
                "notify::selected-item", lambda *_: self._on_fallback_changed("gtk4")
            )
        if self.dropdown_fallback_shell is not None:
            self.dropdown_fallback_shell.set_model(self._fallback_models["shell"])
            self.dropdown_fallback_shell.connect(
                "notify::selected-item", lambda *_: self._on_fallback_changed("shell")
            )
        if self.dropdown_fallback_icons is not None:
            self.dropdown_fallback_icons.set_model(self._fallback_models["icons"])
            self.dropdown_fallback_icons.connect(
                "notify::selected-item", lambda *_: self._on_fallback_changed("icons")
            )
        if self.dropdown_fallback_cursors is not None:
            self.dropdown_fallback_cursors.set_model(self._fallback_models["cursors"])
            self.dropdown_fallback_cursors.connect(
                "notify::selected-item", lambda *_: self._on_fallback_changed("cursors")
            )

        self._updating_fallbacks: bool = False
        self._updating_prefs: bool = False

        # Behavior Preferences (Task 3.2)
        self.row_auto_enable_user_theme: Any = self.builder.get_object("row_auto_enable_user_theme")
        if self.row_auto_enable_user_theme is not None:
            self.row_auto_enable_user_theme.connect(
                "notify::active", self._on_auto_enable_user_theme_changed
            )

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

                fb_gtk_opts: list[str] = []
                fb_shell_opts: list[str] = []
                fb_icon_opts: list[str] = []
                fb_cursor_opts: list[str] = []
                fb_gtk3: str | None = None
                fb_gtk4: str | None = None
                fb_shell: str | None = None
                fb_icons: str | None = None
                fb_cursors: str | None = None

                if self.manager.fallback_manager:
                    try:
                        cfg = self.manager.fallback_manager.get_config()
                        fb_gtk3 = cfg.gtk3
                        fb_gtk4 = cfg.gtk4
                        fb_shell = cfg.shell
                        fb_icons = cfg.icons
                        fb_cursors = cfg.cursors
                        fb_gtk_opts = self.manager.fallback_manager.get_available_fallback_themes(
                            ThemeType.GTK
                        )
                        fb_shell_opts = self.manager.fallback_manager.get_available_fallback_themes(
                            ThemeType.SHELL
                        )
                        fb_icon_opts = self.manager.fallback_manager.get_available_fallback_themes(
                            ThemeType.ICON
                        )
                        fb_cursor_opts = (
                            self.manager.fallback_manager.get_available_fallback_themes(
                                ThemeType.CURSOR
                            )
                        )
                    except Exception as fb_err:
                        logger.warning("Error pre-fetching fallback themes in worker: %s", fb_err)

                auto_enable_val = False
                if self.manager.extensions:
                    try:
                        prefs = self.manager.extensions.get_prefs()
                        auto_enable_val = prefs.auto_enable_user_theme
                    except Exception as pref_err:
                        logger.warning("Error loading UI prefs in worker: %s", pref_err)

                snapshot = StatusSnapshot(
                    themes=themes,
                    system_status=system_status,
                    gtk_path=gtk_path,
                    icon_path=icon_path,
                    cursor_path=cursor_path,
                    shell_path=shell_path,
                    warnings=warnings,
                    fallback_gtk_opts=fb_gtk_opts,
                    fallback_shell_opts=fb_shell_opts,
                    fallback_icon_opts=fb_icon_opts,
                    fallback_cursor_opts=fb_cursor_opts,
                    fallback_cfg_gtk3=fb_gtk3,
                    fallback_cfg_gtk4=fb_gtk4,
                    fallback_cfg_shell=fb_shell,
                    fallback_cfg_icons=fb_icons,
                    fallback_cfg_cursors=fb_cursors,
                    auto_enable_user_theme=auto_enable_val,
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

        if self.row_color_scheme is not None:
            curr_cs = t.color_scheme or "default"
            self._updating_color_scheme = True
            try:
                if curr_cs in self._color_scheme_values:
                    self.row_color_scheme.set_selected(self._color_scheme_values.index(curr_cs))
                else:
                    self.row_color_scheme.set_selected(0)
            finally:
                self._updating_color_scheme = False

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
            if sb.snap_available:
                self.row_snap_status.set_visible(True)
                self.row_snap_status.set_subtitle(
                    format_sandbox_status(
                        available=sb.snap_available,
                        active_or_installed=sb.snap_gtk_common_themes_installed,
                        active_label=_("gtk-common-themes installed"),
                        inactive_label=_("gtk-common-themes not installed"),
                    )
                )
                if self.group_sandbox is not None:
                    self.group_sandbox.set_title(
                        GLib.markup_escape_text(_("Sandbox Integration (Snap & Flatpak)"))
                    )
            else:
                self.row_snap_status.set_visible(False)
                if self.group_sandbox is not None:
                    self.group_sandbox.set_title(
                        GLib.markup_escape_text(_("Sandbox Integration (Flatpak)"))
                    )
        else:
            self.row_flatpak_status.set_subtitle(_("Not available"))
            self.row_snap_status.set_visible(True)
            self.row_snap_status.set_subtitle(_("Not available"))

        if snapshot.warnings:
            self.banner_warning.set_title(_("Warnings: ") + " • ".join(snapshot.warnings))
            self.banner_warning.set_revealed(True)
        else:
            self.banner_warning.set_revealed(False)

        self._populate_fallback_dropdowns(snapshot)

        # Update auto-enable user-theme toggle state (Task 3.2)
        if self.row_auto_enable_user_theme is not None:
            self._updating_prefs = True
            try:
                self.row_auto_enable_user_theme.set_active(snapshot.auto_enable_user_theme)
            finally:
                self._updating_prefs = False

        self.widget.set_visible_child_name("ready")

    def _populate_fallback_dropdowns(self, snapshot: StatusSnapshot | None = None) -> None:
        """Populate the 5 fallback dropdowns filtering for universal availability."""
        if self.manager is None:
            return

        self._updating_fallbacks = True
        try:
            if snapshot is not None and (snapshot.fallback_gtk_opts or snapshot.fallback_cfg_gtk3):
                gtk_opts = snapshot.fallback_gtk_opts
                shell_opts = snapshot.fallback_shell_opts
                icon_opts = snapshot.fallback_icon_opts
                cursor_opts = snapshot.fallback_cursor_opts
                gtk3_val = snapshot.fallback_cfg_gtk3
                gtk4_val = snapshot.fallback_cfg_gtk4
                shell_val = snapshot.fallback_cfg_shell
                icons_val = snapshot.fallback_cfg_icons
                cursors_val = snapshot.fallback_cfg_cursors
            else:
                cfg = self.manager.fallback_manager.get_config()
                gtk_opts = self.manager.fallback_manager.get_available_fallback_themes(
                    ThemeType.GTK
                )
                shell_opts = self.manager.fallback_manager.get_available_fallback_themes(
                    ThemeType.SHELL
                )
                icon_opts = self.manager.fallback_manager.get_available_fallback_themes(
                    ThemeType.ICON
                )
                cursor_opts = self.manager.fallback_manager.get_available_fallback_themes(
                    ThemeType.CURSOR
                )
                gtk3_val = cfg.gtk3
                gtk4_val = cfg.gtk4
                shell_val = cfg.shell
                icons_val = cfg.icons
                cursors_val = cfg.cursors

            self._fill_string_list(
                self._fallback_models["gtk3"], self.dropdown_fallback_gtk3, gtk_opts, gtk3_val
            )
            self._fill_string_list(
                self._fallback_models["gtk4"], self.dropdown_fallback_gtk4, gtk_opts, gtk4_val
            )
            self._fill_string_list(
                self._fallback_models["shell"], self.dropdown_fallback_shell, shell_opts, shell_val
            )
            self._fill_string_list(
                self._fallback_models["icons"], self.dropdown_fallback_icons, icon_opts, icons_val
            )
            self._fill_string_list(
                self._fallback_models["cursors"],
                self.dropdown_fallback_cursors,
                cursor_opts,
                cursors_val,
            )
        finally:
            self._updating_fallbacks = False

    def _fill_string_list(
        self,
        string_list: Gtk.StringList,
        dropdown: Gtk.DropDown | None,
        items: list[str],
        selected: str | None,
    ) -> None:
        """Fill string list and set selected index."""
        while string_list.get_n_items() > 0:
            string_list.remove(0)

        selected_idx = 0
        for idx, it in enumerate(items):
            string_list.append(it)
            if selected and it == selected:
                selected_idx = idx

        if dropdown is not None and items:
            dropdown.set_selected(selected_idx)

    def _on_fallback_changed(self, component_key: str) -> None:
        """Handle user selection changes on fallback dropdowns."""
        if self._updating_fallbacks or self.manager is None:
            return

        dropdown_map = {
            "gtk3": self.dropdown_fallback_gtk3,
            "gtk4": self.dropdown_fallback_gtk4,
            "shell": self.dropdown_fallback_shell,
            "icons": self.dropdown_fallback_icons,
            "cursors": self.dropdown_fallback_cursors,
        }
        dd = dropdown_map.get(component_key)
        if dd is None:
            return

        sel_item = dd.get_selected_item()
        if sel_item is None:
            return
        selected_val = sel_item.get_string() if hasattr(sel_item, "get_string") else str(sel_item)

        cfg = self.manager.fallback_manager.get_config()
        if component_key == "gtk3":
            cfg.gtk3 = selected_val
        elif component_key == "gtk4":
            cfg.gtk4 = selected_val
        elif component_key == "shell":
            cfg.shell = selected_val
        elif component_key == "icons":
            cfg.icons = selected_val
        elif component_key == "cursors":
            cfg.cursors = selected_val
        self.manager.fallback_manager.save_config(cfg)
        logger.debug("Updated fallback config for '%s' to '%s'", component_key, selected_val)

    def _on_auto_enable_user_theme_changed(self, *_: Any) -> None:
        """Handle toggle state change for auto_enable_user_theme preference."""
        if self._updating_prefs or self.manager is None or self.row_auto_enable_user_theme is None:
            return
        is_active = bool(self.row_auto_enable_user_theme.get_active())
        if self.manager.extensions:
            self.manager.extensions.set_auto_enable_user_theme(is_active)
            logger.info("Auto-enable User Themes preference set to %s", is_active)

    def _on_color_scheme_changed(self, *args: Any) -> None:
        """Handle user changing color scheme preference from Status page."""
        if getattr(self, "_updating_color_scheme", False) or self.row_color_scheme is None:
            return

        idx = self.row_color_scheme.get_selected()
        if 0 <= idx < len(self._color_scheme_values):
            val = self._color_scheme_values[idx]
            try:
                if self.manager.gsettings is not None:
                    self.manager.gsettings.set_color_scheme(val)
                    logger.info("Color scheme updated to '%s' from Status page.", val)
                    if self.on_notify_message:
                        self.on_notify_message(
                            _("Color scheme preference updated to '{scheme}'.").format(
                                scheme=self._color_scheme_options[idx][1]
                            ),
                            False,
                        )
            except Exception as err:
                logger.error("Failed to update color scheme from Status page: %s", err)
                if self.on_notify_message:
                    self.on_notify_message(str(err), True)

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
