# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension backends for GNOME Shell extensions.

Provides a unified interface (ExtensionBackend) supporting both:
- Option A: Remote extensions.gnome.org REST API client (online search,
  metadata inspection, bundle downloading, version compatibility checking).
- Option B: Local gnome-extensions CLI wrapper (local inspection, management,
  offline-friendly operations).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    _REQUESTS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    requests = None  # type: ignore[assignment]
    HTTPAdapter = None  # type: ignore[assignment,misc]
    Retry = None  # type: ignore[assignment,misc]
    _REQUESTS_AVAILABLE = False

from .errors import (
    ExtensionError,
    ExtensionIncompatibleError,
    ExtensionInstallError,
    ExtensionNetworkError,
    ExtensionNotFoundError,
)
from .extensions import ExtensionsManager, GnomeExtension
from .gnome_version import detect_gnome_version

logger = logging.getLogger("gnome_theme_manager.core.extension_backend")

EGO_BASE_URL = "https://extensions.gnome.org"
EGO_QUERY_URL = f"{EGO_BASE_URL}/extension-query/"
EGO_INFO_URL = f"{EGO_BASE_URL}/extension-info/"
EGO_DOWNLOAD_URL = f"{EGO_BASE_URL}/download-extension"


@dataclass
class ExtensionItem:
    """Represents an extension from extensions.gnome.org or local system."""

    uuid: str
    name: str
    description: str
    creator: str = ""
    creator_url: str = ""
    pk: int = 0
    link: str = ""
    icon_url: str | None = None
    screenshot_url: str | None = None
    downloads: int = 0
    popularity: int = 0
    rating: float | None = None
    version: str | None = None
    shell_version_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    is_installed: bool = False
    is_enabled: bool = False
    is_compatible: bool = True
    installed_version: str | None = None
    has_update: bool = False
    error: str | None = None

    def get_compatible_version_tag(self, shell_version: str | int | None) -> int | None:
        """Find the pk (version tag) for the target shell version."""
        if not self.shell_version_map:
            return None
        if shell_version is None:
            v_tuple = detect_gnome_version()
            if v_tuple:
                shell_version = v_tuple[0]
            else:
                shell_version = 46

        sv_str = str(shell_version)
        if sv_str in self.shell_version_map:
            val = self.shell_version_map[sv_str].get("pk")
            if isinstance(val, int):
                return val
        # Check sub-version e.g. "46.0" -> "46"
        major = sv_str.split(".")[0]
        if major in self.shell_version_map:
            val = self.shell_version_map[major].get("pk")
            if isinstance(val, int):
                return val
        return None

    def check_compatibility(self, shell_version: str | int | None = None) -> bool:
        """Check if extension is compatible with the given GNOME Shell version."""
        if not self.shell_version_map:
            return True
        return self.get_compatible_version_tag(shell_version) is not None


@dataclass
class ExtensionSearchResult:
    """Result of an extension catalog search."""

    extensions: list[ExtensionItem] = field(default_factory=list)
    total: int = 0
    page: int = 1
    numpages: int = 1


class ExtensionBackend(ABC):
    """Abstract common interface for GNOME Shell extensions backends."""

    @abstractmethod
    def search(
        self,
        query: str = "",
        shell_version: str | None = None,
        sort: str = "popularity",
        page: int = 1,
        limit: int = 25,
    ) -> ExtensionSearchResult:
        """Search available extensions."""

    @abstractmethod
    def get_details(self, uuid: str) -> ExtensionItem | None:
        """Get full metadata for an extension by UUID."""

    @abstractmethod
    def download_bundle(
        self,
        uuid: str,
        target_dir: Path | None = None,
        shell_version: str | None = None,
    ) -> Path:
        """Download extension zip bundle for the given shell version."""

    @abstractmethod
    def install(self, uuid: str, bundle_path: Path | None = None) -> bool:
        """Install extension from local bundle or by downloading it."""

    @abstractmethod
    def uninstall(self, uuid: str) -> bool:
        """Uninstall an extension by UUID."""

    @abstractmethod
    def enable(self, uuid: str) -> bool:
        """Enable an extension."""

    @abstractmethod
    def disable(self, uuid: str) -> bool:
        """Disable an extension."""

    @abstractmethod
    def list_installed(self) -> list[GnomeExtension]:
        """List locally installed extensions."""

    @abstractmethod
    def check_updates(self) -> list[ExtensionItem]:
        """Check for updates for installed extensions."""


