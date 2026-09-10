# SPDX-License-Identifier: GPL-3.0-or-later

"""Dialog for Flatpak repair and theme propagation."""

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.models import FlatpakRepairResult, PropagationResult

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")


class FlatpakPropagationDialog:
    """Modal dialog managing Flatpak repair and theme propagation workflow."""

    def __init__(
        self,
        manager: "ThemeManager | None",
        parent_window: Gtk.Window | None = None,
        on_propagated: Callable[[], None] | None = None,
    ) -> None:
        """Initialize and configure propagation dialog."""
        self.manager = manager
        self.parent_window = parent_window
        self.on_propagated = on_propagated

        self._pulse_timer_id: int | None = None
        self._is_running = False
        self._log_lines: list[str] = []

        self.window = Adw.Window(
            modal=True,
            transient_for=parent_window,
            title=_("Flatpak Propagation & Repair"),
            default_width=540,
            default_height=480,
        )
        self.window.set_size_request(500, 440)
        self.window.add_css_class("flatpak-propagation-dialog")

        toolbar_view = Adw.ToolbarView()
        self.header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(self.header_bar)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._init_prompt_page()
        self._init_progress_page()
        self._init_result_page()

        toolbar_view.set_content(self.stack)
        self.window.set_content(toolbar_view)

        self.window.connect("close-request", self._on_close_request)

    def present(self) -> None:
        """Present the dialog to user."""
        self.stack.set_visible_child_name("prompt")
        self.window.present()

    def _init_prompt_page(self) -> None:
        """Create the initial prompt and scope selection page."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(
            maximum_size=500, margin_top=24, margin_bottom=24, margin_start=20, margin_end=20
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # Header icon and text
        img = Gtk.Image.new_from_icon_name("flatpak-symbolic")
        img.set_pixel_size(56)
        img.set_halign(Gtk.Align.CENTER)
        box.append(img)

        lbl_title = Gtk.Label(
            label=_("Propagate Theme to Flatpak"),
            css_classes=["title-2"],
            halign=Gtk.Align.CENTER,
        )
        box.append(lbl_title)

        lbl_desc = Gtk.Label(
            label=_(
                "Flatpak applications run in sandbox containers and require filesystem "
                "access to host themes and icons. Running repair and propagation configures "
                "permissions automatically."
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
            css_classes=["dim-label"],
        )
        box.append(lbl_desc)

        # Scope group
        scope_group = Adw.PreferencesGroup()
        scope_group.set_title(_("Installation Scope"))

        self.radio_user = Gtk.CheckButton.new()
        row_user = Adw.ActionRow(
            title=_("User scope (recommended)"),
            subtitle=_("Repairs user installation and sets user overrides (~/.local/share)"),
        )
        row_user.add_prefix(self.radio_user)
        row_user.set_activatable_widget(self.radio_user)
        scope_group.add(row_user)

        self.radio_system = Gtk.CheckButton.new()
        self.radio_system.set_group(self.radio_user)
        row_system = Adw.ActionRow(
            title=_("System-wide scope"),
            subtitle=_("Repairs system installation (requires administrator password via pkexec)"),
        )
        row_system.add_prefix(self.radio_system)
        row_system.set_activatable_widget(self.radio_system)
        scope_group.add(row_system)

        self.radio_user.set_active(True)
        box.append(scope_group)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END)
        btn_box.set_margin_top(12)

        self.btn_ignore = Gtk.Button(label=_("Ignore"))
        self.btn_ignore.connect("clicked", lambda _b: self.window.close())
        btn_box.append(self.btn_ignore)

        self.btn_propagate = Gtk.Button(
            label=_("Propagate Now"),
            css_classes=["suggested-action", "pill"],
        )
        self.btn_propagate.connect("clicked", lambda _b: self._start_propagation())
        btn_box.append(self.btn_propagate)

        box.append(btn_box)
        clamp.set_child(box)
        scrolled.set_child(clamp)

        self.stack.add_named(scrolled, "prompt")

    def _init_progress_page(self) -> None:
        """Create progress page with spinner, progress bar, and streaming log."""
        clamp = Adw.Clamp(
            maximum_size=500, margin_top=24, margin_bottom=24, margin_start=20, margin_end=20
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        self.spinner = Gtk.Spinner(
            spinning=True, width_request=48, height_request=48, halign=Gtk.Align.CENTER
        )
        box.append(self.spinner)

        self.lbl_progress_status = Gtk.Label(
            label=_("Repairing Flatpak installation..."),
            css_classes=["title-4"],
            halign=Gtk.Align.CENTER,
        )
        box.append(self.lbl_progress_status)

        self.progress_bar = Gtk.ProgressBar(hexpand=True)
        box.append(self.progress_bar)

        # Expandable log
        expander = Gtk.Expander(label=_("Detailed Log"), expanded=True, vexpand=True)
        scrolled_log = Gtk.ScrolledWindow(vexpand=True, min_content_height=160)
        scrolled_log.add_css_class("card")

        self.text_buffer = Gtk.TextBuffer()
        self.text_view = Gtk.TextView(
            buffer=self.text_buffer,
            editable=False,
            cursor_visible=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD,
            left_margin=10,
            right_margin=10,
            top_margin=10,
            bottom_margin=10,
        )
        scrolled_log.set_child(self.text_view)
        expander.set_child(scrolled_log)
        box.append(expander)

        clamp.set_child(box)
        self.stack.add_named(clamp, "progress")

    def _init_result_page(self) -> None:
        """Create outcome page showing success/error status and detailed log."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(
            maximum_size=500, margin_top=24, margin_bottom=24, margin_start=20, margin_end=20
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        self.result_status_page = Adw.StatusPage()
        box.append(self.result_status_page)

        self.result_expander = Gtk.Expander(label=_("Detailed Log"), expanded=False, vexpand=True)
        scrolled_log = Gtk.ScrolledWindow(vexpand=True, min_content_height=140)
        scrolled_log.add_css_class("card")

        self.result_text_buffer = Gtk.TextBuffer()
        self.result_text_view = Gtk.TextView(
            buffer=self.result_text_buffer,
            editable=False,
            cursor_visible=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD,
            left_margin=10,
            right_margin=10,
            top_margin=10,
            bottom_margin=10,
        )
        scrolled_log.set_child(self.result_text_view)
        self.result_expander.set_child(scrolled_log)
        box.append(self.result_expander)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.CENTER)
        self.btn_close = Gtk.Button(
            label=_("Close"),
            css_classes=["suggested-action", "pill"],
            width_request=140,
        )
        self.btn_close.connect("clicked", lambda _b: self.window.close())
        btn_box.append(self.btn_close)
        box.append(btn_box)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        self.stack.add_named(scrolled, "result")

    def _start_propagation(self) -> None:
        """Execute flatpak repair and override configuration in background thread."""
        if self._is_running:
            return

        self._is_running = True
        self._log_lines.clear()
        self.text_buffer.set_text("")
        self.result_text_buffer.set_text("")

        user_mode = bool(self.radio_user.get_active())
        if hasattr(self.header_bar, "set_show_end_title_buttons"):
            self.header_bar.set_show_end_title_buttons(False)
            self.header_bar.set_show_start_title_buttons(False)
        self.stack.set_visible_child_name("progress")

        self.spinner.start()
        self._pulse_timer_id = GLib.timeout_add(100, self._on_pulse)

        def on_progress_log(line: str) -> None:
            GLib.idle_add(self._append_log_line, line)

        def worker_thread() -> None:
            if self.manager is None:
                repair_res = FlatpakRepairResult(
                    success=False,
                    output="Manager unavailable.",
                    error_message="ThemeManager not initialized.",
                )
                prop_res = PropagationResult(warnings=["ThemeManager is unavailable."])
            else:
                repair_res, prop_res = self.manager.repair_and_propagate_flatpak(
                    user_mode=user_mode,
                    use_pkexec=not user_mode,
                    on_progress=on_progress_log,
                )

            GLib.idle_add(self._on_work_completed, repair_res, prop_res)

        threading.Thread(target=worker_thread, daemon=True).start()

    def _on_pulse(self) -> bool:
        """Pulse the progress bar while running."""
        if self._is_running:
            self.progress_bar.pulse()
            return GLib.SOURCE_CONTINUE
        return GLib.SOURCE_REMOVE

    def _append_log_line(self, line: str) -> bool:
        """Append log line to running buffer."""
        self._log_lines.append(line)
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.insert(end_iter, line + "\n")

        # Update step label with latest action if relevant
        if "Verifying" in line or "Checking" in line or "repair" in line.lower():
            self.lbl_progress_status.set_label(line)
        elif "overrides" in line.lower():
            self.lbl_progress_status.set_label(_("Configuring Flatpak filesystem overrides..."))

        # Scroll to bottom
        adj = self.text_view.get_vadjustment()
        if adj is not None:
            adj.set_value(adj.get_upper() - adj.get_page_size())
        return GLib.SOURCE_REMOVE

    def _on_work_completed(
        self,
        repair_res: FlatpakRepairResult,
        prop_res: PropagationResult,
    ) -> bool:
        """Handle completion of Flatpak repair and propagation."""
        self._is_running = False
        if self._pulse_timer_id is not None:
            GLib.source_remove(self._pulse_timer_id)
            self._pulse_timer_id = None

        self.spinner.stop()
        if hasattr(self.header_bar, "set_show_end_title_buttons"):
            self.header_bar.set_show_end_title_buttons(True)
            self.header_bar.set_show_start_title_buttons(True)

        full_log = "\n".join(self._log_lines)
        if not full_log and repair_res.output:
            full_log = repair_res.output
        self.result_text_buffer.set_text(full_log)

        overall_success = repair_res.success and prop_res.flatpak_success

        if overall_success:
            self.result_status_page.set_icon_name("emblem-ok-symbolic")
            self.result_status_page.set_title(_("Propagation Completed Successfully"))
            self.result_status_page.set_description(
                _("Flatpak runtime was verified and theme filesystem overrides were applied.")
            )
        else:
            err_msg = (
                repair_res.error_message
                or "; ".join(prop_res.warnings)
                or _("Unknown error occurred.")
            )
            self.result_status_page.set_icon_name("dialog-error-symbolic")
            self.result_status_page.set_title(_("Propagation Failed"))
            self.result_status_page.set_description(f"{_('Error:')} {err_msg}")
            self.result_expander.set_expanded(True)

        self.stack.set_visible_child_name("result")

        if self.on_propagated:
            try:
                self.on_propagated()
            except Exception as cb_err:
                logger.warning("Error in on_propagated callback: %s", cb_err)

        return GLib.SOURCE_REMOVE

    def _on_close_request(self, _window: Adw.Window) -> bool:
        """Prevent closing window while operation is actively running."""
        return self._is_running
