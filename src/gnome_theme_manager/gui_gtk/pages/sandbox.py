# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Sandbox Tools' page.

Provides runtime diagnostics for sandbox environments (Flatpak and Snap),
status of `gtk-common-themes` package, compatibility checks for active themes,
and manual propagation of filesystem permissions and environment variables.
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
from gi.repository import Adw, GLib, Gtk

from ...core.errors import GSettingsUnavailableError
from ...core.models import PropagationResult, SandboxStatus, ThemeSet
from ...core.sandbox_bridge import KNOWN_SNAP_COMMON_THEMES

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")

UI_FILE = Path(__file__).parent.parent / "ui" / "sandbox_page.ui"


@dataclass(frozen=True)
class SandboxDiagnosticsData:
    """Immutable data container for sandbox status and diagnostics."""

    status: SandboxStatus
    themes: ThemeSet
    is_compat: bool = False
    has_custom_snap: bool = False
    expected_snap_name: str = ""
    connected_targets: list[str] = field(default_factory=list)


class SandboxPage:
    """Controller for 'Sandbox Tools' GTK4/Libadwaita GUI view."""

    PAGE_ID: str = "sandbox"
    ICON_NAME: str = "changes-allow-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize controller loading sandbox_page.ui template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Sandbox Tools")
        self.icon_name: str = self.ICON_NAME
        self.manager: ThemeManager | None = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        self.loading_spinner: Gtk.Spinner = self.builder.get_object("loading_spinner")
        self.loading_label: Gtk.Label = self.builder.get_object("loading_label")

        self.active_gtk_row: Adw.ActionRow = self.builder.get_object("active_gtk_row")
        self.active_icon_row: Adw.ActionRow = self.builder.get_object("active_icon_row")

        self.flatpak_group: Adw.PreferencesGroup | None = self.builder.get_object("flatpak_group")
        self.flatpak_status_row: Adw.ActionRow = self.builder.get_object("flatpak_status_row")
        self.flatpak_status_icon: Gtk.Image | None = self.builder.get_object("flatpak_status_icon")
        self.flatpak_override_row: Adw.ActionRow = self.builder.get_object("flatpak_override_row")
        self.flatpak_notes_row: Adw.ActionRow = self.builder.get_object("flatpak_notes_row")

        self.snap_group: Adw.PreferencesGroup | None = self.builder.get_object("snap_group")
        self.snap_status_row: Adw.ActionRow = self.builder.get_object("snap_status_row")
        self.snap_status_icon: Gtk.Image | None = self.builder.get_object("snap_status_icon")
        self.snap_gtk_common_row: Adw.ActionRow = self.builder.get_object("snap_gtk_common_row")
        self.snap_theme_compat_row: Adw.ActionRow = self.builder.get_object("snap_theme_compat_row")
        self.snap_installed_content_row: Adw.ActionRow = self.builder.get_object(
            "snap_installed_content_row"
        )
        self.snap_connected_apps_row: Adw.ActionRow = self.builder.get_object(
            "snap_connected_apps_row"
        )
        self.snap_build_custom_row: Adw.ActionRow = self.builder.get_object("snap_build_custom_row")
        self.snap_build_custom_button: Gtk.Button = self.builder.get_object(
            "snap_build_custom_button"
        )
        self.snap_notes_row: Adw.ActionRow = self.builder.get_object("snap_notes_row")

        self.sandbox_help_button: Gtk.Button = self.builder.get_object("sandbox_help_button")
        self.refresh_button: Gtk.Button = self.builder.get_object("refresh_button")
        self.propagate_button: Gtk.Button = self.builder.get_object("propagate_button")

        self.error_status_page: Adw.StatusPage = self.builder.get_object("error_status_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        self._button_configs: dict[str, tuple[str, str]] = {
            "sandbox_help_button": (_("Sandbox Guide"), "help-about-symbolic"),
            "refresh_button": (_("Refresh Status"), "emblem-synchronizing-symbolic"),
            "propagate_button": (_("Propagate Theme to Sandboxed Apps"), "emblem-ok-symbolic"),
            "error_retry_button": (_("Retry"), "emblem-synchronizing-symbolic"),
        }
        for btn_attr, (lbl, icon) in self._button_configs.items():
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                btn.set_label(lbl)
                btn._icon_name = icon
                btn.get_icon_name = lambda _btn_self=btn, _icon_val=icon: _icon_val

        self._is_loading: bool = False
        self._is_propagating: bool = False
        self._refresh_generation: int = 0
        self._propagate_generation: int = 0
        self._confirm_dialog_open: bool = False
        self._current_sandbox_status: SandboxStatus | None = None
        self._current_themes: ThemeSet | None = None

        self.on_sandbox_propagated: Callable[[], None] | None = None

        if self.sandbox_help_button is not None:
            self.sandbox_help_button.connect("clicked", self._on_help_clicked)
        self.refresh_button.connect("clicked", lambda _btn: self.refresh())
        self.propagate_button.connect("clicked", self._on_propagate_clicked)
        self.snap_build_custom_button.connect("clicked", self._on_build_snap_clicked)
        self.error_retry_button.connect("clicked", lambda _btn: self.refresh())

    def get_widget(self) -> Gtk.Stack:
        """Return main Gtk.Stack widget."""
        return self.widget

    def _set_state(self, state_name: str) -> None:
        """Set visible stack state."""
        self.widget.set_visible_child_name(state_name)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Enable or disable action controls."""
        self.refresh_button.set_sensitive(sensitive)
        self.error_retry_button.set_sensitive(sensitive)

        if not sensitive:
            self.propagate_button.set_sensitive(False)
        else:
            sb = self._current_sandbox_status
            can_propagate = bool(sb and (sb.flatpak_available or sb.snap_available))
            self.propagate_button.set_sensitive(can_propagate)

    def refresh(self, sync: bool = False) -> None:
        """Refresh sandbox diagnostics and compatibility asynchronously."""
        if self._is_loading and not sync:
            logger.debug("Sandbox refresh already in progress, request ignored.")
            return

        self._is_loading = True
        self._refresh_generation += 1
        current_gen = self._refresh_generation

        self._set_state("loading")
        self._set_controls_sensitive(False)

        def worker_fetch() -> tuple[SandboxDiagnosticsData | None, Exception | None]:
            try:
                if self.manager is None:
                    return (
                        SandboxDiagnosticsData(
                            status=SandboxStatus(),
                            themes=ThemeSet(),
                        ),
                        None,
                    )

                sb_status = self.manager.get_sandbox_status()
                current_themes: ThemeSet
                try:
                    current_themes = self.manager.get_current_themes()
                except GSettingsUnavailableError:
                    current_themes = ThemeSet()

                active_gtk = current_themes.gtk_theme
                is_compat = False
                has_custom_snap = False
                expected_snap_name = ""
                connected_targets: list[str] = []

                if sb_status.snap_available and active_gtk:
                    norm_name = active_gtk.strip().lower()
                    if norm_name in KNOWN_SNAP_COMMON_THEMES:
                        is_compat = True
                    else:
                        from gnome_theme_manager.core.theme_snap_manager.detector import (
                            ThemeDetector,
                        )

                        detector = ThemeDetector()
                        is_compat, _slots = detector.check_theme_compatibility(active_gtk)

                    expected_snap_name = (
                        f"custom-theme-{norm_name.replace(' ', '-').replace('_', '-')}"
                    )
                    if not is_compat:
                        from gnome_theme_manager.core.theme_snap_manager.connector import (
                            SnapConnector,
                        )

                        connector = SnapConnector(expected_snap_name)
                        installed_snaps = connector.get_installed_snaps()
                        has_custom_snap = expected_snap_name in installed_snaps
                        if has_custom_snap:
                            connected_targets = sorted(
                                connector.get_snaps_using_common_themes()
                            )

                return (
                    SandboxDiagnosticsData(
                        status=sb_status,
                        themes=current_themes,
                        is_compat=is_compat,
                        has_custom_snap=has_custom_snap,
                        expected_snap_name=expected_snap_name,
                        connected_targets=connected_targets,
                    ),
                    None,
                )
            except Exception as err:
                return None, err

        def on_fetch_completed(
            result: tuple[SandboxDiagnosticsData | None, Exception | None],
        ) -> bool:
            if current_gen != self._refresh_generation:
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            diag_data, error = result

            if error is not None or diag_data is None:
                logger.error("Error retrieving sandbox diagnostics: %s", error)
                self.error_status_page.set_description(
                    f"{_('Sandbox diagnostics error:')} {error}"
                )
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            self._current_sandbox_status = diag_data.status
            self._current_themes = diag_data.themes

            self._update_ui_presentation(diag_data)
            self._set_state("ready")
            self._set_controls_sensitive(True)
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_fetch()
            on_fetch_completed(res)
        else:

            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    def _update_ui_presentation(
        self,
        data: SandboxDiagnosticsData,
    ) -> None:
        """Update UI rows with diagnostic data (pure GTK widget calls, no I/O)."""
        sb = data.status
        themes = data.themes

        # Update active desktop configuration display
        active_gtk_text = (themes.gtk_theme or "") if themes else ""
        active_icon_text = (themes.icon_theme or "") if themes else ""
        active_cursor_text = (themes.cursor_theme or "") if themes else ""

        if self.active_gtk_row is not None:
            self.active_gtk_row.set_subtitle(active_gtk_text or _("None detected"))

        if self.active_icon_row is not None:
            if active_icon_text and active_cursor_text and active_icon_text != active_cursor_text:
                self.active_icon_row.set_subtitle(
                    f"{active_icon_text} ({_('Cursors')}: {active_cursor_text})"
                )
            else:
                self.active_icon_row.set_subtitle(
                    active_icon_text or active_cursor_text or _("None detected")
                )

        if sb.flatpak_available:
            self.flatpak_status_row.set_subtitle(_("Available on system"))
            if self.flatpak_status_icon is not None:
                self.flatpak_status_icon.set_from_icon_name("emblem-default-symbolic")
        else:
            self.flatpak_status_row.set_subtitle(_("Not installed"))
            if self.flatpak_status_icon is not None:
                self.flatpak_status_icon.set_from_icon_name("dialog-information-symbolic")

        if not sb.flatpak_available:
            self.flatpak_override_row.set_subtitle(_("Not applicable (Flatpak not present)"))
        elif sb.flatpak_filesystem_override_active:
            self.flatpak_override_row.set_subtitle(_("Active (~/.local/share/themes and icons)"))
        else:
            self.flatpak_override_row.set_subtitle(_("Not configured"))

        if self.flatpak_group is not None:
            self.flatpak_group.set_visible(True)

        if self.snap_group is not None:
            self.snap_group.set_visible(sb.snap_available)

        if sb.snap_available:
            self.snap_status_row.set_subtitle(_("Available on system"))
            if self.snap_status_icon is not None:
                self.snap_status_icon.set_from_icon_name("emblem-default-symbolic")
        else:
            self.snap_status_row.set_subtitle(_("Not installed"))
            if self.snap_status_icon is not None:
                self.snap_status_icon.set_from_icon_name("dialog-information-symbolic")

        if not sb.snap_available:
            self.snap_gtk_common_row.set_subtitle(_("Not applicable (Snap not present)"))
        elif sb.snap_gtk_common_themes_installed:
            self.snap_gtk_common_row.set_subtitle(_("Installed"))
        else:
            self.snap_gtk_common_row.set_subtitle(_("Not installed (recommended for GTK themes)"))

        active_gtk = (themes.gtk_theme or "") if themes else ""
        if not sb.snap_available or not sb.snap_gtk_common_themes_installed:
            self.snap_theme_compat_row.set_subtitle(
                _("Not verifiable (Snap or gtk-common-themes absent)")
            )
            self.snap_installed_content_row.set_visible(False)
            self.snap_connected_apps_row.set_visible(False)
            self.snap_build_custom_row.set_visible(False)
        elif not active_gtk:
            self.snap_theme_compat_row.set_subtitle(_("No active GTK theme detected"))
            self.snap_installed_content_row.set_visible(False)
            self.snap_connected_apps_row.set_visible(False)
            self.snap_build_custom_row.set_visible(False)
        else:
            is_compat = data.is_compat
            has_custom_snap = data.has_custom_snap
            expected_snap_name = data.expected_snap_name
            connected_targets = data.connected_targets

            if is_compat:
                self.snap_theme_compat_row.set_subtitle(
                    f"{_('Theme')} '{active_gtk}' {_('natively supported by gtk-common-themes')}"
                )
                self.snap_installed_content_row.set_visible(False)
                self.snap_connected_apps_row.set_visible(False)
                self.snap_build_custom_row.set_visible(False)
            else:
                self.snap_theme_compat_row.set_subtitle(
                    f"{_('Theme')} '{active_gtk}' {_('custom (requires dedicated snap)')}"
                )
                self.snap_installed_content_row.set_visible(True)
                self.snap_connected_apps_row.set_visible(True)

                if has_custom_snap:
                    self.snap_installed_content_row.set_subtitle(
                        f"{expected_snap_name} ({_('Installed & Active')})"
                    )
                    if connected_targets:
                        apps_list = ", ".join(connected_targets)
                        self.snap_connected_apps_row.set_subtitle(
                            f"{len(connected_targets)} {_('apps')}: {apps_list}"
                        )
                    else:
                        self.snap_connected_apps_row.set_subtitle(
                            _("No consuming Snap apps detected")
                        )

                    self.snap_build_custom_row.set_visible(True)
                    self.snap_build_custom_button.set_label(_("Rebuild Snap"))
                    self.snap_build_custom_row.set_subtitle(
                        _(
                            "Content Snap is active. Click to rebuild and re-sync if theme files changed."
                        )
                    )
                else:
                    self.snap_installed_content_row.set_subtitle(_("Not installed"))
                    self.snap_connected_apps_row.set_subtitle(_("None (Content Snap not present)"))
                    self.snap_build_custom_row.set_visible(True)
                    self.snap_build_custom_button.set_label(_("Build Snap"))
                    self.snap_build_custom_row.set_subtitle(
                        _(
                            "Generate and connect Content Snap for '{theme}' to remove missing themes alert."
                        ).format(theme=active_gtk)
                    )

    def _on_build_snap_clicked(self, _btn: Gtk.Button | None) -> None:
        """Handle building and connecting custom theme snap."""
        if not self.manager or not self._current_themes or not self._current_themes.gtk_theme:
            self._show_toast(_("No active GTK theme available to package."))
            return

        theme_name = self._current_themes.gtk_theme
        self._show_toast(_("Building Content Snap for '{theme}'…").format(theme=theme_name))
        self.snap_build_custom_button.set_sensitive(False)

        def worker() -> tuple[dict[str, Any] | None, Exception | None]:
            try:
                assert self.manager is not None
                res = self.manager.apply_custom_theme_to_snap(theme_name)
                return res, None
            except Exception as err:
                return None, err

        def on_done(result: tuple[dict[str, Any] | None, Exception | None]) -> bool:
            self.snap_build_custom_button.set_sensitive(True)
            res, err = result
            if err:
                logger.error("Failed building Content Snap: %s", err)
                self._show_toast(f"{_('Snap packaging failed:')} {err}")
            elif res:
                snap_name = res.get("snap_name", "")
                self._show_toast(
                    _("Content Snap '{snap}' installed and connected to Snap applications!").format(
                        snap=snap_name
                    )
                )
                self.refresh()
            return GLib.SOURCE_REMOVE

        def run_thread() -> None:
            res = worker()
            GLib.idle_add(on_done, res)

        threading.Thread(target=run_thread, daemon=True).start()

    def _on_propagate_clicked(self, _button: Gtk.Button | None = None) -> None:
        """Open confirmation dialog before propagation."""
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True
        root_window = self._get_root_window()
        heading = _("Propagate theme to sandboxed applications?")
        body = _(
            "This operation configures filesystem overrides for Flatpak and "
            "verifies compatibility of active themes with Snap.\n\n"
            "Not all sandboxed applications or themes can be updated automatically."
        )

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading, body)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("propagate", _("Propagate Theme"))
            dialog.set_response_appearance("propagate", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("propagate")
            dialog.set_close_response("cancel")

            def on_dialog_response(d: Any, response_param: Any) -> None:
                try:
                    if hasattr(d, "choose_finish") and not isinstance(response_param, str):
                        try:
                            resp = d.choose_finish(response_param)
                        except (GLib.GError, TypeError, ValueError):
                            resp = str(response_param)
                    else:
                        resp = str(response_param)

                    if resp == "propagate":
                        self._run_propagation()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(root_window if isinstance(root_window, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                root_window if isinstance(root_window, Gtk.Window) else None,
                heading,
                body,
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("propagate", _("Propagate Theme"))
            dialog.set_response_appearance("propagate", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("propagate")
            dialog.set_close_response("cancel")

            def on_msg_response(_dlg: Any, response: str) -> None:
                try:
                    if response == "propagate":
                        self._run_propagation()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False
            self._run_propagation()

    def _run_propagation(self, sync: bool = False) -> None:
        """Execute propagation."""
        if self._is_propagating and not sync:
            logger.debug("Propagation already in progress, request ignored.")
            return

        self._is_propagating = True
        self._propagate_generation += 1
        current_gen = self._propagate_generation

        self._set_controls_sensitive(False)

        def worker_propagate() -> tuple[PropagationResult | None, Exception | None]:
            try:
                if self.manager is None:
                    return PropagationResult(), None
                res = self.manager.propagate_sandbox()
                return res, None
            except Exception as err:
                return None, err

        def on_propagation_completed(
            result: tuple[PropagationResult | None, Exception | None],
        ) -> bool:
            if current_gen != self._propagate_generation:
                return GLib.SOURCE_REMOVE

            self._is_propagating = False
            prop_res, error = result

            self.refresh(sync=True)

            if error is not None:
                logger.error("Error during sandbox propagation: %s", error)
                self._show_toast(f"{_('Error during propagation:')} {error}")
            elif prop_res is not None:
                if prop_res.warnings:
                    warn_summary = "; ".join(prop_res.warnings[:2])
                    self._show_toast(f"{_('Propagation completed with warnings:')} {warn_summary}")
                elif prop_res.flatpak_success or prop_res.snap_success:
                    self._show_toast(_("Theme propagated successfully to sandboxed applications."))
                else:
                    self._show_toast(_("No changes applied to sandbox environments."))

                if self.on_sandbox_propagated:
                    try:
                        self.on_sandbox_propagated()
                    except Exception as e:
                        logger.warning("Error in on_sandbox_propagated callback: %s", e)

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_propagate()
            on_propagation_completed(res)
        else:

            def thread_target() -> None:
                res = worker_propagate()
                GLib.idle_add(on_propagation_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    def _on_help_clicked(self, _btn: Any) -> None:
        """Display comprehensive, wide guide window with terminal commands for Sandbox theme integration."""
        root_window = self.widget.get_root() if hasattr(self.widget, "get_root") else None
        parent_win = root_window if isinstance(root_window, Gtk.Window) else None

        win = Adw.Window()
        win.set_title(_("Sandbox Integration Guide"))
        win.set_modal(True)
        if parent_win is not None:
            win.set_transient_for(parent_win)
        win.set_default_size(680, 560)

        toolbar_view = Adw.ToolbarView()
        header_bar = Adw.HeaderBar()
        header_bar.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header_bar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(620)
        clamp.set_margin_top(18)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # 1. Flatpak Group
        flatpak_group = Adw.PreferencesGroup()
        flatpak_group.set_title(_("Flatpak Integration"))
        flatpak_group.set_description(
            _("Grant isolated Flatpak applications read-only access to user themes and icons.")
        )

        flatpak_oneclick_row = Adw.ActionRow()
        flatpak_oneclick_row.set_title(_("Automatic 1-Click Setup"))
        flatpak_oneclick_row.set_subtitle(
            _("Click 'Propagate Themes' on the Sandbox page to configure overrides automatically.")
        )
        flatpak_group.add(flatpak_oneclick_row)

        flatpak_cmd_row = Adw.ActionRow()
        flatpak_cmd_row.set_title(_("Manual Terminal Commands"))
        flatpak_cmd_row.set_subtitle(
            "flatpak override --user --filesystem=xdg-data/themes:ro\n"
            "flatpak override --user --filesystem=xdg-data/icons:ro"
        )
        flatpak_cmd_row.set_subtitle_lines(3)
        flatpak_group.add(flatpak_cmd_row)

        flatpak_note_row = Adw.ActionRow()
        flatpak_note_row.set_title(_("Restart Applications"))
        flatpak_note_row.set_subtitle(
            _("Restart any open Flatpak application (e.g. Firefox, Spotify) to apply new themes.")
        )
        flatpak_note_row.set_subtitle_lines(2)
        flatpak_group.add(flatpak_note_row)

        content_box.append(flatpak_group)

        # 2. Snap Group
        snap_group = Adw.PreferencesGroup()
        snap_group.set_title(_("Snap Integration"))
        snap_group.set_description(
            _("Connect theme slots to confined Snap applications on Ubuntu.")
        )

        snap_sys_row = Adw.ActionRow()
        snap_sys_row.set_title(_("System Themes (gtk-common-themes)"))
        snap_sys_row.set_subtitle("sudo snap install gtk-common-themes")
        snap_group.add(snap_sys_row)

        snap_custom_row = Adw.ActionRow()
        snap_custom_row.set_title(_("Custom Themes (Content Snaps)"))
        snap_custom_row.set_subtitle(
            _("Click 'Build Snap' to compile and connect a dedicated local Content Snap.")
        )
        snap_group.add(snap_custom_row)

        snap_cmd_row = Adw.ActionRow()
        snap_cmd_row.set_title(_("Manual App Connection"))
        snap_cmd_row.set_subtitle(
            GLib.markup_escape_text(
                "sudo snap connect <app-name>:gtk-3-themes gtk-common-themes:gtk-3-themes\n"
                "sudo snap connect <app-name>:icon-themes gtk-common-themes:icon-themes"
            )
        )
        snap_cmd_row.set_subtitle_lines(3)
        snap_group.add(snap_cmd_row)

        content_box.append(snap_group)

        clamp.set_child(content_box)
        scrolled.set_child(clamp)
        toolbar_view.set_content(scrolled)
        win.set_content(toolbar_view)

        win.present()


    def _get_root_window(self) -> Gtk.Window | None:
        """Retrieve parent Gtk.Window."""
        root = self.widget.get_root()
        if isinstance(root, Gtk.Window):
            return root
        return None

    def _clear_toast(self) -> None:
        """Clear persistent feedback."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "clear_feedback"):
            root.clear_feedback()

    def _show_toast(self, message: str, timeout: int = 0) -> None:
        """Show persistent feedback notification."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "add_toast"):
            root.add_toast(message, timeout=timeout)
        else:
            logger.info("Feedback [SandboxPage]: %s", message)