class GnomeExtensionsRestBackend(ExtensionBackend):
    """Option A: extensions.gnome.org REST API backend.

    Provides rich search, screenshot/icon retrieval, version compatibility checks,
    and automatic bundle download from the official GNOME extensions repository.
    """

    def __init__(
        self,
        extensions_manager: ExtensionsManager | None = None,
        timeout: float = 15.0,
        user_agent: str = "GnomeThemeManager/1.0 (Linux; GNOME Shell)",
    ) -> None:
        self.mgr = extensions_manager or ExtensionsManager()
        self.timeout = timeout
        self.user_agent = user_agent
        self._session: Any = None
        if _REQUESTS_AVAILABLE and requests is not None:
            self._session = requests.Session()
            if Retry is not None and HTTPAdapter is not None:
                retries = Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504],
                )
                adapter = HTTPAdapter(max_retries=retries)
                self._session.mount("https://", adapter)
                self._session.mount("http://", adapter)

    def _http_get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if _REQUESTS_AVAILABLE and self._session is not None:
            try:
                resp = self._session.get(url, params=params, headers=headers, timeout=self.timeout)
                if resp.status_code == 404:
                    raise ExtensionNotFoundError(f"URL not found (404): {url}")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
            except ExtensionNotFoundError:
                raise
            except Exception as err:
                logger.error("REST API request failed to %s: %s", url, err)
                raise ExtensionNetworkError(
                    f"Network error querying extensions API: {err}"
                ) from err
        else:
            if params:
                query_str = urllib.parse.urlencode(params)
                url = f"{url}?{query_str}"
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    data_urllib: dict[str, Any] = json.loads(raw)
                    return data_urllib
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    raise ExtensionNotFoundError(f"URL not found (404): {url}") from err
                logger.error("HTTP error querying %s: %s", url, err)
                raise ExtensionNetworkError(f"HTTP error {err.code}: {err.reason}") from err
            except Exception as err:
                logger.error("Urllib error querying %s: %s", url, err)
                raise ExtensionNetworkError(f"Network request failed: {err}") from err

    def _parse_extension_item(
        self, raw: dict[str, Any], installed_map: dict[str, GnomeExtension]
    ) -> ExtensionItem:
        uuid = str(raw.get("uuid", "")).strip()
        icon = raw.get("icon")
        icon_url = f"{EGO_BASE_URL}{icon}" if icon and str(icon).startswith("/") else icon
        screenshot = raw.get("screenshot")
        screenshot_url = (
            f"{EGO_BASE_URL}{screenshot}"
            if screenshot and str(screenshot).startswith("/")
            else screenshot
        )

        installed = installed_map.get(uuid)
        is_installed = installed is not None
        is_enabled = installed.enabled if installed else False
        installed_version = installed.version if installed else None

        vmap = raw.get("shell_version_map", {})
        if not isinstance(vmap, dict):
            vmap = {}

        popularity = int(raw.get("popularity", 0))
        rating_raw = raw.get("rating")
        rating: float | None = None
        if rating_raw is not None:
            try:
                rating = float(rating_raw)
            except (ValueError, TypeError):
                rating = None

        raw_version = str(raw.get("version", "")) if raw.get("version") is not None else None
        has_update = False
        if is_installed and installed_version and raw_version:
            try:
                has_update = str(raw_version).strip() != str(installed_version).strip()
            except Exception:
                has_update = False

        link_raw = raw.get("link")
        link_url = (
            f"{EGO_BASE_URL}{link_raw}"
            if link_raw and str(link_raw).startswith("/")
            else str(link_raw or "")
        )
        if not link_url and uuid:
            link_url = f"{EGO_BASE_URL}/extension/{uuid}/"

        creator_url_raw = raw.get("creator_url")
        creator_full_url = (
            f"{EGO_BASE_URL}{creator_url_raw}"
            if creator_url_raw and str(creator_url_raw).startswith("/")
            else str(creator_url_raw or "")
        )

        item = ExtensionItem(
            uuid=uuid,
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "")),
            creator=str(raw.get("creator", "")),
            creator_url=creator_full_url,
            pk=int(raw.get("pk", 0)),
            link=link_url,
            icon_url=icon_url,
            screenshot_url=screenshot_url,
            downloads=int(raw.get("downloads", 0)),
            popularity=popularity,
            rating=rating,
            version=raw_version,
            shell_version_map=vmap,
            is_installed=is_installed,
            is_enabled=is_enabled,
            installed_version=installed_version,
            has_update=has_update,
        )
        item.is_compatible = item.check_compatibility()
        return item

    def search(
        self,
        query: str = "",
        shell_version: str | None = None,
        sort: str = "popularity",
        page: int = 1,
        limit: int = 25,
    ) -> ExtensionSearchResult:
        """Search extensions from extensions.gnome.org."""
        installed_list = self.list_installed()
        installed_map = {ext.uuid: ext for ext in installed_list}

        params: dict[str, Any] = {
            "page": max(1, page),
        }
        if query.strip():
            params["search"] = query.strip()
        if shell_version:
            params["shell_version"] = str(shell_version)
        else:
            ver_tuple = detect_gnome_version()
            if ver_tuple:
                params["shell_version"] = str(ver_tuple[0])

        if sort:
            ego_sort_map = {
                "popularity": "popularity",
                "downloads": "downloads",
                "recent": "created",
                "latest": "created",
                "newest": "created",
                "created": "created",
                "name": "name",
                "relevance": "relevance",
            }
            params["sort"] = ego_sort_map.get(sort, "popularity")

        try:
            data = self._http_get_json(EGO_QUERY_URL, params=params)
        except ExtensionError:
            raise
        except Exception as err:
            raise ExtensionNetworkError(f"Search failed: {err}") from err

        raw_extensions = data.get("extensions", [])
        total = int(data.get("total", len(raw_extensions)))
        numpages = int(data.get("numpages", 1))

        items: list[ExtensionItem] = []
        for raw in raw_extensions:
            if isinstance(raw, dict):
                items.append(self._parse_extension_item(raw, installed_map))

        if sort == "downloads":
            items.sort(key=lambda x: x.downloads, reverse=True)
        elif sort == "popularity":
            items.sort(key=lambda x: (x.popularity, x.downloads), reverse=True)
        elif sort in ("recent", "latest", "newest", "created"):
            items.sort(key=lambda x: x.pk, reverse=True)

        return ExtensionSearchResult(
            extensions=items,
            total=total,
            page=page,
            numpages=numpages,
        )

    def get_details(self, uuid: str) -> ExtensionItem | None:
        """Get detailed metadata for an extension by UUID."""
        installed_list = self.list_installed()
        installed_map = {ext.uuid: ext for ext in installed_list}

        try:
            data = self._http_get_json(EGO_INFO_URL, params={"uuid": uuid})
            return self._parse_extension_item(data, installed_map)
        except ExtensionNotFoundError:
            return None
        except Exception as err:
            logger.warning("Could not fetch extension details for %s: %s", uuid, err)
            # Fallback to installed local extension if available
            if uuid in installed_map:
                loc = installed_map[uuid]
                return ExtensionItem(
                    uuid=loc.uuid,
                    name=loc.name,
                    description=loc.description,
                    is_installed=True,
                    is_enabled=loc.enabled,
                    installed_version=loc.version,
                    version=loc.version,
                    is_compatible=True,
                )
            raise

    def download_bundle(
        self,
        uuid: str,
        target_dir: Path | None = None,
        shell_version: str | None = None,
    ) -> Path:
        """Download zip bundle from extensions.gnome.org."""
        details = self.get_details(uuid)
        if not details:
            raise ExtensionNotFoundError(f"Extension {uuid} not found on extensions.gnome.org")

        version_tag = details.get_compatible_version_tag(shell_version)
        if not version_tag:
            raise ExtensionIncompatibleError(
                f"Extension {uuid} is not compatible with GNOME Shell {shell_version or 'current'}"
            )

        download_url = f"{EGO_DOWNLOAD_URL}/{urllib.parse.quote(uuid)}.shell-extension.zip?version_tag={version_tag}"
        target_directory = target_dir or Path(
            os.path.expanduser("~/.cache/gnome-theme-manager/extensions")
        )
        target_directory.mkdir(parents=True, exist_ok=True)
        dest_file = target_directory / f"{uuid}.zip"

        headers = {"User-Agent": self.user_agent}
        try:
            if _REQUESTS_AVAILABLE and self._session is not None:
                resp = self._session.get(
                    download_url, headers=headers, stream=True, timeout=self.timeout
                )
                resp.raise_for_status()
                with open(dest_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            else:
                req = urllib.request.Request(download_url, headers=headers)
                with (
                    urllib.request.urlopen(req, timeout=self.timeout) as resp,
                    open(dest_file, "wb") as f,
                ):
                    shutil.copyfileobj(resp, f)
        except Exception as err:
            logger.error("Download failed for %s from %s: %s", uuid, download_url, err)
            raise ExtensionNetworkError(f"Failed to download extension {uuid}: {err}") from err

        return dest_file

    def install(self, uuid: str, bundle_path: Path | None = None) -> bool:
        """Install extension from local bundle or by downloading it."""
        if bundle_path is None or not bundle_path.is_file():
            bundle_path = self.download_bundle(uuid)

        # 1. Try gnome-extensions CLI
        if shutil.which("gnome-extensions"):
            try:
                proc = subprocess.run(
                    ["gnome-extensions", "install", "--force", str(bundle_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    logger.info("Installed extension %s via gnome-extensions install", uuid)
                    return True
                logger.warning(
                    "gnome-extensions install exited with code %s: %s",
                    proc.returncode,
                    proc.stderr,
                )
            except Exception as err:
                logger.warning("CLI install failed: %s", err)

        # 2. Fallback: manual unpack to user extensions directory
        user_ext_dir = self.mgr.user_extensions_dir / uuid
        try:
            user_ext_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(bundle_path, "r") as zf:
                # Security check for Zip Slip
                for member in zf.infolist():
                    target_path = user_ext_dir / member.filename
                    if not target_path.resolve().is_relative_to(user_ext_dir.resolve()):
                        raise ExtensionInstallError(f"Unsafe path in zip bundle: {member.filename}")
                zf.extractall(user_ext_dir)
            logger.info("Extracted extension %s to %s", uuid, user_ext_dir)
            return True
        except Exception as err:
            logger.error("Manual extraction failed for %s: %s", uuid, err)
            raise ExtensionInstallError(f"Failed to extract extension bundle: {err}") from err

    def uninstall(self, uuid: str) -> bool:
        return self.mgr.uninstall_extension(uuid)

    def enable(self, uuid: str) -> bool:
        return self.mgr.enable_extension(uuid)

    def disable(self, uuid: str) -> bool:
        return self.mgr.disable_extension(uuid)

    def list_installed(self) -> list[GnomeExtension]:
        return self.mgr.list_extensions()

    def check_updates(self) -> list[ExtensionItem]:
        """Check for updates for installed extensions."""
        installed = self.list_installed()
        updatable: list[ExtensionItem] = []
        for ext in installed:
            if not ext.uuid:
                continue
            try:
                item = self.get_details(ext.uuid)
                if item and item.has_update and item.is_compatible:
                    updatable.append(item)
            except Exception as err:
                logger.debug("Failed to check update for %s: %s", ext.uuid, err)
        return updatable


class GnomeExtensionsCliBackend(ExtensionBackend):
    """Option B: Local gnome-extensions CLI wrapper backend.

    Fully offline-friendly; manages extensions via local CLI commands
    (list, info, enable, disable, uninstall, install from local zip).
    """

    def __init__(self, extensions_manager: ExtensionsManager | None = None) -> None:
        self.mgr = extensions_manager or ExtensionsManager()

    def search(
        self,
        query: str = "",
        shell_version: str | None = None,
        sort: str = "popularity",
        page: int = 1,
        limit: int = 25,
    ) -> ExtensionSearchResult:
        """Search through installed extensions (CLI has no remote catalog search)."""
        installed = self.list_installed()
        q = query.strip().lower()
        matched: list[ExtensionItem] = []
        for ext in installed:
            if (
                not q
                or q in ext.name.lower()
                or q in ext.uuid.lower()
                or q in ext.description.lower()
            ):
                matched.append(
                    ExtensionItem(
                        uuid=ext.uuid,
                        name=ext.name,
                        description=ext.description,
                        version=ext.version,
                        installed_version=ext.version,
                        is_installed=True,
                        is_enabled=ext.enabled,
                        is_compatible=True,
                    )
                )

        total = len(matched)
        start = (page - 1) * limit
        items = matched[start : start + limit]
        numpages = max(1, (total + limit - 1) // limit) if total > 0 else 1

        return ExtensionSearchResult(
            extensions=items,
            total=total,
            page=page,
            numpages=numpages,
        )

    def get_details(self, uuid: str) -> ExtensionItem | None:
        """Get details for an installed extension using CLI / ExtensionsManager."""
        ext = self.mgr.get_extension(uuid)
        if not ext:
            return None
        return ExtensionItem(
            uuid=ext.uuid,
            name=ext.name,
            description=ext.description,
            version=ext.version,
            installed_version=ext.version,
            is_installed=True,
            is_enabled=ext.enabled,
            is_compatible=True,
        )

    def download_bundle(
        self,
        uuid: str,
        target_dir: Path | None = None,
        shell_version: str | None = None,
    ) -> Path:
        """CLI backend does not support downloading from remote without network."""
        raise ExtensionError(
            "CLI backend does not support downloading remote bundles without network access."
        )

    def install(self, uuid: str, bundle_path: Path | None = None) -> bool:
        """Install extension from local zip bundle using gnome-extensions install."""
        if not bundle_path or not bundle_path.is_file():
            raise ExtensionInstallError(
                "CLI backend requires a valid local bundle_path to install an extension."
            )

        if not shutil.which("gnome-extensions"):
            raise ExtensionInstallError("gnome-extensions executable not found on PATH.")

        try:
            proc = subprocess.run(
                ["gnome-extensions", "install", "--force", str(bundle_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.returncode == 0
        except Exception as err:
            logger.error("CLI install failed: %s", err)
            raise ExtensionInstallError(f"CLI install failed: {err}") from err

    def uninstall(self, uuid: str) -> bool:
        return self.mgr.uninstall_extension(uuid)

    def enable(self, uuid: str) -> bool:
        return self.mgr.enable_extension(uuid)

    def disable(self, uuid: str) -> bool:
        return self.mgr.disable_extension(uuid)

    def list_installed(self) -> list[GnomeExtension]:
        return self.mgr.list_extensions()

    def check_updates(self) -> list[ExtensionItem]:
        """Check for updates (offline CLI has no remote catalog)."""
        return []


def get_extension_backend(
    backend_type: str = "rest",
    extensions_manager: ExtensionsManager | None = None,
) -> ExtensionBackend:
    """Factory to instantiate the chosen ExtensionBackend.

    Args:
        backend_type: 'rest' for extensions.gnome.org API (Option A),
                      or 'cli' for local gnome-extensions CLI (Option B).
        extensions_manager: Optional ExtensionsManager instance.

    Returns:
        ExtensionBackend instance.
    """
    if backend_type.lower() == "cli":
        return GnomeExtensionsCliBackend(extensions_manager=extensions_manager)
    return GnomeExtensionsRestBackend(extensions_manager=extensions_manager)
