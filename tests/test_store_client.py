# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Pling / OpenDesktop StoreClient (Task 5.1)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from gnome_theme_manager.core import (
    StoreCategory,
    StoreClient,
    StoreDownloadError,
    StoreDownloadFile,
    StoreError,
    StoreItem,
    StoreItemNotFoundError,
    StoreNetworkError,
    ThemeManager,
    ThemeType,
    theme_type_to_store_category,
)


class TestStoreCategoryMapping:
    """Test category mapping functions and enum values."""

    def test_theme_type_to_store_category_enum(self) -> None:
        assert theme_type_to_store_category(ThemeType.GTK) == StoreCategory.GTK.value
        assert theme_type_to_store_category(ThemeType.SHELL) == StoreCategory.SHELL.value
        assert theme_type_to_store_category(ThemeType.ICON) == StoreCategory.ICON.value
        assert theme_type_to_store_category(ThemeType.CURSOR) == StoreCategory.CURSOR.value

    def test_theme_type_to_store_category_strings(self) -> None:
        assert theme_type_to_store_category("gtk") == "135"
        assert theme_type_to_store_category("gtk4") == "135"
        assert theme_type_to_store_category("gnome-shell") == "134"
        assert theme_type_to_store_category("icons") == "386"
        assert theme_type_to_store_category("cursors") == "107"
        assert theme_type_to_store_category("fonts") == "103"
        assert theme_type_to_store_category("custom_cat") == "custom_cat"
        assert theme_type_to_store_category(None) == ""


class TestStoreClientSearch:
    """Test searching items via StoreClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        return MagicMock(spec=requests.Session)

    def test_search_success(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "12345",
                    "name": "Nordic Theme",
                    "version": "2.2.0",
                    "personid": "author1",
                    "typeid": 135,
                    "typename": "GTK3/4 Themes",
                    "summary": "Dark theme for GTK",
                    "description": "<p>A nice Nordic theme</p>",
                    "score": 95,
                    "downloads": 1024,
                    "previewpic1": "https://images.example.com/nordic1.png",
                    "previewpic2": "https://images.example.com/nordic2.png",
                    "downloadlink1": "https://files.example.com/nordic.tar.xz",
                    "downloadname1": "nordic.tar.xz",
                    "downloadsize1": "1048576",
                }
            ],
        }
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        results = client.search(query="Nordic", category=ThemeType.GTK, page=0, page_size=10)

        assert len(results) == 1
        item = results[0]
        assert item.id == "12345"
        assert item.name == "Nordic Theme"
        assert item.version == "2.2.0"
        assert item.author == "author1"
        assert item.type_id == 135
        assert item.rating == 95
        assert item.downloads == 1024
        assert item.preview_image_url == "https://images.example.com/nordic1.png"
        assert len(item.preview_images) == 2
        assert len(item.files) == 1
        assert item.files[0].download_url == "https://files.example.com/nordic.tar.xz"
        assert item.files[0].name == "nordic.tar.xz"

        # Verify call params
        mock_session.get.assert_called_once()
        call_args, call_kwargs = mock_session.get.call_args
        assert "content/data" in call_args[0]
        assert call_kwargs["params"]["search"] == "Nordic"
        assert call_kwargs["params"]["categories"] == "135"
        assert call_kwargs["params"]["page"] == 0
        assert call_kwargs["params"]["pagesize"] == 10
        assert call_kwargs["params"]["sortmode"] == "new"

    def test_search_sort_modes_mapping(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"status": "ok", "statuscode": 100, "data": []}
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)

        # Rating / Score
        client.search(sort="rating")
        assert mock_session.get.call_args[1]["params"]["sortmode"] == "high"

        # Downloads
        client.search(sort="downloads")
        assert mock_session.get.call_args[1]["params"]["sortmode"] == "down"

        # Alpha
        client.search(sort="alpha")
        assert mock_session.get.call_args[1]["params"]["sortmode"] == "alpha"

        # New
        client.search(sort="new")
        assert mock_session.get.call_args[1]["params"]["sortmode"] == "new"

    def test_search_timeout(self, mock_session: MagicMock) -> None:
        mock_session.get.side_effect = requests.exceptions.Timeout("Connection timed out")
        client = StoreClient(session=mock_session)

        with pytest.raises(StoreNetworkError) as exc_info:
            client.search(query="test")
        assert "timed out" in str(exc_info.value)

    def test_search_network_error(self, mock_session: MagicMock) -> None:
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        client = StoreClient(session=mock_session)

        with pytest.raises(StoreNetworkError) as exc_info:
            client.search(query="test")
        assert "Network error" in str(exc_info.value)

    def test_search_invalid_json(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.side_effect = ValueError("Invalid JSON")
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreError) as exc_info:
            client.search()
        assert "invalid JSON" in str(exc_info.value)

    def test_search_api_error_status(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "status": "failed",
            "statuscode": 999,
            "message": "Category not found",
        }
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreError) as exc_info:
            client.search(category="invalid")
        assert "Category not found" in str(exc_info.value)


class TestStoreClientGetDetails:
    """Test fetching item details via StoreClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        return MagicMock(spec=requests.Session)

    def test_get_details_success(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "9999",
                    "name": "Fluent Icons",
                    "version": "1.0",
                    "personid": "fluent_author",
                    "typename": "Icons",
                    "tags": "fluent,icons,gnome",
                    "downloadlink1": "https://files.example.com/fluent-dark.tar.xz",
                    "downloadname1": "fluent-dark.tar.xz",
                    "downloadlink2": "https://files.example.com/fluent-light.tar.xz",
                    "downloadname2": "fluent-light.tar.xz",
                }
            ],
        }
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        item = client.get_details("9999")

        assert item.id == "9999"
        assert item.name == "Fluent Icons"
        assert len(item.files) == 2
        assert item.files[0].name == "fluent-dark.tar.xz"
        assert item.files[1].name == "fluent-light.tar.xz"
        assert item.tags == ["fluent", "icons", "gnome"]

    def test_get_details_not_found_empty_data(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [],
        }
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreItemNotFoundError):
            client.get_details("1111")

    def test_get_details_http_404(self, mock_session: MagicMock) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 404
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreItemNotFoundError):
            client.get_details("404_item")


