# SPDX-License-Identifier: GPL-3.0-or-later

"""Reusable custom icon picker widget for Global Themes.

Allows the user to select an icon from a rich categorized library of GNOME &
system icons (with real-time search), or clear the selection back to the default
icon.
"""

import logging
from collections.abc import Callable

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

logger = logging.getLogger("gnome_theme_manager.gui_gtk.widgets.icon_picker")

DEFAULT_ICON_NAME = "preferences-desktop-appearance-symbolic"

# Curated library of standard freedesktop / GNOME symbolic icons guaranteed across themes
CURATED_ICON_CATEGORIES: dict[str, list[str]] = {
    "Themes & Styling": [
        "preferences-desktop-appearance-symbolic",
        "preferences-color-symbolic",
        "preferences-desktop-wallpaper-symbolic",
        "color-select-symbolic",
        "display-symbolic",
        "night-light-symbolic",
        "weather-clear-symbolic",
        "weather-clear-night-symbolic",
        "format-text-bold-symbolic",
        "format-text-italic-symbolic",
    ],
    "Symbols & Badges": [
        "starred-symbolic",
        "emblem-favorite-symbolic",
        "emblem-important-symbolic",
        "emblem-ok-symbolic",
        "emblem-default-symbolic",
        "emblem-system-symbolic",
        "flag-symbolic",
        "bookmark-new-symbolic",
        "tag-symbolic",
        "security-high-symbolic",
    ],
    "Devices & Tech": [
        "computer-symbolic",
        "laptop-symbolic",
        "phone-symbolic",
        "drive-harddisk-symbolic",
        "audio-headphones-symbolic",
        "camera-photo-symbolic",
        "gamepad-symbolic",
        "utilities-terminal-symbolic",
        "system-run-symbolic",
        "network-wireless-symbolic",
    ],
    "Creative & Tools": [
        "applications-graphics-symbolic",
        "applications-multimedia-symbolic",
        "applications-engineering-symbolic",
        "applications-science-symbolic",
        "applications-utilities-symbolic",
        "view-grid-symbolic",
        "view-list-bullet-symbolic",
        "accessories-text-editor-symbolic",
        "folder-symbolic",
        "document-save-as-symbolic",
    ],
}


