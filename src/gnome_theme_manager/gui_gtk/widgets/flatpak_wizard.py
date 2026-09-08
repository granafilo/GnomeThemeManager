# SPDX-License-Identifier: GPL-3.0-or-later

"""Step-by-step guided installation wizard for Flatpak and GNOME dependencies."""

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from ...core.models import WizardStepInfo, WizardStepResult

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
        self._is_executing: bool = False

        self.step_sub_stacks: dict[str, Gtk.Stack] = {}
        self.step_install_btns: dict[str, Gtk.Button] = {}
        self.step_skip_btns: dict[str, Gtk.Button] = {}
        self.step_cancel_all_btns: dict[str, Gtk.Button] = {}
        self.step_skip_err_btns: dict[str, Gtk.Button] = {}
        self.step_retry_btns: dict[str, Gtk.Button] = {}

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

        self.window.connect("close-request", self._on_close_request)

    def present(self) -> None:
        """Present the wizard window to the user."""
        self.stack.set_visible_child_name("overview")
        self.back_button.set_visible(False)
        self.window.present()

    def _on_close_request(self, _window: Adw.Window) -> bool:
        """Prevent closing dialog while command execution is in progress."""
        if self._is_executing:
            logger.warning("Attempted to close Flatpak wizard during command execution.")
            return True  # Block closing
        return False

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
        """Construct the UI page for an individual wizard step with interactive states."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(maximum_size=520, margin_top=20, margin_bottom=24, margin_start=16, margin_end=16)
        
        # Sub-stack to manage step states: prompt -> running -> success / error
        step_sub_stack = Gtk.Stack()
        step_sub_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # -------------------------------------------------------------
        # STATE 1: PROMPT
        # -------------------------------------------------------------
        prompt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        step_counter_lbl = Gtk.Label(
            label=_("Step {current} of {total}").format(current=step_num, total=total_steps),
            css_classes=["dim-label", "caption"],
            halign=Gtk.Align.CENTER,
        )
        prompt_box.append(step_counter_lbl)

        title_lbl = Gtk.Label(label=step.title, css_classes=["title-2"], halign=Gtk.Align.CENTER)
        prompt_box.append(title_lbl)

        desc_lbl = Gtk.Label(label=step.description, wrap=True, justify=Gtk.Justification.CENTER, halign=Gtk.Align.CENTER)
        prompt_box.append(desc_lbl)

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
        prompt_box.append(cmd_group)

        needs_root = (not self.user_mode and step.requires_root_system) or ("pkexec" in cmd_text)
        if needs_root:
            auth_banner = Adw.Banner(
                title=_("This command requires administrator privileges (authentication will be prompted)."),
                revealed=True,
            )
            prompt_box.append(auth_banner)

        if step.is_satisfied:
            satisfied_banner = Adw.Banner(
                title=_("This component is already configured on your system."),
                revealed=True,
            )
            prompt_box.append(satisfied_banner)

        step_check = Gtk.CheckButton(label=_("Include this step in the setup"))
        step_check.set_active(step.step_id in self.selected_step_ids)
        step_check.connect("toggled", self._on_step_check_toggled, step.step_id)
        prompt_box.append(step_check)

        prompt_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END, margin_top=16)
        skip_btn = Gtk.Button(label=_("Skip"))
        skip_btn.connect("clicked", lambda _b, s=step: self._on_step_skip(s))
        prompt_actions.append(skip_btn)

        install_btn = Gtk.Button(label=_("Install"), css_classes=["suggested-action", "pill"])
        prompt_actions.append(install_btn)
        prompt_box.append(prompt_actions)

        step_sub_stack.add_named(prompt_box, "prompt")

        # -------------------------------------------------------------
        # STATE 2: RUNNING (SPINNER & LIVE OUTPUT)
        # -------------------------------------------------------------
        running_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        running_counter = Gtk.Label(
            label=_("Step {current} of {total}").format(current=step_num, total=total_steps),
            css_classes=["dim-label", "caption"],
            halign=Gtk.Align.CENTER,
        )
        running_box.append(running_counter)

        spinner = Gtk.Spinner(spinning=True, width_request=40, height_request=40, halign=Gtk.Align.CENTER)
        running_box.append(spinner)

        progress_lbl = Gtk.Label(label=_("Executing command..."), css_classes=["title-3"], halign=Gtk.Align.CENTER)
        running_box.append(progress_lbl)

        log_scroll = Gtk.ScrolledWindow(height_request=160, hexpand=True, vexpand=True)
        log_scroll.add_css_class("card")
        log_buffer = Gtk.TextBuffer()
        log_view = Gtk.TextView(
            buffer=log_buffer,
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        log_scroll.set_child(log_view)
        running_box.append(log_scroll)

        step_sub_stack.add_named(running_box, "running")

        # -------------------------------------------------------------
        # STATE 3: SUCCESS
        # -------------------------------------------------------------
        success_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        success_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        success_icon.set_pixel_size(48)
        success_icon.set_halign(Gtk.Align.CENTER)
        success_box.append(success_icon)

        success_title = Gtk.Label(
            label=_("{step_title} configured successfully!").format(step_title=step.title),
            css_classes=["title-2"],
            halign=Gtk.Align.CENTER,
        )
        success_box.append(success_title)

        success_expander = Adw.ExpanderRow(title=_("Detailed Log"), subtitle=_("View output log"))
        success_log_buffer = Gtk.TextBuffer()
        success_log_view = Gtk.TextView(
            buffer=success_log_buffer,
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        success_log_scroll = Gtk.ScrolledWindow(height_request=140)
        success_log_scroll.set_child(success_log_view)
        success_expander.add_row(success_log_scroll)

        success_group = Adw.PreferencesGroup()
        success_group.add(success_expander)
        success_box.append(success_group)

        success_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END, margin_top=8)
        next_btn = Gtk.Button(label=_("Continue"), css_classes=["suggested-action", "pill"])
        next_btn.connect("clicked", lambda _b: self._advance_next_step())
        success_actions.append(next_btn)
        success_box.append(success_actions)

        step_sub_stack.add_named(success_box, "success")

        # -------------------------------------------------------------
        # STATE 4: ERROR
        # -------------------------------------------------------------
        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        error_icon.set_pixel_size(48)
        error_icon.set_halign(Gtk.Align.CENTER)
        error_box.append(error_icon)

        error_title = Gtk.Label(label=_("Installation Failed"), css_classes=["title-2"], halign=Gtk.Align.CENTER)
        error_box.append(error_title)

        error_msg_lbl = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, halign=Gtk.Align.CENTER)
        error_box.append(error_msg_lbl)

        error_expander = Adw.ExpanderRow(title=_("Detailed Log"), subtitle=_("View error details"))
        error_expander.set_expanded(True)
        error_log_buffer = Gtk.TextBuffer()
        error_log_view = Gtk.TextView(
            buffer=error_log_buffer,
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        error_log_scroll = Gtk.ScrolledWindow(height_request=140)
        error_log_scroll.set_child(error_log_view)
        error_expander.add_row(error_log_scroll)

        error_group = Adw.PreferencesGroup()
        error_group.add(error_expander)
        error_box.append(error_group)

        error_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END, margin_top=8)
        cancel_all_btn = Gtk.Button(label=_("Cancel All"), css_classes=["destructive-action"])
        cancel_all_btn.connect("clicked", lambda _b: self.window.close())
        error_actions.append(cancel_all_btn)

        skip_err_btn = Gtk.Button(label=_("Skip and Continue"))
        skip_err_btn.connect("clicked", lambda _b, s=step: self._on_step_skip(s))
        error_actions.append(skip_err_btn)

        retry_btn = Gtk.Button(label=_("Retry"), css_classes=["suggested-action", "pill"])
        error_actions.append(retry_btn)
        error_box.append(error_actions)

        step_sub_stack.add_named(error_box, "error")

        # Expose test handles in widget mappings
        self.step_sub_stacks[step.step_id] = step_sub_stack
        self.step_install_btns[step.step_id] = install_btn
        self.step_skip_btns[step.step_id] = skip_btn
        self.step_cancel_all_btns[step.step_id] = cancel_all_btn
        self.step_skip_err_btns[step.step_id] = skip_err_btn
        self.step_retry_btns[step.step_id] = retry_btn

        # Connect install and retry triggers
        install_btn.connect(
            "clicked",
            lambda _b: self._run_step_async(
                step=step,
                sub_stack=step_sub_stack,
                progress_lbl=progress_lbl,
                log_buffer=log_buffer,
                log_scroll=log_scroll,
                success_log_buffer=success_log_buffer,
                error_msg_lbl=error_msg_lbl,
                error_log_buffer=error_log_buffer,
            ),
        )

        retry_btn.connect(
            "clicked",
            lambda _b: self._run_step_async(
                step=step,
                sub_stack=step_sub_stack,
                progress_lbl=progress_lbl,
                log_buffer=log_buffer,
                log_scroll=log_scroll,
                success_log_buffer=success_log_buffer,
                error_msg_lbl=error_msg_lbl,
                error_log_buffer=error_log_buffer,
            ),
        )

        step_sub_stack.set_visible_child_name("prompt")
        clamp.set_child(step_sub_stack)
        scrolled.set_child(clamp)
        return scrolled

    def _run_step_async(
        self,
        step: WizardStepInfo,
        sub_stack: Gtk.Stack,
        progress_lbl: Gtk.Label,
        log_buffer: Gtk.TextBuffer,
        log_scroll: Gtk.ScrolledWindow,
        success_log_buffer: Gtk.TextBuffer,
        error_msg_lbl: Gtk.Label,
        error_log_buffer: Gtk.TextBuffer,
    ) -> None:
        """Launch background command execution with real-time feedback."""
        if self._is_executing:
            return

        self._is_executing = True
        self.back_button.set_sensitive(False)
        sub_stack.set_visible_child_name("running")
        progress_lbl.set_label(_("Executing command..."))
        log_buffer.set_text("")

        def on_progress_line(line: str) -> None:
            GLib.idle_add(self._append_log_line, log_buffer, log_scroll, line)

        def worker() -> WizardStepResult:
            if self.manager is not None:
                return self.manager.execute_wizard_step(
                    step=step,
                    user_mode=self.user_mode,
                    on_progress=on_progress_line,
                )
            from ...core.sandbox_bridge import execute_wizard_step

            return execute_wizard_step(
                step=step,
                user_mode=self.user_mode,
                on_progress=on_progress_line,
            )

        def on_done(res: WizardStepResult) -> None:
            self._is_executing = False
            self.back_button.set_sensitive(True)

            if res.success:
                self.step_results[step.step_id] = "installed"
                success_log_buffer.set_text(res.output)
                sub_stack.set_visible_child_name("success")
            else:
                self.step_results[step.step_id] = "failed"
                error_msg_lbl.set_label(res.error_message or _("Command execution failed."))
                error_log_buffer.set_text(res.output)
                sub_stack.set_visible_child_name("error")

        def run_thread() -> None:
            result = worker()
            GLib.idle_add(on_done, result)

        threading.Thread(target=run_thread, daemon=True).start()

    def _append_log_line(self, buffer: Gtk.TextBuffer, scroll: Gtk.ScrolledWindow, line: str) -> bool:
        """Append output line to text buffer and auto-scroll to bottom."""
        end = buffer.get_end_iter()
        buffer.insert(end, f"{line}\n")
        adj = scroll.get_vadjustment()
        if adj is not None:
            adj.set_value(adj.get_upper() - adj.get_page_size())
        return GLib.SOURCE_REMOVE

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
        if self._is_executing:
            return
        if self.current_step_index > 0:
            self._show_step(self.current_step_index - 1)
        else:
            self.stack.set_visible_child_name("overview")
            self.back_button.set_visible(False)

    def _on_step_skip(self, step: WizardStepInfo) -> None:
        """Handle skipping the current step."""
        if self._is_executing:
            return
        self.step_results[step.step_id] = "skipped"
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
            elif status == "failed":
                badge = Gtk.Label(label=_("Failed"), css_classes=["badge", "error"])
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
