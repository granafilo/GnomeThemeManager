# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Profiles and Presets' page.

Provides complete GNOME desktop configuration preset management
via public APIs of ThemeManager.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GLib, Gtk, Pango

from ...core.errors import GnomeThemeManagerError
from ...core.models import ThemeSet

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.presets")

UI_FILE = Path(__file__).parent.parent / "ui" / "presets_page.ui"

PRESET_NAME_MAX_LEN: int = 255

_COMPONENT_LABELS: dict[str, str] = {
    "gtk_theme": _("GTK"),
    "icon_theme": _("Icons"),
    "cursor_theme": _("Cursors"),
    "color_scheme": _("Color scheme"),
    "shell_theme": _("GNOME Shell"),
}


def _build_preset_summary(theme_set: ThemeSet) -> str:
    """Build readable summary string of ThemeSet components."""
    lines: list[str] = []
    for field, label in _COMPONENT_LABELS.items():
        value = getattr(theme_set, field, None)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines) if lines else _("No components configured")


class _PresetRow(Adw.ActionRow):
    """Libadwaita row displaying an individual preset in the list."""

    def __init__(
        self,
        preset_name: str,
        theme_set: ThemeSet | None,
        on_apply: Callable[[str], None],
        on_delete: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._preset_name = preset_name

        self.set_title(preset_name)

        if theme_set is not None:
            summary = _build_preset_summary(theme_set)
            self.set_subtitle(summary)
        else:
            self.set_subtitle(_("⚠ Unreadable preset — corrupted or incomplete data"))
            self.add_css_class("error")

        icon = Gtk.Image.new_from_icon_name("document-save-as-symbolic")
        icon.set_pixel_size(32)
        self.add_prefix(icon)

        apply_btn = Gtk.Button()
        apply_btn.set_label(_("Apply"))
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_sensitive(theme_set is not None)
        apply_btn.connect("clicked", lambda _: on_apply(self._preset_name))
        self.add_suffix(apply_btn)

        delete_btn = Gtk.Button()
        delete_btn.set_icon_name("user-trash-symbolic")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.add_css_class("destructive-action")
        delete_btn.set_tooltip_text(f"{_('Delete preset')} '{preset_name}'")
        delete_btn.connect("clicked", lambda _: on_delete(self._preset_name))
        self.add_suffix(delete_btn)


class PresetsPage:
    """Controller for 'Profiles and Presets' GTK4/Libadwaita GUI page."""

    PAGE_ID: str = "presets"
    ICON_NAME: str = "document-save-as-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize controller loading presets_page.ui template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Profiles and Presets")
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        self.presets_list_box: Gtk.ListBox = self.builder.get_object("presets_list_box")
        self.save_preset_button: Gtk.Button = self.builder.get_object("save_preset_button")
        self.reload_presets_button: Gtk.Button = self.builder.get_object("reload_presets_button")

        self.empty_save_button: Gtk.Button = self.builder.get_object("empty_save_button")
        self.error_message_label: Gtk.Label = self.builder.get_object("error_message_label")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        self._is_loading: bool = False
        self._is_applying: bool = False
        self._load_generation: int = 0
        self._confirm_dialog_open: bool = False
        self._has_loaded: bool = False

        self.on_preset_applied: Callable[[], None] | None = None

        self.save_preset_button.connect("clicked", self._on_save_clicked)
        self.empty_save_button.connect("clicked", self._on_save_clicked)
        self.reload_presets_button.connect("clicked", self._on_reload_clicked)
        self.error_retry_button.connect("clicked", self._on_reload_clicked)

    def get_widget(self) -> Gtk.Stack:
        """Return root widget for embedding into window Gtk.Stack."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indicate if presets are loading."""
        return self._is_loading

    @property
    def has_loaded(self) -> bool:
        """Indicate if page has been loaded at least once."""
        return self._has_loaded

    def refresh(self, sync: bool = False) -> None:
        """Load or reload presets list."""
        if self._is_loading and not sync:
            logger.debug("Presets loading already in progress, request ignored.")
            return

        self._is_loading = True
        self._load_generation += 1
        current_generation = self._load_generation
        self._set_state("loading")

        def worker_fetch() -> tuple[list[tuple[str, ThemeSet | None]] | None, Exception | None]:
            try:
                if self.manager is None:
                    return [], None

                names = self.manager.list_presets()
                rows: list[tuple[str, ThemeSet | None]] = []
                for name in names:
                    try:
                        ts = self.manager.load_preset(name)
                        rows.append((name, ts))
                    except (ValueError, FileNotFoundError, OSError) as err:
                        logger.warning("Preset '%s' unreadable: %s", name, err)
                        rows.append((name, None))
                return rows, None
            except Exception as err:
                return None, err

        def on_fetch_completed(
            result: tuple[list[tuple[str, ThemeSet | None]] | None, Exception | None],
        ) -> bool:
            if current_generation != self._load_generation:
                logger.debug(
                    "Late preset callback discarded: gen %d != %d",
                    current_generation,
                    self._load_generation,
                )
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            self._has_loaded = True
            rows, error = result

            if error is not None:
                logger.error("Error loading presets list: %s", error)
                self.error_message_label.set_text(str(error))
                self._set_state("error")
                return GLib.SOURCE_REMOVE

            while True:
                child = self.presets_list_box.get_first_child()
                if child is None:
                    break
                self.presets_list_box.remove(child)

            if not rows:
                self._set_state("empty")
                return GLib.SOURCE_REMOVE

            for name, theme_set in rows:
                row = _PresetRow(
                    preset_name=name,
                    theme_set=theme_set,
                    on_apply=self._on_apply_preset_requested,
                    on_delete=self._on_delete_preset_requested,
                )
                self.presets_list_box.append(row)

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

    def _on_reload_clicked(self, _button: Gtk.Button) -> None:
        """Reload presets from disk."""
        self.refresh()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        """Open input dialog for new preset name."""
        if self.manager is None:
            return
        self._open_save_dialog()

    def _open_save_dialog(self, prefill_name: str = "") -> None:
        """Open input dialog to enter preset name."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_size_request(400, -1)

        lbl = Gtk.Label(label=_("Preset name:"))
        lbl.set_halign(Gtk.Align.START)
        lbl.set_wrap(False)
        box.append(lbl)

        entry = Gtk.Entry()
        entry.set_placeholder_text(_("e.g. Work Dark Theme"))
        entry.set_max_length(PRESET_NAME_MAX_LEN)
        entry.set_activates_default(True)
        if prefill_name:
            entry.set_text(prefill_name)
        box.append(entry)

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(_("Save Current Configuration"), "")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("save", _("Save"))
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                resp = str(response_param)
                if resp == "save":
                    name = entry.get_text().strip()
                    self._validate_and_save(name)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                _("Save Current Configuration"),
                "",
            )
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("save", _("Save"))
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                if response_id == "save":
                    name = entry.get_text().strip()
                    self._validate_and_save(name)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _validate_and_save(self, name: str) -> None:
        """Validate input preset name and proceed to save."""
        if not name or not name.strip():
            self._show_save_error_and_retry(_("Preset name cannot be empty."), name)
            return

        name = name.strip()

        try:
            existing = self.manager.list_presets() if self.manager else []
        except Exception as err:
            logger.error("Error checking preset duplicates: %s", err)
            existing = []

        if name in existing:
            self._open_overwrite_confirm_dialog(name)
            return

        self._do_save_preset(name, overwrite=False)

    def _show_save_error_and_retry(self, message: str, prefill: str = "") -> None:
        """Show error toast and reopen input dialog."""
        self._show_toast(message)
        self._open_save_dialog(prefill_name=prefill)

    def _open_overwrite_confirm_dialog(self, name: str) -> None:
        """Open confirmation dialog to overwrite an existing preset."""
        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                f'{_("Overwrite preset")} "{name}"?',
                _(
                    "A preset with this name already exists. Overwriting will replace previous data."
                ),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("overwrite", _("Overwrite"))
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                if str(response_param) == "overwrite":
                    self._do_save_preset(name, overwrite=True)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'{_("Overwrite preset")} "{name}"?',
                _("A preset with this name already exists."),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("overwrite", _("Overwrite"))
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                if response_id == "overwrite":
                    self._do_save_preset(name, overwrite=True)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _do_save_preset(self, name: str, overwrite: bool = False) -> None:
        """Execute preset saving."""
        if self.manager is None:
            return
        try:
            self.manager.save_current_as_preset(name, overwrite=overwrite)
            self._show_toast(f'{_("Preset")} "{name}" {_("saved.")}')
            self.refresh()
        except (ValueError, FileExistsError, OSError, GnomeThemeManagerError) as err:
            logger.error("Error saving preset '%s': %s", name, err)
            self._show_toast(f"{_('Error:')} {err}")

    def _on_apply_preset_requested(self, name: str) -> None:
        """Open confirmation dialog for preset application."""
        if self._confirm_dialog_open or self._is_applying:
            logger.debug("Operation already in progress, apply request ignored.")
            return

        try:
            ts = self.manager.load_preset(name) if self.manager else None
        except Exception:
            ts = None

        summary = _build_preset_summary(ts) if ts else _("Details not available.")

        self._confirm_dialog_open = True

        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_size_request(460, -1)
        extra_box.set_margin_top(6)
        extra_box.set_margin_bottom(12)
        extra_box.set_margin_start(16)
        extra_box.set_margin_end(16)

        for line in summary.splitlines():
            lbl = Gtk.Label(label=line)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_wrap(False)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            extra_box.append(lbl)

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(f'{_("Apply preset")} "{name}"?', "")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply", _("Apply"))
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                try:
                    if str(response_param) == "apply":
                        self._run_apply_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'{_("Apply preset")} "{name}"?',
                summary,
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply", _("Apply"))
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "apply":
                        self._run_apply_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False

    def _run_apply_preset(self, name: str, sync: bool = False) -> None:
        """Execute preset apply operation."""
        if self._is_applying:
            logger.debug("Apply already in progress, request ignored.")
            return

        self._is_applying = True
        self._set_controls_sensitive(False)

        if sync:
            self._do_apply_preset(name, sync=True)
        else:
            threading.Thread(
                target=self._do_apply_preset,
                args=(name,),
                daemon=True,
            ).start()

    def _do_apply_preset(self, name: str, sync: bool = False) -> None:
        """Call manager.apply_preset() and handle result."""
        try:
            if self.manager is None:
                raise GnomeThemeManagerError(_("Manager unavailable."))
            result = self.manager.apply_preset(name)
            if sync:
                self._on_apply_done(name, result, None)
            else:
                GLib.idle_add(self._on_apply_done, name, result, None)
        except Exception as err:
            logger.error("Error applying preset '%s': %s", name, err)
            if sync:
                self._on_apply_done(name, None, err)
            else:
                GLib.idle_add(self._on_apply_done, name, None, err)

    def _on_apply_done(self, name: str, result: Any, error: Exception | None) -> bool:
        """Update UI after preset application."""
        self._is_applying = False
        self._set_controls_sensitive(True)

        if error is not None:
            err_msg = _("Error applying preset")
            self._show_toast(f'{err_msg} "{name}": {error}')
            return False

        if result is not None:
            warnings = getattr(result, "warnings", [])
            if warnings:
                self._show_toast(
                    f'{_("Preset")} "{name}" {_("applied with warnings:")} {"; ".join(str(w) for w in warnings)}'
                )
            else:
                self._show_toast(f'{_("Preset")} "{name}" {_("applied successfully.")}')
        else:
            self._show_toast(f'{_("Preset")} "{name}" {_("applied.")}')

        if self.on_preset_applied is not None:
            try:
                self.on_preset_applied()
            except Exception as cb_err:
                logger.warning("Error in on_preset_applied callback: %s", cb_err)

        return False

    def _on_delete_preset_requested(self, name: str) -> None:
        """Open confirmation dialog for preset deletion."""
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                f'{_("Delete preset")} "{name}"?',
                _(
                    "This action will remove the preset file. Installed themes will not be modified."
                ),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("delete", _("Delete"))
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                try:
                    if str(response_param) == "delete":
                        self._do_delete_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'{_("Delete preset")} "{name}"?',
                _(
                    "This action will remove the preset file. Installed themes will not be modified."
                ),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("delete", _("Delete"))
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "delete":
                        self._do_delete_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False

    def _do_delete_preset(self, name: str) -> None:
        """Execute preset deletion."""
        if self.manager is None:
            return
        try:
            self.manager.delete_preset(name)
            self._show_toast(f'{_("Preset")} "{name}" {_("deleted.")}')
            self.refresh()
        except (FileNotFoundError, ValueError, OSError, GnomeThemeManagerError) as err:
            logger.error("Error deleting preset '%s': %s", name, err)
            err_msg = _("Error deleting:")
            self._show_toast(f"{err_msg} {err}")

    def _set_state(self, state: str) -> None:
        """Set visible stack state (loading, ready, empty, error)."""
        self.widget.set_visible_child_name(state)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Enable or disable main controls."""
        self.save_preset_button.set_sensitive(sensitive)
        self.reload_presets_button.set_sensitive(sensitive)
        self.empty_save_button.set_sensitive(sensitive)
        self.error_retry_button.set_sensitive(sensitive)

    def _clear_toast(self) -> None:
        """Clear persistent top feedback."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "clear_feedback"):
            root.clear_feedback()

    def _show_toast(self, message: str, timeout: int = 0) -> None:
        """Show persistent feedback notification."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "add_toast"):
            root.add_toast(message, timeout=timeout)
        else:
            logger.info("[Feedback PresetsPage]: %s", message)
