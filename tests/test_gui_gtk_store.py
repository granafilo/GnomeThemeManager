# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GTK4 / Libadwaita StorePage (Task 5.2)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from gnome_theme_manager.core import (
    StoreClient,
    StoreDownloadFile,
    StoreItem,
    Theme,
    ThemeManager,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk.pages.store import (
    StorePage,
    _clean_html_description,
    _create_badge_pill,
)


@pytest.fixture(scope="session", autouse=True)
def init_adw() -> None:
    """Initialize Adw / GTK runtime once for tests."""
    try:
        Adw.init()
    except Exception:
        pass


class TestStorePageUnit:
    """Unit tests for StorePage widget lifecycle and user interactions."""

    @pytest.fixture
    def mock_store_client(self) -> MagicMock:
        client = MagicMock(spec=StoreClient)
        client.search.return_value = [
            StoreItem(
                id="101",
                name="Nordic Dark GTK",
                author="EliverLara",
                type_name="GTK3/4 Themes",
                rating=95,
                downloads=5400,
                summary="A dark nordic theme",
                description="<p>Full description with <b>bold</b> text.</p>",
                files=[
                    StoreDownloadFile(
                        file_index=1,
                        name="nordic.tar.xz",
                        download_url="https://example.com/nordic.tar.xz",
                        size_str="1.2 MB",
                    )
                ],
            )
        ]
        client.get_details.return_value = client.search.return_value[0]
        return client

    @pytest.fixture
    def mock_manager(self, mock_store_client: MagicMock) -> MagicMock:
        mgr = MagicMock(spec=ThemeManager)
        mgr.store_client = mock_store_client
        mgr.install_theme.return_value = [
            Theme(
                name="Nordic Dark GTK",
                theme_type=ThemeType.GTK,
                path=Path("/tmp/Nordic"),
                is_user_level=True,
            )
        ]
        return mgr

    def test_clean_html_description(self) -> None:
        raw = "<p>First paragraph<br/>Second line</p><p>Second paragraph &amp; more</p>"
        cleaned = _clean_html_description(raw)
        assert "First paragraph" in cleaned
        assert "Second line" in cleaned
        assert "Second paragraph & more" in cleaned
        assert "<p>" not in cleaned

    def test_create_badge_pill(self) -> None:
        pill = _create_badge_pill("GTK Theme")
        assert isinstance(pill, Gtk.Box)

    def test_store_page_initialization(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        assert page.page_id == "store"
        assert page.title == "Online Store"
        assert isinstance(page.get_widget(), Gtk.Stack)
        assert page.widget.get_visible_child_name() == "categories"

    def test_store_page_open_categories(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)

        # Open GTK & Shell category
        page.category_card_gtk_shell.emit("clicked")
        assert page.widget.get_visible_child_name() == "browse"
        assert page._current_category_key == "gtk_shell"
        assert page._current_category_id == "135x134"

        # Back to categories hub
        page.btn_back_to_categories.emit("clicked")
        assert page.widget.get_visible_child_name() == "categories"

        # Open Icons category
        page.category_card_icons.emit("clicked")
        assert page.widget.get_visible_child_name() == "browse"
        assert page._current_category_key == "icons"
        assert page._current_category_id == "386"

        # Open Cursors category
        page.category_card_cursors.emit("clicked")
        assert page.widget.get_visible_child_name() == "browse"
        assert page._current_category_key == "cursors"
        assert page._current_category_id == "107"

    def test_store_page_search_success(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        items = mock_manager.store_client.search.return_value

        # Manually trigger handler simulating thread return
        page._on_search_completed(items, None)

        assert page.widget.get_visible_child_name() == "browse"
        assert page.content_stack.get_visible_child_name() == "grid"
        assert "1 items found" in page.results_count_label.get_text()

    def test_store_page_search_empty(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        page._on_search_completed([], None)

        assert page.widget.get_visible_child_name() == "browse"
        assert page.content_stack.get_visible_child_name() == "empty"

    def test_store_page_clear_search(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        page.search_entry.set_text("nonexistent_theme")

        # Click clear search button
        with patch.object(page, "trigger_search") as mock_trigger:
            page.empty_clear_button.emit("clicked")
            assert page.search_entry.get_text() == ""
            mock_trigger.assert_called_once()

    def test_store_page_pagination(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        items = [mock_manager.store_client.search.return_value[0]] * 30

        # When 30 items returned, next button is active, prev button is disabled (page 0)
        page._on_search_completed(items, None)
        assert page.lbl_page_indicator.get_text() == "Page 1"
        assert page.btn_prev_page.get_sensitive() is False
        assert page.btn_next_page.get_sensitive() is True

        # Click next page
        with patch.object(page, "trigger_search") as mock_trigger:
            page.btn_next_page.emit("clicked")
            assert page._current_page == 1
            mock_trigger.assert_called_once_with(reset_page=False)

        # On page 2 with only 5 items, prev button is enabled, next button is disabled
        few_items = [mock_manager.store_client.search.return_value[0]] * 5
        page._on_search_completed(few_items, None)
        assert page.lbl_page_indicator.get_text() == "Page 2"
        assert page.btn_prev_page.get_sensitive() is True
        assert page.btn_next_page.get_sensitive() is False

        # Click prev page
        with patch.object(page, "trigger_search") as mock_trigger:
            page.btn_prev_page.emit("clicked")
            assert page._current_page == 0
            mock_trigger.assert_called_once_with(reset_page=False)

    def test_store_page_search_error(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        page._on_search_completed([], RuntimeError("Network unreachable"))

        assert page.widget.get_visible_child_name() == "browse"
        assert page.content_stack.get_visible_child_name() == "error"

    def test_store_page_item_details_and_back(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        item = mock_manager.store_client.search.return_value[0]

        page._populate_detail_view(item)

        assert page.widget.get_visible_child_name() == "detail"
        assert page.detail_title_label.get_text() == "Nordic Dark GTK"
        assert "EliverLara" in page.detail_author_label.get_text()

        # Simulate back button
        page.detail_back_button.emit("clicked")
        assert page.widget.get_visible_child_name() == "browse"

    def test_store_page_sort_dropdown_selection(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        # Select "Rating" (index 1)
        page.sort_dropdown.set_selected(1)
        assert page.sort_dropdown.get_selected() == 1

        # Select "Downloads" (index 2)
        page.sort_dropdown.set_selected(2)
        assert page.sort_dropdown.get_selected() == 2

    def test_store_page_gallery_multiple_screenshots(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        item = StoreItem(
            id="202",
            name="Multi Screenshot Theme",
            author="Author",
            preview_images=[
                "https://example.com/shot1.png",
                "https://example.com/shot2.png",
                "https://example.com/shot3.png",
            ],
        )

        page._populate_detail_view(item)

        assert page.detail_prev_image_button.get_visible() is True
        assert page.detail_next_image_button.get_visible() is True
        assert page.detail_thumbnails_scrolled.get_visible() is True
        assert "1 of 3" in page.detail_image_counter_label.get_text()
        assert len(page._thumbnail_buttons) == 3

        # Click next image button
        page.detail_next_image_button.emit("clicked")
        assert page._detail_image_index == 1
        assert "2 of 3" in page.detail_image_counter_label.get_text()

        # Click thumbnail button for image 3
        page._thumbnail_buttons[2].emit("clicked")
        assert page._detail_image_index == 2
        assert "3 of 3" in page.detail_image_counter_label.get_text()

        # Click previous image button
        page.detail_prev_image_button.emit("clicked")
        assert page._detail_image_index == 1
        assert "2 of 3" in page.detail_image_counter_label.get_text()

    def test_store_page_fullscreen_dialog(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        item = StoreItem(
            id="203",
            name="Fullscreen Test Theme",
            author="Author",
            preview_images=[
                "https://example.com/shot1.png",
                "https://example.com/shot2.png",
            ],
        )
        page._populate_detail_view(item)

        # Trigger fullscreen dialog button
        page.detail_fullscreen_button.emit("clicked")
        # Ensure it does not crash and works cleanly with valid index
        assert page._detail_image_index == 0

    def test_store_page_install_workflow(self, mock_manager: MagicMock, tmp_path: Path) -> None:
        page = StorePage(manager=mock_manager)
        item = mock_manager.store_client.search.return_value[0]
        page._selected_item = item

        # Mock download returning dummy archive
        fake_archive = tmp_path / "theme.tar.xz"
        fake_archive.write_bytes(b"dummy")
        mock_manager.store_client.download.return_value = fake_archive

        notifications: list[tuple[str, bool]] = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        # Simulate install completion
        page._on_install_finished(
            installed=mock_manager.install_theme.return_value,
            applied=[],
            error=None,
        )

        assert len(notifications) == 1
        assert not notifications[0][1]  # is_error False
        assert "Successfully installed 'Nordic Dark GTK'" in notifications[0][0]

    def test_store_page_install_error(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        page._selected_item = mock_manager.store_client.search.return_value[0]

        notifications: list[tuple[str, bool]] = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        page._on_install_finished(
            installed=[],
            applied=[],
            error=RuntimeError("Extraction failed"),
        )

        assert len(notifications) == 1
        assert notifications[0][1]  # is_error True
        assert "Installation failed: Extraction failed" in notifications[0][0]

    def test_store_card_click_opens_details(self, mock_manager: MagicMock) -> None:
        from gnome_theme_manager.gui_gtk.pages.store import _StoreCardWidget

        item = mock_manager.store_client.search.return_value[0]
        details_called = []
        install_called = []

        card = _StoreCardWidget(
            item=item,
            on_view_details=lambda it: details_called.append(it),
            on_quick_install=lambda it: install_called.append(it),
        )

        # Trigger card click handler directly
        gesture = Gtk.GestureClick.new()
        card._on_card_clicked(gesture, 1, 10.0, 10.0)

        assert len(details_called) == 1
        assert details_called[0].id == item.id
        assert len(install_called) == 0

    def test_store_unsupported_item_handling(self, mock_manager: MagicMock) -> None:
        from gnome_theme_manager.gui_gtk.pages.store import _StoreCardWidget

        unsupported_item = StoreItem(
            id="999",
            name="Abstract Wallpaper",
            type_name="Wallpaper Other",
            tags=["wallpaper", "4k"],
        )

        # 1. Card button should be disabled
        card = _StoreCardWidget(
            item=unsupported_item,
            on_view_details=lambda _: None,
            on_quick_install=lambda _: None,
        )
        assert card.btn_install.get_sensitive() is False

        # 2. Detail view should show warning banner and disable install buttons
        page = StorePage(manager=mock_manager)
        page._populate_detail_view(unsupported_item)
        assert page.detail_unsupported_banner.get_revealed() is True
        assert page.detail_install_button.get_sensitive() is False
        assert page.detail_install_apply_button.get_sensitive() is False

    def test_store_page_grid_width_responsive_columns(self, mock_manager: MagicMock) -> None:
        page = StorePage(manager=mock_manager)
        items = mock_manager.store_client.search.return_value
        page._on_search_completed(items, None)

        assert isinstance(page.cards_grid, Gtk.FlowBox)
        assert page.cards_grid.get_max_children_per_line() == 4
        assert page.cards_grid.get_min_children_per_line() == 1
        page._on_grid_width_changed()


class TestMainWindowStoreIntegration:
    """Test MainWindow integration and sidebar selection of StorePage."""

    def test_main_window_has_store_page(self) -> None:
        from gi.repository import Gio

        from gnome_theme_manager.gui_gtk.window import MainWindow

        app = Adw.Application(
            application_id=None,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        mock_mgr = MagicMock(spec=ThemeManager)
        mock_mgr.installer.ensure_user_directories.return_value = []
        mock_mgr.get_system_status.return_value.user_themes_path = Path(
            "/home/user/.local/share/themes"
        )
        mock_mgr.get_system_status.return_value.user_icons_path = Path(
            "/home/user/.local/share/icons"
        )
        mock_mgr.get_system_status.return_value.sandbox_status = None
        mock_mgr.get_system_status.return_value.gtk4_override_active = False
        mock_mgr.get_system_status.return_value.gtk4_override_status = None
        mock_mgr.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
        mock_mgr.store_client.search.return_value = []

        window = MainWindow(app=app, manager=mock_mgr)
        assert "store" in window.pages
        assert isinstance(window.pages["store"], StorePage)
        assert window.row_store is not None

        # Select store page
        window.select_page("store")
        assert window.content_stack.get_visible_child_name() == "store"