class _IconChooserDialog(Adw.Window):
    """Modal dialog presenting a searchable, categorized grid of system icons."""

    def __init__(
        self,
        parent: Gtk.Window | None,
        current_icon: str | None,
        on_selected: Callable[[str], None],
    ) -> None:
        super().__init__(
            title=_("Select Theme Icon"),
            modal=True,
            transient_for=parent,
            default_width=480,
            default_height=520,
        )
        self._on_selected = on_selected
        self._current_icon = current_icon or DEFAULT_ICON_NAME

        # Root content box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(box)

        # Header bar
        header = Adw.HeaderBar()
        box.append(header)

        # Search Bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.set_margin_start(16)
        search_box.set_margin_end(16)
        search_box.set_margin_top(8)
        search_box.set_margin_bottom(8)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_placeholder_text(_("Search icons…"))
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_box.append(self._search_entry)
        box.append(search_box)

        # Scrolled window with icons
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box.append(scroll)

        self._content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content_container.set_margin_start(16)
        self._content_container.set_margin_end(16)
        self._content_container.set_margin_top(8)
        self._content_container.set_margin_bottom(16)
        scroll.set_child(self._content_container)

        self._category_boxes: list[tuple[Gtk.Widget, list[tuple[Gtk.Button, str]]]] = []
        self._build_icon_library()

    def _build_icon_library(self) -> None:
        """Construct the category sections and icon buttons."""
        for cat_name, icon_names in CURATED_ICON_CATEGORIES.items():
            cat_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

            cat_title = Gtk.Label(label=_(cat_name))
            cat_title.add_css_class("heading")
            cat_title.set_xalign(0)
            cat_group.append(cat_title)

            flow = Gtk.FlowBox()
            flow.set_valign(Gtk.Align.START)
            flow.set_max_children_per_line(6)
            flow.set_min_children_per_line(4)
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_row_spacing(8)
            flow.set_column_spacing(8)
            cat_group.append(flow)

            btn_list: list[tuple[Gtk.Button, str]] = []
            for icon_name in icon_names:
                btn = Gtk.Button()
                btn.set_tooltip_text(icon_name)
                btn.add_css_class("flat")
                btn.set_size_request(56, 56)

                img = Gtk.Image.new_from_icon_name(icon_name)
                img.set_pixel_size(28)
                btn.set_child(img)

                if icon_name == self._current_icon:
                    btn.add_css_class("suggested-action")

                def _make_handler(name: str) -> Callable[[Gtk.Button], None]:
                    return lambda _b: self._on_icon_clicked(name)

                btn.connect("clicked", _make_handler(icon_name))
                flow.append(btn)
                btn_list.append((btn, icon_name))

            self._content_container.append(cat_group)
            self._category_boxes.append((cat_group, btn_list))

    def _on_icon_clicked(self, icon_name: str) -> None:
        """Handle user selection."""
        self._on_selected(icon_name)
        self.close()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filter visible icons based on user query."""
        query = entry.get_text().strip().lower()
        for cat_group, btn_list in self._category_boxes:
            visible_count = 0
            for btn, icon_name in btn_list:
                match = not query or (query in icon_name.lower())
                btn.set_visible(match)
                if match:
                    visible_count += 1
            cat_group.set_visible(visible_count > 0)


class IconPickerButton(Gtk.Box):
    """Sleek inline control to preview, select from icon library, and reset custom icon."""

    def __init__(self) -> None:
        """Initialize icon picker."""
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._icon_name: str | None = None

        # Main clickable button containing icon preview + label + chevron
        self._main_btn = Gtk.Button()
        self._main_btn.add_css_class("flat")
        self._main_btn.set_valign(Gtk.Align.CENTER)
        self._main_btn.set_tooltip_text(_("Select an icon from the library"))

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_start(4)
        btn_box.set_margin_end(4)

        self._preview_image = Gtk.Image.new_from_icon_name(DEFAULT_ICON_NAME)
        self._preview_image.set_pixel_size(22)
        btn_box.append(self._preview_image)

        self._label = Gtk.Label(label=_("Default Icon"))
        self._label.add_css_class("body")
        btn_box.append(self._label)

        chevron = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        chevron.set_pixel_size(14)
        chevron.add_css_class("dim-label")
        btn_box.append(chevron)

        self._main_btn.set_child(btn_box)
        self._main_btn.connect("clicked", self._on_main_btn_clicked)
        self.append(self._main_btn)

        # Clear / reset button (only visible when custom icon is selected)
        self._clear_btn = Gtk.Button()
        self._clear_btn.set_icon_name("edit-clear-symbolic")
        self._clear_btn.set_tooltip_text(_("Reset to default icon"))
        self._clear_btn.add_css_class("flat")
        self._clear_btn.set_valign(Gtk.Align.CENTER)
        self._clear_btn.set_visible(False)
        self._clear_btn.connect("clicked", self._on_clear_clicked)
        self.append(self._clear_btn)

    # -- Public API ---------------------------------------------------------
    def get_icon_path(self) -> str | None:
        """Return selected custom icon name/path or ``None`` for default."""
        return self._icon_name

    def set_icon_path(self, icon: str | None) -> None:
        """Set the current custom icon name (``None`` resets to default)."""
        self._icon_name = icon.strip() if icon and icon.strip() else None
        self._refresh_ui()

    # -- Internals ----------------------------------------------------------
    def _refresh_ui(self) -> None:
        """Update preview image, label, and clear button visibility."""
        if self._icon_name:
            self._preview_image.set_from_icon_name(self._icon_name)
            # Friendly label or truncated name
            clean_name = (
                self._icon_name.removesuffix("-symbolic").replace("-", " ").title()
            )
            self._label.set_text(clean_name)
            self._clear_btn.set_visible(True)
        else:
            self._preview_image.set_from_icon_name(DEFAULT_ICON_NAME)
            self._label.set_text(_("Default Icon"))
            self._clear_btn.set_visible(False)

    def _on_main_btn_clicked(self, _btn: Gtk.Button) -> None:
        """Open the icon chooser library dialog."""
        root = self.get_root()
        parent_window = root if isinstance(root, Gtk.Window) else None
        dialog = _IconChooserDialog(
            parent=parent_window,
            current_icon=self._icon_name,
            on_selected=self._on_icon_selected,
        )
        dialog.present()

    def _on_icon_selected(self, selected_icon: str) -> None:
        """Callback when an icon is chosen from the dialog."""
        self.set_icon_path(selected_icon)

    def _on_clear_clicked(self, _btn: Gtk.Button) -> None:
        """Reset custom icon to default."""
        self.set_icon_path(None)
