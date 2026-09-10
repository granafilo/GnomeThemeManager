# SPDX-License-Identifier: GPL-3.0-or-later

"""GNOME Shell Extensions browser and management page controller.

Supports browsing local installed extensions, searching the online catalog
(extensions.gnome.org), checking for updates, filtering via dropdown, sorting,
and lazy loading.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

try:
    import requests

    _REQUESTS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False

from ...core.constants import STATE_DIR
from ...core.errors import ExtensionNetworkError
from ...core.extension_backend import EGO_BASE_URL, ExtensionItem, ExtensionSearchResult
from ...core.extensions import GnomeExtension
from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")

UI_FILE = Path(__file__).parent.parent / "ui" / "extensions_page.ui"
THUMBNAILS_CACHE_DIR = STATE_DIR / "extension_thumbnails"


def _get_icon_cache_path(url: str) -> Path:
    """Compute deterministic local file path for caching extension icon."""
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in (".png", ".svg", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    return THUMBNAILS_CACHE_DIR / f"icon_{url_hash}{ext}"


def _download_icon_bytes(url: str, timeout: float = 10.0) -> bytes | None:
    """Download icon bytes using requests if available, falling back to urllib."""
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GnomeThemeManager"}
    try:
        if _REQUESTS_AVAILABLE and requests is not None:
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200 and len(res.content) > 0:
                return res.content
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data: bytes = resp.read()
                return data if len(data) > 0 else None
    except Exception as err:
        logger.debug("Failed to download icon from %s: %s", url, err)
    return None


def _is_offline_error(err: Any) -> bool:
    """Determine whether an error is caused by missing internet connectivity."""
    if isinstance(err, ExtensionNetworkError):
        return True
    msg = str(err).lower()
    offline_keywords = (
        "network error",
        "offline",
        "temporary failure in name resolution",
        "nameresolutionerror",
        "connection refused",
        "timed out",
        "timeout",
        "network is unreachable",
        "no route to host",
        "connection reset",
    )
    return any(k in msg for k in offline_keywords)


def _clean_html_description(raw_html: str) -> str:
    """Convert HTML description from extensions API into clean readable text."""
    if not raw_html:
        return ""
    text = re.sub(r"<\s*br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def _format_downloads_count(count: int) -> str:
    """Format download count compactly (e.g. 1.2k, 3.4M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


class ExtensionsPage:
    """Controller for GNOME Shell Extensions management and browsing page."""

    PAGE_ID: str = "extensions"
    ICON_NAME: str = "application-x-addon-symbolic"

    FILTER_OPTIONS: ClassVar[list[tuple[str, str]]] = [
        (_("Installed"), "installed"),
        (_("Available"), "available"),
        (_("Updatable"), "updatable"),
    ]

    SORT_OPTIONS: ClassVar[list[tuple[str, str]]] = [
        (_("Popularity"), "popularity"),
        (_("Downloads"), "downloads"),
        (_("Latest"), "recent"),
    ]

    def __init__(self, manager: ThemeManager | None = None) -> None:
        """Initialize ExtensionsPage controller.

        Args:
            manager: Application ThemeManager instance.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = _("GNOME Extensions")
        self.icon_name: str = self.ICON_NAME
        self.manager: ThemeManager = manager or ThemeManager()

        # Notification & status callbacks
        self.on_loading_changed: Callable[[bool], None] | None = None
        self.on_notify_message: Callable[[str, bool], None] | None = None
        self.on_view_details: Callable[[ExtensionItem], None] | None = None

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.loading_page: Adw.StatusPage | None = self.builder.get_object("loading_page")
        self.header_title: Gtk.Label | None = self.builder.get_object("header_title")
        self.header_subtitle: Gtk.Label | None = self.builder.get_object("header_subtitle")
        self.btn_open_app: Gtk.Button = self.builder.get_object("btn_open_app")
        self.btn_browse_portal: Gtk.Button = self.builder.get_object("btn_browse_portal")
        self.scrolled_window: Gtk.ScrolledWindow | None = self.builder.get_object("scrolled_window")

        # Toolbar controls: search, filter dropdown, sort dropdown, refresh
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.filter_dropdown: Gtk.DropDown = self.builder.get_object("filter_dropdown")
        self.sort_dropdown: Gtk.DropDown = self.builder.get_object("sort_dropdown")
        self.btn_refresh: Gtk.Button = self.builder.get_object("btn_refresh")
        self.status_stack: Gtk.Stack = self.builder.get_object("status_stack")

        # Content groups
        self.user_extensions_group: Adw.PreferencesGroup = self.builder.get_object(
            "user_extensions_group"
        )
        self.system_extensions_group: Adw.PreferencesGroup = self.builder.get_object(
            "system_extensions_group"
        )
        self.remote_extensions_group: Adw.PreferencesGroup | None = self.builder.get_object(
            "remote_extensions_group"
        )

        # Lazy loading widgets
        self.lazy_load_box: Gtk.Box | None = self.builder.get_object("lazy_load_box")
        self.lazy_spinner: Gtk.Spinner | None = self.builder.get_object("lazy_spinner")
        self.btn_load_more: Gtk.Button | None = self.builder.get_object("btn_load_more")

        # Additional status pages
        self.empty_status_page: Adw.StatusPage = self.builder.get_object("empty_status_page")
        self.searching_status_page: Adw.StatusPage | None = self.builder.get_object(
            "searching_status_page"
        )
        self.error_status_page: Adw.StatusPage | None = self.builder.get_object("error_status_page")
        self.btn_error_retry: Gtk.Button | None = self.builder.get_object("btn_error_retry")
        self.offline_status_page: Adw.StatusPage | None = self.builder.get_object(
            "offline_status_page"
        )
        self.btn_offline_retry: Gtk.Button | None = self.builder.get_object("btn_offline_retry")
        self.btn_offline_switch_installed: Gtk.Button | None = self.builder.get_object(
            "btn_offline_switch_installed"
        )

        # Installation options widgets
        self.install_banner: Adw.Banner | None = self.builder.get_object("install_banner")
        self.group_install_manager: Adw.PreferencesGroup | None = self.builder.get_object(
            "group_install_manager"
        )
        self.expander_install_options: Adw.ExpanderRow | None = self.builder.get_object(
            "expander_install_options"
        )
        self.combo_install_method: Adw.ComboRow | None = self.builder.get_object(
            "combo_install_method"
        )
        self.row_install_command: Adw.ActionRow | None = self.builder.get_object(
            "row_install_command"
        )
        self.row_basic_app: Adw.ActionRow | None = self.builder.get_object("row_basic_app")
        self.btn_open_basic_app: Gtk.Button | None = self.builder.get_object("btn_open_basic_app")
        self.btn_copy_install_command: Gtk.Button | None = self.builder.get_object(
            "btn_copy_install_command"
        )

        # Detail view widgets
        self.view_stack: Gtk.Stack | None = self.builder.get_object("view_stack")
        self.btn_detail_back: Gtk.Button | None = self.builder.get_object("btn_detail_back")
        self.detail_icon_image: Gtk.Image | None = self.builder.get_object("detail_icon_image")
        self.detail_title_label: Gtk.Label | None = self.builder.get_object("detail_title_label")
        self.detail_creator_label: Gtk.Label | None = self.builder.get_object(
            "detail_creator_label"
        )
        self.detail_uuid_label: Gtk.Label | None = self.builder.get_object("detail_uuid_label")
        self.detail_meta_pills_box: Gtk.Box | None = self.builder.get_object(
            "detail_meta_pills_box"
        )
        self.detail_compat_banner: Adw.Banner | None = self.builder.get_object(
            "detail_compat_banner"
        )
        self.detail_screenshot_container: Gtk.Box | None = self.builder.get_object(
            "detail_screenshot_container"
        )
        self.btn_detail_prev_image: Gtk.Button | None = self.builder.get_object(
            "btn_detail_prev_image"
        )
        self.detail_screenshot_picture: Gtk.Picture | None = self.builder.get_object(
            "detail_screenshot_picture"
        )
        self.detail_image_counter_label: Gtk.Label | None = self.builder.get_object(
            "detail_image_counter_label"
        )
        self.btn_detail_fullscreen: Gtk.Button | None = self.builder.get_object(
            "btn_detail_fullscreen"
        )
        self.btn_detail_next_image: Gtk.Button | None = self.builder.get_object(
            "btn_detail_next_image"
        )
        self.detail_thumbnails_scrolled: Gtk.ScrolledWindow | None = self.builder.get_object(
            "detail_thumbnails_scrolled"
        )
        self.detail_thumbnails_box: Gtk.Box | None = self.builder.get_object(
            "detail_thumbnails_box"
        )
        self.detail_description_label: Gtk.Label | None = self.builder.get_object(
            "detail_description_label"
        )
        self.detail_progress_box: Gtk.Box | None = self.builder.get_object("detail_progress_box")
        self.detail_progress_spinner: Gtk.Spinner | None = self.builder.get_object(
            "detail_progress_spinner"
        )
        self.detail_progress_label: Gtk.Label | None = self.builder.get_object(
            "detail_progress_label"
        )
        self.btn_detail_website: Gtk.Button | None = self.builder.get_object("btn_detail_website")
        self.btn_detail_prefs: Gtk.Button | None = self.builder.get_object("btn_detail_prefs")
        self.detail_switch_box: Gtk.Box | None = self.builder.get_object("detail_switch_box")
        self.detail_switch_label: Gtk.Label | None = self.builder.get_object("detail_switch_label")
        self.detail_switch_enable: Gtk.Switch | None = self.builder.get_object(
            "detail_switch_enable"
        )
        self.btn_detail_remove: Gtk.Button | None = self.builder.get_object("btn_detail_remove")
        self.btn_detail_update: Gtk.Button | None = self.builder.get_object("btn_detail_update")
        self.btn_detail_install: Gtk.Button | None = self.builder.get_object("btn_detail_install")

        self._selected_item: ExtensionItem | None = None
        self._is_detail_action_in_progress: bool = False
        self._detail_images: list[str] = []
        self._detail_image_index: int = 0
        self._thumbnail_buttons: list[Gtk.Button] = []

        self._apply_localized_labels()
        self._init_dropdowns()

        # State tracking
        self._filter_mode: str = "installed"  # "installed" | "available" | "updatable"
        self._extensions: list[GnomeExtension] = []
        self._filtered_extensions: list[GnomeExtension] = []
        self._remote_items: list[ExtensionItem] = []
        self._install_options: list[dict[str, str]] = []
        self._is_loading: bool = False
        self._is_loading_remote: bool = False
        self._is_loading_more: bool = False
        self._current_page: int = 1
        self._numpages: int = 1
        self._search_debounce_id: int = 0
        self._row_widgets: list[tuple[Adw.PreferencesGroup, Gtk.Widget]] = []
        self._remote_row_widgets: list[Gtk.Widget] = []

        self.widget.set_visible_child_name("loading")
        self._init_install_options()
        self._connect_signals()
        self._update_app_status()

    def _apply_localized_labels(self) -> None:
        """Explicitly apply localized strings to all widgets."""
        if self.loading_page is not None:
            self.loading_page.set_title(_("Loading extensions..."))
            self.loading_page.set_description(
                _("Scanning installed extensions across system and user directories.")
            )

        if self.header_title is not None:
            self.header_title.set_text(_("GNOME Extensions"))
        if self.header_subtitle is not None:
            self.header_subtitle.set_text(
                _("Manage, enable, and inspect installed GNOME Shell extensions.")
            )

        if self.btn_browse_portal is not None:
            self.btn_browse_portal.set_tooltip_text(_("Open official GNOME Extensions website"))

        if self.search_entry is not None:
            self.search_entry.set_placeholder_text(_("Search extensions..."))

        if self.filter_dropdown is not None:
            self.filter_dropdown.set_tooltip_text(_("Filter extensions"))

        if self.sort_dropdown is not None:
            self.sort_dropdown.set_tooltip_text(_("Sort extensions"))

        if self.btn_refresh is not None:
            self.btn_refresh.set_tooltip_text(_("Refresh extension list"))

        if self.user_extensions_group is not None:
            self.user_extensions_group.set_title(_("User Extensions"))
            self.user_extensions_group.set_description(
                _("Extensions installed in your user directory")
            )

        if self.system_extensions_group is not None:
            self.system_extensions_group.set_title(_("System and Built-in Extensions"))
            self.system_extensions_group.set_description(
                _("Integrated system extensions provided by GNOME Shell or system packages")
            )

        if self.remote_extensions_group is not None:
            self.remote_extensions_group.set_title(_("Available Extensions"))
            self.remote_extensions_group.set_description(
                _("Browse and install extensions from official catalog")
            )

        if self.empty_status_page is not None:
            self.empty_status_page.set_title(_("No Extensions Found"))
            self.empty_status_page.set_description(
                _("No extensions matched your filter or none are installed.")
            )

        if self.searching_status_page is not None:
            self.searching_status_page.set_title(_("Searching extensions..."))
            self.searching_status_page.set_description(_("Connecting to extensions catalog..."))

        if self.error_status_page is not None:
            self.error_status_page.set_title(_("Catalog Unavailable"))
            self.error_status_page.set_description(
                _("Unable to query online extensions catalog. Please try again later.")
            )

        if self.btn_error_retry is not None:
            self.btn_error_retry.set_label(_("Retry"))

        if self.offline_status_page is not None:
            self.offline_status_page.set_title(_("You Are Offline"))
            self.offline_status_page.set_description(
                _(
                    "An internet connection is required to browse the online catalog."
                    " You can still manage all your installed extensions."
                )
            )

        if self.btn_offline_retry is not None:
            self.btn_offline_retry.set_label(_("Retry Connection"))

        if self.btn_offline_switch_installed is not None:
            self.btn_offline_switch_installed.set_label(_("View Installed"))

        if self.btn_load_more is not None:
            self.btn_load_more.set_label(_("Load more extensions..."))

        if self.group_install_manager is not None:
            self.group_install_manager.set_title(_("Extension Manager"))
            self.group_install_manager.set_description(
                _("Options and commands to install or manage GNOME Extension Manager.")
            )

        if self.row_install_command is not None:
            self.row_install_command.set_title(_("Terminal Command"))

        if self.row_basic_app is not None:
            self.row_basic_app.set_title(_("GNOME Extensions (Basic)"))
            self.row_basic_app.set_subtitle(_("Launch standard GNOME Extensions utility"))

        if self.btn_open_basic_app is not None:
            self.btn_open_basic_app.set_label(_("Open"))

        if self.combo_install_method is not None:
            self.combo_install_method.set_title(_("Installation Method"))

        if self.btn_copy_install_command is not None:
            self.btn_copy_install_command.set_tooltip_text(_("Copy installation command"))

        if self.btn_detail_back is not None:
            self.btn_detail_back.set_label(_("← Back to Extensions"))
        if self.detail_compat_banner is not None:
            self.detail_compat_banner.set_title(
                _(
                    "This extension does not officially support your GNOME Shell version."
                    " Installation may cause instability."
                )
            )
        if self.btn_detail_website is not None:
            self.btn_detail_website.set_label(_("Website"))
        if self.btn_detail_prefs is not None:
            self.btn_detail_prefs.set_label(_("Settings"))
        if self.detail_switch_label is not None:
            self.detail_switch_label.set_label(_("Enabled"))
        if self.btn_detail_remove is not None:
            self.btn_detail_remove.set_label(_("Uninstall"))
        if self.btn_detail_update is not None:
            self.btn_detail_update.set_label(_("Update Extension"))
        if self.btn_detail_install is not None:
            self.btn_detail_install.set_label(_("Install"))

    def _init_dropdowns(self) -> None:
        """Initialize filter and sort dropdown options."""
        if self.filter_dropdown is not None:
            filter_model = Gtk.StringList.new([name for name, _ in self.FILTER_OPTIONS])
            self.filter_dropdown.set_model(filter_model)
            self.filter_dropdown.set_selected(0)

        if self.sort_dropdown is not None:
            sort_model = Gtk.StringList.new([name for name, _ in self.SORT_OPTIONS])
            self.sort_dropdown.set_model(sort_model)
            self.sort_dropdown.set_selected(0)

    @property
    def is_loading(self) -> bool:
        """Return whether extension loading is active."""
        return self._is_loading or self._is_loading_remote

    def get_widget(self) -> Gtk.Stack:
        """Return root widget container."""
        return self.widget

    def _connect_signals(self) -> None:
        """Connect UI widget signals."""
        self.btn_refresh.connect("clicked", lambda _: self.refresh())
        self.btn_open_app.connect("clicked", lambda _: self._on_app_button_clicked())
        if self.btn_open_basic_app is not None:
            self.btn_open_basic_app.connect("clicked", lambda _: self._open_basic_app())
        if self.install_banner is not None:
            self.install_banner.connect("button-clicked", self._on_copy_install_command)
        if self.combo_install_method is not None:
            self.combo_install_method.connect(
                "notify::selected", lambda *_: self._on_install_method_changed()
            )
        if self.btn_copy_install_command is not None:
            self.btn_copy_install_command.connect(
                "clicked", lambda *_: self._on_copy_install_command()
            )
        self.btn_browse_portal.connect("clicked", lambda _: self._open_portal())
        self.search_entry.connect("search-changed", self._on_search_changed)

        # Dropdowns
        if self.filter_dropdown is not None:
            self.filter_dropdown.connect("notify::selected", lambda *_: self._on_filter_changed())
        if self.sort_dropdown is not None:
            self.sort_dropdown.connect("notify::selected", lambda *_: self._on_sort_changed())

        # Lazy loading
        if self.btn_load_more is not None:
            self.btn_load_more.connect("clicked", lambda _: self._load_more_results())
        if self.scrolled_window is not None:
            adj = self.scrolled_window.get_vadjustment()
            if adj is not None:
                adj.connect("value-changed", self._on_scroll_value_changed)

        # Error and offline retry
        if self.btn_error_retry is not None:
            self.btn_error_retry.connect("clicked", lambda _: self.refresh())
        if self.btn_offline_retry is not None:
            self.btn_offline_retry.connect("clicked", lambda _: self.refresh())
        if self.btn_offline_switch_installed is not None:
            self.btn_offline_switch_installed.connect(
                "clicked", lambda _: self._switch_to_installed_filter()
            )

        # Detail view signals
        if self.btn_detail_back is not None:
            self.btn_detail_back.connect("clicked", lambda _: self.show_catalog())
        if self.btn_detail_prev_image is not None:
            self.btn_detail_prev_image.connect("clicked", lambda _: self._navigate_image(-1))
        if self.btn_detail_next_image is not None:
            self.btn_detail_next_image.connect("clicked", lambda _: self._navigate_image(1))
        if self.btn_detail_fullscreen is not None:
            self.btn_detail_fullscreen.connect("clicked", lambda _: self._open_fullscreen_dialog())
        if self.detail_screenshot_picture is not None:
            click_gesture = Gtk.GestureClick.new()
            click_gesture.connect("released", lambda *_: self._open_fullscreen_dialog())
            self.detail_screenshot_picture.add_controller(click_gesture)
        if self.btn_detail_website is not None:
            self.btn_detail_website.connect("clicked", lambda _: self._on_detail_website_clicked())
        if self.btn_detail_prefs is not None:
            self.btn_detail_prefs.connect("clicked", lambda _: self._on_detail_prefs_clicked())
        if self.detail_switch_enable is not None:
            self.detail_switch_enable.connect("state-set", self._on_detail_switch_state_set)
        if self.btn_detail_remove is not None:
            self.btn_detail_remove.connect("clicked", lambda _: self._on_detail_remove_clicked())
        if self.btn_detail_update is not None:
            self.btn_detail_update.connect("clicked", lambda _: self._on_detail_update_clicked())
        if self.btn_detail_install is not None:
            self.btn_detail_install.connect("clicked", lambda _: self._on_detail_install_clicked())

    def _on_filter_changed(self) -> None:
        """Handle selection change in filter dropdown."""
        if not self.filter_dropdown:
            return
        idx = self.filter_dropdown.get_selected()
        if 0 <= idx < len(self.FILTER_OPTIONS):
            mode = self.FILTER_OPTIONS[idx][1]
            self._set_filter_mode(mode)

    def _switch_to_installed_filter(self) -> None:
        """Switch filter view to installed extensions."""
        if self.filter_dropdown is not None:
            self.filter_dropdown.set_selected(0)
        else:
            self._set_filter_mode("installed")

    def _on_sort_changed(self) -> None:
        """Handle selection change in sort dropdown."""
        if self._filter_mode == "available":
            self._perform_remote_search(reset_page=True)

    def _set_filter_mode(self, mode: str) -> None:
        """Switch active filter mode and reload view."""
        self._filter_mode = mode
        if mode == "installed":
            if self.sort_dropdown is not None:
                self.sort_dropdown.set_visible(False)
            self.user_extensions_group.set_visible(True)
            self.system_extensions_group.set_visible(True)
            if self.remote_extensions_group is not None:
                self.remote_extensions_group.set_visible(False)
            if self.lazy_load_box is not None:
                self.lazy_load_box.set_visible(False)
            self._update_app_status()
            self._filter_extensions(self.search_entry.get_text().strip())
        elif mode == "available":
            if self.sort_dropdown is not None:
                self.sort_dropdown.set_visible(True)
            self.user_extensions_group.set_visible(False)
            self.system_extensions_group.set_visible(False)
            if self.group_install_manager is not None:
                self.group_install_manager.set_visible(False)
            if self.install_banner is not None:
                self.install_banner.set_revealed(False)
            if self.remote_extensions_group is not None:
                self.remote_extensions_group.set_title(_("Available Extensions"))
                self.remote_extensions_group.set_description(
                    _("Browse and install extensions from official catalog")
                )
                self.remote_extensions_group.set_visible(True)
            self._perform_remote_search(reset_page=True)
        elif mode == "updatable":
            if self.sort_dropdown is not None:
                self.sort_dropdown.set_visible(False)
            self.user_extensions_group.set_visible(False)
            self.system_extensions_group.set_visible(False)
            if self.group_install_manager is not None:
                self.group_install_manager.set_visible(False)
            if self.install_banner is not None:
                self.install_banner.set_revealed(False)
            if self.lazy_load_box is not None:
                self.lazy_load_box.set_visible(False)
            if self.remote_extensions_group is not None:
                self.remote_extensions_group.set_title(_("Updatable Extensions"))
                self.remote_extensions_group.set_description(
                    _("Extensions with a newer version available on catalog")
                )
                self.remote_extensions_group.set_visible(True)
            self._perform_updatable_check()

    def _init_install_options(self) -> None:
        """Initialize installation choices in the combo dropdown."""
        self._install_options = []
        if hasattr(self.manager, "get_extension_manager_install_options"):
            try:
                self._install_options = self.manager.get_extension_manager_install_options()
            except Exception as err:
                logger.debug("Failed to get extension manager options: %s", err)

        if not self._install_options:
            cmd = self.manager.get_install_command("extension-manager")
            self._install_options = [
                {
                    "id": "system",
                    "name": _("Extension Manager (System Package)"),
                    "command": cmd,
                    "description": _("Recommended native package for Extension Manager."),
                }
            ]

        if self.combo_install_method is not None:
            names: list[str] = []
            for opt in self._install_options:
                opt_id = opt.get("id", "")
                name = opt.get("name", opt_id)
                if opt_id == "system":
                    name = _("Extension Manager (System Package)")
                elif opt_id == "flatpak":
                    name = _("Extension Manager (Flatpak Flathub)")
                elif opt_id == "gnome-extensions-app":
                    name = _("GNOME Extensions Basic (without online browsing)")
                names.append(name)

            self.combo_install_method.set_model(Gtk.StringList.new(names))
            self.combo_install_method.set_selected(0)
            self._on_install_method_changed()

    def _on_install_method_changed(self) -> None:
        """Update displayed terminal command and subtitle when installation method changes."""
        if not self.combo_install_method or not self._install_options:
            return
        idx = self.combo_install_method.get_selected()
        if 0 <= idx < len(self._install_options):
            opt = self._install_options[idx]
            cmd = opt.get("command", "")
            desc = opt.get("description", "")
            opt_id = opt.get("id", "")
            if opt_id == "system":
                desc = _("Recommended native package for Extension Manager.")
            elif opt_id == "flatpak":
                desc = _("Official Extension Manager release in sandbox from Flathub.")
            elif opt_id == "gnome-extensions-app":
                desc = _("Basic GNOME Extensions utility without online extension browsing.")

            if self.row_install_command is not None:
                self.row_install_command.set_subtitle(cmd)
            if self.combo_install_method is not None and desc:
                self.combo_install_method.set_subtitle(desc)

    def _get_active_install_command(self) -> str:
        """Return the currently selected installation command from options."""
        if self._install_options:
            idx = 0
            if self.combo_install_method is not None:
                idx = self.combo_install_method.get_selected()
            if 0 <= idx < len(self._install_options):
                return self._install_options[idx].get("command", "")
        return self.manager.get_install_command("extension-manager")

    def refresh(self) -> None:
        """Reload extensions based on current filter mode."""
        if self._filter_mode == "installed":
            self._reload_installed_extensions()
        elif self._filter_mode == "available":
            self._perform_remote_search(reset_page=True)
        elif self._filter_mode == "updatable":
            self._perform_updatable_check()

    def _reload_installed_extensions(self) -> None:
        """Reload installed extensions asynchronously."""
        if self._is_loading:
            return

        self._is_loading = True
        self.widget.set_visible_child_name("loading")
        if self.on_loading_changed:
            self.on_loading_changed(True)

        def worker() -> None:
            extensions: list[GnomeExtension] = []
            try:
                if self.manager.extensions:
                    extensions = self.manager.extensions.list_extensions()
            except Exception as err:
                logger.error("Failed to list extensions: %s", err)
            finally:
                GLib.idle_add(self._on_extensions_loaded, extensions)

        threading.Thread(target=worker, daemon=True).start()

    def _on_extensions_loaded(self, extensions: list[GnomeExtension]) -> bool:
        """Process extensions loaded from background thread."""
        self._is_loading = False
        if self.on_loading_changed:
            self.on_loading_changed(False)

        self._extensions = extensions
        self._filter_extensions(self.search_entry.get_text().strip())
        self._update_app_status()
        self.widget.set_visible_child_name("ready")
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filter extensions when search query changes."""
        query = entry.get_text().strip()
        if self._filter_mode == "installed":
            self._filter_extensions(query)
        else:
            # Debounce remote search by 350ms
            if self._search_debounce_id > 0:
                GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = GLib.timeout_add(350, self._on_remote_search_timeout)

    def _on_remote_search_timeout(self) -> bool:
        """Execute debounced remote search."""
        self._search_debounce_id = 0
        if self._filter_mode == "available":
            self._perform_remote_search(reset_page=True)
        elif self._filter_mode == "updatable":
            self._filter_updatable_rows(self.search_entry.get_text().strip())
        return False

    def _filter_extensions(self, query: str) -> None:
        """Filter cached installed extensions list and update UI rows."""
        q = query.lower()
        if not q:
            self._filtered_extensions = list(self._extensions)
        else:
            self._filtered_extensions = [
                ext
                for ext in self._extensions
                if q in ext.name.lower() or q in ext.uuid.lower() or q in ext.description.lower()
            ]

        self._render_extensions_list()

    def _render_extensions_list(self) -> None:
        """Populate user and system AdwPreferencesGroups with filtered extension rows."""
        # Clear existing rows
        for group, row in self._row_widgets:
            group.remove(row)
        self._row_widgets.clear()

        if not self._filtered_extensions:
            self.empty_status_page.set_title(_("No Extensions Found"))
            self.empty_status_page.set_description(
                _("No extensions matched your filter or none are installed.")
            )
            self.status_stack.set_visible_child_name("empty")
            return

        user_count = 0
        system_count = 0

        for ext in self._filtered_extensions:
            expander = Adw.ExpanderRow()
            expander.set_title(GLib.markup_escape_text(ext.name))
            expander.set_subtitle(GLib.markup_escape_text(ext.uuid))

            # Header Suffixes container: Settings button on left + Switch on right
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            header_box.set_valign(Gtk.Align.CENTER)

            if ext.has_prefs:
                btn_prefs = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
                btn_prefs.set_valign(Gtk.Align.CENTER)
                btn_prefs.add_css_class("flat")
                btn_prefs.set_tooltip_text(_("Extension Settings"))
                btn_prefs.connect("clicked", lambda _, u=ext.uuid: self._open_prefs(u))
                header_box.append(btn_prefs)

            switch = Gtk.Switch()
            switch.set_active(ext.enabled)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect(
                "state-set",
                lambda _sw, state, e=ext: self._on_switch_state_set(e, state),
            )
            header_box.append(switch)
            expander.add_suffix(header_box)

            # Expanded Child 1: Description
            row_desc = Adw.ActionRow()
            row_desc.set_title(_("Description"))
            clean_desc = (ext.description or _("No description provided.")).strip()
            row_desc.set_subtitle(GLib.markup_escape_text(clean_desc))
            row_desc.set_subtitle_lines(0)
            expander.add_row(row_desc)

            # Expanded Child 2: Version
            row_ver = Adw.ActionRow()
            row_ver.set_title(_("Version"))
            row_ver.set_subtitle(GLib.markup_escape_text(str(ext.version or _("Unknown"))))
            expander.add_row(row_ver)

            # Expanded Child 3: Actions (Details link + Remove button)
            row_actions = Adw.ActionRow()
            link_url = ext.url or (
                self.manager.extensions.get_store_url(ext.uuid) if self.manager.extensions else ""
            )
            # Create ExtensionItem representation for local extension
            ext_item = ExtensionItem(
                uuid=ext.uuid,
                name=ext.name,
                description=ext.description,
                version=ext.version,
                installed_version=ext.version,
                is_installed=True,
                is_enabled=ext.enabled,
                is_compatible=True,
                link=link_url,
            )
            btn_details = Gtk.Button(label=_("Details"))
            btn_details.set_valign(Gtk.Align.CENTER)
            btn_details.add_css_class("flat")
            btn_details.set_tooltip_text(_("View extension details"))
            btn_details.connect("clicked", lambda _, it=ext_item: self._on_view_item_details(it))
            row_actions.add_suffix(btn_details)

            if ext.is_user_level:
                btn_remove = Gtk.Button(label=_("Remove"))
                btn_remove.set_valign(Gtk.Align.CENTER)
                btn_remove.add_css_class("destructive-action")
                btn_remove.set_tooltip_text(_("Uninstall this extension"))
                btn_remove.connect("clicked", lambda _, e=ext: self._on_remove_extension(e))
                row_actions.add_suffix(btn_remove)

            expander.add_row(row_actions)

            target_group = (
                self.user_extensions_group if ext.is_user_level else self.system_extensions_group
            )
            target_group.add(expander)
            self._row_widgets.append((target_group, expander))

            if ext.is_user_level:
                user_count += 1
            else:
                system_count += 1

        self.user_extensions_group.set_visible(user_count > 0)
        self.system_extensions_group.set_visible(system_count > 0)
        self.status_stack.set_visible_child_name("content")

    # --- Online Catalog & Remote Search (Step 2) ---

    def _perform_remote_search(self, reset_page: bool = True) -> None:
        """Search extensions from extensions.gnome.org asynchronously."""
        if self._is_loading_remote:
            return

        if reset_page:
            self._current_page = 1
            self._remote_items.clear()
            self._clear_remote_rows()
            self.status_stack.set_visible_child_name("searching")

        self._is_loading_remote = True
        if self.on_loading_changed:
            self.on_loading_changed(True)
        query = self.search_entry.get_text().strip()
        page = self._current_page

        # Get sort order from dropdown
        sort_by = "popularity"
        if self.sort_dropdown is not None:
            sort_idx = self.sort_dropdown.get_selected()
            if 0 <= sort_idx < len(self.SORT_OPTIONS):
                sort_by = self.SORT_OPTIONS[sort_idx][1]

        def worker() -> None:
            backend = self.manager.extension_backend
            try:
                result = backend.search(query=query, sort=sort_by, page=page, limit=20)
                GLib.idle_add(self._on_remote_search_success, result, reset_page)
            except Exception as err:
                logger.error("Remote search error: %s", err)
                is_off = _is_offline_error(err)
                GLib.idle_add(self._on_remote_search_error, str(err), is_off)

        threading.Thread(target=worker, daemon=True).start()

    def _on_remote_search_success(self, result: ExtensionSearchResult, reset_page: bool) -> bool:
        """Handle successful response from remote catalog."""
        self._is_loading_remote = False
        self._is_loading_more = False
        if self.on_loading_changed:
            self.on_loading_changed(False)
        self._current_page = result.page
        self._numpages = result.numpages

        if reset_page:
            self._remote_items = list(result.extensions)
            self._clear_remote_rows()
        else:
            self._remote_items.extend(result.extensions)

        if not self._remote_items:
            self.empty_status_page.set_title(_("No Extensions Found"))
            self.empty_status_page.set_description(
                _("No extensions matched your filter or search query.")
            )
            self.status_stack.set_visible_child_name("empty")
            if self.lazy_load_box is not None:
                self.lazy_load_box.set_visible(False)
            return False

        for item in result.extensions:
            row = self._create_remote_extension_row(item)
            if self.remote_extensions_group is not None:
                self.remote_extensions_group.add(row)
                self._remote_row_widgets.append(row)

        self.status_stack.set_visible_child_name("content")

        has_more = self._current_page < self._numpages
        if self.lazy_load_box is not None:
            self.lazy_load_box.set_visible(has_more)
        if self.btn_load_more is not None:
            self.btn_load_more.set_visible(has_more)
            self.btn_load_more.set_sensitive(True)
            self.btn_load_more.set_label(_("Load more extensions..."))
        if self.lazy_spinner is not None:
            self.lazy_spinner.set_spinning(False)
            self.lazy_spinner.set_visible(False)

        return False

    def _on_remote_search_error(self, err_msg: str, is_offline: bool = False) -> bool:
        """Handle error querying online catalog."""
        self._is_loading_remote = False
        self._is_loading_more = False
        if self.on_loading_changed:
            self.on_loading_changed(False)

        if is_offline or _is_offline_error(err_msg):
            self.status_stack.set_visible_child_name("offline")
        else:
            if self.error_status_page is not None:
                self.error_status_page.set_description(
                    _("Unable to query online extensions catalog: {err}").format(err=err_msg)
                )
            self.status_stack.set_visible_child_name("error")

        if self.lazy_load_box is not None:
            self.lazy_load_box.set_visible(False)
        return False

    def _load_more_results(self) -> None:
        """Request next page of catalog results (lazy loading)."""
        if self._filter_mode != "available":
            return
        if self._is_loading_remote or self._is_loading_more:
            return
        if self._current_page >= self._numpages:
            return

        self._is_loading_more = True
        self._current_page += 1
        if self.lazy_spinner is not None:
            self.lazy_spinner.set_visible(True)
            self.lazy_spinner.set_spinning(True)
        if self.btn_load_more is not None:
            self.btn_load_more.set_label(_("Loading more..."))
            self.btn_load_more.set_sensitive(False)

        self._perform_remote_search(reset_page=False)

    def _on_scroll_value_changed(self, adj: Gtk.Adjustment) -> None:
        """Trigger lazy loading when scrolling reaches near bottom."""
        if self._filter_mode != "available":
            return
        if self._is_loading_remote or self._is_loading_more:
            return
        if self._current_page >= self._numpages:
            return

        # Trigger when within 100px of bottom
        if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 100:
            self._load_more_results()

    def _perform_updatable_check(self) -> None:
        """Check for updates for installed extensions."""
        self.status_stack.set_visible_child_name("searching")
        self._clear_remote_rows()
        if self.on_loading_changed:
            self.on_loading_changed(True)

        def worker() -> None:
            backend = self.manager.extension_backend
            try:
                items = backend.check_updates()
                GLib.idle_add(self._on_updatable_loaded, items)
            except Exception as err:
                logger.error("Error checking updates: %s", err)
                is_off = _is_offline_error(err)
                GLib.idle_add(self._on_remote_search_error, str(err), is_off)

        threading.Thread(target=worker, daemon=True).start()

    def _on_updatable_loaded(self, items: list[ExtensionItem]) -> bool:
        """Populate view with updatable extensions."""
        if self.on_loading_changed:
            self.on_loading_changed(False)
        self._remote_items = list(items)
        self._filter_updatable_rows(self.search_entry.get_text().strip())
        return False

    def _filter_updatable_rows(self, query: str) -> None:
        """Filter cached updatable items by search query."""
        self._clear_remote_rows()
        q = query.lower()
        filtered = [
            it
            for it in self._remote_items
            if not q or q in it.name.lower() or q in it.uuid.lower() or q in it.description.lower()
        ]

        if not filtered:
            self.empty_status_page.set_title(_("All Extensions Up to Date"))
            self.empty_status_page.set_description(
                _("No updates available for your installed extensions.")
            )
            self.status_stack.set_visible_child_name("empty")
            return

        for item in filtered:
            row = self._create_remote_extension_row(item)
            if self.remote_extensions_group is not None:
                self.remote_extensions_group.add(row)
                self._remote_row_widgets.append(row)

        self.status_stack.set_visible_child_name("content")

    def _clear_remote_rows(self) -> None:
        """Remove existing remote extension rows from UI."""
        if self.remote_extensions_group is not None:
            for row in self._remote_row_widgets:
                self.remote_extensions_group.remove(row)
        self._remote_row_widgets.clear()

    def _create_remote_extension_row(self, item: ExtensionItem) -> Adw.ActionRow:
        """Build an AdwActionRow representing an extension with icon, metadata, badges, and action."""
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(item.name))

        # Subtitle: version • creator/uuid • brief description snippet
        subtitle_parts: list[str] = []
        if item.version:
            subtitle_parts.append(f"v{item.version}")
        if item.creator:
            subtitle_parts.append(f"{_('by')} {item.creator}")
        elif item.uuid:
            subtitle_parts.append(item.uuid)

        desc = (item.description or "").split("\n")[0].strip()
        if len(desc) > 80:
            desc = desc[:77] + "..."
        if desc:
            subtitle_parts.append(desc)

        row.set_subtitle(GLib.markup_escape_text(" • ".join(subtitle_parts)))
        row.set_subtitle_lines(2)

        # Prefix: Extension Icon (async cached)
        img = Gtk.Image.new_from_icon_name("application-x-addon-symbolic")
        img.set_pixel_size(36)
        img.set_valign(Gtk.Align.CENTER)
        row.add_prefix(img)

        if item.icon_url:
            self._load_icon_async(item.icon_url, img)

        # Suffix 1: Downloads / Rating
        if item.rating is not None and item.rating > 0:
            box_stat = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            box_stat.set_valign(Gtk.Align.CENTER)
            star_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            star_icon.set_pixel_size(14)
            lbl_stat = Gtk.Label(label=f"{item.rating:.1f}")
            lbl_stat.add_css_class("dim-label")
            lbl_stat.add_css_class("caption")
            box_stat.append(star_icon)
            box_stat.append(lbl_stat)
            row.add_suffix(box_stat)
        elif item.downloads > 0:
            box_stat = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            box_stat.set_valign(Gtk.Align.CENTER)
            dl_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
            dl_icon.set_pixel_size(14)
            lbl_stat = Gtk.Label(label=_format_downloads_count(item.downloads))
            lbl_stat.add_css_class("dim-label")
            lbl_stat.add_css_class("caption")
            box_stat.append(dl_icon)
            box_stat.append(lbl_stat)
            row.add_suffix(box_stat)

        # Suffix 2: Compatibility badge
        lbl_compat = Gtk.Label()
        lbl_compat.set_valign(Gtk.Align.CENTER)
        lbl_compat.add_css_class("caption")
        if item.is_compatible:
            lbl_compat.set_text(_("Compatible"))
            lbl_compat.add_css_class("success")
        else:
            lbl_compat.set_text(_("Incompatible"))
            lbl_compat.add_css_class("error")
        row.add_suffix(lbl_compat)

        # Suffix 3: State / Action buttons
        if item.is_installed:
            lbl_inst = Gtk.Label(label=_("Installed"))
            lbl_inst.set_valign(Gtk.Align.CENTER)
            lbl_inst.add_css_class("accent")
            lbl_inst.add_css_class("caption")
            row.add_suffix(lbl_inst)

            if item.has_update:
                lbl_up = Gtk.Label(label=_("Update"))
                lbl_up.set_valign(Gtk.Align.CENTER)
                lbl_up.add_css_class("warning")
                lbl_up.add_css_class("caption")
                row.add_suffix(lbl_up)

            switch = Gtk.Switch()
            switch.set_active(item.is_enabled)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect(
                "state-set",
                lambda _sw, state, it=item: self._on_remote_switch_toggled(it, state),
            )
            row.add_suffix(switch)
        else:
            btn_details = Gtk.Button(label=_("Details"))
            btn_details.set_valign(Gtk.Align.CENTER)
            btn_details.add_css_class("flat")
            btn_details.set_tooltip_text(_("View extension details"))
            btn_details.connect("clicked", lambda _, it=item: self._on_view_item_details(it))
            row.add_suffix(btn_details)

        row.set_activatable(True)
        row.connect("activated", lambda _, it=item: self._on_view_item_details(it))
        return row

    def _load_icon_async(self, icon_url: str, img: Gtk.Image) -> None:
        """Download and set extension icon asynchronously with local disk caching."""

        def worker() -> None:
            try:
                THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_path = _get_icon_cache_path(icon_url)
                if not cache_path.is_file() or cache_path.stat().st_size == 0:
                    data = _download_icon_bytes(icon_url)
                    if data:
                        cache_path.write_bytes(data)

                if cache_path.is_file() and cache_path.stat().st_size > 0:
                    GLib.idle_add(img.set_from_file, str(cache_path))
            except Exception as err:
                logger.debug("Failed to cache icon %s: %s", icon_url, err)

        threading.Thread(target=worker, daemon=True).start()

    def _on_view_item_details(self, item: ExtensionItem) -> None:
        """Callback when an extension row or its Details button is activated."""
        self.show_details(item)
        if self.on_view_details:
            self.on_view_details(item)

    def show_catalog(self) -> None:
        """Switch view to the main catalog browsing page."""
        if hasattr(self, "view_stack") and self.view_stack is not None:
            self.view_stack.set_visible_child_name("catalog")

    def show_details(self, item: ExtensionItem) -> None:
        """Populate and display the details view for an extension."""
        self._selected_item = item

        if self.detail_title_label is not None:
            self.detail_title_label.set_text(item.name)
        if self.detail_creator_label is not None:
            creator_text = _("by {author}").format(author=item.creator) if item.creator else ""
            self.detail_creator_label.set_text(creator_text)
            self.detail_creator_label.set_visible(bool(creator_text))
        if self.detail_uuid_label is not None:
            self.detail_uuid_label.set_text(item.uuid)

        # Clean Description
        clean_desc = _clean_html_description(item.description or _("No description available."))
        if self.detail_description_label is not None:
            self.detail_description_label.set_text(clean_desc)

        # Meta pills
        if self.detail_meta_pills_box is not None:
            while child := self.detail_meta_pills_box.get_first_child():
                self.detail_meta_pills_box.remove(child)

            # Compatibility pill
            pill_compat = Gtk.Label()
            pill_compat.add_css_class("caption")
            if item.is_compatible:
                pill_compat.set_text(_("Compatible"))
                pill_compat.add_css_class("success")
            else:
                pill_compat.set_text(_("Incompatible"))
                pill_compat.add_css_class("error")
            self.detail_meta_pills_box.append(pill_compat)

            # Version pill
            if item.version or item.installed_version:
                v_text = str(item.version or item.installed_version)
                pill_ver = Gtk.Label(label=f"v{v_text}")
                pill_ver.add_css_class("caption")
                pill_ver.add_css_class("dim-label")
                self.detail_meta_pills_box.append(pill_ver)

            # Downloads pill
            if item.downloads > 0:
                d_text = _format_downloads_count(item.downloads)
                pill_dl = Gtk.Label(label=f"⬇ {d_text}")
                pill_dl.add_css_class("caption")
                pill_dl.add_css_class("dim-label")
                self.detail_meta_pills_box.append(pill_dl)

            # Popularity / Rating pill
            if item.rating is not None:
                pill_rate = Gtk.Label(label=f"★ {item.rating:.1f}")
                pill_rate.add_css_class("caption")
                pill_rate.add_css_class("dim-label")
                self.detail_meta_pills_box.append(pill_rate)

        # Compatibility banner
        if self.detail_compat_banner is not None:
            self.detail_compat_banner.set_revealed(not item.is_compatible)

        # Icon
        if self.detail_icon_image is not None:
            self.detail_icon_image.set_from_icon_name("application-x-addon-symbolic")
            if item.icon_url:
                self._load_icon_async(item.icon_url, self.detail_icon_image)

        # Screenshots gallery
        gallery_images: list[str] = []
        if item.screenshots:
            gallery_images = list(item.screenshots)
        elif item.screenshot_url:
            gallery_images = [item.screenshot_url]
        self._update_gallery_ui(gallery_images)

        # Reset progress box
        if self.detail_progress_box is not None:
            self.detail_progress_box.set_visible(False)

        self._update_detail_actions(item)

        # Background metadata enrichment for local extensions with minimal info
        if (
            (not item.screenshots or not item.screenshot_url)
            and item.uuid
            and self.manager.extension_backend
        ):

            def enrich_worker() -> None:
                try:
                    if self.manager.extension_backend:
                        full_details = self.manager.extension_backend.get_details(item.uuid)
                        if full_details:

                            def apply_enrich() -> None:
                                if self._selected_item and self._selected_item.uuid == item.uuid:
                                    if full_details.screenshots:
                                        item.screenshots = full_details.screenshots
                                    if full_details.screenshot_url:
                                        item.screenshot_url = full_details.screenshot_url
                                    new_images = (
                                        list(item.screenshots)
                                        if item.screenshots
                                        else ([item.screenshot_url] if item.screenshot_url else [])
                                    )
                                    if new_images:
                                        self._update_gallery_ui(new_images)
                                    if full_details.description and len(
                                        full_details.description
                                    ) > len(item.description):
                                        item.description = full_details.description
                                        if self.detail_description_label:
                                            self.detail_description_label.set_text(
                                                _clean_html_description(full_details.description)
                                            )
                                    if full_details.rating is not None and item.rating is None:
                                        item.rating = full_details.rating
                                    if full_details.downloads > 0 and item.downloads == 0:
                                        item.downloads = full_details.downloads

                            GLib.idle_add(apply_enrich)
                except Exception as err:
                    logger.debug("Failed background metadata enrichment for %s: %s", item.uuid, err)

            threading.Thread(target=enrich_worker, daemon=True).start()

        if hasattr(self, "view_stack") and self.view_stack is not None:
            self.view_stack.set_visible_child_name("detail")

    def _update_detail_actions(self, item: ExtensionItem) -> None:
        """Update action buttons on the detail page according to item state."""
        has_web = bool(item.link or item.uuid)
        if self.btn_detail_website is not None:
            self.btn_detail_website.set_visible(has_web)

        if item.is_installed:
            if self.btn_detail_install is not None:
                self.btn_detail_install.set_visible(False)

            if self.btn_detail_update is not None:
                self.btn_detail_update.set_visible(bool(item.has_update))

            if self.detail_switch_box is not None:
                self.detail_switch_box.set_visible(True)
            if self.detail_switch_enable is not None:
                self.detail_switch_enable.set_active(item.is_enabled)

            if self.btn_detail_remove is not None:
                self.btn_detail_remove.set_visible(True)
                self.btn_detail_remove.set_sensitive(True)

            can_configure = False
            if self.manager.extensions:
                local_ext = self.manager.extensions.get_extension(item.uuid)
                if local_ext and local_ext.has_prefs:
                    can_configure = True
            if self.btn_detail_prefs is not None:
                self.btn_detail_prefs.set_visible(can_configure)
        else:
            if self.btn_detail_update is not None:
                self.btn_detail_update.set_visible(False)
            if self.btn_detail_install is not None:
                self.btn_detail_install.set_visible(True)
                self.btn_detail_install.set_sensitive(True)

            if self.detail_switch_box is not None:
                self.detail_switch_box.set_visible(False)
            if self.btn_detail_remove is not None:
                self.btn_detail_remove.set_visible(False)
            if self.btn_detail_prefs is not None:
                self.btn_detail_prefs.set_visible(False)

    def _update_gallery_ui(self, images: list[str]) -> None:
        """Configure screenshot gallery, thumbnails and navigation for detail view."""
        self._detail_images = list(images)
        self._detail_image_index = 0

        if self.detail_thumbnails_box is not None:
            while child := self.detail_thumbnails_box.get_first_child():
                self.detail_thumbnails_box.remove(child)
        self._thumbnail_buttons.clear()

        has_images = bool(images)
        has_multiple = len(images) > 1

        if self.detail_screenshot_container is not None:
            self.detail_screenshot_container.set_visible(has_images)

        if self.btn_detail_prev_image is not None:
            self.btn_detail_prev_image.set_visible(has_multiple)
        if self.btn_detail_next_image is not None:
            self.btn_detail_next_image.set_visible(has_multiple)
        if self.detail_thumbnails_scrolled is not None:
            self.detail_thumbnails_scrolled.set_visible(has_multiple)
        if self.detail_image_counter_label is not None:
            self.detail_image_counter_label.set_visible(has_multiple)

        if has_multiple and self.detail_thumbnails_box is not None:
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

    def _set_active_screenshot_index(self, index: int) -> None:
        """Switch active displayed screenshot and highlight active thumbnail."""
        if not self._detail_images or index < 0 or index >= len(self._detail_images):
            return

        self._detail_image_index = index

        if len(self._detail_images) > 1:
            if self.detail_image_counter_label is not None:
                counter_str = _("Image {cur} of {tot}").format(
                    cur=index + 1, tot=len(self._detail_images)
                )
                self.detail_image_counter_label.set_text(counter_str)

            for i, btn in enumerate(self._thumbnail_buttons):
                if i == index:
                    btn.add_css_class("suggested-action")
                else:
                    btn.remove_css_class("suggested-action")

        if self.detail_screenshot_picture is not None:
            self._load_picture_async(self._detail_images[index], self.detail_screenshot_picture)

    def _navigate_image(self, delta: int) -> None:
        """Navigate to previous or next screenshot in gallery."""
        if not self._detail_images:
            return
        new_idx = (self._detail_image_index + delta) % len(self._detail_images)
        self._set_active_screenshot_index(new_idx)

    def _load_gallery_thumbnail_async(self, pic_widget: Gtk.Picture, img_url: str) -> None:
        """Download thumbnail in background and set on Gtk.Picture widget."""

        def worker() -> None:
            try:
                THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cached_path = _get_icon_cache_path(img_url)

                if not cached_path.is_file() or cached_path.stat().st_size == 0:
                    content = _download_icon_bytes(img_url, timeout=15.0)
                    if content:
                        cached_path.write_bytes(content)

                if cached_path.is_file() and cached_path.stat().st_size > 0:
                    GLib.idle_add(pic_widget.set_filename, str(cached_path))
            except Exception as err:
                logger.debug("Failed to load gallery thumbnail preview: %s", err)

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

            cached_path = _get_icon_cache_path(url)
            if cached_path.is_file() and cached_path.stat().st_size > 0:
                picture.set_filename(str(cached_path))
            else:
                self._load_picture_async(url, picture, on_loaded=lambda p: picture.set_filename(p))

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

    def _load_picture_async(
        self,
        url: str,
        picture: Gtk.Picture,
        on_loaded: Callable[[str], None] | None = None,
    ) -> None:
        """Download or fetch cached screenshot and set it on GtkPicture."""
        cache_path = _get_icon_cache_path(url)
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            picture.set_filename(str(cache_path))
            if on_loaded:
                on_loaded(str(cache_path))
            return

        def worker() -> None:
            try:
                data = _download_icon_bytes(url, timeout=15.0)
                if data:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(data)

                    def apply() -> None:
                        path_str = str(cache_path)
                        if self._selected_item and (
                            self._selected_item.screenshot_url == url or url in self._detail_images
                        ):
                            picture.set_filename(path_str)
                        if on_loaded:
                            on_loaded(path_str)

                    GLib.idle_add(apply)
            except Exception as err:
                logger.debug("Failed to cache screenshot %s: %s", url, err)

        threading.Thread(target=worker, daemon=True).start()

    def _show_confirmation_dialog(
        self,
        title: str,
        body: str,
        confirm_label: str,
        appearance: Any,
        parent_win: Gtk.Window | None,
        on_confirm: Callable[[], None],
    ) -> None:
        """Display confirmation dialog supporting Adw.MessageDialog or fallback."""
        if hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(parent_win, title, body)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("confirm", confirm_label)
            if appearance is not None:
                dialog.set_response_appearance("confirm", appearance)
            dialog.set_default_response("confirm")
            dialog.set_close_response("cancel")

            def on_response(_dlg: Any, response: str) -> None:
                if response == "confirm":
                    on_confirm()

            dialog.connect("response", on_response)
            dialog.present()
        else:
            on_confirm()

    def _on_detail_install_clicked(self) -> None:
        """Handle install button click with user confirmation."""
        item = self._selected_item
        if not item or self._is_detail_action_in_progress:
            return

        root_win = self.widget.get_root()
        parent_win = root_win if isinstance(root_win, Gtk.Window) else None

        title = _("Install Extension?")
        if item.is_compatible:
            body = _(
                "Do you want to download and install '{name}' ({uuid}) from extensions.gnome.org?"
            ).format(name=item.name, uuid=item.uuid)
        else:
            body = _(
                "Warning: '{name}' does not officially support your GNOME Shell version.\n\n"
                "Installation may cause errors or system instability.\n"
                "Do you still want to proceed?"
            ).format(name=item.name)

        appearance = (
            Adw.ResponseAppearance.SUGGESTED if hasattr(Adw, "ResponseAppearance") else None
        )
        self._show_confirmation_dialog(
            title=title,
            body=body,
            confirm_label=_("Install"),
            appearance=appearance,
            parent_win=parent_win,
            on_confirm=lambda: self._execute_install(item),
        )

    def _on_detail_update_clicked(self) -> None:
        """Handle update button click with user confirmation."""
        item = self._selected_item
        if not item or self._is_detail_action_in_progress:
            return

        root_win = self.widget.get_root()
        parent_win = root_win if isinstance(root_win, Gtk.Window) else None

        title = _("Update Extension?")
        version_str = f"v{item.version}" if item.version else ""
        body = _("Do you want to update '{name}' to version {version}?").format(
            name=item.name, version=version_str
        )

        appearance = (
            Adw.ResponseAppearance.SUGGESTED if hasattr(Adw, "ResponseAppearance") else None
        )
        self._show_confirmation_dialog(
            title=title,
            body=body,
            confirm_label=_("Update Extension"),
            appearance=appearance,
            parent_win=parent_win,
            on_confirm=lambda: self._execute_install(item, is_update=True),
        )

    def _execute_install(self, item: ExtensionItem, is_update: bool = False) -> None:
        """Perform asynchronous installation or update of an extension."""
        if not self.manager.extension_backend:
            return

        self._is_detail_action_in_progress = True
        if self.detail_progress_box is not None:
            self.detail_progress_box.set_visible(True)
        if self.detail_progress_spinner is not None:
            self.detail_progress_spinner.set_spinning(True)
        if self.detail_progress_label is not None:
            action_label = _("Updating extension...") if is_update else _("Installing extension...")
            self.detail_progress_label.set_text(action_label)

        if self.btn_detail_install is not None:
            self.btn_detail_install.set_sensitive(False)
        if self.btn_detail_update is not None:
            self.btn_detail_update.set_sensitive(False)

        def worker() -> None:
            success = False
            err_msg = ""
            try:
                if self.manager.extension_backend:
                    success = self.manager.extension_backend.install(item.uuid)
            except Exception as err:
                err_msg = str(err)
                logger.error("Failed installing/updating extension %s: %s", item.uuid, err)

            def finish() -> None:
                self._is_detail_action_in_progress = False
                if self.detail_progress_box is not None:
                    self.detail_progress_box.set_visible(False)
                if self.detail_progress_spinner is not None:
                    self.detail_progress_spinner.set_spinning(False)
                if self.btn_detail_install is not None:
                    self.btn_detail_install.set_sensitive(True)
                if self.btn_detail_update is not None:
                    self.btn_detail_update.set_sensitive(True)

                if success:
                    item.is_installed = True
                    item.is_enabled = True
                    item.has_update = False
                    if self.manager.extensions:
                        self.manager.extensions.list_extensions()
                    self._update_detail_actions(item)
                    self._sync_item_in_catalog(item)
                    msg = (
                        _("Extension '{name}' updated successfully.").format(name=item.name)
                        if is_update
                        else _("Extension '{name}' installed successfully.").format(name=item.name)
                    )
                    if self.on_notify_message:
                        self.on_notify_message(msg, False)
                else:
                    msg = _("Failed to install extension '{name}': {error}").format(
                        name=item.name, error=err_msg or _("Unknown error")
                    )
                    if self.on_notify_message:
                        self.on_notify_message(msg, True)

            GLib.idle_add(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_detail_remove_clicked(self) -> None:
        """Handle remove button click with user confirmation."""
        item = self._selected_item
        if not item or self._is_detail_action_in_progress:
            return

        root_win = self.widget.get_root()
        parent_win = root_win if isinstance(root_win, Gtk.Window) else None

        title = _("Uninstall Extension?")
        body = _("Are you sure you want to uninstall '{name}' ({uuid})?").format(
            name=item.name, uuid=item.uuid
        )

        appearance = (
            Adw.ResponseAppearance.DESTRUCTIVE if hasattr(Adw, "ResponseAppearance") else None
        )
        self._show_confirmation_dialog(
            title=title,
            body=body,
            confirm_label=_("Uninstall"),
            appearance=appearance,
            parent_win=parent_win,
            on_confirm=lambda: self._execute_remove(item),
        )

    def _execute_remove(self, item: ExtensionItem) -> None:
        """Perform removal of an extension."""
        if not self.manager.extensions:
            return

        ok = self.manager.extensions.uninstall_extension(item.uuid)
        if ok:
            item.is_installed = False
            item.is_enabled = False
            item.has_update = False
            self._update_detail_actions(item)
            self._sync_item_in_catalog(item)
            msg = _("Extension '{name}' removed.").format(name=item.name)
            if self.on_notify_message:
                self.on_notify_message(msg, False)
            if self._filter_mode == "installed":
                self.refresh()
        else:
            msg = _("Failed to remove extension '{name}'.").format(name=item.name)
            if self.on_notify_message:
                self.on_notify_message(msg, True)

    def _sync_item_in_catalog(self, item: ExtensionItem) -> None:
        """Synchronize extension state across remote items and active filter."""
        for it in self._remote_items:
            if it.uuid == item.uuid:
                it.is_installed = item.is_installed
                it.is_enabled = item.is_enabled
                it.has_update = item.has_update
                break
        if self._filter_mode == "updatable":
            self._filter_updatable_rows(self.search_entry.get_text().strip())

    def _on_detail_switch_state_set(self, switch: Gtk.Switch, state: bool) -> bool:
        """Handle toggling extension enabled state from the detail view."""
        item = self._selected_item
        if not item or not self.manager.extensions:
            return False

        ok = self.manager.extensions.toggle_extension(item.uuid, state)
        item.is_enabled = state if ok else not state
        self._sync_item_in_catalog(item)

        if ok:
            msg = (
                _("Extension '{name}' enabled.").format(name=item.name)
                if state
                else _("Extension '{name}' disabled.").format(name=item.name)
            )
            if self.on_notify_message:
                self.on_notify_message(msg, False)
        else:
            msg = _("Failed to toggle extension '{name}'.").format(name=item.name)
            if self.on_notify_message:
                self.on_notify_message(msg, True)
            switch.set_state(not state)

        return True

    def _on_detail_prefs_clicked(self) -> None:
        """Open settings dialog for the currently selected extension."""
        if self._selected_item:
            self._open_prefs(self._selected_item.uuid)

    def _on_detail_website_clicked(self) -> None:
        """Open website for the currently selected extension."""
        if self._selected_item:
            url = (
                self._selected_item.link or f"{EGO_BASE_URL}/extension/{self._selected_item.uuid}/"
            )
            self._open_url(url)

    def _on_remote_switch_toggled(self, item: ExtensionItem, state: bool) -> bool:
        """Handle toggling an installed extension from the remote/updatable list."""
        if not self.manager.extensions:
            return False

        ok = self.manager.extensions.toggle_extension(item.uuid, state)
        item.is_enabled = state if ok else not state

        if ok:
            msg = (
                _("Extension '{name}' enabled.").format(name=item.name)
                if state
                else _("Extension '{name}' disabled.").format(name=item.name)
            )
            if self.on_notify_message:
                self.on_notify_message(msg, False)
        else:
            msg = _("Failed to toggle extension '{name}'.").format(name=item.name)
            if self.on_notify_message:
                self.on_notify_message(msg, True)
        return False

    # --- Installed Extension Operations ---

    def _on_switch_state_set(self, ext: GnomeExtension, target_state: bool) -> bool:
        """Handle switch toggle by user."""
        self._on_extension_switch_toggled(ext, target_state)
        return False

    def _on_extension_switch_toggled(self, ext: GnomeExtension, active: bool) -> None:
        """Execute extension state toggle and notify."""
        if not self.manager.extensions:
            return

        ok = self.manager.extensions.toggle_extension(ext.uuid, active)
        ext.enabled = active if ok else not active

        if ok:
            msg = (
                _("Extension '{name}' enabled.").format(name=ext.name)
                if active
                else _("Extension '{name}' disabled.").format(name=ext.name)
            )
            if self.on_notify_message:
                self.on_notify_message(msg, False)
        else:
            msg = _("Failed to toggle extension '{name}'.").format(name=ext.name)
            if self.on_notify_message:
                self.on_notify_message(msg, True)

    def _update_app_status(self) -> None:
        """Update header button, banner, and expander based on Extension Manager status."""
        is_mgr_installed = False
        is_basic_installed = False
        if self.manager.extensions:
            try:
                if hasattr(self.manager.extensions, "is_extension_manager_installed"):
                    is_mgr_installed = self.manager.extensions.is_extension_manager_installed()
                    is_basic_installed = self.manager.extensions.is_gnome_extensions_installed()
                else:
                    is_mgr_installed = self.manager.extensions.is_extensions_app_installed()
            except Exception as err:
                logger.debug("Error checking extensions app: %s", err)

        cmd = self._get_active_install_command()

        # Item 1: Completely hide install banner & options group if already installed!
        if is_mgr_installed:
            if self.install_banner is not None:
                self.install_banner.set_revealed(False)
            if self.group_install_manager is not None:
                self.group_install_manager.set_visible(False)
            if self.btn_open_app is not None:
                self.btn_open_app.set_label(_("Open Extension Manager"))
                self.btn_open_app.set_tooltip_text(
                    _("Open GNOME Extensions application to manage installed extensions")
                )
        else:
            if self.install_banner is not None:
                self.install_banner.set_title(
                    _("Extension Manager is not installed. Install with: {cmd}").format(cmd=cmd)
                )
                self.install_banner.set_revealed(True)
            if self.group_install_manager is not None:
                self.group_install_manager.set_visible(True)
            if self.btn_open_app is not None:
                self.btn_open_app.set_label(_("Install Extension Manager"))
                self.btn_open_app.set_tooltip_text(
                    _("Extension Manager not detected. Click to install: {cmd}").format(cmd=cmd)
                )

        if self.row_basic_app is not None:
            self.row_basic_app.set_visible(is_basic_installed)

    def _on_app_button_clicked(self) -> None:
        """Handle click on primary header action button."""
        is_mgr_installed = False
        if self.manager.extensions:
            try:
                if hasattr(self.manager.extensions, "is_extension_manager_installed"):
                    is_mgr_installed = self.manager.extensions.is_extension_manager_installed()
                else:
                    is_mgr_installed = self.manager.extensions.is_extensions_app_installed()
            except Exception as err:
                logger.debug("Error checking extensions app: %s", err)

        if is_mgr_installed:
            self._open_app()
        else:
            self._on_copy_install_command()

    def _on_copy_install_command(self, _btn: object | None = None) -> None:
        """Copy the installation command for Extension Manager to clipboard."""
        cmd = self._get_active_install_command()
        try:
            from gi.repository import Gdk

            display = Gdk.Display.get_default()
            if display:
                clipboard = display.get_clipboard()
                clipboard.set(cmd)
        except Exception as err:
            logger.debug("Failed to set clipboard: %s", err)

        if self.on_notify_message:
            self.on_notify_message(
                _("Installation command copied to clipboard: {cmd}").format(cmd=cmd),
                False,
            )

    def _open_app(self) -> None:
        """Launch specifically Extension Manager app."""
        if not self.manager.extensions:
            return
        if hasattr(self.manager.extensions, "open_extension_manager"):
            ok = self.manager.extensions.open_extension_manager()
        else:
            ok = self.manager.extensions.open_extensions_app(fallback_to_basic=False)
        if not ok:
            self._update_app_status()
            if self.expander_install_options is not None:
                self.expander_install_options.set_expanded(True)
            self._on_copy_install_command()

    def _open_basic_app(self) -> None:
        """Launch standard basic GNOME Extensions app."""
        if not self.manager.extensions:
            return
        if hasattr(self.manager.extensions, "open_gnome_extensions_app"):
            self.manager.extensions.open_gnome_extensions_app()
        else:
            self.manager.extensions.open_extensions_app(fallback_to_basic=True)

    def _open_prefs(self, uuid: str) -> None:
        """Launch preferences dialog for an extension."""
        if not self.manager.extensions:
            return
        ok = self.manager.extensions.open_prefs(uuid)
        if not ok and self.on_notify_message:
            self.on_notify_message(_("Could not open settings for this extension."), True)

    def _open_url(self, url: str) -> None:
        """Open web URL in default browser."""
        if not url or not url.strip():
            return
        target_url = url.strip()
        if target_url.startswith("/"):
            target_url = f"{EGO_BASE_URL}{target_url}"
        elif not target_url.startswith(("http://", "https://")):
            target_url = f"https://{target_url}"
        try:
            Gio.AppInfo.launch_default_for_uri(target_url, None)
        except Exception as err:
            logger.warning("Failed to open URL '%s': %s", target_url, err)

    def _on_remove_extension(self, ext: GnomeExtension) -> None:
        """Handle uninstalling a user-level extension."""
        if not self.manager.extensions:
            return

        ok = self.manager.extensions.uninstall_extension(ext.uuid)
        if ok:
            msg = _("Extension '{name}' removed.").format(name=ext.name)
            if self.on_notify_message:
                self.on_notify_message(msg, False)
            self.refresh()
        else:
            msg = _("Failed to remove extension '{name}'.").format(name=ext.name)
            if self.on_notify_message:
                self.on_notify_message(msg, True)

    def _open_portal(self) -> None:
        """Open official GNOME extensions portal in browser."""
        portal_url = (
            self.manager.extensions.get_store_url("")
            if self.manager.extensions
            else "https://extensions.gnome.org/"
        )
        self._open_url(portal_url)
