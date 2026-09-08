# SPDX-License-Identifier: GPL-3.0-or-later

"""Step-by-step guided installation wizard for Flatpak and GNOME dependencies."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ...core.models import WizardStepInfo

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")


class FlatpakWizardDialog:
    """Step-by-step wizard to install Flatpak, Flathub, Extension Manager, and User Themes."""

    def __init__(
        self,
        manager: "ThemeManager | None",
        parent_window: Gtk.Window | None = None,
        on_completed: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the wizard dialog."""
        self.manager = manager
        self.parent_window = parent_window
        self.on_completed = on_completed

        self.user_mode: bool = True
        self.steps: list[WizardStepInfo] = []
        self.selected_step_ids: set[str] = set()
        self.current_step_index: int = 0
        self.step_results: dict[str, str] = {}  # step_id -> "installed" | "skipped" | "already_satisfied" | "failed"

        self.window = Adw.Window(
            modal=True,
            transient_for=parent_window,
            title=_("Dependency Setup Wizard"),
            default_width=580,
            default_height=520,
        )
        self.window.set_size_request(540, 480)
        self.window.add_css_class("flatpak-wizard-dialog")

        toolbar_view = Adw.ToolbarView()
        self.header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(self.header_bar)

        # Back button in header bar
        self.back_button = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.back_button.set_tooltip_text(_("Back"))
        self.back_button.set_visible(False)
        self.back_button.connect("clicked", self._on_back_clicked)
        self.header_bar.pack_start(self.back_button)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self._load_steps()
        self._init_overview_page()
        self._init_summary_page()

        toolbar_view.set_content(self.stack)
        self.window.set_content(toolbar_view)

    def present(self) -> None:
        """Present the wizard window to the user."""
        self.stack.set_visible_child_name("overview")
        self.back_button.set_visible(False)
        self.window.present()

    def _load_steps(self) -> None:
        """Fetch wizard step definitions and statuses from core."""
        if self.manager is not None:
            self.steps = self.manager.get_flatpak_wizard_steps(user_mode=self.user_mode)
        else:
            from ...core.sandbox_bridge import get_flatpak_wizard_steps

            self.steps = get_flatpak_wizard_steps(user_mode=self.user_mode)

        # By default, select steps that are NOT already satisfied
        self.selected_step_ids = {s.step_id for s in self.steps if not s.is_satisfied}
        for s in self.steps:
            if s.is_satisfied:
                self.step_results[s.step_id] = "already_satisfied"

    def _init_overview_page(self) -> None:
        """Build the overview checklist page."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(maximum_size=520, margin_top=20, margin_bottom=24, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)

        # Icon and header title
        icon = Gtk.Image.new_from_icon_name("system-software-install-symbolic")
        icon.set_pixel_size(48)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        title_lbl = Gtk.Label(
            label=_("Guided Component Setup"),
            css_classes=["title-2"],
            halign=Gtk.Align.CENTER,
        )
        box.append(title_lbl)

        desc_lbl = Gtk.Label(
            label=_(
                "Select the components and dependencies you want to configure. "
                "The wizard will guide you through each step with the exact commands."
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
            css_classes=["dim-label"],
            halign=Gtk.Align.CENTER,
        )
        box.append(desc_lbl)

        # Scope selector: User vs System
        scope_group = Adw.PreferencesGroup(
            title=_("Installation Scope"),
            description=_("Choose whether to install Flatpak remotes and apps for the current user or system-wide."),
        )
        self.scope_row = Adw.ActionRow(
            title=_("User Scope (--user)"),
            subtitle=_("Installs components without root privileges whenever possible."),
        )
        self.scope_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.user_mode)
        self.scope_switch.connect("notify::active", self._on_scope_toggled)
        self.scope_row.add_suffix(self.scope_switch)
        scope_group.add(self.scope_row)
        box.append(scope_group)

        # Steps checklist group
        checklist_group = Adw.PreferencesGroup(
            title=_("Components to Configure"),
            description=_("Check the steps you wish to execute:"),
        )

        self.checkbox_map: dict[str, Gtk.CheckButton] = {}
        for step in self.steps:
            row = Adw.ActionRow(title=step.title, subtitle=step.description)
            row.set_subtitle_lines(2)

            check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            check.set_active(step.step_id in self.selected_step_ids)
            check.connect("toggled", self._on_step_check_toggled, step.step_id)
            self.checkbox_map[step.step_id] = check
            row.add_prefix(check)
            row.set_activatable_widget(check)

            if step.is_satisfied:
                badge = Gtk.Label(label=_("Already satisfied"), css_classes=["badge", "accent"])
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)

            checklist_group.add(row)

        box.append(checklist_group)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END, margin_top=8)

        cancel_btn = Gtk.Button(label=_("Cancel"))
        cancel_btn.connect("clicked", lambda _b: self.window.close())
        btn_box.append(cancel_btn)

        self.start_btn = Gtk.Button(label=_("Start Setup"), css_classes=["suggested-action", "pill"])
        self.start_btn.connect("clicked", self._on_start_wizard_clicked)
        btn_box.append(self.start_btn)

        box.append(btn_box)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        self.stack.add_named(scrolled, "overview")

    def _on_scope_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        """Handle toggle of user vs system scope."""
        self.user_mode = switch.get_active()
        if self.user_mode:
            self.scope_row.set_title(_("User Scope (--user)"))
            self.scope_row.set_subtitle(_("Installs components without root privileges whenever possible."))
        else:
            self.scope_row.set_title(_("System-Wide Scope"))
            self.scope_row.set_subtitle(_("Installs components system-wide using administrator privileges (pkexec)."))

        # Reload step commands and satisfaction for the new scope
        self._load_steps()
        self._rebuild_step_pages()

    def _on_step_check_toggled(self, check: Gtk.CheckButton, step_id: str) -> None:
        """Handle toggling of a step checkbox in the overview."""
        if check.get_active():
            self.selected_step_ids.add(step_id)
        else:
            self.selected_step_ids.discard(step_id)

    def _on_start_wizard_clicked(self, _button: Gtk.Button) -> None:
        """Transition from overview to the first active step."""
        active_steps = [s for s in self.steps if s.step_id in self.selected_step_ids]
        if not active_steps:
            # If nothing selected, go straight to summary
            self._show_summary_page()
            return

        self._rebuild_step_pages()
        self.current_step_index = 0
        self._show_step(0)

    def _rebuild_step_pages(self) -> None:
        """Create or recreate step pages in the stack."""
        # Remove existing step pages
        for step in self.steps:
            child = self.stack.get_child_by_name(f"step_{step.step_id}")
            if child is not None:
                self.stack.remove(child)

        active_steps = [s for s in self.steps if s.step_id in self.selected_step_ids]
        total_steps = len(active_steps)

        for idx, step in enumerate(active_steps):
            page = self._build_single_step_page(step, idx + 1, total_steps)
            self.stack.add_named(page, f"step_{step.step_id}")

    def _build_single_step_page(self, step: WizardStepInfo, step_num: int, total_steps: int) -> Gtk.Widget:
        """Construct the UI page for an individual wizard step."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(maximum_size=520, margin_top=20, margin_bottom=24, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Step header counter
        step_counter_lbl = Gtk.Label(
            label=_("Step {current} of {total}").format(current=step_num, total=total_steps),
            css_classes=["dim-label", "caption"],
            halign=Gtk.Align.CENTER,
        )
        box.append(step_counter_lbl)

        # Step Title
        title_lbl = Gtk.Label(
            label=step.title,
            css_classes=["title-2"],
            halign=Gtk.Align.CENTER,
        )
        box.append(title_lbl)

        # Description
        desc_lbl = Gtk.Label(
            label=step.description,
            wrap=True,
            justify=Gtk.Justification.CENTER,
            halign=Gtk.Align.CENTER,
        )
        box.append(desc_lbl)

        # Command to execute
        cmd_text = step.command_user if self.user_mode else step.command_system

        cmd_group = Adw.PreferencesGroup(title=_("Command to Execute"))
        cmd_row = Adw.ActionRow()
        cmd_row.set_subtitle(cmd_text)
        cmd_row.set_subtitle_lines(3)
        cmd_row.add_css_class("monospace")

        copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_btn.set_tooltip_text(_("Copy command to clipboard"))
        copy_btn.set_valign(Gtk.Align.CENTER)
        copy_btn.connect("clicked", lambda _b, c=cmd_text: self._copy_to_clipboard(c))
        cmd_row.add_suffix(copy_btn)

        cmd_group.add(cmd_row)
        box.append(cmd_group)

        # Root / Privileges notice if needed
        needs_root = (not self.user_mode and step.requires_root_system) or ("pkexec" in cmd_text)
        if needs_root:
            auth_banner = Adw.Banner(
                title=_("This command requires administrator privileges (authentication will be prompted)."),
                revealed=True,
            )
            box.append(auth_banner)

        # Inclusion Checkbox for this step
        step_check = Gtk.CheckButton(label=_("Include this step in the setup"))
        step_check.set_active(step.step_id in self.selected_step_ids)
        step_check.connect("toggled", self._on_step_check_toggled, step.step_id)
        box.append(step_check)

        # Action buttons: Skip / Install
        actions_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.END,
            margin_top=16,
        )

        skip_btn = Gtk.Button(label=_("Skip"))
        skip_btn.connect("clicked", lambda _b, s=step: self._on_step_skip(s))
        actions_box.append(skip_btn)

        install_btn = Gtk.Button(label=_("Install"), css_classes=["suggested-action", "pill"])
        install_btn.connect("clicked", lambda _b, s=step: self._on_step_install(s))
        actions_box.append(install_btn)

        box.append(actions_box)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy command string to clipboard."""
        display = Gdk.Display.get_default()
        if display:
            clipboard = display.get_clipboard()
            clipboard.set(text)

    def _show_step(self, index: int) -> None:
        """Display step at given index."""
        active_steps = [s for s in self.steps if s.step_id in self.selected_step_ids]
        if index < 0 or index >= len(active_steps):
            self._show_summary_page()
            return

        self.current_step_index = index
        current_step = active_steps[index]
        self.stack.set_visible_child_name(f"step_{current_step.step_id}")
        self.back_button.set_visible(True)

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        """Navigate back to previous step or overview."""
        if self.current_step_index > 0:
            self._show_step(self.current_step_index - 1)
        else:
            self.stack.set_visible_child_name("overview")
            self.back_button.set_visible(False)

    def _on_step_skip(self, step: WizardStepInfo) -> None:
        """Handle skipping the current step."""
        self.step_results[step.step_id] = "skipped"
        self._advance_next_step()

    def _on_step_install(self, step: WizardStepInfo) -> None:
        """Handle installing the current step."""
        # Note: Async execution with streaming log and pkexec will be handled in Step 4.
        # For Step 3, mark as executed and advance.
        self.step_results[step.step_id] = "installed"
        self._advance_next_step()

    def _advance_next_step(self) -> None:
        """Move to the next active step or summary page."""
        active_steps = [s for s in self.steps if s.step_id in self.selected_step_ids]
        next_index = self.current_step_index + 1
        if next_index < len(active_steps):
            self._show_step(next_index)
        else:
            self._show_summary_page()

    def _init_summary_page(self) -> None:
        """Build initial container for completion summary page."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.summary_clamp = Adw.Clamp(maximum_size=520, margin_top=20, margin_bottom=24, margin_start=16, margin_end=16)
        scrolled.set_child(self.summary_clamp)
        self.stack.add_named(scrolled, "summary")

    def _show_summary_page(self) -> None:
        """Populate and display final summary page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)

        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_pixel_size(48)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        title_lbl = Gtk.Label(
            label=_("Setup Completed"),
            css_classes=["title-2"],
            halign=Gtk.Align.CENTER,
        )
        box.append(title_lbl)

        summary_group = Adw.PreferencesGroup(title=_("Summary of Actions"))

        for step in self.steps:
            row = Adw.ActionRow(title=step.title)
            status = self.step_results.get(step.step_id, "skipped")

            if status == "installed":
                badge = Gtk.Label(label=_("Configured"), css_classes=["badge", "accent"])
            elif status == "already_satisfied":
                badge = Gtk.Label(label=_("Already satisfied"), css_classes=["badge"])
            else:
                badge = Gtk.Label(label=_("Skipped"), css_classes=["badge", "dim-label"])

            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)
            summary_group.add(row)

        box.append(summary_group)

        close_btn = Gtk.Button(label=_("Close"), css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER)
        close_btn.connect("clicked", self._on_finish_clicked)
        box.append(close_btn)

        self.summary_clamp.set_child(box)
        self.back_button.set_visible(False)
        self.stack.set_visible_child_name("summary")

    def _on_finish_clicked(self, _button: Gtk.Button) -> None:
        """Close dialog and trigger completion callback."""
        self.window.close()
        if self.on_completed:
            try:
                self.on_completed()
            except Exception as e:
                logger.warning("Error in on_completed callback: %s", e)
