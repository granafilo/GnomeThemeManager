# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GNOME Shell extensions backend module (REST and CLI)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import (
    ExtensionError,
    ExtensionIncompatibleError,
    ExtensionInstallError,
    ExtensionNetworkError,
    ExtensionNotFoundError,
)
from gnome_theme_manager.core.extension_backend import (
    ExtensionItem,
    ExtensionSearchResult,
    GnomeExtensionsCliBackend,
    GnomeExtensionsRestBackend,
    get_extension_backend,
)
from gnome_theme_manager.core.extensions import ExtensionsManager, GnomeExtension


@pytest.fixture
def mock_mgr(tmp_path: Path) -> ExtensionsManager:
    user_dir = tmp_path / "user_extensions"
    user_dir.mkdir(parents=True)
    sys_dir = tmp_path / "sys_extensions"
    sys_dir.mkdir(parents=True)
    prefs_file = tmp_path / "ui_prefs.json"
    return ExtensionsManager(
        prefs_file=prefs_file,
        user_extensions_dir=user_dir,
        system_extensions_dir=sys_dir,
    )


def test_extension_item_compatibility() -> None:
    item = ExtensionItem(
        uuid="test@example.com",
        name="Test Extension",
        description="A test extension",
        shell_version_map={
            "45": {"pk": 101, "version": 1},
            "46": {"pk": 102, "version": 2},
        },
    )
    assert item.check_compatibility("46") is True
    assert item.get_compatible_version_tag("46") == 102
    assert item.get_compatible_version_tag("46.1") == 102
    assert item.check_compatibility("47") is False
    assert item.get_compatible_version_tag("47") is None


