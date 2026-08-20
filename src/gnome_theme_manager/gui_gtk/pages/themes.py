# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Browse themes' page with Active Theme Card and Available Themes List.

Renders active theme Card and list of available alternative themes
for each component (GNOME Shell, GTK, Icons, Cursors).
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ...core.errors import GnomeThemeManagerError
from ...core.models import ApplyResult, Theme, ThemeSet, ThemeType
from ..widgets.icon_pack_preview import IconPackPreview

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.themes")

UI_FILE = Path(__file__).parent.parent / "ui" / "themes_page.ui"

CATEGORY_ICONS: dict[ThemeType, str] = {
    ThemeType.GTK: "preferences-desktop-theme-symbolic",
    ThemeType.ICON: "applications-graphics-symbolic",
    ThemeType.CURSOR: "input-mouse-symbolic",
    ThemeType.SHELL: "preferences-system-windows-symbolic",
}


def get_category_label(theme_type: ThemeType) -> str:
    """Return localized label for theme category."""
    labels = {
        ThemeType.GTK: _("Applications (GTK)"),
        ThemeType.ICON: _("Icons"),
        ThemeType.CURSOR: _("Cursors"),
        ThemeType.SHELL: _("GNOME Shell"),
    }
    return labels.get(theme_type, str(theme_type.value).upper())


def get_dialog_category_name(theme_type: ThemeType) -> str:
    """Return localized dialog category name."""
    names = {
        ThemeType.SHELL: _("GNOME Shell"),
        ThemeType.GTK: _("GTK"),
        ThemeType.ICON: _("Icons"),
        ThemeType.CURSOR: _("Cursors"),
    }
    return names.get(theme_type, str(theme_type.value).upper())


def get_category_title(theme_type: ThemeType) -> str:
    """Return localized category title."""
    titles = {
        ThemeType.GTK: _("Application Themes (GTK)"),
        ThemeType.ICON: _("Icon Themes"),
        ThemeType.CURSOR: _("Cursor Themes"),
        ThemeType.SHELL: _("GNOME Shell Themes"),
    }
    return titles.get(theme_type, str(theme_type.value))


@dataclass(frozen=True)
class ThemeItemPresentation:
    """Immutable presentation model for a theme row."""

    name: str
    theme_type: ThemeType
    category_display: str
    icon_name: str
    path_display: str
    origin_display: str
    is_user_level: bool
    is_invalid: bool = False
    warning_message: str | None = None


@dataclass(frozen=True)
class ThemesSnapshot:
    """Immutable snapshot of full scanned themes list and active themes."""

    items: list[ThemeItemPresentation]
    active_themes: dict[ThemeType, str | None]


def build_theme_presentation(
    theme: Theme,
    is_invalid: bool = False,
    warning_message: str | None = None,
) -> ThemeItemPresentation:
    """Build a presentation model from domain Theme object."""
    category_display = get_category_label(theme.theme_type)
    icon_name = CATEGORY_ICONS.get(theme.theme_type, "applications-graphics-symbolic")
    origin_display = (
        _("User (~/.local/share/...)") if theme.is_user_level else _("System (/usr/share/...)")
    )

    return ThemeItemPresentation(
        name=theme.name,
        theme_type=theme.theme_type,
        category_display=category_display,
        icon_name=icon_name,
        path_display=str(theme.path),
        origin_display=origin_display,
        is_user_level=theme.is_user_level,
        is_invalid=is_invalid or theme.invalid,
        warning_message=warning_message,
    )


