# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Theme Editor & Mixer' page (Task 2.3).

Allows mixing installed components (GTK, Shell, Icons, Cursors, Color Scheme),
customizing extracted theme colors with ColorPickerButtons, testing with live preview,
and saving compositions as user-composed Global Themes.
"""

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ...core.css_extractor import ExtractedColors, extract_theme_colors
from ...core.editor_draft import EditorDraft
from ...core.models import Theme, ThemeSet, ThemeType
from ...core.theme_editor import ThemeComposition
from ..widgets.color_picker import ColorPickerButton

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.editor_view")

UI_FILE = Path(__file__).parent.parent / "ui" / "editor_page.ui"


class ThemeEditorPage:
    """Page controller for Theme Editor and Component Mixer."""

    def __init__(self, manager: "ThemeManager") -> None:
        """Initialize ThemeEditorPage.

        Args:
            manager: ThemeManager facade instance.
        """
        self.manager = manager
        self.page_id = "editor"
        self.title = _("Theme Editor")

        self.on_loading_changed: Any | None = None
        self.on_notify_message: Any | None = None
        self.on_theme_saved: Any | None = None

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        # Root stack and states
        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        # Header controls
        self.theme_name_entry: Gtk.Entry = self.builder.get_object("theme_name_entry")
        self.save_button: Gtk.Button = self.builder.get_object("save_as_global_theme_button")
        self.preview_button: Gtk.Button = self.builder.get_object("preview_button")
        self.preview_banner: Adw.Banner | None = self.builder.get_object("preview_banner")
        if self.preview_banner:
            self.preview_banner.connect("button-clicked", self._on_stop_preview_clicked)

        self.draft_banner: Adw.Banner | None = self.builder.get_object("draft_banner")
        if self.draft_banner:
            self.draft_banner.connect("button-clicked", self._on_resume_draft_clicked)

        # Component dropdowns
        self.gtk_dropdown: Gtk.DropDown = self.builder.get_object("dropdown_gtk")
        self.shell_dropdown: Gtk.DropDown = self.builder.get_object("dropdown_shell")
        self.icon_dropdown: Gtk.DropDown = self.builder.get_object("dropdown_icon")
        self.cursor_dropdown: Gtk.DropDown = self.builder.get_object("dropdown_cursor")
        self.color_scheme_dropdown: Gtk.DropDown = self.builder.get_object("dropdown_color_scheme")

        # Color reset button
        self.reset_colors_button: Gtk.Button = self.builder.get_object("reset_colors_button")

        # Containers for ColorPickerButtons
        self.fg_color_container: Gtk.Box = self.builder.get_object("fg_color_container")
        self.bg_color_container: Gtk.Box = self.builder.get_object("bg_color_container")
        self.accent_color_container: Gtk.Box = self.builder.get_object("accent_color_container")
        self.accent_fg_color_container: Gtk.Box = self.builder.get_object(
            "accent_fg_color_container"
        )

        # Instantiate ColorPickerButtons
        self.fg_color_button = ColorPickerButton(_("Foreground Color"), "#ffffff")
        self.bg_color_button = ColorPickerButton(_("Background Color"), "#242424")
        self.accent_color_button = ColorPickerButton(_("Accent Color"), "#3584e4")
        self.accent_fg_color_button = ColorPickerButton(_("Accent Text Color"), "#ffffff")

        self.fg_color_container.append(self.fg_color_button)
        self.bg_color_container.append(self.bg_color_button)
        self.accent_color_container.append(self.accent_color_button)
        self.accent_fg_color_container.append(self.accent_fg_color_button)

        # Models for dropdowns
        self._gtk_model = Gtk.StringList()
        self._shell_model = Gtk.StringList()
        self._icon_model = Gtk.StringList()
        self._cursor_model = Gtk.StringList()
        self._color_scheme_model = Gtk.StringList()

        self.gtk_dropdown.set_model(self._gtk_model)
        self.shell_dropdown.set_model(self._shell_model)
        self.icon_dropdown.set_model(self._icon_model)
        self.cursor_dropdown.set_model(self._cursor_model)
        self.color_scheme_dropdown.set_model(self._color_scheme_model)

        self._color_schemes = ["default", "prefer-dark", "prefer-light"]
        for cs in self._color_schemes:
            self._color_scheme_model.append(cs)

        self._is_restoring_draft = False

        # Connect event handlers
        if self.theme_name_entry:
            self.theme_name_entry.connect("changed", self._on_user_edited)
        if self.save_button:
            self.save_button.connect("clicked", self._on_save_as_global_theme_clicked)
        if self.preview_button:
            self.preview_button.connect("clicked", self._on_preview_clicked)
        if self.reset_colors_button:
            self.reset_colors_button.connect("clicked", self._on_reset_colors_clicked)

        self.gtk_dropdown.connect("notify::selected-item", self._on_gtk_theme_changed)
        self.shell_dropdown.connect("notify::selected-item", self._on_component_changed_while_preview)
        self.icon_dropdown.connect("notify::selected-item", self._on_component_changed_while_preview)
        self.cursor_dropdown.connect("notify::selected-item", self._on_component_changed_while_preview)
        self.color_scheme_dropdown.connect(
            "notify::selected-item", self._on_component_changed_while_preview
        )

        self.fg_color_button.connect("color-changed", self._on_color_value_changed)
        self.bg_color_button.connect("color-changed", self._on_color_value_changed)
        self.accent_color_button.connect("color-changed", self._on_color_value_changed)
        self.accent_fg_color_button.connect("color-changed", self._on_color_value_changed)

        self._extracted_colors: ExtractedColors | None = None
        self._installed_gtk_themes: dict[str, Theme] = {}
        self._is_loading: bool = False
        self._is_loaded: bool = False

    @property
    def is_loading(self) -> bool:
        """Return True if refresh is in progress."""
        return self._is_loading

    @property
    def is_loaded(self) -> bool:
        """Return True if themes have been loaded at least once."""
        return self._is_loaded

    def get_widget(self) -> Gtk.Widget:
        """Return root GTK widget."""
        return self.widget

    def refresh(self, sync: bool = False) -> None:
        """Refresh installed theme components and active system defaults."""
        if self._is_loading and not sync:
            return

        self._set_loading(True)
        if sync:
            self._do_sync_refresh()
        else:
            threading.Thread(target=self._worker_refresh, daemon=True).start()

    def _do_sync_refresh(self) -> None:
        """Synchronously load themes (e.g. for testing)."""
        try:
            current_set, gtk_themes, shell_themes, icon_themes, cursor_themes = (
                self._fetch_theme_data()
            )
            self._apply_theme_data(
                current_set, gtk_themes, shell_themes, icon_themes, cursor_themes
            )
            self._is_loaded = True
        except Exception as err:
            logger.error("Error during sync refresh of Theme Editor: %s", err)
        finally:
            self._set_loading(False)

    def _fetch_theme_data(
        self,
    ) -> tuple[ThemeSet, list[Theme], list[Theme], list[Theme], list[Theme]]:
        """Fetch all theme data from manager without touching GTK widgets."""
        current_set = self.manager.get_current_themes()
        gtk_themes = self.manager.list_themes(ThemeType.GTK)
        shell_themes = self.manager.list_themes(ThemeType.SHELL)
        icon_themes = self.manager.list_themes(ThemeType.ICON)
        cursor_themes = self.manager.list_themes(ThemeType.CURSOR)
        return current_set, gtk_themes, shell_themes, icon_themes, cursor_themes

    def _worker_refresh(self) -> None:
        """Worker thread that only reads data and schedules UI update."""
        try:
            current_set, gtk_themes, shell_themes, icon_themes, cursor_themes = (
                self._fetch_theme_data()
            )

            def _on_main_thread() -> bool:
                try:
                    self._apply_theme_data(
                        current_set, gtk_themes, shell_themes, icon_themes, cursor_themes
                    )
                    self._is_loaded = True
                finally:
                    self._set_loading(False)
                return False

            GLib.idle_add(_on_main_thread)
        except Exception as err:
            logger.error("Worker error refreshing theme editor: %s", err)
            GLib.idle_add(self._set_loading, False)

    def _set_loading(self, is_loading: bool) -> None:
        """Update stack visible child to loading or ready."""
        self._is_loading = is_loading
        self.widget.set_visible_child_name("loading" if is_loading else "ready")
        if self.on_loading_changed:
            self.on_loading_changed(is_loading)

    def _populate_string_list(
        self, string_list: Gtk.StringList, items: list[str], selected: str | None
    ) -> int:
        """Populate a Gtk.StringList with items and return selected index."""
        # Clear existing items
        while string_list.get_n_items() > 0:
            string_list.remove(0)

        selected_idx = 0
        for idx, item in enumerate(items):
            string_list.append(item)
            if selected and item == selected:
                selected_idx = idx
        return selected_idx

    def _apply_theme_data(
        self,
        current_set: ThemeSet,
        gtk_themes: list[Theme],
        shell_themes: list[Theme],
        icon_themes: list[Theme],
        cursor_themes: list[Theme],
    ) -> None:
        """Apply fetched theme data to GTK widgets on the main GTK thread."""
        self._installed_gtk_themes = {t.name: t for t in gtk_themes}

        gtk_names = sorted(t.name for t in gtk_themes)
        shell_names = sorted(t.name for t in shell_themes)
        icon_names = sorted(t.name for t in icon_themes)
        cursor_names = sorted(t.name for t in cursor_themes)

        gtk_idx = self._populate_string_list(self._gtk_model, gtk_names, current_set.gtk_theme)
        self.gtk_dropdown.set_selected(gtk_idx)

        shell_idx = self._populate_string_list(
            self._shell_model, shell_names, current_set.shell_theme
        )
        self.shell_dropdown.set_selected(shell_idx)

        icon_idx = self._populate_string_list(
            self._icon_model, icon_names, current_set.icon_theme
        )
        self.icon_dropdown.set_selected(icon_idx)

        cursor_idx = self._populate_string_list(
            self._cursor_model, cursor_names, current_set.cursor_theme
        )
        self.cursor_dropdown.set_selected(cursor_idx)

        cs_val = current_set.color_scheme or "default"
        cs_idx = self._color_schemes.index(cs_val) if cs_val in self._color_schemes else 0
        self.color_scheme_dropdown.set_selected(cs_idx)

        self._update_colors_from_selected_gtk()
        self._check_for_saved_draft()

    def _check_for_saved_draft(self) -> None:
        """Reveal draft_banner if an unsaved draft exists in manager."""
        if (
            hasattr(self.manager, "editor_drafts")
            and self.manager.editor_drafts.has_draft()
            and self.draft_banner
        ):
            self.draft_banner.set_revealed(True)

    def _on_user_edited(self, *_: Any) -> None:
        """Auto-save current editor state to editor_draft.json on any user change."""
        if self._is_restoring_draft or self._is_loading:
            return
        self._save_current_draft()

    def _save_current_draft(self) -> None:
        """Serialize and write current editor state to manager.editor_drafts."""
        if not hasattr(self.manager, "editor_drafts"):
            return

        draft = EditorDraft(
            theme_name=self.theme_name_entry.get_text().strip(),
            gtk_theme=self._get_selected_string(self.gtk_dropdown),
            shell_theme=self._get_selected_string(self.shell_dropdown),
            icon_theme=self._get_selected_string(self.icon_dropdown),
            cursor_theme=self._get_selected_string(self.cursor_dropdown),
            color_scheme=self._get_selected_string(self.color_scheme_dropdown),
            colors=self._get_current_colors(),
        )
        self.manager.editor_drafts.save_draft(draft)

    def _on_resume_draft_clicked(self, _banner: Any) -> None:
        """Restore all controls from saved draft and hide banner."""
        if not hasattr(self.manager, "editor_drafts"):
            return

        draft = self.manager.editor_drafts.load_draft()
        if not draft:
            if self.draft_banner:
                self.draft_banner.set_revealed(False)
            return

        self._is_restoring_draft = True
        try:
            if draft.theme_name:
                self.theme_name_entry.set_text(draft.theme_name)

            if draft.gtk_theme:
                gtk_idx = self._find_model_index(self._gtk_model, draft.gtk_theme)
                if gtk_idx >= 0:
                    self.gtk_dropdown.set_selected(gtk_idx)

            if draft.shell_theme:
                shell_idx = self._find_model_index(self._shell_model, draft.shell_theme)
                if shell_idx >= 0:
                    self.shell_dropdown.set_selected(shell_idx)

            if draft.icon_theme:
                icon_idx = self._find_model_index(self._icon_model, draft.icon_theme)
                if icon_idx >= 0:
                    self.icon_dropdown.set_selected(icon_idx)

            if draft.cursor_theme:
                cursor_idx = self._find_model_index(self._cursor_model, draft.cursor_theme)
                if cursor_idx >= 0:
                    self.cursor_dropdown.set_selected(cursor_idx)

            if draft.color_scheme and draft.color_scheme in self._color_schemes:
                self.color_scheme_dropdown.set_selected(
                    self._color_schemes.index(draft.color_scheme)
                )

            if draft.colors:
                if "theme_fg_color" in draft.colors:
                    self.fg_color_button.set_color_hex(draft.colors["theme_fg_color"])
                if "theme_bg_color" in draft.colors:
                    self.bg_color_button.set_color_hex(draft.colors["theme_bg_color"])
                if "theme_selected_bg_color" in draft.colors:
                    self.accent_color_button.set_color_hex(draft.colors["theme_selected_bg_color"])
                if "theme_selected_fg_color" in draft.colors:
                    self.accent_fg_color_button.set_color_hex(
                        draft.colors["theme_selected_fg_color"]
                    )

            if self.draft_banner:
                self.draft_banner.set_revealed(False)
            if self.on_notify_message:
                self.on_notify_message(_("Draft resumed successfully."), False)
        finally:
            self._is_restoring_draft = False

    def _find_model_index(self, string_list: Gtk.StringList, target: str) -> int:
        """Find index of target item in Gtk.StringList."""
        for i in range(string_list.get_n_items()):
            if string_list.get_string(i) == target:
                return i
        return -1

    def _get_selected_string(self, dropdown: Gtk.DropDown) -> str | None:
        """Helper to get text of selected item in DropDown."""
        item = dropdown.get_selected_item()
        if item is not None and isinstance(item, Gtk.StringObject):
            return item.get_string()
        return None

    def _update_colors_from_selected_gtk(self) -> None:
        """Extract and populate colors from selected GTK theme."""
        gtk_name = self._get_selected_string(self.gtk_dropdown)
        if not gtk_name:
            return

        theme = self._installed_gtk_themes.get(gtk_name)
        theme_path = theme.path if theme else None

        if theme_path and theme_path.is_dir():
            extracted = extract_theme_colors(theme_path)
            self._extracted_colors = extracted
            self.fg_color_button.set_color_hex(extracted.theme_fg_color or "#ffffff")
            self.bg_color_button.set_color_hex(extracted.theme_bg_color or "#242424")
            self.accent_color_button.set_color_hex(
                extracted.theme_selected_bg_color or "#3584e4"
            )
            self.accent_fg_color_button.set_color_hex(
                extracted.theme_selected_fg_color or "#ffffff"
            )
        else:
            self.fg_color_button.set_color_hex("#ffffff")
            self.bg_color_button.set_color_hex("#242424")
            self.accent_color_button.set_color_hex("#3584e4")
            self.accent_fg_color_button.set_color_hex("#ffffff")

    def _on_gtk_theme_changed(self, _dropdown: Gtk.DropDown, _param: Any) -> None:
        """Handle GTK theme selection change by re-extracting colors and updating preview."""
        if not self._is_restoring_draft:
            self._update_colors_from_selected_gtk()
            self._update_live_preview_if_active()
            self._on_user_edited()

    def _on_component_changed_while_preview(self, _dropdown: Gtk.DropDown, _param: Any) -> None:
        """Update live preview dynamically when any component dropdown selection changes."""
        self._update_live_preview_if_active()
        self._on_user_edited()

    def _on_color_value_changed(self, _picker: Any, _color_hex: str) -> None:
        """Update live preview dynamically when color picker value changes."""
        self._update_live_preview_if_active()
        self._on_user_edited()

    def _update_live_preview_if_active(self) -> None:
        """If a live preview is currently active on the desktop, re-apply with new values."""
        if hasattr(self.manager, "theme_preview") and self.manager.theme_preview.is_preview_active:
            name = self.theme_name_entry.get_text().strip() or _("Custom Mix")
            try:
                effective_gtk, theme_path = self._get_or_create_fork_if_needed(name)
                if not effective_gtk:
                    effective_gtk = self._get_selected_string(self.gtk_dropdown)
                    theme = self._installed_gtk_themes.get(effective_gtk) if effective_gtk else None
                    theme_path = theme.path if theme else None

                shell_name = self._get_selected_string(self.shell_dropdown)
                icon_name = self._get_selected_string(self.icon_dropdown)
                cursor_name = self._get_selected_string(self.cursor_dropdown)
                color_scheme = self._get_selected_string(self.color_scheme_dropdown)

                theme_set = ThemeSet(
                    gtk_theme=effective_gtk,
                    icon_theme=icon_name,
                    cursor_theme=cursor_name,
                    shell_theme=shell_name,
                    color_scheme=color_scheme,
                )
                self.manager.theme_preview.start_preview(
                    theme_set=theme_set,
                    theme_path=theme_path,
                    force=True,
                )
            except Exception as err:
                logger.debug("Could not auto-update active live preview: %s", err)

    def _on_reset_colors_clicked(self, _btn: Gtk.Button | None) -> None:
        """Reset colors to extracted GTK theme defaults or standard fallback and update active preview."""
        gtk_name = self._get_selected_string(self.gtk_dropdown)
        theme = self._installed_gtk_themes.get(gtk_name) if gtk_name else None
        theme_path = theme.path if theme else None

        if theme_path and theme_path.is_dir():
            extracted = extract_theme_colors(theme_path)
            self._extracted_colors = extracted
            self.fg_color_button.set_color_hex(extracted.theme_fg_color or "#ffffff")
            self.bg_color_button.set_color_hex(extracted.theme_bg_color or "#242424")
            self.accent_color_button.set_color_hex(
                extracted.theme_selected_bg_color or "#3584e4"
            )
            self.accent_fg_color_button.set_color_hex(
                extracted.theme_selected_fg_color or "#ffffff"
            )
        else:
            self._extracted_colors = None
            self.fg_color_button.set_color_hex("#ffffff")
            self.bg_color_button.set_color_hex("#242424")
            self.accent_color_button.set_color_hex("#3584e4")
            self.accent_fg_color_button.set_color_hex("#ffffff")

        self._update_live_preview_if_active()

    def _get_current_colors(self) -> dict[str, str]:
        """Return dict of currently chosen colors from picker buttons."""
        return {
            "theme_fg_color": self.fg_color_button.get_color_hex(),
            "theme_bg_color": self.bg_color_button.get_color_hex(),
            "theme_selected_bg_color": self.accent_color_button.get_color_hex(),
            "theme_selected_fg_color": self.accent_fg_color_button.get_color_hex(),
            "accent_color": self.accent_color_button.get_color_hex(),
            "accent_bg_color": self.accent_color_button.get_color_hex(),
            "accent_fg_color": self.accent_fg_color_button.get_color_hex(),
        }

    def _get_customized_colors(self) -> dict[str, str]:
        """Return dict containing only the colors that the user actually modified."""
        current = self._get_current_colors()
        if not self._extracted_colors or self._extracted_colors.is_empty():
            return current

        customized: dict[str, str] = {}
        if (
            not self._extracted_colors.theme_fg_color
            or current["theme_fg_color"].lower()
            != self._extracted_colors.theme_fg_color.lower()
        ):
            customized["theme_fg_color"] = current["theme_fg_color"]
            customized["window_fg_color"] = current["theme_fg_color"]
            customized["view_fg_color"] = current["theme_fg_color"]
            customized["theme_text_color"] = current["theme_fg_color"]

        if (
            not self._extracted_colors.theme_bg_color
            or current["theme_bg_color"].lower()
            != self._extracted_colors.theme_bg_color.lower()
        ):
            customized["theme_bg_color"] = current["theme_bg_color"]
            customized["window_bg_color"] = current["theme_bg_color"]
            customized["view_bg_color"] = current["theme_bg_color"]
            customized["theme_base_color"] = current["theme_bg_color"]

        if (
            not self._extracted_colors.theme_selected_bg_color
            or current["theme_selected_bg_color"].lower()
            != self._extracted_colors.theme_selected_bg_color.lower()
        ):
            customized["theme_selected_bg_color"] = current["theme_selected_bg_color"]
            customized["accent_bg_color"] = current["theme_selected_bg_color"]
            customized["accent_color"] = current["theme_selected_bg_color"]

        if (
            not self._extracted_colors.theme_selected_fg_color
            or current["theme_selected_fg_color"].lower()
            != self._extracted_colors.theme_selected_fg_color.lower()
        ):
            customized["theme_selected_fg_color"] = current["theme_selected_fg_color"]
            customized["accent_fg_color"] = current["theme_selected_fg_color"]

        return customized

    def _are_colors_customized(self) -> bool:
        """Check if any color differs from extracted base theme values."""
        return bool(self._get_customized_colors())

    def _get_or_create_fork_if_needed(self, custom_name: str) -> tuple[str | None, Path | None]:
        """Create a persistent theme fork if colors were customized.

        Returns:
            Tuple of (effective_gtk_name, effective_theme_path).
        """
        base_gtk_name = self._get_selected_string(self.gtk_dropdown)
        if not base_gtk_name:
            return None, None

        base_theme = self._installed_gtk_themes.get(base_gtk_name)
        base_path = base_theme.path if base_theme else None

        colors = self._get_customized_colors()
        if not colors or not base_path or not base_path.is_dir():
            return base_gtk_name, base_path

        fork_name = f"{custom_name}"
        fork = self.manager.theme_forks.create_fork(
            base_theme_name=base_gtk_name,
            base_theme_path=base_path,
            custom_name=fork_name,
            colors=colors,
            overwrite=True,
        )
        return fork.fork_name, fork.fork_path

    def _get_current_composition(self) -> ThemeComposition:
        """Build ThemeComposition from current UI widget selections."""
        name = self.theme_name_entry.get_text().strip() or _("Custom Mix")
        fork_gtk, _fork_path = self._get_or_create_fork_if_needed(name)
        gtk_name = fork_gtk or self._get_selected_string(self.gtk_dropdown)

        shell_name = self._get_selected_string(self.shell_dropdown)
        icon_name = self._get_selected_string(self.icon_dropdown)
        cursor_name = self._get_selected_string(self.cursor_dropdown)
        color_scheme = self._get_selected_string(self.color_scheme_dropdown)

        return ThemeComposition(
            name=name,
            gtk3=gtk_name,
            gtk4=gtk_name,
            shell=shell_name,
            icon=icon_name,
            cursor=cursor_name,
            color_scheme=color_scheme,
            description=_("Composed in Theme Editor"),
            user_composed=True,
        )

    def _on_save_as_global_theme_clicked(self, _btn: Gtk.Button | None) -> None:
        """Save composition as Global Theme and clear draft."""
        try:
            composition = self._get_current_composition()
            saved = self.manager.save_theme_composition(composition, overwrite=True)
            if hasattr(self.manager, "editor_drafts"):
                self.manager.editor_drafts.clear_draft()
            if self.draft_banner:
                self.draft_banner.set_revealed(False)

            msg = _("Global Theme '{name}' saved successfully.").format(name=saved.name)
            if self.on_notify_message:
                self.on_notify_message(msg, False)
            if self.on_theme_saved:
                self.on_theme_saved(saved)
        except Exception as err:
            logger.error("Failed to save theme composition: %s", err)
            if self.on_notify_message:
                self.on_notify_message(str(err), True)

    def _on_preview_clicked(self, _btn: Gtk.Button | None) -> None:
        """Trigger in-app/system preview of the composed theme with customized colors."""
        if hasattr(self.manager, "theme_preview") and self.manager.theme_preview.is_preview_active:
            self._on_stop_preview_clicked(None)
            return

        name = self.theme_name_entry.get_text().strip() or _("Custom Mix")
        try:
            effective_gtk, theme_path = self._get_or_create_fork_if_needed(name)
            if not effective_gtk:
                effective_gtk = self._get_selected_string(self.gtk_dropdown)
                theme = self._installed_gtk_themes.get(effective_gtk) if effective_gtk else None
                theme_path = theme.path if theme else None

            shell_name = self._get_selected_string(self.shell_dropdown)
            icon_name = self._get_selected_string(self.icon_dropdown)
            cursor_name = self._get_selected_string(self.cursor_dropdown)
            color_scheme = self._get_selected_string(self.color_scheme_dropdown)

            theme_set = ThemeSet(
                gtk_theme=effective_gtk,
                icon_theme=icon_name,
                cursor_theme=cursor_name,
                shell_theme=shell_name,
                color_scheme=color_scheme,
            )

            if hasattr(self.manager, "theme_preview") and self.manager.theme_preview:
                self.manager.theme_preview.start_preview(
                    theme_set=theme_set,
                    theme_path=theme_path,
                    force=True,
                )
                if self.preview_banner:
                    self.preview_banner.set_revealed(True)
                if self.preview_button:
                    self.preview_button.set_label(_("Stop Preview"))
                    self.preview_button.add_css_class("destructive-action")

                msg = _("Preview started for '{name}'. Dismiss or commit to finalize.").format(
                    name=name
                )
                if self.on_notify_message:
                    self.on_notify_message(msg, False)
        except Exception as err:
            logger.error("Failed to start preview: %s", err)
            if self.on_notify_message:
                self.on_notify_message(str(err), True)

    def _on_stop_preview_clicked(self, _btn: Any) -> None:
        """Stop the active live preview and restore previous desktop themes."""
        if hasattr(self.manager, "theme_preview") and self.manager.theme_preview.is_preview_active:
            self.manager.theme_preview.cancel_preview()
            if self.preview_banner:
                self.preview_banner.set_revealed(False)
            if self.preview_button:
                self.preview_button.set_label(_("Preview"))
                self.preview_button.remove_css_class("destructive-action")
            if self.on_notify_message:
                self.on_notify_message(_("Live preview reverted to previous system themes."), False)