class TestStoreClientDownload:
    """Test downloading files with StoreClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        return MagicMock(spec=requests.Session)

    def test_download_success_with_progress(self, mock_session: MagicMock, tmp_path: Path) -> None:
        # 1. Mock details response
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.raise_for_status.return_value = None
        details_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "555",
                    "name": "Sample Theme",
                    "downloadlink1": "https://example.com/download/sample.tar.gz",
                    "downloadname1": "sample.tar.gz",
                }
            ],
        }

        # 2. Mock streaming download response
        download_response = MagicMock()
        download_response.status_code = 200
        download_response.raise_for_status.return_value = None
        download_response.headers = {"Content-Length": "12"}
        download_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        download_response.__enter__.return_value = download_response
        download_response.__exit__.return_value = None

        mock_session.get.side_effect = [details_response, download_response]

        progress_records: list[tuple[int, int | None]] = []

        def on_progress(downloaded: int, total: int | None) -> None:
            progress_records.append((downloaded, total))

        client = StoreClient(session=mock_session)
        downloaded_file = client.download(
            item_id="555",
            dest_dir=tmp_path,
            progress_callback=on_progress,
        )

        assert downloaded_file.exists()
        assert downloaded_file.name == "sample.tar.gz"
        assert downloaded_file.read_bytes() == b"chunk1chunk2"
        assert len(progress_records) == 2
        assert progress_records[-1] == (12, 12)

    def test_download_no_files_available(self, mock_session: MagicMock, tmp_path: Path) -> None:
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.raise_for_status.return_value = None
        details_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "555",
                    "name": "Sample Theme",
                }
            ],
        }
        mock_session.get.return_value = details_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreDownloadError) as exc_info:
            client.download(item_id="555", dest_dir=tmp_path)
        assert "No download files available" in str(exc_info.value)

    def test_download_network_timeout(self, mock_session: MagicMock, tmp_path: Path) -> None:
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.raise_for_status.return_value = None
        details_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "555",
                    "name": "Sample Theme",
                    "downloadlink1": "https://example.com/file.tar.gz",
                }
            ],
        }
        mock_session.get.side_effect = [
            details_response,
            requests.exceptions.Timeout("Download timed out"),
        ]

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreNetworkError) as exc_info:
            client.download(item_id="555", dest_dir=tmp_path)
        assert "Download timed out" in str(exc_info.value)

    def test_download_custom_filename_and_empty_file_error(
        self, mock_session: MagicMock, tmp_path: Path
    ) -> None:
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.raise_for_status.return_value = None
        details_response.json.return_value = {
            "status": "ok",
            "statuscode": 100,
            "data": [
                {
                    "id": "555",
                    "name": "Sample Theme",
                    "downloadlink1": "https://example.com/file.tar.gz",
                }
            ],
        }

        # Response yielding empty chunks
        download_response = MagicMock()
        download_response.status_code = 200
        download_response.raise_for_status.return_value = None
        download_response.headers = {}
        download_response.iter_content.return_value = []
        download_response.__enter__.return_value = download_response
        download_response.__exit__.return_value = None

        mock_session.get.side_effect = [details_response, download_response]

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreDownloadError) as exc_info:
            client.download(item_id="555", dest_dir=tmp_path, file_name="custom.tar.gz")
        assert "empty or was not created" in str(exc_info.value)


class TestStoreClientEdgeCases:
    """Test various edge cases and helper methods."""

    def test_base_url_normalization(self) -> None:
        client = StoreClient(base_url="https://api.example.com/ocs/v1")
        assert client.base_url == "https://api.example.com/ocs/v1/"

    def test_get_details_empty_id(self) -> None:
        client = StoreClient()
        with pytest.raises(StoreItemNotFoundError):
            client.get_details("")

    def test_get_details_invalid_json(self) -> None:
        mock_session = MagicMock(spec=requests.Session)
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status.return_value = None
        fake_response.json.side_effect = ValueError("Corrupted JSON")
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreError) as exc_info:
            client.get_details("123")
        assert "invalid JSON" in str(exc_info.value)

    def test_get_details_timeout(self) -> None:
        mock_session = MagicMock(spec=requests.Session)
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreNetworkError) as exc_info:
            client.get_details("123")
        assert "timed out" in str(exc_info.value)

    def test_get_details_network_error(self) -> None:
        mock_session = MagicMock(spec=requests.Session)
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Failed")

        client = StoreClient(session=mock_session)
        with pytest.raises(StoreNetworkError) as exc_info:
            client.get_details("123")
        assert "Network error" in str(exc_info.value)

    def test_search_non_list_data(self) -> None:
        mock_session = MagicMock(spec=requests.Session)
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"status": "ok", "statuscode": 100, "data": "invalid"}
        mock_session.get.return_value = fake_response

        client = StoreClient(session=mock_session)
        assert client.search() == []

    def test_extract_filename_from_url(self) -> None:
        assert (
            StoreClient._extract_filename_from_url("https://example.com/path/theme-dark.tar.gz")
            == "theme-dark.tar.gz"
        )
        assert (
            StoreClient._extract_filename_from_url(
                "https://example.com/path/theme%20name.zip?dl=1#frag"
            )
            == "theme name.zip"
        )
        assert StoreClient._extract_filename_from_url("") == ""


class TestThemeManagerStoreIntegration:
    """Test ThemeManager facade store methods."""

    def test_theme_manager_store_methods(self, tmp_path: Path) -> None:
        mock_store_client = MagicMock(spec=StoreClient)
        mock_store_client.search.return_value = [
            StoreItem(id="1", name="Theme A"),
            StoreItem(id="2", name="Theme B"),
        ]
        mock_store_client.get_details.return_value = StoreItem(
            id="1",
            name="Theme A",
            files=[
                StoreDownloadFile(
                    file_index=1,
                    name="theme_a.tar.gz",
                    download_url="https://example.com/a.tar.gz",
                )
            ],
        )
        fake_archive = tmp_path / "mock_theme.tar.gz"
        fake_archive.write_bytes(b"dummy_archive")
        mock_store_client.download.return_value = fake_archive

        manager = ThemeManager(store_client=mock_store_client)
        assert manager.store_client is mock_store_client

        # 1. Search
        search_res = manager.search_store(query="Theme", category=ThemeType.GTK)
        assert len(search_res) == 2
        mock_store_client.search.assert_called_once_with(
            query="Theme",
            category=ThemeType.GTK,
            page=0,
            page_size=20,
            sort="new",
        )

        # 2. Get details
        details = manager.get_store_item_details("1")
        assert details.name == "Theme A"
        mock_store_client.get_details.assert_called_once_with(item_id="1")

        # 3. Download
        dl_path = manager.download_store_item("1", dest_dir=tmp_path)
        assert dl_path == fake_archive

        # 4. Install
        with patch.object(manager, "install_theme") as mock_install:
            mock_install.return_value = []
            manager.install_store_item("1", overwrite=True)
            mock_install.assert_called_once()


class TestStoreItemInstallable:
    """Test is_installable detection for supported and unsupported store items."""

    def test_supported_theme_types(self) -> None:
        gtk_item = StoreItem(id="1", name="Adwaita Dark", type_id=135)
        assert gtk_item.is_installable is True

        shell_item = StoreItem(id="2", name="Blur Shell", type_id=134)
        assert shell_item.is_installable is True

        icon_item = StoreItem(id="3", name="Papirus", type_id=386)
        assert icon_item.is_installable is True

        cursor_item = StoreItem(id="4", name="Bibata", type_id=107)
        assert cursor_item.is_installable is True

        font_item = StoreItem(id="5", name="Inter Font", type_id=103)
        assert font_item.is_installable is True

    def test_supported_by_name_or_tags(self) -> None:
        named_item = StoreItem(id="6", name="Custom Theme", type_name="GNOME Shell Theme")
        assert named_item.is_installable is True

        tagged_item = StoreItem(id="7", name="Nordic", tags=["gtk3", "dark", "flatpak"])
        assert tagged_item.is_installable is True

    def test_unsupported_items(self) -> None:
        wallpaper_item = StoreItem(
            id="8",
            name="Mountain 4k",
            type_name="Wallpaper Other",
            tags=["wallpaper", "landscape", "cc0"],
        )
        assert wallpaper_item.is_installable is False

        sddm_item = StoreItem(
            id="9",
            name="Breeze SDDM",
            type_name="SDDM Themes",
            tags=["sddm", "login", "plasma"],
        )
        assert sddm_item.is_installable is False
