# SPDX-License-Identifier: GPL-3.0-or-later

"""Pling / OpenDesktop (OCS API) online store client for GnomeThemeManager.

Provides search, item metadata inspection, and streaming download capabilities
for GTK themes, Shell themes, icons, cursors, and fonts from openDesktop/Pling.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .errors import (
    StoreDownloadError,
    StoreError,
    StoreItemNotFoundError,
    StoreNetworkError,
)
from .models import ThemeType

logger = logging.getLogger("gnome_theme_manager.core.store_client")

DEFAULT_OCS_API_BASE = "https://api.opendesktop.org/ocs/v1/"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3


class StoreCategory(str, Enum):
    """Pling / OpenDesktop category IDs for desktop themes."""

    ALL = ""
    GTK_SHELL = "135x134"  # GTK 3/4 & GNOME Shell Themes combined
    GTK = "135"  # GTK 3.x / 4.x Theme/Style
    SHELL = "134"  # GNOME Shell Theme
    ICON = "386"  # Icon Theme
    CURSOR = "107"  # X11 Mouse / Cursor Theme
    FONT = "103"  # Fonts


def theme_type_to_store_category(theme_type: ThemeType | str | None) -> str:
    """Map ThemeType to corresponding Pling / OpenDesktop category ID string.

    Args:
        theme_type: ThemeType enum, string name, or None.

    Returns:
        Category ID string (e.g. "135", "134", "386", "107") or empty string.
    """
    if theme_type is None:
        return ""
    if isinstance(theme_type, str):
        val = theme_type.lower()
        if val in ("gtk", "gtk3", "gtk4"):
            return StoreCategory.GTK.value
        if val in ("shell", "gnome-shell"):
            return StoreCategory.SHELL.value
        if val in ("icon", "icons"):
            return StoreCategory.ICON.value
        if val in ("cursor", "cursors"):
            return StoreCategory.CURSOR.value
        if val in ("font", "fonts"):
            return StoreCategory.FONT.value
        return val

    if theme_type == ThemeType.GTK:
        return StoreCategory.GTK.value
    if theme_type == ThemeType.SHELL:
        return StoreCategory.SHELL.value
    if theme_type == ThemeType.ICON:
        return StoreCategory.ICON.value
    if theme_type == ThemeType.CURSOR:
        return StoreCategory.CURSOR.value

    return ""


@dataclass
class StoreDownloadFile:
    """Metadata for a downloadable file attached to a store item."""

    file_index: int
    name: str
    download_url: str
    size_str: str = ""
    version: str = ""
    price: str = "0"
    mimetype: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert download file metadata to dictionary."""
        return {
            "file_index": self.file_index,
            "name": self.name,
            "download_url": self.download_url,
            "size_str": self.size_str,
            "version": self.version,
            "price": self.price,
            "mimetype": self.mimetype,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreDownloadFile":
        """Reconstruct StoreDownloadFile from dictionary."""
        return cls(
            file_index=int(data.get("file_index", 0)),
            name=str(data.get("name", "")),
            download_url=str(data.get("download_url", "")),
            size_str=str(data.get("size_str", "")),
            version=str(data.get("version", "")),
            price=str(data.get("price", "0")),
            mimetype=str(data.get("mimetype", "")),
        )


@dataclass
class StoreItem:
    """Complete metadata for an item listed in the online store."""

    id: str
    name: str
    version: str = ""
    author: str = ""
    type_id: int = 0
    type_name: str = ""
    summary: str = ""
    description: str = ""
    rating: int = 0
    downloads: int = 0
    created: str = ""
    updated: str = ""
    details_url: str = ""
    preview_image_url: str = ""
    small_preview_image_url: str = ""
    preview_images: list[str] = field(default_factory=list)
    files: list[StoreDownloadFile] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    xdg_type: str = ""
    score: int = 0
    homepage: str = ""
    category: str = ""

    @property
    def typename(self) -> str:
        """Alias for type_name."""
        return self.type_name

    @property
    def preview_urls(self) -> list[str]:
        """Alias for preview_images."""
        return self.preview_images

    @property
    def is_installable(self) -> bool:
        """Return True if this store item represents a theme type installable on GNOME."""
        supported_type_ids = {
            int(StoreCategory.GTK.value),  # 135
            int(StoreCategory.SHELL.value),  # 134
            int(StoreCategory.ICON.value),  # 386
            int(StoreCategory.CURSOR.value),  # 107
            int(StoreCategory.FONT.value),  # 103
        }
        if self.type_id in supported_type_ids:
            return True

        t_name = self.type_name.lower()
        if any(kw in t_name for kw in ("gtk", "gnome shell", "icon", "cursor", "font")):
            return True

        all_tags = " ".join(self.tags).lower()
        return any(
            kw in all_tags for kw in ("gtk", "gnome-shell", "gnome shell", "icon", "cursor", "font")
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert store item to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "type_id": self.type_id,
            "type_name": self.type_name,
            "summary": self.summary,
            "description": self.description,
            "rating": self.rating,
            "downloads": self.downloads,
            "score": self.score,
            "created": self.created,
            "updated": self.updated,
            "details_url": self.details_url,
            "homepage": self.homepage,
            "preview_image_url": self.preview_image_url,
            "small_preview_image_url": self.small_preview_image_url,
            "preview_images": list(self.preview_images),
            "files": [f.to_dict() for f in self.files],
            "tags": list(self.tags),
            "xdg_type": self.xdg_type,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreItem":
        """Reconstruct StoreItem from dictionary."""
        files_data = data.get("files", [])
        files = (
            [StoreDownloadFile.from_dict(f) if isinstance(f, dict) else f for f in files_data]
            if isinstance(files_data, list)
            else []
        )
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            author=str(data.get("author", data.get("personid", ""))),
            type_id=int(data.get("type_id", 0)),
            type_name=str(data.get("type_name", data.get("typename", ""))),
            summary=str(data.get("summary", "")),
            description=str(data.get("description", "")),
            rating=int(data.get("rating", 0)),
            downloads=int(data.get("downloads", 0)),
            score=int(data.get("score", 0)),
            created=str(data.get("created", "")),
            updated=str(data.get("updated", "")),
            details_url=str(data.get("details_url", "")),
            homepage=str(data.get("homepage", "")),
            preview_image_url=str(data.get("preview_image_url", "")),
            small_preview_image_url=str(data.get("small_preview_image_url", "")),
            preview_images=list(data.get("preview_images", data.get("preview_urls", []))),
            files=files,
            tags=list(data.get("tags", [])),
            xdg_type=str(data.get("xdg_type", "")),
            category=str(data.get("category", "")),
        )


class StoreClient:
    """Client for interacting with OpenDesktop/Pling OCS v1 API."""

    def __init__(
        self,
        base_url: str = DEFAULT_OCS_API_BASE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize StoreClient with configuration and retry adapter.

        Args:
            base_url: OCS API base URL (must end with slash).
            timeout: Request timeout in seconds.
            max_retries: Maximum automatic retry attempts for transient network issues.
            session: Optional custom requests Session.
        """
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.timeout = timeout
        self.max_retries = max_retries

        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            retry_strategy = Retry(
                total=max_retries,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("https://", adapter)
            self._session.mount("http://", adapter)

    def search(
        self,
        query: str = "",
        category: str | StoreCategory | ThemeType | None = None,
        page: int = 0,
        page_size: int = 20,
        sort: str = "new",
    ) -> list[StoreItem]:
        """Search and list items from the Pling / OpenDesktop store.

        Args:
            query: Free text search keyword.
            category: Target category ID, StoreCategory, or ThemeType.
            page: 0-indexed page number.
            page_size: Maximum items to return per page.
            sort: Sort criteria ("new", "rating", "high", etc.).

        Returns:
            List of StoreItem objects matching search criteria.

        Raises:
            StoreNetworkError: If connection or timeout fails.
            StoreError: If API returns an error status code.
        """
        cat_str = ""
        if isinstance(category, StoreCategory):
            cat_str = category.value
        elif isinstance(category, (ThemeType, str)):
            cat_str = theme_type_to_store_category(category)

        sort_mapping: dict[str, str] = {
            "new": "new",
            "latest": "new",
            "recent": "new",
            "rating": "high",
            "high": "high",
            "score": "high",
            "downloads": "down",
            "down": "down",
            "most": "down",
            "top": "down",
            "alpha": "alpha",
            "alphabetical": "alpha",
        }
        sort_mode = sort_mapping.get(sort.lower().strip(), "new") if sort else "new"

        params: dict[str, Any] = {
            "format": "json",
            "page": max(0, page),
            "pagesize": max(1, page_size),
            "sortmode": sort_mode,
        }
        if query.strip():
            params["search"] = query.strip()
        if cat_str.strip():
            params["categories"] = cat_str.strip()

        url = f"{self.base_url}content/data"
        logger.debug("Searching store: %s with params %s", url, params)

        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.Timeout as err:
            logger.warning("Store API search timeout: %s", err)
            raise StoreNetworkError(f"Store search timed out after {self.timeout}s: {err}") from err
        except requests.exceptions.RequestException as err:
            logger.warning("Store API search network error: %s", err)
            raise StoreNetworkError(f"Network error during store search: {err}") from err
        except ValueError as err:
            logger.error("Invalid JSON response from store API: %s", err)
            raise StoreError(f"Store API returned invalid JSON: {err}") from err

        if not isinstance(payload, dict):
            raise StoreError("Malformed API response: expected JSON object.")

        if "ocs" in payload and isinstance(payload["ocs"], dict):
            payload = payload["ocs"]

        status_code = 100
        if "meta" in payload and isinstance(payload["meta"], dict):
            status_code = payload["meta"].get("statuscode", 100)
            if status_code != 100 and payload["meta"].get("status") != "ok":
                msg = payload["meta"].get("message", f"API status code {status_code}")
                raise StoreError(f"Store API error: {msg}")
        else:
            status_code = payload.get("statuscode", 100)
            if status_code != 100 and payload.get("status") != "ok":
                msg = payload.get("message", f"API status code {status_code}")
                raise StoreError(f"Store API error: {msg}")

        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        items: list[StoreItem] = []
        for raw_item in data:
            if isinstance(raw_item, dict):
                items.append(self._parse_item_dict(raw_item))

        return items

    def get_details(self, item_id: str | int) -> StoreItem:
        """Fetch full details and metadata for a specific store item ID.

        Args:
            item_id: Item identifier.

        Returns:
            Detailed StoreItem instance.

        Raises:
            StoreItemNotFoundError: If item does not exist.
            StoreNetworkError: If network request fails.
            StoreError: If API response is invalid.
        """
        clean_id = str(item_id).strip()
        if not clean_id:
            raise StoreItemNotFoundError("Item ID cannot be empty.")

        url = f"{self.base_url}content/data/{clean_id}"
        params = {"format": "json"}

        logger.debug("Fetching store item details: %s", url)

        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 404:
                raise StoreItemNotFoundError(f"Store item '{clean_id}' was not found (HTTP 404).")
            response.raise_for_status()
            payload = response.json()
        except StoreItemNotFoundError:
            raise
        except requests.exceptions.Timeout as err:
            logger.warning("Store API get_details timeout: %s", err)
            raise StoreNetworkError(
                f"Store details request timed out after {self.timeout}s: {err}"
            ) from err
        except requests.exceptions.RequestException as err:
            logger.warning("Store API get_details network error: %s", err)
            raise StoreNetworkError(f"Network error during store get_details: {err}") from err
        except ValueError as err:
            logger.error("Invalid JSON response in get_details: %s", err)
            raise StoreError(f"Store API returned invalid JSON: {err}") from err

        if not isinstance(payload, dict):
            raise StoreError("Malformed API response: expected JSON object.")

        if "ocs" in payload and isinstance(payload["ocs"], dict):
            payload = payload["ocs"]

        data = payload.get("data", [])
        if not data or not isinstance(data, list) or not isinstance(data[0], dict):
            raise StoreItemNotFoundError(f"Store item '{clean_id}' not found in API response.")

        return self._parse_item_dict(data[0])

    def download(
        self,
        item_id: str | int,
        dest_dir: Path | str,
        file_index: int = 1,
        file_name: str | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
    ) -> Path:
        """Download an archive/package file associated with a store item.

        Args:
            item_id: Item identifier.
            dest_dir: Destination directory where the downloaded file will be saved.
            file_index: 1-indexed file number from the item's available download links.
            file_name: Optional explicit filename. If None, derived from API metadata or URL.
            progress_callback: Optional callback receiving (bytes_downloaded, total_bytes).

        Returns:
            Path of the saved downloaded archive file.

        Raises:
            StoreItemNotFoundError: If item does not exist.
            StoreDownloadError: If download fails, returns bad status, or has no download links.
            StoreNetworkError: If network connection drops or times out.
        """
        dest_path_dir = Path(dest_dir).resolve()
        dest_path_dir.mkdir(parents=True, exist_ok=True)

        details = self.get_details(item_id)
        if not details.files:
            raise StoreDownloadError(f"No download files available for store item '{item_id}'.")

        # Find matching file by index or take the first available
        target_file: StoreDownloadFile | None = None
        for f in details.files:
            if f.file_index == file_index:
                target_file = f
                break

        if target_file is None:
            target_file = details.files[0]
            logger.debug(
                "Requested file_index %d not found; falling back to index %d (%s)",
                file_index,
                target_file.file_index,
                target_file.name,
            )

        download_url = target_file.download_url
        if not download_url:
            raise StoreDownloadError(
                f"Store item '{item_id}' file index {file_index} has an empty download URL."
            )

        resolved_filename = (
            file_name.strip()
            if file_name and file_name.strip()
            else (target_file.name.strip() or self._extract_filename_from_url(download_url))
        )
        if not resolved_filename:
            resolved_filename = f"theme_{item_id}_{target_file.file_index}.tar.gz"

        # Sanitize filename
        resolved_filename = re.sub(r'[\\/*?:"<>|]', "_", resolved_filename)
        output_file_path = dest_path_dir / resolved_filename

        logger.debug(
            "Downloading file for store item '%s' from '%s' to '%s'",
            item_id,
            download_url,
            output_file_path,
        )

        try:
            with self._session.get(
                download_url, stream=True, timeout=self.timeout, allow_redirects=True
            ) as res:
                res.raise_for_status()

                total_size: int | None = None
                content_len_header = res.headers.get("Content-Length")
                if content_len_header and content_len_header.isdigit():
                    total_size = int(content_len_header)

                bytes_downloaded = 0
                chunk_size = 256 * 1024  # 256 KB

                with open(output_file_path, "wb") as f_out:
                    for chunk in res.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f_out.write(chunk)
                            bytes_downloaded += len(chunk)
                            if progress_callback is not None:
                                progress_callback(bytes_downloaded, total_size)

        except requests.exceptions.Timeout as err:
            logger.warning("Download timeout for item %s: %s", item_id, err)
            if output_file_path.exists():
                output_file_path.unlink(missing_ok=True)
            raise StoreNetworkError(f"Download timed out after {self.timeout}s: {err}") from err
        except requests.exceptions.RequestException as err:
            logger.warning("Download network error for item %s: %s", item_id, err)
            if output_file_path.exists():
                output_file_path.unlink(missing_ok=True)
            raise StoreDownloadError(f"Failed to download store item '{item_id}': {err}") from err
        except OSError as err:
            logger.error("Filesystem write error during download: %s", err)
            if output_file_path.exists():
                output_file_path.unlink(missing_ok=True)
            raise StoreDownloadError(
                f"Filesystem error saving download to '{output_file_path}': {err}"
            ) from err

        if not output_file_path.exists() or output_file_path.stat().st_size == 0:
            if output_file_path.exists():
                output_file_path.unlink(missing_ok=True)
            raise StoreDownloadError(
                f"Downloaded file for item '{item_id}' is empty or was not created."
            )

        logger.info(
            "Successfully downloaded '%s' (%d bytes) to '%s'",
            details.name,
            output_file_path.stat().st_size,
            output_file_path,
        )
        return output_file_path

    def _parse_item_dict(self, raw: dict[str, Any]) -> StoreItem:
        """Parse raw OCS dictionary into a structured StoreItem object."""
        item_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "")).strip()
        version = str(raw.get("version", "")).strip()
        author = str(raw.get("personid", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        description = str(raw.get("description", "")).strip()
        details_url = str(raw.get("detailpage", "") or raw.get("homepage", "")).strip()
        created = str(raw.get("created", "")).strip()
        updated = str(raw.get("changed", "")).strip()
        xdg_type = str(raw.get("xdg_type", "")).strip()
        type_name = str(raw.get("typename", "")).strip()

        type_id = 0
        raw_type_id = raw.get("typeid")
        if raw_type_id is not None and str(raw_type_id).isdigit():
            type_id = int(raw_type_id)

        rating = 0
        raw_score = raw.get("score")
        if raw_score is not None and str(raw_score).isdigit():
            rating = int(raw_score)

        downloads = 0
        raw_downloads = raw.get("downloads")
        if raw_downloads is not None and str(raw_downloads).isdigit():
            downloads = int(raw_downloads)

        # Parse preview images with high-resolution master URL normalization
        preview_images: list[str] = []
        for i in range(1, 30):
            pic_url = str(raw.get(f"previewpic{i}", "")).strip()
            if pic_url and pic_url.startswith("http"):
                high_res_url = re.sub(r"/cache/[^/]+/", "/", pic_url)
                if high_res_url not in preview_images:
                    preview_images.append(high_res_url)

        # Also extract embedded images from HTML description if available
        if description:
            for img_url in re.findall(
                r'<img[^>]+src=["\'](https?://[^"\']+)["\']', description, re.IGNORECASE
            ):
                clean_img = re.sub(r"/cache/[^/]+/", "/", img_url.strip())
                if clean_img and clean_img not in preview_images:
                    preview_images.append(clean_img)

        preview_image_url = preview_images[0] if preview_images else ""
        small_preview_image_url = str(raw.get("smallpreviewpic1", "")).strip()
        if small_preview_image_url:
            small_preview_image_url = re.sub(r"/cache/[^/]+/", "/", small_preview_image_url)
        if not small_preview_image_url and preview_image_url:
            small_preview_image_url = preview_image_url

        # Parse tags
        tags: list[str] = []
        raw_tags = raw.get("tags")
        if isinstance(raw_tags, str) and raw_tags.strip():
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

        # Parse downloadable files
        files: list[StoreDownloadFile] = []
        for i in range(1, 20):
            link_key = f"downloadlink{i}"
            if link_key not in raw:
                continue

            link = str(raw.get(link_key, "")).strip()
            if not link:
                continue

            fname = str(raw.get(f"downloadname{i}", "")).strip()
            if not fname:
                fname = self._extract_filename_from_url(link) or f"download_{i}.tar.gz"

            fsize = str(raw.get(f"downloadsize{i}", "")).strip()
            fver = str(raw.get(f"download_version{i}", "")).strip()
            fprice = str(raw.get(f"downloadprice{i}", "0")).strip()
            ftags = str(raw.get(f"downloadtags{i}", "")).strip()

            files.append(
                StoreDownloadFile(
                    file_index=i,
                    name=fname,
                    download_url=link,
                    size_str=fsize,
                    version=fver,
                    price=fprice,
                    mimetype=ftags,
                )
            )

        return StoreItem(
            id=item_id,
            name=name,
            version=version,
            author=author,
            type_id=type_id,
            type_name=type_name,
            summary=summary,
            description=description,
            rating=rating,
            downloads=downloads,
            created=created,
            updated=updated,
            details_url=details_url,
            preview_image_url=preview_image_url,
            small_preview_image_url=small_preview_image_url,
            preview_images=preview_images,
            files=files,
            tags=tags,
            xdg_type=xdg_type,
        )

    @staticmethod
    def _extract_filename_from_url(url: str) -> str:
        """Extract path filename from a URL."""
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            parts = path.rstrip("/").split("/")
            if parts:
                return parts[-1]
        except Exception:
            pass
        return ""