def test_rest_backend_search_success(mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    mock_payload = {
        "total": 1,
        "numpages": 1,
        "extensions": [
            {
                "uuid": "test@example.com",
                "name": "Test Extension",
                "description": "Short desc",
                "creator": "author",
                "pk": 123,
                "link": "/extension/123/test-extension/",
                "creator_url": "/accounts/profile/author/",
                "icon": "/icon.png",
                "screenshot": "/shot.png",
                "downloads": 500,
                "shell_version_map": {"46": {"pk": 999, "version": 5}},
            }
        ],
    }

    with patch.object(backend, "_http_get_json", return_value=mock_payload) as mock_get:
        res: ExtensionSearchResult = backend.search(query="test", shell_version="46", sort="recent")
        assert res.total == 1
        assert len(res.extensions) == 1
        item = res.extensions[0]
        assert item.uuid == "test@example.com"
        assert item.link == "https://extensions.gnome.org/extension/123/test-extension/"
        assert item.creator_url == "https://extensions.gnome.org/accounts/profile/author/"
        assert item.icon_url == "https://extensions.gnome.org/icon.png"
        assert item.screenshot_url == "https://extensions.gnome.org/shot.png"
        assert item.check_compatibility("46") is True

        # Verify query parameters
        mock_get.assert_called_once()
        sent_params = mock_get.call_args[1]["params"]
        assert sent_params["sort"] == "created"


def test_rest_backend_get_details(mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    mock_detail = {
        "uuid": "test@example.com",
        "name": "Test Extension",
        "description": "Full desc",
        "pk": 123,
    }

    with patch.object(backend, "_http_get_json", return_value=mock_detail):
        details = backend.get_details("test@example.com")
        assert details is not None
        assert details.name == "Test Extension"

    # Test 440/404 handling
    with patch.object(backend, "_http_get_json", side_effect=ExtensionNotFoundError("404")):
        details = backend.get_details("nonexistent@example.com")
        assert details is None


def test_rest_backend_download_bundle(tmp_path: Path, mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    item = ExtensionItem(
        uuid="test@example.com",
        name="Test Extension",
        description="Desc",
        shell_version_map={"46": {"pk": 999, "version": 1}},
    )

    mock_resp = MagicMock()
    mock_resp.iter_content.return_value = [b"PKfakezipcontent"]
    mock_resp.raise_for_status.return_value = None

    target_dir = tmp_path / "downloads"
    with patch.object(backend, "get_details", return_value=item):
        if backend._session is not None:
            with patch.object(backend._session, "get", return_value=mock_resp):
                dest = backend.download_bundle(
                    "test@example.com", target_dir=target_dir, shell_version="46"
                )
                assert dest.exists()
                assert dest.name == "test@example.com.zip"
        else:
            with patch("urllib.request.urlopen") as mock_url:
                mock_u_resp = MagicMock()
                mock_u_resp.read.side_effect = [b"PKfakezipcontent", b""]
                mock_url.return_value.__enter__.return_value = mock_u_resp
                dest = backend.download_bundle(
                    "test@example.com", target_dir=target_dir, shell_version="46"
                )
                assert dest.exists()
                assert dest.name == "test@example.com.zip"

    # Incompatible shell version
    with patch.object(backend, "get_details", return_value=item):
        with pytest.raises(ExtensionIncompatibleError):
            backend.download_bundle("test@example.com", target_dir=target_dir, shell_version="50")


def test_rest_backend_install_zip_extraction(tmp_path: Path, mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    uuid = "dummy@example.com"

    # Create dummy zip bundle
    bundle_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr("metadata.json", '{"uuid": "dummy@example.com", "name": "Dummy"}')
        zf.writestr("extension.js", 'console.log("hello");')

    with patch("shutil.which", return_value=None):  # simulate no CLI tool
        success = backend.install(uuid, bundle_path=bundle_path)
        assert success is True
        installed_meta = mock_mgr.user_extensions_dir / uuid / "metadata.json"
        assert installed_meta.is_file()


def test_rest_backend_install_zip_slip_prevention(
    tmp_path: Path, mock_mgr: ExtensionsManager
) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    uuid = "slip@example.com"

    # Create zip bundle with Zip Slip exploit entry
    bundle_path = tmp_path / "slip.zip"
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr("../../../evil.txt", "pwned")

    with patch("shutil.which", return_value=None):
        with pytest.raises(ExtensionInstallError, match="Unsafe path"):
            backend.install(uuid, bundle_path=bundle_path)


def test_cli_backend_operations(mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsCliBackend(extensions_manager=mock_mgr)

    # Mock installed extension
    dummy_ext = GnomeExtension(
        uuid="local@example.com",
        name="Local Extension",
        description="Local installed extension",
        enabled=True,
    )
    with patch.object(mock_mgr, "list_extensions", return_value=[dummy_ext]):
        res = backend.search("local")
        assert res.total == 1
        assert res.extensions[0].uuid == "local@example.com"

        res_none = backend.search("nonexistent")
        assert res_none.total == 0

    with patch.object(mock_mgr, "get_extension", return_value=dummy_ext):
        det = backend.get_details("local@example.com")
        assert det is not None
        assert det.name == "Local Extension"

    # CLI backend download should raise ExtensionError
    with pytest.raises(ExtensionError):
        backend.download_bundle("local@example.com")

    # Install without bundle path
    with pytest.raises(ExtensionInstallError):
        backend.install("local@example.com", bundle_path=None)


def test_get_extension_backend_factory(mock_mgr: ExtensionsManager) -> None:
    rest_b = get_extension_backend("rest", extensions_manager=mock_mgr)
    assert isinstance(rest_b, GnomeExtensionsRestBackend)

    cli_b = get_extension_backend("cli", extensions_manager=mock_mgr)
    assert isinstance(cli_b, GnomeExtensionsCliBackend)


def test_rest_backend_parse_multiple_screenshots(mock_mgr: ExtensionsManager) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    raw_payload = {
        "uuid": "gallery@example.com",
        "name": "Gallery Extension",
        "description": 'Here is an image: <img src="/images/shot2.png"/> and ![alt](https://example.com/shot3.png)',
        "screenshot": "/shot1.png",
        "screenshots": ["/shot1.png", "/shot4.png"],
    }
    item = backend._parse_extension_item(raw_payload, {})
    assert item.screenshot_url == "https://extensions.gnome.org/shot1.png"
    assert len(item.screenshots) == 4
    assert item.screenshots[0] == "https://extensions.gnome.org/shot1.png"
    assert item.screenshots[1] == "https://extensions.gnome.org/shot4.png"
    assert item.screenshots[2] == "https://extensions.gnome.org/images/shot2.png"
    assert item.screenshots[3] == "https://example.com/shot3.png"


def test_rest_backend_cache_search_and_offline_fallback(
    tmp_path: Path, mock_mgr: ExtensionsManager
) -> None:
    cache_dir = tmp_path / "ext_cache"
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr, cache_dir=cache_dir)

    mock_payload = {
        "total": 1,
        "numpages": 1,
        "extensions": [
            {
                "uuid": "cached@example.com",
                "name": "Cached Extension",
                "description": "Cached desc",
                "pk": 555,
                "shell_version_map": {"46": {"pk": 555, "version": 1}},
            }
        ],
    }

    # 1. First call succeeds and populates cache
    with patch.object(backend, "_http_get_json", return_value=mock_payload):
        res = backend.search(query="cached", shell_version="46")
        assert res.total == 1
        assert res.from_cache is False
        assert len(res.extensions) == 1
        assert res.extensions[0].uuid == "cached@example.com"

    # Verify cache file was written
    cache_files = list(cache_dir.glob("search_*.json"))
    assert len(cache_files) == 1

    # 2. Second call fails with network error: fallback to offline cache
    with patch.object(
        backend,
        "_http_get_json",
        side_effect=ExtensionNetworkError("Network unreachable"),
    ):
        res_offline = backend.search(query="cached", shell_version="46")
        assert res_offline.total == 1
        assert res_offline.from_cache is True
        assert res_offline.extensions[0].uuid == "cached@example.com"


def test_rest_backend_cache_get_details(tmp_path: Path, mock_mgr: ExtensionsManager) -> None:
    cache_dir = tmp_path / "ext_cache"
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr, cache_dir=cache_dir)
    uuid = "detail_cached@example.com"

    mock_detail = {
        "uuid": uuid,
        "name": "Detail Cached",
        "description": "Offline detail desc",
        "pk": 888,
    }

    # 1. First call populates cache
    with patch.object(backend, "_http_get_json", return_value=mock_detail):
        det = backend.get_details(uuid)
        assert det is not None
        assert det.name == "Detail Cached"

    # Verify detail cache file was written
    detail_cache_files = list(cache_dir.glob("detail_*.json"))
    assert len(detail_cache_files) == 1

    # 2. Network error falls back to cached details
    with patch.object(
        backend,
        "_http_get_json",
        side_effect=ExtensionNetworkError("Connection refused"),
    ):
        det_offline = backend.get_details(uuid)
        assert det_offline is not None
        assert det_offline.uuid == uuid
        assert det_offline.name == "Detail Cached"


def test_rest_backend_download_bundle_rollback_on_failure(
    tmp_path: Path, mock_mgr: ExtensionsManager
) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    target_dir = tmp_path / "bundles"
    uuid = "rollback@example.com"

    item = ExtensionItem(
        uuid=uuid,
        name="Rollback Extension",
        shell_version_map={"46": {"pk": 111, "version": 1}},
    )

    with patch.object(backend, "get_details", return_value=item):
        if backend._session is not None:
            # Simulate network failure during chunk write
            mock_resp = MagicMock()
            mock_resp.iter_content.side_effect = RuntimeError("Connection dropped")
            mock_resp.raise_for_status.return_value = None
            with patch.object(backend._session, "get", return_value=mock_resp):
                with pytest.raises(ExtensionNetworkError):
                    backend.download_bundle(uuid, target_dir=target_dir, shell_version="46")
        else:
            with patch("urllib.request.urlopen", side_effect=RuntimeError("Connection dropped")):
                with pytest.raises(ExtensionNetworkError):
                    backend.download_bundle(uuid, target_dir=target_dir, shell_version="46")

    # Verify partial file is removed (rollback)
    dest_file = target_dir / f"{uuid}.zip"
    assert not dest_file.exists()


def test_rest_backend_install_rollback_on_failure(
    tmp_path: Path, mock_mgr: ExtensionsManager
) -> None:
    backend = GnomeExtensionsRestBackend(extensions_manager=mock_mgr)
    uuid = "fail_install@example.com"

    # Create an invalid zip file
    bad_bundle = tmp_path / "corrupt.zip"
    bad_bundle.write_bytes(b"This is not a zip file at all!")

    with patch("shutil.which", return_value=None):
        with pytest.raises(ExtensionInstallError):
            backend.install(uuid, bundle_path=bad_bundle)

    # Verify extension directory was completely rolled back and cleaned up
    user_ext_dir = mock_mgr.user_extensions_dir / uuid
    assert not user_ext_dir.exists()
