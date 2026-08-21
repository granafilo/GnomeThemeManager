# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Global Themes' page.

Provides cards grid view with 1-click apply for complete desktop themes.
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
from gi.repository import Adw, GLib, Gtk

from ...core.global_themes import GlobalTheme
from ...core.models import ApplyResult, ThemeSet

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.global_themes")

UI_FILE = Path(__file__).parent.parent / "ui" / "global_themes_page.ui"


def _create_component_pill(label_text: str, value_text: str) -> Gtk.Box:
    """Helper to build a small visually distinct pill for component metadata."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    box.add_css_class("card")
    box.set_margin_top(2)
    box.set_margin_bottom(2)
    box.set_margin_start(2)
    box.set_margin_end(2)

    lbl_key = Gtk.Label(label=label_text)
    lbl_key.add_css_class("dim-label")
    lbl_key.set_margin_start(6)
    lbl_key.set_margin_top(3)
    lbl_key.set_margin_bottom(3)

    lbl_val = Gtk.Label(label=value_text)
    lbl_val.add_css_class("heading")
    lbl_val.set_margin_end(6)
    lbl_val.set_margin_top(3)
    lbl_val.set_margin_bottom(3)

    box.append(lbl_key)
    box.append(lbl_val)
    return box


class _GlobalThemeCard(Gtk.Box):
    """Card widget displaying an individual Global Theme."""

    def __init__(
        self,
        theme: GlobalTheme,
        on_apply: Callable[[str], None],
        on_delete: Callable[[str], None] | None = None,
        on_edit: Callable[["GlobalTheme"], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._theme = theme
        self._on_apply = on_apply
        self._on_delete = on_delete
        self._on_edit = on_edit

        self.add_css_class("card")
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Header Box: Icon/Thumb + Title/Author + Action Buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header_box.set_margin_start(16)
        header_box.set_margin_end(16)
        header_box.set_margin_top(16)

        # Icon/Thumbnail
        is_user = theme.origin == "user"
        icon = Gtk.Image.new_from_icon_name(
            "document-save-as-symbolic" if is_user else "starred-symbolic"
        )
        icon.set_pixel_size(36)
        icon.set_valign(Gtk.Align.CENTER)
        header_box.append(icon)

        # Title + Author + Description
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title_box.set_hexpand(True)

        title_label = Gtk.Label(label=theme.name)
        title_label.set_xalign(0)
        title_label.add_css_class("title-3")
        title_box.append(title_label)

        meta_parts: list[str] = []
        if is_user:
            meta_parts.append(_("User Created"))
        else:
            meta_parts.append(_("Bundled Theme"))
        if theme.author:
            meta_parts.append(f"{_('by')} {theme.author}")

        meta_label = Gtk.Label(label=" • ".join(meta_parts))
        meta_label.set_xalign(0)
        meta_label.add_css_class("dim-label")
        title_box.append(meta_label)

        header_box.append(title_box)

        # Action buttons box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)

        # Delete button for user themes
        if is_user and self._on_delete is not None:
            del_btn = Gtk.Button()
            del_btn.set_icon_name("user-trash-symbolic")
            del_btn.set_tooltip_text(_("Delete this Global Theme"))
            del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _: self._on_delete(self._theme.id))
            btn_box.append(del_btn)

        # Edit button for user themes
        if is_user and self._on_edit is not None:
            edit_btn = Gtk.Button()
            edit_btn.set_icon_name("document-edit-symbolic")
            edit_btn.set_tooltip_text(_("Edit this Global Theme"))
            edit_btn.add_css_class("flat")
            edit_btn.connect("clicked", lambda _: self._on_edit(self._theme))
            btn_box.append(edit_btn)

        # Apply Button
        self.apply_btn = Gtk.Button()
        self.apply_btn.set_label(_("Apply"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", lambda _: self._on_apply(self._theme.id))
        btn_box.append(self.apply_btn)

        header_box.append(btn_box)
        self.append(header_box)

        # Description if present
        if theme.description:
            desc_label = Gtk.Label(label=theme.description)
            desc_label.set_xalign(0)
            desc_label.set_wrap(True)
            desc_label.set_margin_start(16)
            desc_label.set_margin_end(16)
            desc_label.add_css_class("body")
            self.append(desc_label)

        # Component Pills FlowBox (wraps gracefully without pushing window width)
        comp_box = Gtk.FlowBox()
        comp_box.set_selection_mode(Gtk.SelectionMode.NONE)
        comp_box.set_max_children_per_line(10)
        comp_box.set_min_children_per_line(1)
        comp_box.set_column_spacing(6)
        comp_box.set_row_spacing(6)
        comp_box.set_margin_start(16)
        comp_box.set_margin_end(16)
        comp_box.set_margin_bottom(16)
        comp_box.set_hexpand(True)

        ts: ThemeSet = theme.components
        if ts.gtk_theme:
            comp_box.append(_create_component_pill(_("GTK"), ts.gtk_theme))
        if ts.icon_theme:
            comp_box.append(_create_component_pill(_("Icons"), ts.icon_theme))
        if ts.cursor_theme:
            comp_box.append(_create_component_pill(_("Cursors"), ts.cursor_theme))
        if ts.shell_theme:
            comp_box.append(_create_component_pill(_("Shell"), ts.shell_theme))
        if ts.color_scheme:
            comp_box.append(_create_component_pill(_("Mode"), ts.color_scheme))

        self.append(comp_box)


class GlobalThemesPage:
    """Controller for 'Global Themes' GTK4/Libadwaita GUI page."""

    def __init__(self, manager: "ThemeManager") -> None:
        """Initialize GlobalThemesPage loading UI template.

        Args:
            manager: ThemeManager instance.

        Raises:
            FileNotFoundError: If UI template file is not found.
        """
        self.manager = manager
        self.page_id = "global_themes"
        self.title = _("Global Themes")

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        # Main widgets
        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.themes_container: Gtk.Box = self.builder.get_object("themes_container")
        self.save_theme_button: Gtk.Button | None = self.builder.get_object("save_theme_button")
        self.reload_button: Gtk.Button | None = self.builder.get_object("reload_button")
        self.empty_page: Adw.StatusPage = self.builder.get_object("empty_page")
        self.error_page: Adw.StatusPage = self.builder.get_object("error_page")

        # Internal state
        self._all_themes: list[GlobalTheme] = []
        self._is_loading: bool = False
        self._filter_text: str = ""

        # Callbacks
        self.on_loading_changed: Callable[[bool], None] | None = None
        self.on_theme_applied: Callable[[str, ApplyResult], None] | None = None
        self.on_notify_message: Callable[[str, bool], None] | None = None
        self.on_edit_requested: Callable[[GlobalTheme], None] | None = None

        # Signals
        self.search_entry.connect("search-changed", self._on_search_changed)
        if self.save_theme_button is not None:
            self.save_theme_button.connect("clicked", self._on_save_clicked)
        if self.reload_button is not None:
            self.reload_button.connect("clicked", lambda _: self.refresh())

    def get_widget(self) -> Gtk.Stack:
        """Return the root GTK widget for this page."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Return whether asynchronous background operation is active."""
        return self._is_loading

    def _set_loading(self, loading: bool) -> None:
        """Update loading state flag and notify observer callback."""
        self._is_loading = loading
        if self.on_loading_changed:
            self.on_loading_changed(loading)

    def refresh(self, sync: bool = False) -> None:
        """Refresh list of global themes."""
        if self._is_loading and not sync:
            return

        self._set_loading(True)
        self.widget.set_visible_child_name("loading")

        if sync:
            self._do_load()
            return

        thread = threading.Thread(target=self._async_load, daemon=True)
        thread.start()

    def _async_load(self) -> None:
        """Background thread worker to discover global themes."""
        try:
            themes = self.manager.list_global_themes()
            GLib.idle_add(self._on_load_success, themes)
        except Exception as err:
            logger.error("Error loading global themes: %s", err)
            GLib.idle_add(self._on_load_error, str(err))

    def _do_load(self) -> None:
        """Synchronous load helper."""
        try:
            themes = self.manager.list_global_themes()
            self._on_load_success(themes)
        except Exception as err:
            logger.error("Error loading global themes synchronously: %s", err)
            self._on_load_error(str(err))

    def _on_load_success(self, themes: list[GlobalTheme]) -> None:
        """Update UI with loaded themes."""
        self._all_themes = themes
        self._set_loading(False)
        self._render_themes()

    def _on_load_error(self, error_msg: str) -> None:
        """Show error state on load failure."""
        self._set_loading(False)
        self.error_page.set_description(error_msg)
        self.widget.set_visible_child_name("error")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filter visible cards on search input changes."""
        self._filter_text = entry.get_text().strip().lower()
        self._render_themes()

    def _render_themes(self) -> None:
        """Render theme cards inside the container."""
        while True:
            child = self.themes_container.get_first_child()
            if child is None:
                break
            self.themes_container.remove(child)

        filtered = [
            t
            for t in self._all_themes
            if (
                not self._filter_text
                or self._filter_text in t.name.lower()
                or self._filter_text in t.description.lower()
                or any(self._filter_text in tag.lower() for tag in t.tags)
            )
        ]

        if not filtered:
            self.widget.set_visible_child_name("empty")
            return

        for theme in filtered:
            card = _GlobalThemeCard(
                theme=theme,
                on_apply=self._apply_theme,
                on_delete=self._on_delete_theme_requested,
                on_edit=self._on_edit_theme_requested,
            )
            self.themes_container.append(card)

        self.widget.set_visible_child_name("ready")

    def _apply_theme(self, theme_id: str) -> None:
        """Apply selected global theme in background."""
        if self._is_loading:
            return

        self._set_loading(True)

        def worker() -> None:
            try:
                res = self.manager.apply_global_theme(theme_id, propagate_sandbox=True)
                GLib.idle_add(self._on_apply_success, theme_id, res)
            except Exception as err:
                logger.error("Failed to apply global theme '%s': %s", theme_id, err)
                GLib.idle_add(self._on_apply_error, theme_id, str(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_apply_success(self, theme_id: str, result: ApplyResult) -> None:
        """Handle theme application success."""
        self._set_loading(False)
        theme = self.manager.get_global_theme(theme_id)
        name = theme.name if theme else theme_id

        msg = f"{_('Global Theme applied successfully')}: {name}"
        if self.on_notify_message:
            self.on_notify_message(msg, False)

        if self.on_theme_applied:
            self.on_theme_applied(theme_id, result)

    def _on_apply_error(self, theme_id: str, error_msg: str) -> None:
        """Handle theme application error."""
        self._set_loading(False)
        msg = f"{_('Failed to apply global theme')}: {error_msg}"
        if self.on_notify_message:
            self.on_notify_message(msg, True)

    def _on_save_clicked(self, _btn: Gtk.Button) -> None:
        """Show dialog to save current configuration as a new Global Theme."""
        entry = Gtk.Entry()
        entry.set_placeholder_text(_("e.g. My Custom Desktop"))
        entry.set_hexpand(True)

        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_margin_start(16)
        extra_box.set_margin_end(16)
        extra_box.set_margin_bottom(8)
        extra_box.append(entry)

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                _("Save Current Configuration"), _("Enter a name for your new Global Theme:")
            )
            dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("save", _("Save"))
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_response(_d: Any, response_id: str) -> None:
                if response_id == "save":
                    theme_name = entry.get_text().strip()
                    if theme_name:
                        self._do_save_theme(theme_name)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                _("Save Current Configuration"),
                _("Enter a name for your new Global Theme:"),
            )
            dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("save", _("Save"))
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

            def on_md_response(_d: Any, response_id: str) -> None:
                if response_id == "save":
                    theme_name = entry.get_text().strip()
                    if theme_name:
                        self._do_save_theme(theme_name)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _do_save_theme(self, name: str) -> None:
        """Execute theme saving via manager."""
        try:
            self.manager.save_current_as_global_theme(name, overwrite=True)
            msg = f"{_('Global Theme saved successfully')}: {name}"
            if self.on_notify_message:
                self.on_notify_message(msg, False)
            self.refresh()
        except Exception as err:
            logger.error("Error saving global theme '%s': %s", name, err)
            msg = f"{_('Failed to save global theme')}: {err}"
            if self.on_notify_message:
                self.on_notify_message(msg, True)

    def _on_edit_theme_requested(self, theme: GlobalTheme) -> None:
        """Forward edit request for a user Global Theme to the editor page."""
        if self.on_edit_requested:
            self.on_edit_requested(theme)

    def _on_delete_theme_requested(self, theme_id: str) -> None:
        """Show delete confirmation dialog for user global theme."""
        theme = self.manager.get_global_theme(theme_id)
        if not theme:
            return

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                _("Delete Global Theme"), f"{_('Are you sure you want to delete')} '{theme.name}'?"
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("delete", _("Delete"))
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(_d: Any, response_id: str) -> None:
                if response_id == "delete":
                    self._do_delete_theme(theme_id, theme.name)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                _("Delete Global Theme"),
                f"{_('Are you sure you want to delete')} '{theme.name}'?",
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("delete", _("Delete"))
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_md_response(_d: Any, response_id: str) -> None:
                if response_id == "delete":
                    self._do_delete_theme(theme_id, theme.name)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _do_delete_theme(self, theme_id: str, name: str) -> None:
        """Execute theme deletion via manager."""
        try:
            self.manager.delete_global_theme(theme_id)
            msg = f"{_('Global Theme deleted successfully')}: {name}"
            if self.on_notify_message:
                self.on_notify_message(msg, False)
            self.refresh()
        except Exception as err:
            logger.error("Error deleting global theme '%s': %s", theme_id, err)
            msg = f"{_('Failed to delete global theme')}: {err}"
            if self.on_notify_message:
                self.on_notify_message(msg, True)
