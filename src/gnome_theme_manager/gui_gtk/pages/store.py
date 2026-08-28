# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Online Store' (Pling / OpenDesktop) page.

Provides search, category filtering, grid cards view, item detail inspection with screenshots,
and 1-click install & apply workflow with progress indicators.
"""

import html
import logging
import re
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ...core.models import Theme, ThemeType
from ...core.store_client import (
    StoreCategory,
    StoreClient,
    StoreItem,
)

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.store")

UI_FILE = Path(__file__).parent.parent / "ui" / "store_page.ui"
THUMBNAILS_CACHE_DIR = Path.home() / ".cache" / "gnome-theme-manager" / "store_thumbnails"


def _clean_html_description(raw_html: str) -> str:
    """Convert HTML description from store API into plain readable text."""
    if not raw_html:
        return ""
    text = re.sub(r"<\s*br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def _format_downloads(downloads: int) -> str:
    """Format download count compactly (e.g. 1.6M+, 450K+)."""
    if downloads >= 1_000_000:
        val = downloads / 1_000_000
        return f"{val:.1f}M+".replace(".0M+", "M+")
    if downloads >= 1_000:
        val = downloads / 1_000
        return f"{val:.0f}K+"
    return str(downloads)


def _create_badge_pill(label_text: str) -> Gtk.Box:
    """Helper to create a small pill tag widget."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    box.add_css_class("badge")
    box.add_css_class("caption")
    lbl = Gtk.Label(label=label_text)
    lbl.set_max_width_chars(12)
    lbl.set_ellipsize(Pango.EllipsizeMode.END)
    lbl.set_margin_start(8)
    lbl.set_margin_end(8)
    lbl.set_margin_top(2)
    lbl.set_margin_bottom(2)
    box.append(lbl)
    return box


