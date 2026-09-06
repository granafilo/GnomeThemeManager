# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for the Terminal Palette & Preferences Editor page (FASE 4 Task 4.4).

Provides interactive controls to view, derive, customize, export, and apply
the 16-color ANSI terminal palette, background transparency, cursor shape,
fonts, audible bell, and multi-profile management to GNOME Terminal.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gtk, Pango

from ...core.terminal_detector import KNOWN_TERMINALS, is_terminal_installed
from ...core.terminal_palette import (
    DEFAULT_ANSI_PALETTE,
    TerminalPalette,
    TerminalProfileSummary,
    export_palette_to_json,
)
from ..widgets.color_picker import ColorPickerButton
from ..widgets.font_utils import safe_set_font_desc

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.terminal")

UI_FILE = Path(__file__).parent.parent / "ui" / "terminal_page.ui"


class TerminalPage:
    """Controller for Terminal Editor page."""

    def __init__(self, manager: "ThemeManager") -> None:
        """Initialize TerminalPage.

        Args:
            manager: ThemeManager facade instance.
        """
        self.manager = manager
        self.page_id = "terminal"
        self.title = _("Terminal")
        self.on_notify_message: Callable[[str, bool], None] | None = None

        builder = Gtk.Builder()
        builder.set_translation_domain("gnomethememanager")
        builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = builder.get_object("page_root")
        self.ready_view: Adw.ToolbarView = builder.get_object("ready")

        self.terminal_preview_box: Gtk.Box = builder.get_object("terminal_preview_box")
        self.terminal_preview_label: Gtk.Label = builder.get_object("terminal_preview_label")

        # Profiles UI
        self.profile_combo_row: Adw.ComboRow = builder.get_object("profile_combo_row")
        self.set_default_button: Gtk.Button = builder.get_object("set_default_button")
        self.new_profile_button: Gtk.Button = builder.get_object("new_profile_button")
        self.delete_profile_button: Gtk.Button = builder.get_object("delete_profile_button")

        self.bg_picker_container: Gtk.Box = builder.get_object("bg_picker_container")
        self.fg_picker_container: Gtk.Box = builder.get_object("fg_picker_container")
        self.ansi_grid_container: Gtk.Box = builder.get_object("ansi_grid_container")

        self.transparency_switch_row: Adw.SwitchRow = builder.get_object("transparency_switch_row")
        self.transparency_percent_row: Adw.ActionRow = builder.get_object(
            "transparency_percent_row"
        )
        self.transparency_spin_button: Gtk.SpinButton = builder.get_object(
            "transparency_spin_button"
        )

        self.use_system_font_row: Adw.SwitchRow = builder.get_object("use_system_font_row")
        self.custom_font_row: Adw.ActionRow = builder.get_object("custom_font_row")
        self.terminal_font_button: Gtk.FontDialogButton = builder.get_object("terminal_font_button")

        self.cursor_shape_row: Adw.ComboRow = builder.get_object("cursor_shape_row")
        self.cursor_blink_row: Adw.ComboRow = builder.get_object("cursor_blink_row")
        self.audible_bell_row: Adw.SwitchRow = builder.get_object("audible_bell_row")

        self.derive_button: Gtk.Button = builder.get_object("derive_button")
        self.export_button: Gtk.Button = builder.get_object("export_button")
        self.apply_button: Gtk.Button = builder.get_object("apply_button")

        # Color pickers
        self.bg_picker = ColorPickerButton(title=_("Background"), default_hex="#241f31")
        self.fg_picker = ColorPickerButton(title=_("Text Color"), default_hex="#d0d0d0")
        if self.bg_picker_container:
            self.bg_picker_container.append(self.bg_picker)
        if self.fg_picker_container:
            self.fg_picker_container.append(self.fg_picker)

        self.bg_picker.connect("color-changed", self._on_color_changed)
        self.fg_picker.connect("color-changed", self._on_color_changed)

        if self.terminal_preview_box:
            self.terminal_preview_box.add_css_class("terminal-preview-box")
        self._preview_css_provider = Gtk.CssProvider()

        # Terminal Environment UI (Prompt 2.1 Step 4)
        self.terminal_environment_group: Adw.PreferencesGroup = builder.get_object(
            "terminal_environment_group"
        )
        self.terminal_selector_row: Adw.ComboRow = builder.get_object("terminal_selector_row")
        self.terminal_icon_image: Gtk.Image = builder.get_object("terminal_icon_image")
        self.terminal_status_badge: Gtk.Label = builder.get_object("terminal_status_badge")
        self.terminal_command_row: Adw.ActionRow = builder.get_object("terminal_command_row")
        self.terminal_warning_row: Adw.ActionRow = builder.get_object("terminal_warning_row")
        self.profiles_group: Adw.PreferencesGroup = builder.get_object("profiles_group")

        self._supported_terminals: list[str] = [
            "ptyxis",
            "gnome-terminal",
            "kgx",
            "tilix",
            "terminator",
            "konsole",
            "xfce4-terminal",
            "mate-terminal",
            "alacritty",
            "kitty",
            "wezterm",
            "warp",
            "xterm",
            "urxvt",
        ]
        self._selected_terminal_id: str = "ptyxis"
        self._updating_terminal_selector: bool = False

        # Setup ComboRows models
        self._updating_terminal_selector = True
        try:
            self._setup_combo_models()
        finally:
            self._updating_terminal_selector = False

        if self.terminal_selector_row:
            self.terminal_selector_row.connect(
                "notify::selected", self._on_terminal_selection_changed
            )

        # Setup FontDialog
        if self.terminal_font_button:
            font_dialog = Gtk.FontDialog.new()
            font_dialog.set_title(_("Select Terminal Font"))
            self.terminal_font_button.set_dialog(font_dialog)
            self.terminal_font_button.connect("notify::font-desc", self._on_font_changed)

        # Setup switch handlers
        if self.transparency_switch_row:
            self.transparency_switch_row.connect("notify::active", self._on_transparency_toggled)
        if self.use_system_font_row:
            self.use_system_font_row.connect("notify::active", self._on_system_font_toggled)

        # ANSI 16 Color Buttons
        self._ansi_pickers: list[ColorPickerButton] = []
        self._build_ansi_grid()

        # Profiles event listeners
        self._profiles: list[TerminalProfileSummary] = []
        self._selected_profile_id: str | None = None
        self._updating_profiles_ui = False

        if self.profile_combo_row:
            self.profile_combo_row.connect("notify::selected", self._on_profile_dropdown_changed)
        if self.set_default_button:
            self.set_default_button.connect("clicked", self._on_set_default_profile_clicked)
        if self.new_profile_button:
            self.new_profile_button.connect("clicked", self._on_new_profile_clicked)
        if self.delete_profile_button:
            self.delete_profile_button.connect("clicked", self._on_delete_profile_clicked)

        if self.derive_button:
            self.derive_button.connect("clicked", self._on_derive_button_clicked)
        if self.export_button:
            self.export_button.connect("clicked", self._on_export_button_clicked)
        if self.apply_button:
            self.apply_button.connect("clicked", self.on_apply_button_clicked)

        self._current_palette: TerminalPalette = TerminalPalette()

    def get_widget(self) -> Gtk.Widget:
        """Return the top-level widget of this page."""
        return self.widget

    def refresh(self, sync: bool = False) -> None:
        """Load detected terminal, profile list, and currently selected profile."""
        try:
            self._init_terminal_detection()
            self._reload_profiles_list()
            self._load_selected_profile()
        except Exception as err:
            logger.warning("Failed to load terminal palette: %s", err)

    def _update_terminal_selector_model(self) -> None:
        """Populate the terminal selector dropdown with installation warning alerts."""
        if not self.terminal_selector_row:
            return
        names: list[str] = []
        for tid in self._supported_terminals:
            spec = KNOWN_TERMINALS.get(tid, {})
            tname = str(spec.get("terminal_name", tid))
            desktop_file = f"{spec.get('icon_name', tid)}.desktop"
            if not is_terminal_installed(tid, desktop_file):
                names.append(f"{tname}  ⚠️ ({_('Not Installed')})")
            else:
                names.append(tname)
        self.terminal_selector_row.set_model(Gtk.StringList.new(names))

    def _init_terminal_detection(self) -> None:
        """Detect system terminal and initialize terminal selector dropdown."""
        self._updating_terminal_selector = True
        try:
            self._update_terminal_selector_model()

            detected = self.manager.detect_terminal()
            tid = getattr(detected, "terminal_id", "ptyxis")
            if tid in self._supported_terminals:
                self._selected_terminal_id = tid
            elif self._supported_terminals:
                self._selected_terminal_id = self._supported_terminals[0]

            if self.terminal_selector_row:
                idx = (
                    self._supported_terminals.index(self._selected_terminal_id)
                    if self._selected_terminal_id in self._supported_terminals
                    else 0
                )
                self.terminal_selector_row.set_selected(idx)
        finally:
            self._updating_terminal_selector = False

        self._update_terminal_ui()

    def _on_terminal_selection_changed(self, _combo: Adw.ComboRow, _param: Any) -> None:
        """Handle user manual selection override in terminal selector dropdown."""
        if self._updating_terminal_selector or not self.terminal_selector_row:
            return
        idx = self.terminal_selector_row.get_selected()
        if 0 <= idx < len(self._supported_terminals):
            self._selected_terminal_id = self._supported_terminals[idx]
            self._update_terminal_ui()

            # Immediate alert notification if the selected terminal is not installed
            profile = self.manager.get_terminal_profile(self._selected_terminal_id)
            if not isinstance(getattr(profile, "terminal_name", None), str):
                from ...core.terminal_profile import get_terminal_profile

                profile = get_terminal_profile(self._selected_terminal_id)
            installed = is_terminal_installed(
                profile.terminal_id, f"{profile.icon_name}.desktop"
            )
            if not installed:
                self._notify(
                    _(
                        "The terminal '{name}' is not installed. Install with: {cmd}"
                    ).format(name=profile.terminal_name, cmd=profile.install_command),
                    is_error=True,
                )

    def _update_terminal_ui(self) -> None:
        """Update UI elements based on the currently selected terminal profile."""
        profile = self.manager.get_terminal_profile(self._selected_terminal_id)
        if not isinstance(getattr(profile, "terminal_name", None), str):
            from ...core.terminal_profile import get_terminal_profile

            profile = get_terminal_profile(self._selected_terminal_id)

        detected = self.manager.detect_terminal()
        default_term = self.manager.detect_default_terminal()

        is_detected_active = (
            getattr(detected, "terminal_id", "") == self._selected_terminal_id
        )
        is_default = (
            getattr(default_term, "terminal_id", "") == self._selected_terminal_id
        )
        installed = is_terminal_installed(
            profile.terminal_id, f"{profile.icon_name}.desktop"
        )

        # 1. Update Subtitle
        if self.terminal_selector_row:
            if not installed:
                self.terminal_selector_row.set_subtitle(
                    f"⚠️ {_('Not Installed')} — {_('Manual override: {name}')}".format(
                        name=profile.terminal_name
                    )
                )
            elif is_detected_active:
                self.terminal_selector_row.set_subtitle(
                    _("Active terminal: {name}").format(name=profile.terminal_name)
                )
            elif is_default:
                self.terminal_selector_row.set_subtitle(
                    _("Default terminal: {name}").format(name=profile.terminal_name)
                )
            else:
                self.terminal_selector_row.set_subtitle(
                    _("Manual override: {name}").format(name=profile.terminal_name)
                )

        # 2. Update Badge & Row Styling
        if self.terminal_status_badge:
            self.terminal_status_badge.remove_css_class("accent")
            self.terminal_status_badge.remove_css_class("success")
            self.terminal_status_badge.remove_css_class("warning")
            if not installed:
                self.terminal_status_badge.set_label(f"⚠️ {_('Not Installed')}")
                self.terminal_status_badge.add_css_class("warning")
            elif is_default:
                self.terminal_status_badge.set_label(_("Default"))
                self.terminal_status_badge.add_css_class("accent")
            else:
                self.terminal_status_badge.set_label(_("Installed"))
                self.terminal_status_badge.add_css_class("success")

        if self.terminal_selector_row:
            if not installed:
                self.terminal_selector_row.add_css_class("warning")
            else:
                self.terminal_selector_row.remove_css_class("warning")

        # 3. Update Icon
        if self.terminal_icon_image:
            icon_str = getattr(profile, "icon_name", "utilities-terminal-symbolic")
            if not isinstance(icon_str, str) or icon_str.startswith("<MagicMock"):
                icon_str = "utilities-terminal-symbolic"
            self.terminal_icon_image.set_from_icon_name(icon_str)

        # 4. Update Command row
        if self.terminal_command_row:
            self.terminal_command_row.set_subtitle(profile.launch_command)

        # 5. Update Warning row
        if self.terminal_warning_row:
            installed = is_terminal_installed(
                profile.terminal_id, f"{profile.icon_name}.desktop"
            )
            if not installed:
                self.terminal_warning_row.set_visible(True)
                self.terminal_warning_row.set_title(_("Terminal Not Installed"))
                self.terminal_warning_row.set_subtitle(
                    _("The terminal '{name}' is not installed. Install with: {cmd}").format(
                        name=profile.terminal_name, cmd=profile.install_command
                    )
                )
            elif not profile.supports_profiles:
                self.terminal_warning_row.set_visible(True)
                self.terminal_warning_row.set_title(_("Configuration Notice"))
                self.terminal_warning_row.set_subtitle(
                    _("{name} uses file configuration instead of GSettings. Config path: {path}").format(
                        name=profile.terminal_name, path=profile.config_file_path
                    )
                )
            else:
                self.terminal_warning_row.set_visible(False)

        # 6. Adapt profiles management group
        if self.profiles_group:
            self.profiles_group.set_visible(profile.supports_profiles)

        # 7. Update preview label
        if self.terminal_preview_label:
            markup = (
                f"<tt><b>user@gnome</b>:<b>~</b>$ uname -a\n"
                f"Linux 6.8.0-generic x86_64 GNU/Linux\n"
                f"<b>user@gnome</b>:<b>~</b>$ echo \"{profile.terminal_name} Palette Theme\"\n"
                f'<span foreground="#3584e4">■</span> <span foreground="#26a269">■</span> '
                f'<span foreground="#c01c28">■</span> <span foreground="#a347ba">■</span> '
                f'<span foreground="#e9ad0c">■</span> <span foreground="#2aa1b3">■</span></tt>'
            )
            self.terminal_preview_label.set_label(markup)

    def _show_error_dialog(self, heading: str, body: str) -> None:
        """Present an informational error dialogue to the user (Fix 4)."""
        win = self.widget.get_root()
        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading=heading, body=body)
            dialog.add_response("ok", _("OK"))
            dialog.set_default_response("ok")
            dialog.set_close_response("ok")
            dialog.present(win if isinstance(win, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                heading,
                body,
            )
            dialog.add_response("ok", _("OK"))
            dialog.set_default_response("ok")
            dialog.set_close_response("ok")
            dialog.present()
        else:
            self._notify(f"{heading}: {body}", is_error=True)

    def on_apply_button_clicked(self, _btn: Gtk.Button) -> None:
        """Apply current terminal palette and preferences with comprehensive validation."""
        profile = self.manager.get_terminal_profile(self._selected_terminal_id)
        if not isinstance(getattr(profile, "terminal_name", None), str):
            from ...core.terminal_profile import get_terminal_profile

            profile = get_terminal_profile(self._selected_terminal_id)

        installed = is_terminal_installed(
            profile.terminal_id, f"{profile.icon_name}.desktop"
        )

        # Scenario A - Target terminal not installed
        if not installed:
            msg = _("The target terminal '{name}' is not installed. Install with: {cmd}").format(
                name=profile.terminal_name, cmd=profile.install_command
            )
            self._show_error_dialog(_("Terminal not installed"), msg)
            self._notify(msg, is_error=True)
            return

        # Scenario C - Terminal does not use GSettings
        if not profile.supports_profiles and profile.terminal_id not in ("kgx", "ptyxis"):
            msg = _("{terminal} does not use GSettings profiles. Config path: {path}").format(
                terminal=profile.terminal_name, path=profile.config_file_path
            )
            self._show_error_dialog(_("GSettings not supported"), msg)
            self._notify(msg, is_error=True)
            return

        # Scenario B - Schema accessibility check for GSettings
        term_info = self.manager.detect_terminal()
        schema_acc = getattr(term_info, "schema_accessible", True)
        if (
            isinstance(schema_acc, bool)
            and not schema_acc
            and getattr(term_info, "terminal_id", "") == self._selected_terminal_id
        ):
            self._show_error_dialog(
                _("GSettings schema unavailable"),
                _(
                    "The terminal GSettings schema is not accessible. Check application permissions."
                ),
            )
            self._notify(
                _(
                    "The terminal GSettings schema is not accessible. Check application permissions."
                ),
                is_error=True,
            )
            return

        palette = self._build_current_palette()
        target_pid = self._selected_profile_id
        try:
            success = self.manager.apply_terminal_palette(palette, profile_id=target_pid)
            if success:
                self._notify(
                    _("Terminal preferences applied successfully."),
                    is_error=False,
                )
            else:
                # Scenario D - Generic application error
                fail_msg = _("Could not apply preferences to {terminal}.").format(
                    terminal=profile.terminal_name
                )
                self._show_error_dialog(_("Error applying theme"), fail_msg)
                self._notify(fail_msg, is_error=True)
        except Exception as err:
            # Scenario D - Detailed exception error
            err_msg = _("Failed to apply terminal theme: {error}").format(error=str(err))
            self._show_error_dialog(_("Error applying theme"), err_msg)
            self._notify(err_msg, is_error=True)

    # ------------------------------------------------------------------
    # Profiles Management
    # ------------------------------------------------------------------

    def _reload_profiles_list(self) -> None:
        """Fetch profiles and update ComboRow items."""
        if not self.profile_combo_row:
            return

        self._updating_profiles_ui = True
        try:
            self._profiles = self.manager.list_terminal_profiles()
            if not self._profiles:
                # Fallback: single mock item
                self._profiles = [
                    TerminalProfileSummary(id="default", name=_("Default"), is_default=True)
                ]

            names = [
                f"{p.name} ({_('Default')})" if p.is_default else p.name for p in self._profiles
            ]
            str_list = Gtk.StringList.new(names)
            self.profile_combo_row.set_model(str_list)

            # Determine initial selection
            target_idx = 0
            if self._selected_profile_id:
                for idx, p in enumerate(self._profiles):
                    if p.id == self._selected_profile_id:
                        target_idx = idx
                        break
            else:
                for idx, p in enumerate(self._profiles):
                    if p.is_default:
                        target_idx = idx
                        break

            self.profile_combo_row.set_selected(target_idx)
            self._selected_profile_id = self._profiles[target_idx].id
            self._update_profile_action_buttons()
        finally:
            self._updating_profiles_ui = False

    def _update_profile_action_buttons(self) -> None:
        """Update sensitivity of 'Set Default' and 'Delete' buttons."""
        curr_prof = self._get_current_profile_summary()
        if curr_prof:
            # Can set default only if it is not already default
            if self.set_default_button:
                self.set_default_button.set_sensitive(not curr_prof.is_default)
            # Can delete only if it is NOT the default/active profile
            if self.delete_profile_button:
                self.delete_profile_button.set_sensitive(not curr_prof.is_default)

    def _get_current_profile_summary(self) -> TerminalProfileSummary | None:
        """Return summary of selected profile."""
        if not self.profile_combo_row or not self._profiles:
            return None
        idx = self.profile_combo_row.get_selected()
        if 0 <= idx < len(self._profiles):
            return self._profiles[idx]
        return None

    def _on_profile_dropdown_changed(self, _combo: Adw.ComboRow, _param: Any) -> None:
        """Handle selection change in profiles ComboRow."""
        if self._updating_profiles_ui:
            return
        curr = self._get_current_profile_summary()
        if curr:
            self._selected_profile_id = curr.id
            self._update_profile_action_buttons()
            self._load_selected_profile()

    def _load_selected_profile(self) -> None:
        """Load settings for the currently selected profile."""
        curr_id = self._selected_profile_id
        profile_data = self.manager.get_current_terminal_palette(profile_id=curr_id)
        if profile_data is not None:
            self._load_palette(profile_data)
        else:
            derived = self.manager.get_derived_terminal_palette()
            self._load_palette(derived)

    def _on_set_default_profile_clicked(self, _btn: Gtk.Button) -> None:
        """Set the selected profile as default."""
        curr = self._get_current_profile_summary()
        if not curr:
            return
        if self.manager.set_default_terminal_profile(curr.id):
            self._notify(_("Profile set as default: {}").format(curr.name), is_error=False)
            self._reload_profiles_list()
        else:
            self._notify(_("Failed to set default profile."), is_error=True)

    def _on_new_profile_clicked(self, _btn: Gtk.Button) -> None:
        """Prompt to create a new profile with current palette."""

        def on_confirm(name: str) -> None:
            if not name.strip():
                return
            palette = self._build_current_palette()
            new_id = self.manager.create_terminal_profile(name.strip(), palette=palette)
            if new_id:
                self._selected_profile_id = new_id
                self._reload_profiles_list()
                self._notify(_("Created profile: {}").format(name.strip()), is_error=False)
            else:
                self._notify(_("Failed to create profile."), is_error=True)

        self._show_text_input_dialog(
            title=_("New Terminal Profile"),
            heading=_("Enter a name for the new profile:"),
            default_text=_("Custom Profile"),
            on_submit=on_confirm,
        )

    def _on_delete_profile_clicked(self, _btn: Gtk.Button) -> None:
        """Delete current non-default profile after confirmation."""
        curr = self._get_current_profile_summary()
        if not curr or curr.is_default:
            return

        def on_confirm() -> None:
            if self.manager.delete_terminal_profile(curr.id):
                self._selected_profile_id = None
                self._reload_profiles_list()
                self._load_selected_profile()
                self._notify(_("Profile deleted: {}").format(curr.name), is_error=False)
            else:
                self._notify(_("Failed to delete profile."), is_error=True)

        self._show_confirm_dialog(
            title=_("Delete Profile"),
            body=_("Are you sure you want to delete profile '{}'?").format(curr.name),
            on_confirm=on_confirm,
        )

    def _show_text_input_dialog(
        self,
        title: str,
        heading: str,
        default_text: str,
        on_submit: Callable[[str], None],
    ) -> None:
        """Show a modern Libadwaita text input dialog."""
        root = self.widget.get_root()
        parent_win = root if isinstance(root, Gtk.Window) else None
        dialog = Adw.MessageDialog.new(parent_win, title, heading)
        entry = Gtk.Entry()
        entry.set_text(default_text)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")

        def _on_response(_dlg: Adw.MessageDialog, response: str) -> None:
            if response == "create":
                on_submit(entry.get_text())

        dialog.connect("response", _on_response)
        dialog.present()

    def _show_confirm_dialog(
        self,
        title: str,
        body: str,
        on_confirm: Callable[[], None],
    ) -> None:
        """Show a confirmation dialog."""
        root = self.widget.get_root()
        parent_win = root if isinstance(root, Gtk.Window) else None
        dialog = Adw.MessageDialog.new(parent_win, title, body)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def _on_response(_dlg: Adw.MessageDialog, response: str) -> None:
            if response == "delete":
                on_confirm()

        dialog.connect("response", _on_response)
        dialog.present()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_combo_models(self) -> None:
        """Configure models for terminal selector, cursor shape, and blinking ComboRows."""
        self._update_terminal_selector_model()

        if self.cursor_shape_row:
            shapes = Gtk.StringList.new([_("Block"), _("I-Beam"), _("Underline")])
            self.cursor_shape_row.set_model(shapes)

        if self.cursor_blink_row:
            blinks = Gtk.StringList.new([_("System Default"), _("Enabled"), _("Disabled")])
            self.cursor_blink_row.set_model(blinks)

    def _build_ansi_grid(self) -> None:
        """Build 2 rows of 8 labeled color swatches with descriptive captions."""
        if not self.ansi_grid_container:
            return

        short_names = [
            _("Black"),
            _("Red"),
            _("Green"),
            _("Yellow"),
            _("Blue"),
            _("Magenta"),
            _("Cyan"),
            _("White"),
        ]

        # Container for Normal ANSI 0-7
        normal_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        normal_header = Gtk.Label(label=_("Standard Colors (0-7)"))
        normal_header.set_xalign(0)
        normal_header.add_css_class("caption")
        normal_header.add_css_class("dim-label")
        normal_group.append(normal_header)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row1.set_halign(Gtk.Align.CENTER)
        normal_group.append(row1)

        # Container for Bright ANSI 8-15
        bright_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bright_header = Gtk.Label(label=_("Bright Colors (8-15)"))
        bright_header.set_xalign(0)
        bright_header.add_css_class("caption")
        bright_header.add_css_class("dim-label")
        bright_group.append(bright_header)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row2.set_halign(Gtk.Align.CENTER)
        bright_group.append(row2)

        for i in range(16):
            default_color = DEFAULT_ANSI_PALETTE[i] if i < len(DEFAULT_ANSI_PALETTE) else "#ffffff"
            col_name = short_names[i % 8]
            is_bright = i >= 8
            full_title = f"{'Bright ' if is_bright else ''}{col_name} (ANSI {i})"

            # Column item container
            col_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col_box.set_halign(Gtk.Align.CENTER)

            picker = ColorPickerButton(title=full_title, default_hex=default_color, compact=True)
            picker.connect("color-changed", self._on_color_changed)
            self._ansi_pickers.append(picker)
            col_box.append(picker)

            lbl = Gtk.Label(label=col_name)
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            lbl.set_tooltip_text(full_title)
            col_box.append(lbl)

            if i < 8:
                row1.append(col_box)
            else:
                row2.append(col_box)

        self.ansi_grid_container.append(normal_group)
        self.ansi_grid_container.append(bright_group)

    def _load_palette(self, palette: TerminalPalette) -> None:
        """Update form controls and live preview with palette values."""
        self._current_palette = palette
        self.bg_picker.set_color_hex(palette.background_color)
        self.fg_picker.set_color_hex(palette.foreground_color)

        for i, picker in enumerate(self._ansi_pickers):
            if i < len(palette.palette):
                picker.set_color_hex(palette.palette[i])

        if self.transparency_switch_row:
            self.transparency_switch_row.set_active(palette.use_transparent_background)
        if self.transparency_percent_row:
            self.transparency_percent_row.set_sensitive(palette.use_transparent_background)
        if self.transparency_spin_button:
            self.transparency_spin_button.set_value(palette.background_transparency_percent)

        if self.use_system_font_row:
            self.use_system_font_row.set_active(palette.use_system_font)
        if self.custom_font_row:
            self.custom_font_row.set_sensitive(not palette.use_system_font)

        if self.terminal_font_button and palette.font:
            try:
                desc = Pango.FontDescription.from_string(palette.font)
                safe_set_font_desc(self.terminal_font_button, desc)
            except Exception as err:
                logger.debug("Failed to set font desc: %s", err)

        shape_map = {"block": 0, "ibeam": 1, "underline": 2}
        if self.cursor_shape_row:
            self.cursor_shape_row.set_selected(shape_map.get(palette.cursor_shape, 0))

        blink_map = {"system": 0, "on": 1, "off": 2}
        if self.cursor_blink_row:
            self.cursor_blink_row.set_selected(blink_map.get(palette.cursor_blink_mode, 0))

        if self.audible_bell_row:
            self.audible_bell_row.set_active(palette.audible_bell)

        self._update_preview()

    def _build_current_palette(self) -> TerminalPalette:
        """Construct TerminalPalette from current widget picker values."""
        palette_list = [p.get_color_hex() for p in self._ansi_pickers]

        shape_keys = ["block", "ibeam", "underline"]
        shape_idx = self.cursor_shape_row.get_selected() if self.cursor_shape_row else 0
        c_shape = shape_keys[shape_idx] if shape_idx < len(shape_keys) else "block"

        blink_keys = ["system", "on", "off"]
        blink_idx = self.cursor_blink_row.get_selected() if self.cursor_blink_row else 0
        c_blink = blink_keys[blink_idx] if blink_idx < len(blink_keys) else "system"

        font_name = "Monospace 11"
        if self.terminal_font_button:
            fdesc = self.terminal_font_button.get_font_desc()
            if fdesc is not None:
                font_name = fdesc.to_string()

        use_sys_font = self.use_system_font_row.get_active() if self.use_system_font_row else True
        use_trans = (
            self.transparency_switch_row.get_active() if self.transparency_switch_row else False
        )
        trans_pct = (
            int(self.transparency_spin_button.get_value()) if self.transparency_spin_button else 0
        )
        aud_bell = self.audible_bell_row.get_active() if self.audible_bell_row else False

        return TerminalPalette(
            name="Custom Terminal Theme",
            foreground_color=self.fg_picker.get_color_hex(),
            background_color=self.bg_picker.get_color_hex(),
            palette=palette_list,
            use_system_font=use_sys_font,
            font=font_name,
            cursor_shape=c_shape,
            cursor_blink_mode=c_blink,
            audible_bell=aud_bell,
            use_transparent_background=use_trans,
            background_transparency_percent=trans_pct,
        )

    def _on_color_changed(self, _picker: Any, _color: str) -> None:
        """Callback on any color change to update terminal preview box."""
        self._update_preview()

    def _on_font_changed(self, _btn: Any, _param: Any) -> None:
        """Callback on font selection change."""
        self._update_preview()

    def _on_transparency_toggled(self, _row: Any, _param: Any) -> None:
        """Handle transparent background switch toggle."""
        if self.transparency_switch_row and self.transparency_percent_row:
            active = self.transparency_switch_row.get_active()
            self.transparency_percent_row.set_sensitive(active)

    def _on_system_font_toggled(self, _row: Any, _param: Any) -> None:
        """Handle system monospace font switch toggle."""
        if self.use_system_font_row and self.custom_font_row:
            use_sys = self.use_system_font_row.get_active()
            self.custom_font_row.set_sensitive(not use_sys)

    def _update_preview(self) -> None:
        """Update CSS and markup of the live terminal preview box."""
        if not self.terminal_preview_box:
            return

        bg = self.bg_picker.get_color_hex()
        fg = self.fg_picker.get_color_hex()

        c_blue = self._ansi_pickers[4].get_color_hex() if len(self._ansi_pickers) > 4 else "#3584e4"
        c_green = (
            self._ansi_pickers[2].get_color_hex() if len(self._ansi_pickers) > 2 else "#26a269"
        )
        c_red = self._ansi_pickers[1].get_color_hex() if len(self._ansi_pickers) > 1 else "#c01c28"
        c_mag = self._ansi_pickers[5].get_color_hex() if len(self._ansi_pickers) > 5 else "#a347ba"
        c_yel = self._ansi_pickers[3].get_color_hex() if len(self._ansi_pickers) > 3 else "#e9ad0c"
        c_cya = self._ansi_pickers[6].get_color_hex() if len(self._ansi_pickers) > 6 else "#2aa1b3"

        # Apply background color directly to preview box widget using CSS provider (clean CSS without !important)
        css_data = f".terminal-preview-box {{ background-color: {bg}; border-radius: 8px; }}"
        try:
            if hasattr(self._preview_css_provider, "load_from_string"):
                self._preview_css_provider.load_from_string(css_data)
            else:
                self._preview_css_provider.load_from_data(css_data.encode("utf-8"))
            from gi.repository import Gdk

            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, self._preview_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
        except Exception as err:
            logger.debug("Failed to apply preview background CSS: %s", err)

        markup = (
            f"<tt><span foreground='{c_green}'><b>user@gnome</b></span>:"
            f"<span foreground='{c_blue}'><b>~</b></span>$ uname -a\n"
            f"<span foreground='{fg}'>Linux 6.8.0-generic x86_64 GNU/Linux</span>\n"
            f"<span foreground='{c_green}'><b>user@gnome</b></span>:"
            f"<span foreground='{c_blue}'><b>~</b></span>$ echo \"GNOME Terminal Palette Theme\"\n"
            f"<span foreground='{c_blue}'>■</span> <span foreground='{c_green}'>■</span> "
            f"<span foreground='{c_red}'>■</span> <span foreground='{c_mag}'>■</span> "
            f"<span foreground='{c_yel}'>■</span> <span foreground='{c_cya}'>■</span></tt>"
        )
        if self.terminal_preview_label:
            self.terminal_preview_label.set_markup(markup)

    def _on_derive_button_clicked(self, _btn: Gtk.Button) -> None:
        """Derive fresh palette from the active GTK theme."""
        try:
            palette = self.manager.get_derived_terminal_palette()
            self._load_palette(palette)
            self._notify(_("Derived terminal palette from active theme."), is_error=False)
        except Exception as err:
            logger.warning("Failed to derive palette: %s", err)

    def _on_export_button_clicked(self, _btn: Gtk.Button) -> None:
        """Export current palette to JSON file."""
        palette = self._build_current_palette()
        dest = Path.home() / ".local" / "state" / "gnome-theme-manager" / "terminal_palette.json"
        try:
            export_palette_to_json(palette, dest)
            self._notify(_("Exported palette to {}").format(dest), is_error=False)
        except Exception as err:
            logger.warning("Failed to export palette: %s", err)
            self._notify(_("Failed to export palette."), is_error=True)

    def _notify(self, message: str, is_error: bool) -> None:
        """Forward user-facing message to the toast overlay."""
        if self.on_notify_message is not None:
            self.on_notify_message(message, is_error)