class ThemesPage:
    """Controller for Active Theme Card and Other Available Themes."""

    PAGE_ID: str = "themes"
    ICON_NAME: str = "applications-graphics-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize controller loading themes_page.ui template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Browse Themes")
        self.icon_name: str = self.ICON_NAME

        self.manager = manager

        self.active_category: ThemeType = ThemeType.GTK
        self._selected_theme: ThemeItemPresentation | None = None

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self._toggle_states: dict[ThemeType, bool] = {
            ThemeType.GTK: False,
            ThemeType.ICON: False,
            ThemeType.CURSOR: False,
            ThemeType.SHELL: False,
        }

        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.loading_spinner: Gtk.Spinner = self.builder.get_object("loading_spinner")
        self.category_title_label: Gtk.Label = self.builder.get_object("category_title_label")

        self.active_theme_group: Adw.PreferencesGroup = self.builder.get_object(
            "active_theme_group"
        )
        self.active_theme_row: Adw.ActionRow = self.builder.get_object("active_theme_row")
        self.active_theme_icon: Gtk.Image = self.builder.get_object("active_theme_icon")
        self.active_theme_badge: Gtk.Label = self.builder.get_object("active_theme_badge")

        self.available_section_title: Gtk.Label = self.builder.get_object("available_section_title")
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.system_themes_toggle: Gtk.CheckButton = self.builder.get_object("system_themes_toggle")
        self.themes_scrolled_window: Gtk.ScrolledWindow = self.builder.get_object(
            "themes_scrolled_window"
        )
        self.count_label: Gtk.Label = self.builder.get_object("count_label")
        self.themes_list_box: Gtk.ListBox = self.builder.get_object("themes_list_box")
        self.no_results_page: Adw.StatusPage = self.builder.get_object("no_results_page")

        self.selection_info_label: Gtk.Label = self.builder.get_object("selection_info_label")
        self.apply_button: Gtk.Button = self.builder.get_object("apply_button")

        self.empty_page: Adw.StatusPage = self.builder.get_object("empty_page")
        self.empty_refresh_button: Gtk.Button = self.builder.get_object("empty_refresh_button")
        self.error_page: Adw.StatusPage = self.builder.get_object("error_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        self._load_ui_prefs()

        self.search_entry.connect("search-changed", self._on_filter_criteria_changed)
        self.search_entry.connect("changed", self._on_filter_criteria_changed)
        self.system_themes_toggle.connect("toggled", self._on_filter_criteria_changed)

        self.themes_list_box.set_activate_on_single_click(False)
        self.themes_list_box.connect("row-selected", self._on_row_selected)
        self.themes_list_box.connect("row-activated", self._on_row_activated)

        self.apply_button.connect("clicked", lambda _: self.confirm_and_apply_selected())

        self.empty_refresh_button.connect("clicked", lambda _: self.refresh())
        self.error_retry_button.connect("clicked", lambda _: self.refresh())

        self._is_loading: bool = False
        self._generation_id: int = 0
        self.on_loading_changed: Callable[[bool], None] | None = None

        self._is_applying: bool = False
        self._apply_generation_id: int = 0
        self.on_theme_applied: Callable[[ThemeItemPresentation, ApplyResult], None] | None = None

        self._confirm_dialog_open: bool = False
        self._snapshot: ThemesSnapshot | None = None

        self._update_category_header()

    def get_widget(self) -> Gtk.Widget:
        """Return root widget for embedding into window Gtk.Stack."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indicate if scanning is running."""
        return self._is_loading

    @property
    def is_applying(self) -> bool:
        """Indicate if apply is running."""
        return self._is_applying

    @property
    def current_snapshot(self) -> ThemesSnapshot | None:
        """Return last loaded snapshot."""
        return self._snapshot

    @property
    def selected_theme(self) -> ThemeItemPresentation | None:
        """Return currently selected theme."""
        return self._selected_theme

    def set_category(self, category: ThemeType) -> None:
        """Set active category displayed in page."""
        self._clear_toast()
        self.active_category = category
        self.title = get_category_label(category)
        self._selected_theme = None
        self.apply_button.set_sensitive(False)
        self.selection_info_label.set_text(_("Select a theme from the list to apply it"))
        self._update_category_header()

        active_state = self._toggle_states.get(category, False)
        self._updating_toggle = True
        try:
            self.system_themes_toggle.set_active(active_state)
        finally:
            self._updating_toggle = False

        if self._snapshot is not None and self.widget.get_visible_child_name() == "ready":
            self._update_filtered_list()

    def _update_category_header(self) -> None:
        """Update category header title."""
        title_text = get_category_title(self.active_category)
        self.category_title_label.set_text(title_text)

    def refresh(self, sync: bool = False) -> None:
        """Scan and refresh installed themes from backend."""
        if (self._is_loading or self._is_applying) and not sync:
            logger.debug("Operation already running: refresh request ignored.")
            return

        self._is_loading = True
        self._generation_id += 1
        current_generation = self._generation_id

        if self.on_loading_changed:
            self.on_loading_changed(True)
        self.search_entry.set_sensitive(False)
        self.apply_button.set_sensitive(False)
        self.widget.set_visible_child_name("loading")

        def worker_fetch() -> tuple[ThemesSnapshot | None, Exception | None]:
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError(_("ThemeManager unavailable or not initialized."))

                themes_list = self.manager.list_themes(theme_type=None, user_only=False)
                presentation_items: list[ThemeItemPresentation] = []
                for t in themes_list:
                    val_res = self.manager.validator.validate(t.path, t.theme_type)
                    warn_str = (
                        "; ".join(_(w) for w in val_res.warnings) if val_res.warnings else None
                    )
                    presentation_items.append(
                        build_theme_presentation(
                            t,
                            is_invalid=not val_res.valid,
                            warning_message=warn_str,
                        )
                    )

                active_map: dict[ThemeType, str | None] = {}
                try:
                    current_set = self.manager.get_current_themes()
                    if isinstance(current_set, ThemeSet):
                        active_map = {
                            ThemeType.GTK: current_set.gtk_theme
                            if isinstance(current_set.gtk_theme, str)
                            else None,
                            ThemeType.ICON: current_set.icon_theme
                            if isinstance(current_set.icon_theme, str)
                            else None,
                            ThemeType.CURSOR: current_set.cursor_theme
                            if isinstance(current_set.cursor_theme, str)
                            else None,
                            ThemeType.SHELL: current_set.shell_theme
                            if isinstance(current_set.shell_theme, str)
                            else None,
                        }
                except (
                    GnomeThemeManagerError,
                    OSError,
                    PermissionError,
                    GLib.GError,
                    AttributeError,
                    TypeError,
                    ValueError,
                ) as err:
                    logger.warning("Unable to retrieve active themes: %s", err)

                snapshot = ThemesSnapshot(items=presentation_items, active_themes=active_map)
                return snapshot, None
            except (GnomeThemeManagerError, OSError, PermissionError, TimeoutError) as err:
                return None, err
            except Exception as err:
                return None, GnomeThemeManagerError(f"{_('Unexpected error during scan:')} {err}")

        def on_fetch_completed(result: tuple[ThemesSnapshot | None, Exception | None]) -> bool:
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

            self.search_entry.set_sensitive(True)

            snapshot, error = result

            if error is not None:
                logger.error("Error during themes scan: %s", error)
                self._handle_error(error)
            elif snapshot is not None and not snapshot.items:
                self._snapshot = snapshot
                self._update_filtered_list()
                self.widget.set_visible_child_name("empty")
            elif snapshot is not None:
                self._snapshot = snapshot
                self._update_filtered_list()
                self.widget.set_visible_child_name("ready")
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

    def _on_filter_criteria_changed(self, *args: Any) -> None:
        """Handle search text or toggle changes."""
        if getattr(self, "_updating_toggle", False):
            return
        self._clear_toast()
        self._save_ui_prefs()
        if self._snapshot is not None and self.widget.get_visible_child_name() == "ready":
            self._update_filtered_list()

    def _on_row_selected(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Handle row selection in available themes list."""
        self._clear_toast()
        if row is not None and hasattr(row, "_theme_item"):
            self._selected_theme = row._theme_item
            self.apply_button.set_sensitive(not self._is_applying and not self._is_loading)
            self.selection_info_label.set_text(f"{_('Selected:')} {self._selected_theme.name}")
        else:
            self._selected_theme = None
            self.apply_button.set_sensitive(False)
            self.selection_info_label.set_text(_("Select a theme from the list to apply it"))

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Handle row activation (double-click / Enter)."""
        if row is None or not hasattr(row, "_theme_item"):
            return
        if self._is_loading or self._is_applying or self._confirm_dialog_open:
            return

        item: ThemeItemPresentation = row._theme_item
        logger.debug("row-activated: %s", item.name)

        list_box.select_row(row)
        self._selected_theme = item
        self.apply_button.set_sensitive(True)
        self.selection_info_label.set_text(f"{_('Selected:')} {item.name}")

        self.confirm_and_apply_selected()

    def _update_filtered_list(self) -> None:
        """Update active theme card and filtered available themes list."""
        if self._snapshot is None:
            return

        target_category = self.active_category
        active_theme_raw = self._snapshot.active_themes.get(target_category)
        active_theme_name = active_theme_raw if isinstance(active_theme_raw, str) else None

        active_item: ThemeItemPresentation | None = None
        for item in self._snapshot.items:
            if item.theme_type == target_category and item.name == active_theme_name:
                active_item = item
                break

        icon_name = CATEGORY_ICONS.get(target_category, "preferences-desktop-theme-symbolic")
        self.active_theme_icon.set_from_icon_name(icon_name)

        if active_item is not None:
            self.active_theme_row.set_title(active_item.name)
            self.active_theme_row.set_subtitle(
                f"{active_item.origin_display}\n{active_item.path_display}"
            )
            self.active_theme_badge.set_text(_("In use"))
            self.active_theme_badge.set_visible(True)
        elif active_theme_name:
            self.active_theme_row.set_title(active_theme_name)
            self.active_theme_row.set_subtitle(_("Theme not found in local directories"))
            self.active_theme_badge.set_text(_("Not found"))
            self.active_theme_badge.set_visible(True)
        else:
            self.active_theme_row.set_title(_("Not available"))
            self.active_theme_row.set_subtitle(_("No settings detected or backend unavailable"))
            self.active_theme_badge.set_visible(False)

        query = self.search_entry.get_text().strip().lower()
        hide_system = self.system_themes_toggle.get_active()

        self._save_ui_prefs()

        filtered: list[ThemeItemPresentation] = []
        for item in self._snapshot.items:
            if item.theme_type != target_category:
                continue
            if active_theme_name is not None and item.name == active_theme_name:
                continue
            if hide_system and not item.is_user_level:
                continue
            if query and query not in item.name.lower():
                continue
            filtered.append(item)

        # Sorting: valid themes first (user before system, then alphabetical), incomplete/invalid themes at bottom
        filtered.sort(
            key=lambda it: (
                it.is_invalid,
                not it.is_user_level,
                it.name.casefold(),
                it.path_display,
            )
        )

        while child := self.themes_list_box.get_first_child():
            self.themes_list_box.remove(child)

        self._selected_theme = None
        self.apply_button.set_sensitive(False)
        self.selection_info_label.set_text(_("Select a theme from the list to apply it"))

        cat_label = get_category_label(target_category).lower()
        if not filtered:
            self.no_results_page.set_visible(True)
            self.themes_list_box.set_visible(False)
            if query:
                self.count_label.set_text(f"{_('No themes matching')} '{query}'")
            else:
                self.count_label.set_text(f"{_('No other alternative themes for')} {cat_label}")
        else:
            self.no_results_page.set_visible(False)
            self.themes_list_box.set_visible(True)
            self.count_label.set_text(f"{len(filtered)} {_('other')} {cat_label} {_('available')}")

            for item in filtered:
                row = Adw.ActionRow()
                row.set_title(item.name)

                if item.is_invalid:
                    subtitle_text = item.path_display
                    if item.warning_message:
                        subtitle_text += f"\n⚠️ {item.warning_message}"
                    else:
                        subtitle_text += (
                            f"\n⚠️ {_('Missing required stylesheet or files in folder.')}"
                        )
                    row.set_subtitle(subtitle_text)
                    row.set_subtitle_lines(2)
                    row.set_activatable(False)
                    row.set_sensitive(False)
                else:
                    row.set_subtitle(item.path_display)
                    row.set_subtitle_lines(1)
                    row.set_activatable(True)
                    row.set_sensitive(True)

                row._theme_item = item

                img = Gtk.Image.new_from_icon_name(item.icon_name)
                img.set_pixel_size(24)
                if item.is_invalid:
                    img.add_css_class("dim-label")
                row.add_prefix(img)

                if item.is_invalid:
                    warn_badge = Gtk.Label(label=_("Incomplete"))
                    warn_badge.add_css_class("caption")
                    warn_badge.add_css_class("warning")
                    warn_badge.set_valign(Gtk.Align.CENTER)
                    row.add_suffix(warn_badge)

                badge = Gtk.Label(label=_("User") if item.is_user_level else _("System"))
                badge.add_css_class("caption")
                badge.add_css_class("dim-label")
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)

                self.themes_list_box.append(row)

    def confirm_and_apply_selected(
        self, parent_window: Gtk.Window | None = None, sync: bool = False
    ) -> None:
        """Confirm and apply selected theme."""
        if self._selected_theme is None:
            logger.warning("Attempted to apply without active selection.")
            return
        if self._confirm_dialog_open:
            logger.debug("Confirmation dialog already open: request ignored.")
            return

        self.confirm_and_apply_theme(self._selected_theme, parent_window=parent_window, sync=sync)

    def confirm_and_apply_theme(
        self,
        item: ThemeItemPresentation,
        parent_window: Gtk.Window | None = None,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
    ) -> None:
        """Display explicit confirmation dialog before applying theme."""
        if self._confirm_dialog_open:
            logger.debug("Confirmation dialog already open for '%s': request ignored.", item.name)
            return

        win = parent_window or self.widget.get_root()

        # Structural integrity validation (Task 1.2 / 1.3)
        if self.manager is not None:
            found_theme = self.manager.scanner.find_theme(item.name, item.theme_type)
            if found_theme:
                val_res = self.manager.validator.validate(found_theme.path, item.theme_type)
                if not val_res.valid:
                    err_title = _("Incomplete Theme Warning")
                    err_body = (
                        f"{_('The theme')} «{item.name}» {_('has structural issues or missing files:')}\n\n"
                        + "\n".join(f"• {w}" for w in val_res.warnings)
                        + f"\n\n{_('Applying it might cause unexpected graphical glitches. Do you want to apply anyway?')}"
                    )
                    self._show_invalid_theme_dialog(
                        err_title,
                        err_body,
                        win,
                        item=item,
                        on_complete=on_complete,
                        sync=sync,
                    )
                    return

        needs_extension_check = item.theme_type == ThemeType.SHELL
        if self.manager is not None and needs_extension_check:
            is_enabled = self.manager.extensions.is_user_theme_enabled()
            if not is_enabled:
                self._open_enable_extension_dialog(item, win, on_complete, sync)
                return

        cat_name = get_dialog_category_name(item.theme_type)
        heading = f"{_('Apply')} “{item.name}” {_('to')} {cat_name}?"

        active_theme_raw = (
            self._snapshot.active_themes.get(item.theme_type) if self._snapshot else None
        )
        active_name = (
            active_theme_raw
            if isinstance(active_theme_raw, str) and active_theme_raw.strip()
            else None
        )

        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_size_request(500, -1)
        extra_box.set_margin_top(6)
        extra_box.set_margin_bottom(12)
        extra_box.set_margin_start(16)
        extra_box.set_margin_end(16)
        extra_box.set_halign(Gtk.Align.CENTER)

        lbl_cat = Gtk.Label(label=f"{_('Category:')} {cat_name}")
        lbl_cat.set_wrap(False)
        if hasattr(Pango, "EllipsizeMode"):
            lbl_cat.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_cat.set_halign(Gtk.Align.CENTER)
        extra_box.append(lbl_cat)

        if active_name:
            lbl_active = Gtk.Label(label=f"{_('Currently active theme:')} {active_name}")
            lbl_active.set_wrap(False)
            if hasattr(Pango, "EllipsizeMode"):
                lbl_active.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_active.add_css_class("dim-label")
            lbl_active.set_halign(Gtk.Align.CENTER)
            extra_box.append(lbl_active)

        # Visual preview grid for Icon packs (Task 1.4)
        if item.theme_type == ThemeType.ICON:
            t_path = Path(item.path_display) if item.path_display else None
            preview_widget = IconPackPreview(theme_name=item.name, theme_path=t_path, icon_size=36)
            preview_widget.set_margin_top(8)
            preview_widget.set_margin_bottom(4)
            extra_box.append(preview_widget)

        cross_checkbox = None
        if self.manager is not None:
            if item.theme_type == ThemeType.GTK:
                opposite_theme = self.manager.scanner.find_theme(item.name, ThemeType.SHELL)
                if opposite_theme:
                    val_res = self.manager.validator.validate(opposite_theme.path, ThemeType.SHELL)
                    if val_res.valid:
                        cross_checkbox = Gtk.CheckButton.new_with_label(
                            _("Also apply as GNOME Shell theme")
                        )
            elif item.theme_type == ThemeType.SHELL:
                opposite_theme = self.manager.scanner.find_theme(item.name, ThemeType.GTK)
                if opposite_theme:
                    val_res = self.manager.validator.validate(opposite_theme.path, ThemeType.GTK)
                    if val_res.valid:
                        cross_checkbox = Gtk.CheckButton.new_with_label(
                            _("Also apply as GTK theme")
                        )

        if cross_checkbox is not None:
            cross_checkbox.set_margin_top(8)
            cross_checkbox.set_halign(Gtk.Align.CENTER)
            extra_box.append(cross_checkbox)

        def execute_confirmed_apply() -> None:
            if cross_checkbox is not None and cross_checkbox.get_active():
                opposite_type = (
                    ThemeType.SHELL if item.theme_type == ThemeType.GTK else ThemeType.GTK
                )
                self.apply_theme(
                    item,
                    on_complete=lambda res, err: self._apply_opposite_after(
                        item.name, opposite_type, on_complete
                    ),
                    sync=sync,
                )
            else:
                self.apply_theme(item, on_complete=on_complete, sync=sync)

        if hasattr(Adw, "AlertDialog"):
            self._confirm_dialog_open = True
            dialog = Adw.AlertDialog.new(heading=heading, body="")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply", _("Apply"))
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
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

                    if resp == "apply":
                        execute_confirmed_apply()
                    elif on_complete:
                        on_complete(None, None)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(win if isinstance(win, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            self._confirm_dialog_open = True
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                heading,
                "",
            )
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply", _("Apply"))
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "apply":
                        execute_confirmed_apply()
                    elif on_complete:
                        on_complete(None, None)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()

        else:
            self._confirm_dialog_open = False
            execute_confirmed_apply()

    def _apply_opposite_after(
        self,
        theme_name: str,
        opposite_type: ThemeType,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
    ) -> None:
        """Apply second component sequentially in worker thread."""
        opposite_item = ThemeItemPresentation(
            name=theme_name,
            theme_type=opposite_type,
            category_display=get_category_label(opposite_type),
            icon_name=CATEGORY_ICONS.get(opposite_type, ""),
            path_display="",
            origin_display="",
            is_user_level=False,
        )

        self.apply_theme(opposite_item, on_complete=on_complete, sync=True)

    def _open_enable_extension_dialog(
        self,
        item: ThemeItemPresentation,
        parent_window: Gtk.Window | None = None,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
    ) -> None:
        """Open modal dialog proposing to enable GNOME Shell 'user-theme' extension."""
        win = parent_window or self.widget.get_root()
        title = _("User Themes Extension Disabled")
        body = _(
            "The 'User Themes' extension is required to apply custom themes to GNOME Shell. Do you want to enable it now?"
        )

        def handle_enable_and_continue() -> None:
            if self.manager is not None:
                success = self.manager.extensions.enable_user_theme()
                if success:
                    if self.manager.gsettings is not None:
                        try:
                            self.manager.gsettings.__init__(
                                schema_name=self.manager.gsettings.schema_name,
                                shell_schema_name=self.manager.gsettings.shell_schema_name,
                                custom_schema_dirs=self.manager.gsettings.custom_schema_dirs,
                            )
                        except Exception:
                            pass
                    self.confirm_and_apply_theme(
                        item, parent_window=parent_window, on_complete=on_complete, sync=sync
                    )
                else:
                    self._show_toast(_("Unable to enable 'User Themes' extension."))
                    if on_complete:
                        on_complete(
                            None,
                            GnomeThemeManagerError(_("User Themes extension unavailable.")),
                        )

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading=title, body=body)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("enable", _("Enable and Continue"))
            dialog.set_response_appearance("enable", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("enable")
            dialog.set_close_response("cancel")

            def on_dialog_response(d: Any, response_param: Any) -> None:
                resp = str(response_param)
                if resp == "enable":
                    handle_enable_and_continue()
                elif on_complete:
                    on_complete(None, None)

            dialog.connect("response", on_dialog_response)
            dialog.present(win if isinstance(win, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                title,
                body,
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("enable", _("Enable and Continue"))
            dialog.set_response_appearance("enable", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("enable")
            dialog.set_close_response("cancel")

            def on_msg_response(_d: Any, response_id: str) -> None:
                if response_id == "enable":
                    handle_enable_and_continue()
                elif on_complete:
                    on_complete(None, None)

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            handle_enable_and_continue()

    def _show_invalid_theme_dialog(
        self,
        title: str,
        body: str,
        win: Any,
        item: ThemeItemPresentation | None = None,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
    ) -> None:
        """Display a warning confirmation dialog offering 'Apply anyway' / 'Cancel' for invalid/incomplete themes."""
        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading=title, body=body)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply_anyway", _("Apply anyway"))
            dialog.set_response_appearance("apply_anyway", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_dialog_response(_d: Any, resp_param: Any) -> None:
                resp = str(resp_param)
                if resp == "apply_anyway" and item is not None:
                    self.apply_theme(item, on_complete=on_complete, sync=sync, force=True)
                elif on_complete:
                    on_complete(None, None)

            dialog.connect("response", on_dialog_response)
            dialog.present(win if isinstance(win, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                title,
                body,
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("apply_anyway", _("Apply anyway"))
            dialog.set_response_appearance("apply_anyway", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_msg_response(_d: Any, resp_id: str) -> None:
                if resp_id == "apply_anyway" and item is not None:
                    self.apply_theme(item, on_complete=on_complete, sync=sync, force=True)
                elif on_complete:
                    on_complete(None, None)

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            self._show_toast(f"{title}: {body}")
            if on_complete:
                on_complete(None, None)

    def apply_theme(
        self,
        item: ThemeItemPresentation,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
        force: bool = False,
    ) -> None:
        """Apply theme component through ThemeManager facade."""
        if self._is_applying:
            logger.warning("Theme application already in progress. Request discarded.")
            if on_complete:
                on_complete(None, GnomeThemeManagerError(_("Application already in progress.")))
            return

        self._is_applying = True
        self._apply_generation_id += 1
        current_apply_gen = self._apply_generation_id

        self._set_ui_applying_state(True)

        def worker_apply() -> tuple[ApplyResult | None, Exception | None]:
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError(_("ThemeManager unavailable or not initialized."))

                kwargs: dict[str, Any] = {
                    "component": item.theme_type,
                    "theme_name": item.name,
                    "apply_gtk4_override": True,
                    "propagate_sandbox": True,
                }
                if force:
                    kwargs["force"] = True

                result = self.manager.apply_component(**kwargs)
                return result, None
            except Exception as err:
                return None, err

        def on_apply_completed(result: tuple[ApplyResult | None, Exception | None]) -> bool:
            if current_apply_gen != self._apply_generation_id:
                logger.debug("Late application callback discarded.")
                return GLib.SOURCE_REMOVE

            self._is_applying = False
            self._set_ui_applying_state(False)

            apply_result, error = result

            if error is not None:
                logger.error("Error applying theme '%s': %s", item.name, error)
                self._show_toast(f"{_('Unable to apply theme')} «{item.name}»: {error}")
            elif apply_result is not None:
                if item.theme_type == ThemeType.SHELL and apply_result.shell_theme is None:
                    warning_text = f"{_('Theme')} «{item.name}» {_('partially applied.')}\n" + _(
                        "Shell not applied: 'User Themes' extension inactive or unsupported."
                    )
                    logger.warning(warning_text)
                    self._show_toast(warning_text)
                else:
                    new_active_map = dict(self._snapshot.active_themes) if self._snapshot else {}
                    new_active_map[item.theme_type] = item.name

                    current_items = list(self._snapshot.items) if self._snapshot else [item]
                    self._snapshot = ThemesSnapshot(
                        items=current_items, active_themes=new_active_map
                    )

                    if item.theme_type == ThemeType.CURSOR:
                        self._propagate_cursor_theme_in_process(item.name)

                    self._update_filtered_list()

                    if item.theme_type == ThemeType.CURSOR:
                        msg = f"{_('Cursor theme')} «{item.name}» {_('applied.')}\n" + _(
                            "You may need to switch windows or restart some applications."
                        )
                    elif item.theme_type == ThemeType.GTK:
                        if apply_result.gtk4_override_applied:
                            msg = f"{_('GTK theme')} «{item.name}» {_('applied (with GTK4/Libadwaita override).')}"
                        else:
                            msg = f"{_('GTK theme')} «{item.name}» {_('applied.')}"
                    elif item.theme_type == ThemeType.SHELL:
                        msg = f"{_('GNOME Shell theme')} «{item.name}» {_('applied.')}"
                    elif item.theme_type == ThemeType.ICON:
                        msg = f"{_('Icon theme')} «{item.name}» {_('applied.')}"
                    else:
                        cat_name = get_category_label(item.theme_type)
                        msg = f"{_('Theme')} {cat_name} «{item.name}» {_('applied.')}"

                    if apply_result.warnings:
                        msg += f"\n{_('Warnings:')} {'; '.join(apply_result.warnings)}"

                    logger.info("Theme '%s' applied: %s", item.name, msg)
                    self._show_toast(msg)

                    if self.on_theme_applied:
                        self.on_theme_applied(item, apply_result)

            if on_complete:
                on_complete(apply_result, error)

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_apply()
            on_apply_completed(res)
        else:

            def thread_target() -> None:
                res = worker_apply()
                GLib.idle_add(on_apply_completed, res)

            thread = threading.Thread(target=thread_target, daemon=True)
            thread.start()

    def _propagate_cursor_theme_in_process(self, cursor_theme_name: str) -> bool:
        """Propagate cursor theme immediately to application GTK display."""
        try:
            display = Gdk.Display.get_default() if hasattr(Gdk, "Display") else None
            if display is None:
                return False

            if hasattr(Gtk.Settings, "get_for_display"):
                gtk_settings = Gtk.Settings.get_for_display(display)
            elif hasattr(Gtk.Settings, "get_default"):
                gtk_settings = Gtk.Settings.get_default()
            else:
                gtk_settings = None

            if gtk_settings is not None and hasattr(gtk_settings, "set_property"):
                gtk_settings.set_property("gtk-cursor-theme-name", cursor_theme_name)
                logger.debug(
                    "Propagated gtk-cursor-theme-name='%s' to in-process GTK display.",
                    cursor_theme_name,
                )

            root = self.widget.get_root()
            if root is not None and hasattr(root, "set_cursor"):
                root.set_cursor(None)

            return True
        except (GLib.GError, AttributeError, TypeError, ValueError, RuntimeError) as err:
            logger.warning("Unable to update gtk-cursor-theme-name in-process: %s", err)
            return False

    def _show_cursor_info_alert(self, cursor_name: str) -> None:
        """Show informative dialog after applying cursor theme."""
        win = self.widget.get_root()
        heading = _("Cursor theme applied")
        body = (
            f"{_('The cursor theme')} «{cursor_name}» {_('was configured on the system.')}\n\n"
            + _(
                "The new cursor might not appear immediately across all windows.\n"
                "Switch windows or restart applications to see the change."
            )
        )

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

    def _build_theme_set_for_item(self, item: ThemeItemPresentation) -> ThemeSet:
        """Create ThemeSet instance configuring only specified component."""
        if item.theme_type == ThemeType.GTK:
            return ThemeSet(gtk_theme=item.name)
        elif item.theme_type == ThemeType.ICON:
            return ThemeSet(icon_theme=item.name)
        elif item.theme_type == ThemeType.CURSOR:
            return ThemeSet(cursor_theme=item.name)
        elif item.theme_type == ThemeType.SHELL:
            return ThemeSet(shell_theme=item.name)
        return ThemeSet()

    def _set_ui_applying_state(self, is_applying: bool) -> None:
        """Enable or disable controls during theme apply."""
        self.search_entry.set_sensitive(not is_applying)
        self.themes_list_box.set_sensitive(not is_applying)
        if self._selected_theme is not None:
            self.apply_button.set_sensitive(not is_applying)
        else:
            self.apply_button.set_sensitive(False)

    def _clear_toast(self) -> None:
        """Clear persistent top feedback."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "clear_feedback"):
            root.clear_feedback()

    def _show_toast(self, message: str) -> None:
        """Send feedback message to top notification area."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "add_toast"):
            root.add_toast(message)
        else:
            logger.info("Feedback [ThemesPage]: %s", message)

    def _load_ui_prefs(self) -> None:
        """Load UI preferences for current session."""
        active_state = self._toggle_states.get(self.active_category, False)
        self._updating_toggle = True
        try:
            self.system_themes_toggle.set_active(active_state)
        finally:
            self._updating_toggle = False

    def _save_ui_prefs(self) -> None:
        """Save UI preferences for current session."""
        self._toggle_states[self.active_category] = self.system_themes_toggle.get_active()

    def _handle_error(self, error: Exception) -> None:
        """Handle errors setting error view."""
        if isinstance(error, GnomeThemeManagerError):
            user_msg = str(error)
        elif isinstance(error, PermissionError):
            user_msg = _("Insufficient permissions to access some theme folders.")
        elif isinstance(error, OSError):
            user_msg = f"{_('Filesystem error:')} {error}"
        else:
            user_msg = f"{_('An error occurred during scan:')} {error}"

        self.error_page.set_description(user_msg)
        self.widget.set_visible_child_name("error")