class _StoreCardWidget(Gtk.Box):
    """Card widget displaying a single store item summary with rich banner in the search grid."""

    def __init__(
        self,
        item: StoreItem,
        on_view_details: Callable[[StoreItem], None],
        on_quick_install: Callable[[StoreItem], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.item = item
        self.on_view_details = on_view_details
        self.on_quick_install = on_quick_install

        self.add_css_class("store-theme-card")
        self.set_cursor_from_name("pointer")
        self.set_hexpand(True)
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # 1. Top Banner / Image Area with Gradient Backdrop
        banner_box = Gtk.Box()
        banner_box.add_css_class("store-banner-box")
        banner_box.set_size_request(-1, 150)
        banner_box.set_hexpand(True)

        self.banner_picture = Gtk.Picture()
        self.banner_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.banner_picture.set_can_shrink(True)
        self.banner_picture.set_hexpand(True)
        self.banner_picture.set_vexpand(True)
        banner_box.append(self.banner_picture)
        self.append(banner_box)

        # 2. Header Info: Title & Author
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)

        lbl_title = Gtk.Label(label=item.name)
        lbl_title.set_xalign(0)
        lbl_title.set_wrap(True)
        lbl_title.set_lines(1)
        lbl_title.set_max_width_chars(12)
        lbl_title.set_width_chars(8)
        lbl_title.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_title.add_css_class("heading")
        info_box.append(lbl_title)

        author_str = _("by {author}").format(author=item.author or _("Unknown"))
        lbl_author = Gtk.Label(label=author_str)
        lbl_author.set_xalign(0)
        lbl_author.set_wrap(True)
        lbl_author.set_lines(1)
        lbl_author.set_max_width_chars(12)
        lbl_author.set_width_chars(8)
        lbl_author.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_author.add_css_class("dim-label")
        lbl_author.add_css_class("caption")
        info_box.append(lbl_author)
        self.append(info_box)

        # 3. Summary / Description text (2 lines)
        desc_text = item.summary or item.description
        if desc_text:
            clean_summary = _clean_html_description(desc_text)
            lbl_summary = Gtk.Label(label=clean_summary)
            lbl_summary.set_xalign(0)
            lbl_summary.set_wrap(True)
            lbl_summary.set_lines(2)
            lbl_summary.set_max_width_chars(14)
            lbl_summary.set_width_chars(8)
            lbl_summary.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_summary.add_css_class("dim-label")
            self.append(lbl_summary)

        # 4. Badges & Stats row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        meta_box.set_valign(Gtk.Align.CENTER)
        if item.type_name:
            meta_box.append(_create_badge_pill(item.type_name))
        for tag in item.tags[:1]:
            meta_box.append(_create_badge_pill(tag))

        if item.rating > 0:
            lbl_rating = Gtk.Label(label=f"⭐ {item.rating}%")
            lbl_rating.add_css_class("caption")
            lbl_rating.add_css_class("dim-label")
            meta_box.append(lbl_rating)

        if item.downloads > 0:
            lbl_dl = Gtk.Label(label=f"⬇ {_format_downloads(item.downloads)}")
            lbl_dl.add_css_class("caption")
            lbl_dl.add_css_class("dim-label")
            meta_box.append(lbl_dl)

        self.append(meta_box)

        # 5. Actions row
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(4)

        self.btn_details = Gtk.Button(label=_("Details"))
        self.btn_details.add_css_class("flat")
        self.btn_details.set_hexpand(True)
        self.btn_details.connect("clicked", lambda _: self.on_view_details(self.item))
        btn_box.append(self.btn_details)

        self.btn_install = Gtk.Button(label=_("Install"))
        self.btn_install.add_css_class("suggested-action")
        self.btn_install.set_hexpand(True)
        if not self.item.is_installable:
            self.btn_install.set_sensitive(False)
            self.btn_install.set_tooltip_text(
                _("This item format is not supported for automatic GNOME installation.")
            )
        else:
            self.btn_install.connect("clicked", lambda _: self.on_quick_install(self.item))
        btn_box.append(self.btn_install)

        self.append(btn_box)

        # 6. Click gesture to open theme details from anywhere on the card (excluding Install button)
        card_gesture = Gtk.GestureClick.new()
        card_gesture.connect("released", self._on_card_clicked)
        self.add_controller(card_gesture)

        # Asynchronously fetch banner thumbnail if available
        preview_url = item.preview_image_url or (
            item.preview_images[0] if item.preview_images else ""
        )
        if preview_url:
            self._load_thumbnail_async(preview_url)

    def _on_card_clicked(
        self, _gesture: Gtk.GestureClick, _n_press: int, x: float, y: float
    ) -> None:
        """Open item details on card click, excluding direct clicks on the Install button."""
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is not None:
            curr: Gtk.Widget | None = picked
            while curr is not None and curr != self:
                if curr == self.btn_install:
                    return
                curr = curr.get_parent()
        self.on_view_details(self.item)

    def _load_thumbnail_async(self, img_url: str) -> None:
        """Download and cache card thumbnail in background."""

        def worker() -> None:
            try:
                THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                safe_name = (
                    re.sub(r"[^a-zA-Z0-9_\.-]", "_", img_url.split("/")[-1])
                    or f"thumb_{self.item.id}.png"
                )
                cached_path = THUMBNAILS_CACHE_DIR / safe_name

                if not cached_path.is_file() or cached_path.stat().st_size == 0:
                    import requests

                    res = requests.get(img_url, timeout=10)
                    if res.status_code == 200 and len(res.content) > 0:
                        cached_path.write_bytes(res.content)

                if cached_path.is_file() and cached_path.stat().st_size > 0:
                    GLib.idle_add(self._apply_thumbnail, str(cached_path))
            except Exception as err:
                logger.debug("Failed to load thumbnail for store item %s: %s", self.item.id, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_thumbnail(self, path: str) -> bool:
        try:
            self.banner_picture.set_filename(path)
        except Exception:
            pass
        return False


class StorePage:
    """Controller for the GTK4 / Libadwaita Online Store page."""

    PAGE_ID: str = "store"
    ICON_NAME: str = "software-store-symbolic"

    CATEGORIES_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "gtk_shell": (StoreCategory.GTK_SHELL.value, _("GTK3/4 & GNOME Shell Themes")),
        "icons": (StoreCategory.ICON.value, _("Full Icon Themes")),
        "cursors": (StoreCategory.CURSOR.value, _("Cursors")),
    }

    SORT_OPTIONS: ClassVar[list[tuple[str, str]]] = [
        (_("Latest"), "new"),
        (_("Rating"), "high"),
        (_("Downloads"), "down"),
    ]

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize StorePage from UI template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Online Store")
        self.icon_name: str = self.ICON_NAME
        self.manager: ThemeManager | None = manager
        self.store_client: StoreClient = (
            manager.store_client if manager is not None else StoreClient()
        )

        self.on_loading_changed: Callable[[bool], None] | None = None
        self.on_notify_message: Callable[[str, bool], None] | None = None

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        # Category Hub Cards
        self.category_card_gtk_shell: Gtk.Button = self.builder.get_object(
            "category_card_gtk_shell"
        )
        self.category_card_icons: Gtk.Button = self.builder.get_object("category_card_icons")
        self.category_card_cursors: Gtk.Button = self.builder.get_object("category_card_cursors")
        self.category_card_gtk_shell.set_cursor_from_name("pointer")
        self.category_card_icons.set_cursor_from_name("pointer")
        self.category_card_cursors.set_cursor_from_name("pointer")

        # Dedicated Category Browser Navigation & Controls
        self.scrolled_window: Gtk.ScrolledWindow = self.builder.get_object("scrolled_window")
        self.btn_back_to_categories: Gtk.Button = self.builder.get_object("btn_back_to_categories")
        self.category_title_label: Gtk.Label = self.builder.get_object("category_title_label")
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.sort_dropdown: Gtk.DropDown = self.builder.get_object("sort_dropdown")
        self.search_button: Gtk.Button = self.builder.get_object("search_button")
        self.content_stack: Gtk.Stack = self.builder.get_object("content_stack")
        self.cards_grid: Gtk.Grid = self.builder.get_object("cards_grid")
        self.results_count_label: Gtk.Label = self.builder.get_object("results_count_label")
        self.btn_prev_page: Gtk.Button = self.builder.get_object("btn_prev_page")
        self.lbl_page_indicator: Gtk.Label = self.builder.get_object("lbl_page_indicator")
        self.btn_next_page: Gtk.Button = self.builder.get_object("btn_next_page")
        self.empty_clear_button: Gtk.Button = self.builder.get_object("empty_clear_button")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        # Detail View Widgets
        self.detail_back_button: Gtk.Button = self.builder.get_object("detail_back_button")
        self.detail_icon_image: Gtk.Image = self.builder.get_object("detail_icon_image")
        self.detail_title_label: Gtk.Label = self.builder.get_object("detail_title_label")
        self.detail_author_label: Gtk.Label = self.builder.get_object("detail_author_label")
        self.detail_meta_pills_box: Gtk.Box = self.builder.get_object("detail_meta_pills_box")
        self.detail_screenshot_picture: Gtk.Picture = self.builder.get_object(
            "detail_screenshot_picture"
        )
        self.detail_prev_image_button: Gtk.Button = self.builder.get_object(
            "detail_prev_image_button"
        )
        self.detail_next_image_button: Gtk.Button = self.builder.get_object(
            "detail_next_image_button"
        )
        self.detail_image_counter_label: Gtk.Label = self.builder.get_object(
            "detail_image_counter_label"
        )
        self.detail_fullscreen_button: Gtk.Button = self.builder.get_object(
            "detail_fullscreen_button"
        )
        self.detail_thumbnails_scrolled: Gtk.ScrolledWindow = self.builder.get_object(
            "detail_thumbnails_scrolled"
        )
        self.detail_thumbnails_box: Gtk.Box = self.builder.get_object("detail_thumbnails_box")
        self.detail_description_label: Gtk.Label = self.builder.get_object(
            "detail_description_label"
        )
        self.detail_unsupported_banner: Adw.Banner = self.builder.get_object(
            "detail_unsupported_banner"
        )
        self.detail_file_dropdown: Gtk.DropDown = self.builder.get_object("detail_file_dropdown")
        self.detail_file_selector_box: Gtk.Box = self.builder.get_object("detail_file_selector_box")
        self.detail_install_button: Gtk.Button = self.builder.get_object("detail_install_button")
        self.detail_install_apply_button: Gtk.Button = self.builder.get_object(
            "detail_install_apply_button"
        )
        self.detail_progress_box: Gtk.Box = self.builder.get_object("detail_progress_box")
        self.detail_progress_bar: Gtk.ProgressBar = self.builder.get_object("detail_progress_bar")
        self.detail_progress_label: Gtk.Label = self.builder.get_object("detail_progress_label")

        # State tracking
        self._current_category_key: str = "gtk_shell"
        self._current_category_id: str = StoreCategory.GTK_SHELL.value
        self._current_page: int = 0
        self.PAGE_SIZE: int = 30
        self._current_items: list[StoreItem] = []
        self._selected_item: StoreItem | None = None
        self._is_searching: bool = False
        self._is_installing: bool = False
        self._detail_images: list[str] = []
        self._detail_image_index: int = 0
        self._thumbnail_buttons: list[Gtk.Button] = []
        self._active_cols: int = 3

        self._setup_dropdowns()
        self._connect_signals()
        self._show_state("categories")

    def get_widget(self) -> Gtk.Widget:
        """Return root widget container."""
        return self.widget

    def _setup_dropdowns(self) -> None:
        """Populate sort dropdown options."""
        sort_model = Gtk.StringList.new([name for name, _ in self.SORT_OPTIONS])
        self.sort_dropdown.set_model(sort_model)
        self.sort_dropdown.set_selected(0)

    def _connect_signals(self) -> None:
        """Bind signal callbacks."""
        self.category_card_gtk_shell.connect("clicked", lambda _: self._open_category("gtk_shell"))
        self.category_card_icons.connect("clicked", lambda _: self._open_category("icons"))
        self.category_card_cursors.connect("clicked", lambda _: self._open_category("cursors"))
        self.btn_back_to_categories.connect("clicked", lambda _: self._show_state("categories"))

        self.search_button.connect("clicked", lambda _: self.trigger_search(reset_page=True))
        self.search_entry.connect("activate", lambda _: self.trigger_search(reset_page=True))
        self.sort_dropdown.connect(
            "notify::selected", lambda *_: self.trigger_search(reset_page=True)
        )
        self.btn_prev_page.connect("clicked", lambda _: self._navigate_page(-1))
        self.btn_next_page.connect("clicked", lambda _: self._navigate_page(1))
        self.empty_clear_button.connect("clicked", lambda _: self._on_clear_search_clicked())
        self.error_retry_button.connect("clicked", lambda _: self.trigger_search(reset_page=False))

        self.cards_grid.connect("notify::width", self._on_grid_width_changed)

        self.detail_back_button.connect("clicked", lambda _: self._show_state("browse"))
        self.detail_prev_image_button.connect("clicked", lambda _: self._navigate_image(-1))
        self.detail_next_image_button.connect("clicked", lambda _: self._navigate_image(1))
        self.detail_fullscreen_button.connect("clicked", lambda _: self._open_fullscreen_dialog())

        # Click on screenshot opens fullscreen dialog
        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", lambda *_: self._open_fullscreen_dialog())
        self.detail_screenshot_picture.add_controller(click_gesture)

        self.detail_install_button.connect(
            "clicked", lambda _: self._on_install_clicked(apply_after=False)
        )
        self.detail_install_apply_button.connect(
            "clicked", lambda _: self._on_install_clicked(apply_after=True)
        )

    def _open_category(self, cat_key: str) -> None:
        """Open dedicated browse view for selected category and load themes."""
        self._current_category_key = cat_key
        cat_id, cat_title = self.CATEGORIES_MAP.get(
            cat_key, (StoreCategory.GTK_SHELL.value, _("GTK3/4 & GNOME Shell Themes"))
        )
        self._current_category_id = cat_id
        self._current_page = 0
        self.category_title_label.set_text(cat_title)
        self.search_entry.set_text("")
        self._show_state("browse")
        self.trigger_search(reset_page=True)

    def _navigate_page(self, delta: int) -> None:
        """Navigate to previous or next page in store results."""
        new_page = max(0, self._current_page + delta)
        if new_page != self._current_page:
            self._current_page = new_page
            vadj = self.scrolled_window.get_vadjustment()
            if vadj is not None:
                vadj.set_value(0)
            self.trigger_search(reset_page=False)

    def trigger_search(self, reset_page: bool = True) -> None:
        """Initiate asynchronous store search based on active filters."""
        if self._is_searching:
            return

        if reset_page:
            self._current_page = 0

        self._is_searching = True
        self._show_state("loading")
        if self.on_loading_changed:
            self.on_loading_changed(True)

        query = self.search_entry.get_text().strip()
        category = self._current_category_id
        page_num = self._current_page

        sort_idx = self.sort_dropdown.get_selected()
        sort_by = (
            self.SORT_OPTIONS[sort_idx][1] if 0 <= sort_idx < len(self.SORT_OPTIONS) else "new"
        )

        def worker() -> None:
            items: list[StoreItem] = []
            err_msg: str | None = None
            try:
                items = self.store_client.search(
                    query=query,
                    category=category,
                    sort=sort_by,
                    page=page_num,
                    page_size=self.PAGE_SIZE,
                )
            except Exception as err:
                logger.error("Store search error: %s", err)
                err_msg = str(err)
            finally:
                GLib.idle_add(self._display_results, items, err_msg)

        threading.Thread(target=worker, daemon=True).start()

    def _display_results(
        self, items: list[StoreItem], error: str | Exception | None = None
    ) -> bool:
        """Update ready state cards container with search results."""
        return self._on_search_completed(items, error)

    def _on_search_completed(
        self, items: list[StoreItem], error: str | Exception | None = None
    ) -> bool:
        """Handle search completion on the main GTK loop."""
        self._is_searching = False
        if self.on_loading_changed:
            self.on_loading_changed(False)

        if error is not None:
            logger.warning("Store search failed: %s", error)
            self._show_state("error")
            return False

        self._current_items = items

        if not items:
            while child := self.cards_grid.get_first_child():
                self.cards_grid.remove(child)
            self._show_state("empty")
            self.results_count_label.set_text(_("No items found."))
            return False

        count_text = _("{count} items found").format(count=len(items))
        self.results_count_label.set_text(count_text)

        self.lbl_page_indicator.set_text(_("Page {page}").format(page=self._current_page + 1))
        self.btn_prev_page.set_sensitive(self._current_page > 0)
        self.btn_next_page.set_sensitive(len(items) >= self.PAGE_SIZE)

        self._populate_grid_cards(items)
        self._show_state("ready")
        return False

    def _populate_grid_cards(self, items: list[StoreItem]) -> None:
        """Render store cards into the multi-column GtkGrid taking sidebar into account."""
        self._is_populating = True
        try:
            while child := self.cards_grid.get_first_child():
                self.cards_grid.remove(child)

            if not items:
                return

            grid_width = self.cards_grid.get_width()
            if grid_width <= 0:
                root = self.widget.get_root()
                win_width = root.get_width() if isinstance(root, Gtk.Window) else 1000
                # Account for sidebar ~240px and margins
                grid_width = max(300, win_width - 280)

            if grid_width >= 860:
                cols = 4
            elif grid_width >= 520:
                cols = 3
            else:
                cols = 2

            self._active_cols = cols

            for idx, item in enumerate(items):
                card = _StoreCardWidget(
                    item=item,
                    on_view_details=self.show_item_details,
                    on_quick_install=self._on_quick_install_item,
                )
                row = idx // cols
                col = idx % cols
                self.cards_grid.attach(card, col, row, 1, 1)
        finally:
            self._is_populating = False

    def _on_grid_width_changed(self, *_args: object) -> None:
        """Handle window width resize considering sidebar width."""
        if (
            getattr(self, "_is_populating", False)
            or not self._current_items
            or self.widget.get_visible_child_name() != "browse"
        ):
            return
        grid_width = self.cards_grid.get_width()
        if grid_width <= 0:
            return
        if grid_width >= 860:
            target_cols = 4
        elif grid_width >= 520:
            target_cols = 3
        else:
            target_cols = 2

        if target_cols != getattr(self, "_active_cols", 0):
            self._populate_grid_cards(self._current_items)

    def show_item_details(self, item: StoreItem) -> None:
        """Switch to detailed item view, fetch complete metadata and screenshots."""
        self._selected_item = item
        self._show_state("loading")

        def worker() -> None:
            try:
                detailed_item = self.store_client.get_details(item.id)
                GLib.idle_add(self._populate_detail_view, detailed_item)
            except Exception as err:
                logger.warning("Failed to fetch full details for item %s: %s", item.id, err)
                # Fall back to basic item metadata
                GLib.idle_add(self._populate_detail_view, item)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_detail_view(self, item: StoreItem) -> bool:
        """Render details view with item fields."""
        self._selected_item = item
        self.detail_title_label.set_text(item.name)
        author_str = _("by {author} • Version {ver}").format(
            author=item.author or _("Unknown"),
            ver=item.version or "1.0",
        )
        self.detail_author_label.set_text(author_str)

        # Clear and repopulate meta pills
        while child := self.detail_meta_pills_box.get_first_child():
            self.detail_meta_pills_box.remove(child)

        if item.type_name:
            self.detail_meta_pills_box.append(_create_badge_pill(item.type_name))
        if item.rating > 0:
            self.detail_meta_pills_box.append(_create_badge_pill(f"★ {item.rating}%"))
        if item.downloads > 0:
            self.detail_meta_pills_box.append(_create_badge_pill(f"⬇ {item.downloads}"))
        if item.updated or item.created:
            date_str = (item.updated or item.created).split("T")[0]
            self.detail_meta_pills_box.append(_create_badge_pill(date_str))

        # Description
        clean_desc = _clean_html_description(item.description or item.summary)
        self.detail_description_label.set_text(clean_desc or _("No description provided."))

        # Populate file variants
        if item.files:
            file_names = [f"{f.name} ({f.size_str})" if f.size_str else f.name for f in item.files]
            file_model = Gtk.StringList.new(file_names)
            self.detail_file_dropdown.set_model(file_model)
            self.detail_file_dropdown.set_selected(0)
            self.detail_file_selector_box.set_visible(len(item.files) > 1)
        else:
            self.detail_file_dropdown.set_model(Gtk.StringList.new([_("Default Package")]))
            self.detail_file_selector_box.set_visible(False)

        # Reset Progress bar & check installable state
        self.detail_progress_box.set_visible(False)
        self.detail_progress_bar.set_fraction(0.0)

        is_inst = item.is_installable
        self.detail_unsupported_banner.set_revealed(not is_inst)
        self.detail_install_button.set_sensitive(is_inst)
        self.detail_install_apply_button.set_sensitive(is_inst)
        if not is_inst:
            self.detail_install_button.set_tooltip_text(
                _("This item format is not supported for automatic GNOME installation.")
            )
            self.detail_install_apply_button.set_tooltip_text(
                _("This item format is not supported for automatic GNOME installation.")
            )
        else:
            self.detail_install_button.set_tooltip_text("")
            self.detail_install_apply_button.set_tooltip_text("")

        # Clear and setup Gallery & Screenshots
        while child := self.detail_thumbnails_box.get_first_child():
            self.detail_thumbnails_box.remove(child)
        self._thumbnail_buttons.clear()

        images: list[str] = []
        if item.preview_images:
            images = list(item.preview_images)
        elif item.preview_image_url:
            images = [item.preview_image_url]

        self._detail_images = images
        self._detail_image_index = 0

        has_multiple = len(images) > 1
        self.detail_prev_image_button.set_visible(has_multiple)
        self.detail_next_image_button.set_visible(has_multiple)
        self.detail_thumbnails_scrolled.set_visible(has_multiple)
        self.detail_image_counter_label.set_visible(has_multiple)

        if has_multiple:
            for idx, img_url in enumerate(images):
                btn = Gtk.Button()
                btn.add_css_class("flat")
                btn.add_css_class("store-thumb-btn")
                btn_pic = Gtk.Picture()
                btn_pic.set_can_shrink(True)
                btn_pic.set_content_fit(Gtk.ContentFit.COVER)
                btn_pic.set_size_request(72, 48)
                btn.set_child(btn_pic)
                btn.connect("clicked", lambda _, i=idx: self._set_active_screenshot_index(i))
                self.detail_thumbnails_box.append(btn)
                self._thumbnail_buttons.append(btn)
                self._load_gallery_thumbnail_async(btn_pic, img_url)

        if images:
            self._set_active_screenshot_index(0)

        self._show_state("detail")
        return False

    def _navigate_image(self, delta: int) -> None:
        """Navigate to previous or next screenshot."""
        if not self._detail_images:
            return
        new_idx = (self._detail_image_index + delta) % len(self._detail_images)
        self._set_active_screenshot_index(new_idx)

    def _set_active_screenshot_index(self, index: int) -> None:
        """Switch active displayed screenshot and highlight active thumbnail."""
        if not self._detail_images or index < 0 or index >= len(self._detail_images):
            return

        self._detail_image_index = index

        if len(self._detail_images) > 1:
            counter_str = _("Image {cur} of {tot}").format(
                cur=index + 1, tot=len(self._detail_images)
            )
            self.detail_image_counter_label.set_text(counter_str)

            for i, btn in enumerate(self._thumbnail_buttons):
                if i == index:
                    btn.add_css_class("suggested-action")
                else:
                    btn.remove_css_class("suggested-action")

        self._load_screenshot_async(self._detail_images[index])

    def _load_gallery_thumbnail_async(self, pic_widget: Gtk.Picture, img_url: str) -> None:
        """Download thumbnail in background and set on Gtk.Picture widget."""

        def worker() -> None:
            try:
                THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                safe_name = "gthumb_" + re.sub(r"[^a-zA-Z0-9_\.-]", "_", img_url.split("/")[-1])
                cached_path = THUMBNAILS_CACHE_DIR / safe_name

                if not cached_path.is_file() or cached_path.stat().st_size == 0:
                    import requests

                    res = requests.get(img_url, timeout=15)
                    if res.status_code == 200 and len(res.content) > 0:
                        cached_path.write_bytes(res.content)

                if cached_path.is_file() and cached_path.stat().st_size > 0:
                    GLib.idle_add(pic_widget.set_filename, str(cached_path))
            except Exception as err:
                logger.debug("Failed to load gallery thumbnail preview: %s", err)

        threading.Thread(target=worker, daemon=True).start()

    def _load_screenshot_async(self, img_url: str) -> None:
        """Download screenshot in background for detail view."""

        def worker() -> None:
            try:
                THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                safe_name = (
                    re.sub(r"[^a-zA-Z0-9_\.-]", "_", img_url.split("/")[-1])
                    or f"shot_{self._selected_item.id if self._selected_item else 'item'}.png"
                )
                cached_path = THUMBNAILS_CACHE_DIR / safe_name

                if not cached_path.is_file() or cached_path.stat().st_size == 0:
                    import requests

                    res = requests.get(img_url, timeout=15)
                    if res.status_code == 200 and len(res.content) > 0:
                        cached_path.write_bytes(res.content)

                if cached_path.is_file() and cached_path.stat().st_size > 0:
                    GLib.idle_add(self.detail_screenshot_picture.set_filename, str(cached_path))
            except Exception as err:
                logger.debug("Failed to load screenshot preview: %s", err)

        threading.Thread(target=worker, daemon=True).start()

    def _open_fullscreen_dialog(self) -> None:
        """Open modal fullscreen lightbox for screenshot inspection."""
        if not self._detail_images:
            return

        dialog = Gtk.Window()
        dialog.set_modal(True)
        root_win = self.widget.get_root()
        if isinstance(root_win, Gtk.Window):
            dialog.set_transient_for(root_win)

        title = self._selected_item.name if self._selected_item else _("Screenshot")
        dialog.set_title(title)
        dialog.set_default_size(1100, 750)

        # Header Bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title=title, subtitle="")
        header.set_title_widget(title_widget)

        # Prev / Next in Header
        btn_prev = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        btn_prev.set_tooltip_text(_("Previous Screenshot"))
        btn_prev.add_css_class("flat")
        btn_next = Gtk.Button.new_from_icon_name("go-next-symbolic")
        btn_next.set_tooltip_text(_("Next Screenshot"))
        btn_next.add_css_class("flat")

        header.pack_start(btn_prev)
        header.pack_start(btn_next)

        # Fullscreen toggle button
        btn_fullscreen = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        btn_fullscreen.set_tooltip_text(_("Toggle Fullscreen"))
        btn_fullscreen.add_css_class("flat")
        header.pack_end(btn_fullscreen)

        # Content Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.append(header)

        # Black backdrop for image viewer
        img_container = Gtk.Box()
        img_container.set_hexpand(True)
        img_container.set_vexpand(True)
        img_container.add_css_class("store-lightbox-bg")

        picture = Gtk.Picture()
        picture.set_can_shrink(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        img_container.append(picture)
        main_box.append(img_container)

        dialog.set_child(main_box)

        # State tracking for dialog
        current_idx = [self._detail_image_index]
        is_fs = [False]

        def update_image(idx: int) -> None:
            if not self._detail_images:
                return
            current_idx[0] = idx % len(self._detail_images)
            url = self._detail_images[current_idx[0]]
            counter = _("Image {cur} of {tot}").format(
                cur=current_idx[0] + 1, tot=len(self._detail_images)
            )
            title_widget.set_subtitle(counter)
            self._set_active_screenshot_index(current_idx[0])

            safe_name = (
                re.sub(r"[^a-zA-Z0-9_\.-]", "_", url.split("/")[-1])
                or f"shot_{self._selected_item.id if self._selected_item else 'item'}.png"
            )
            cached_path = THUMBNAILS_CACHE_DIR / safe_name
            if cached_path.is_file() and cached_path.stat().st_size > 0:
                picture.set_filename(str(cached_path))
            else:
                self._load_screenshot_async(url)
                if cached_path.is_file():
                    picture.set_filename(str(cached_path))

        def on_prev(_: Gtk.Button) -> None:
            update_image(current_idx[0] - 1)

        def on_next(_: Gtk.Button) -> None:
            update_image(current_idx[0] + 1)

        def toggle_fullscreen(_: Gtk.Button) -> None:
            if is_fs[0]:
                dialog.unfullscreen()
                is_fs[0] = False
                btn_fullscreen.set_icon_name("view-fullscreen-symbolic")
            else:
                dialog.fullscreen()
                is_fs[0] = True
                btn_fullscreen.set_icon_name("view-restore-symbolic")

        btn_prev.connect("clicked", on_prev)
        btn_next.connect("clicked", on_next)
        btn_fullscreen.connect("clicked", toggle_fullscreen)

        # Keyboard shortcuts
        key_controller = Gtk.EventControllerKey()

        def on_key_pressed(
            _ctrl: Gtk.EventControllerKey,
            keyval: int,
            _keycode: int,
            _state: Gdk.ModifierType,
        ) -> bool:
            if keyval == Gdk.KEY_Left:
                on_prev(btn_prev)
                return True
            elif keyval == Gdk.KEY_Right:
                on_next(btn_next)
                return True
            elif keyval == Gdk.KEY_F11:
                toggle_fullscreen(btn_fullscreen)
                return True
            elif keyval == Gdk.KEY_Escape:
                if is_fs[0]:
                    toggle_fullscreen(btn_fullscreen)
                else:
                    dialog.close()
                return True
            return False

        key_controller.connect("key-pressed", on_key_pressed)
        dialog.add_controller(key_controller)

        has_multiple = len(self._detail_images) > 1
        btn_prev.set_visible(has_multiple)
        btn_next.set_visible(has_multiple)

        update_image(self._detail_image_index)
        dialog.present()

    def _on_quick_install_item(self, item: StoreItem) -> None:
        """Quick install triggered directly from card."""
        if not item.is_installable:
            if self.on_notify_message:
                self.on_notify_message(
                    _(
                        "'{name}' is not a supported GNOME theme format and cannot be installed."
                    ).format(name=item.name),
                    True,
                )
            return
        self.show_item_details(item)
        self._on_install_clicked(apply_after=False)

    def _on_install_clicked(self, apply_after: bool = False) -> None:
        """Execute package download and installation in background worker thread."""
        if not self._selected_item or self._is_installing:
            return
        if not self._selected_item.is_installable:
            if self.on_notify_message:
                self.on_notify_message(
                    _(
                        "'{name}' is not a supported GNOME theme format and cannot be installed."
                    ).format(name=self._selected_item.name),
                    True,
                )
            return

        self._is_installing = True
        self.detail_install_button.set_sensitive(False)
        self.detail_install_apply_button.set_sensitive(False)
        self.detail_progress_box.set_visible(True)
        self.detail_progress_bar.set_fraction(0.0)
        self.detail_progress_label.set_text(_("Connecting and downloading..."))

        item = self._selected_item
        selected_file_index = 1
        if item.files:
            idx = self.detail_file_dropdown.get_selected()
            if 0 <= idx < len(item.files):
                selected_file_index = item.files[idx].file_index

        last_update_time = 0.0

        def progress_cb(downloaded: int, total: int | None) -> None:
            nonlocal last_update_time
            now = time.monotonic()
            # Throttle UI dispatch to at most once per 100ms or when complete
            if not (total and downloaded >= total) and (now - last_update_time < 0.1):
                return
            last_update_time = now

            if total and total > 0:
                frac = min(1.0, downloaded / total)
                mb_dl = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                text = _("Downloading: {dl:.1f} MB / {tot:.1f} MB ({pct:.0f}%)").format(
                    dl=mb_dl, tot=mb_tot, pct=frac * 100
                )
            else:
                frac = 0.5
                text = _("Downloading: {dl:.1f} MB").format(dl=downloaded / (1024 * 1024))

            GLib.idle_add(self._update_progress_ui, frac, text)

        def worker() -> None:
            try:
                with tempfile.TemporaryDirectory() as tmp_dir_str:
                    tmp_dir = Path(tmp_dir_str)
                    downloaded_path = self.store_client.download(
                        item_id=item.id,
                        dest_dir=tmp_dir,
                        file_index=selected_file_index,
                        progress_callback=progress_cb,
                    )

                    GLib.idle_add(
                        self._update_progress_ui, 0.9, _("Extracting and installing theme...")
                    )

                    if self.manager is not None:
                        installed = self.manager.install_theme(
                            source_path=downloaded_path,
                            overwrite=True,
                        )
                    else:
                        from ...core.installer import ThemeInstaller

                        installed = ThemeInstaller().install(
                            archive_path=downloaded_path,
                            overwrite=True,
                        )

                    # Optional Apply
                    applied_names: list[str] = []
                    if apply_after and installed and self.manager is not None:
                        for th in installed:
                            try:
                                if th.theme_type in (
                                    ThemeType.GTK,
                                    ThemeType.SHELL,
                                    ThemeType.ICON,
                                    ThemeType.CURSOR,
                                ):
                                    self.manager.apply_component(th.theme_type, th.name)
                                    applied_names.append(th.name)
                            except Exception as apply_err:
                                logger.warning(
                                    "Could not automatically apply installed theme '%s': %s",
                                    th.name,
                                    apply_err,
                                )

                    GLib.idle_add(self._on_install_finished, installed, applied_names, None)
            except Exception as err:
                GLib.idle_add(self._on_install_finished, [], [], err)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_ui(self, fraction: float, text: str) -> bool:
        """Update progress bar fraction and label safely on main thread."""
        self.detail_progress_bar.set_fraction(fraction)
        self.detail_progress_label.set_text(text)
        return False

    def _on_install_finished(
        self, installed: list[Theme], applied: list[str], error: Exception | None
    ) -> bool:
        """Handle install completion on the main GTK loop."""
        self._is_installing = False
        self.detail_install_button.set_sensitive(True)
        self.detail_install_apply_button.set_sensitive(True)
        self.detail_progress_box.set_visible(False)

        if error is not None:
            logger.error("Installation failed for store item: %s", error)
            msg = _("Installation failed: {error}").format(error=str(error))
            if self.on_notify_message:
                self.on_notify_message(msg, True)
            return False

        theme_names = ", ".join(t.name for t in installed) or (
            self._selected_item.name if self._selected_item else "Theme"
        )
        if applied:
            msg = _("Successfully installed and applied '{name}'!").format(name=theme_names)
        else:
            msg = _("Successfully installed '{name}'!").format(name=theme_names)

        if self.on_notify_message:
            self.on_notify_message(msg, False)

        return False

    def _on_clear_search_clicked(self) -> None:
        """Clear search query and reload current category."""
        self.search_entry.set_text("")
        self.trigger_search()

    def _show_state(self, state_name: str) -> None:
        """Switch visible child of root and content stacks."""
        if state_name in ("categories", "detail"):
            self.widget.set_visible_child_name(state_name)
        elif state_name == "browse":
            self.widget.set_visible_child_name("browse")
            self.content_stack.set_visible_child_name("grid" if self._current_items else "loading")
        else:
            self.widget.set_visible_child_name("browse")
            target = "grid" if state_name in ("grid", "ready") else state_name
            self.content_stack.set_visible_child_name(target)
