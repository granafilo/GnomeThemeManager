# SPDX-License-Identifier: GPL-3.0-or-later

"""Module containing the application main window (GnomeThemeWindow).

Manages the main GTK4 and Libadwaita shell:
- Adw.ToastOverlay for unified temporary notifications;
- Adw.NavigationSplitView with left sidebar (Gtk.ListBox) and right content;
- 4 dedicated sections per component (GNOME Shell, GTK, Icons, Cursors);
- Centralized router based on Gtk.Stack inside Adw.NavigationPage content;
- Contextual refresh button visible only when status or themes page is active;
- Adaptive responsiveness via Adw.Breakpoint (collapsing below 700px).
"""

import logging
import os
from pathlib import Path
from typing import Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, Gdk, GLib, Gtk

from ..core.manager import ThemeManager
from ..core.models import ThemeType
from .pages import (
    ExtensionsPage,
    FontsPage,
    GlobalThemesPage,
    InstallerPage,
    SandboxPage,
    StatusPage,
    StorePage,
    TerminalPage,
    ThemeEditorPage,
    ThemesPage,
)

logger = logging.getLogger("gnome_theme_manager.gui_gtk.window")

# Path to associated UI template file
UI_FILE = Path(__file__).parent / "ui" / "window.ui"

# Path to bundled fallback icons directory (data/icons)
BUNDLED_ICONS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "icons"

# Threshold for responsive automatic collapse (collapsible sidebar)
COLLAPSE_BREAKPOINT_WIDTH: int = 0

# Main window minimum geometry to keep sidebar + content fully usable
MIN_WINDOW_WIDTH: int = 980
MIN_WINDOW_HEIGHT: int = 680

# Main window default geometry at startup
DEFAULT_WINDOW_WIDTH: int = 1080
DEFAULT_WINDOW_HEIGHT: int = 720


def init_bundled_icon_theme(icon_theme: Gtk.IconTheme | None = None) -> None:
    """Register bundled icons directory in the Gtk.IconTheme search path chain."""
    search_dirs: list[Path] = [
        BUNDLED_ICONS_DIR,
        BUNDLED_ICONS_DIR / "hicolor",
        BUNDLED_ICONS_DIR / "hicolor" / "scalable" / "apps",
        BUNDLED_ICONS_DIR / "hicolor" / "512x512" / "apps",
    ]

    # AppImage runtime icon search paths (from $APPDIR)
    appdir_env = os.environ.get("APPDIR")
    if appdir_env:
        appdir_path = Path(appdir_env)
        for appdir_candidate in [
            appdir_path / "usr" / "share" / "icons",
            appdir_path / "usr" / "share" / "icons" / "hicolor",
            appdir_path / "data" / "icons",
            appdir_path / "data" / "icons" / "hicolor",
        ]:
            if appdir_candidate.is_dir() and appdir_candidate not in search_dirs:
                search_dirs.append(appdir_candidate)

    # Flatpak runtime icon search paths
    for flatpak_dir in [
        Path("/app/share/icons"),
        Path("/app/share/icons/hicolor"),
        Path("/app/share/gnome-theme-manager/data/icons"),
        Path("/app/share/gnome-theme-manager/icons"),
    ]:
        if flatpak_dir.is_dir() and flatpak_dir not in search_dirs:
            search_dirs.append(flatpak_dir)

    # User local and system icon paths (including Flatpak host mounts)
    for candidate in [
        Path.home() / ".local" / "share" / "icons",
        Path.home() / ".local" / "share" / "icons" / "hicolor",
        Path.home() / ".icons",
        Path.home() / ".icons" / "hicolor",
        Path("/run/host/share/icons"),
        Path("/run/host/share/icons/hicolor"),
        Path("/run/host/usr/share/icons"),
        Path("/run/host/usr/share/icons/hicolor"),
        Path("/run/host/user-share/icons"),
        Path("/usr/local/share/icons"),
        Path("/usr/local/share/icons/hicolor"),
        Path("/usr/share/icons"),
        Path("/usr/share/icons/hicolor"),
    ]:
        if candidate.is_dir() and candidate not in search_dirs:
            search_dirs.append(candidate)

    try:
        theme = icon_theme
        if theme is None:
            display = Gdk.Display.get_default()
            if display is not None:
                theme = Gtk.IconTheme.get_for_display(display)

        if theme is not None and hasattr(theme, "add_search_path"):
            current_paths = theme.get_search_path() if hasattr(theme, "get_search_path") else []
            for s_dir in search_dirs:
                if s_dir.is_dir():
                    s_str = str(s_dir)
                    if s_str not in current_paths:
                        theme.add_search_path(s_str)
                        logger.debug("Added bundled icons directory to Gtk.IconTheme: %s", s_str)
    except Exception as err:
        logger.warning("Failed to initialize bundled icon theme: %s", err)


class MainWindow(Adw.ApplicationWindow):
    """Main application window for GTK4 / Libadwaita."""

    def __init__(self, app: Adw.Application, manager: ThemeManager | None = None) -> None:
        """Initialize main window loading window.ui template.

        Args:
            app: Adw.Application owning the window.
            manager: ThemeManager instance (created automatically if omitted).

        Raises:
            FileNotFoundError: If window.ui template file is missing.
        """
        super().__init__(application=app, title=_("GNOME Theme Manager"))

        # Initialize bundled icons fallback chain
        init_bundled_icon_theme()

        # Set application window icon name
        self.set_icon_name("io.github.granafilo.ThemeManager")

        # Minimum sizing ensuring all pages/cards are fully visible without truncation and satisfying Libadwaita constraints
        self.set_size_request(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.set_default_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Apply application-wide CSS styling for enhanced readability and typography
        self._setup_custom_styling()

        self.manager = manager or ThemeManager()
        try:
            self.manager.installer.ensure_user_directories()
        except Exception as err:
            logger.warning("Failed to initialize user theme directories: %s", err)

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        # Retrieve XML widgets
        self.toast_overlay: Adw.ToastOverlay = self.builder.get_object("toast_overlay")
        self.split_view: Adw.NavigationSplitView = self.builder.get_object("split_view")
        self.sidebar_page: Adw.NavigationPage = self.builder.get_object("sidebar_page")
        self.sidebar_list_box: Gtk.ListBox = self.builder.get_object("sidebar_list_box")
        self.content_page: Adw.NavigationPage = self.builder.get_object("content_page")
        self.content_header_bar: Adw.HeaderBar = self.builder.get_object("content_header_bar")
        self.content_stack: Gtk.Stack = self.builder.get_object("content_stack")
        self.refresh_button: Gtk.Button = self.builder.get_object("refresh_button")

        # Retrieve responsive feedback widgets
        self.feedback_revealer: Gtk.Revealer = self.builder.get_object("feedback_revealer")
        self.feedback_box: Gtk.Box = self.builder.get_object("feedback_box")
        self.feedback_icon: Gtk.Image = self.builder.get_object("feedback_icon")
        self.feedback_label: Gtk.Label = self.builder.get_object("feedback_label")
        self.feedback_close_button: Gtk.Button = self.builder.get_object("feedback_close_button")
        self._feedback_timeout_id: int | None = None

        if self.feedback_close_button is not None:
            self.feedback_close_button.connect("clicked", self._on_feedback_close_clicked)

        # Retrieve sidebar rows
        self.row_status: Gtk.ListBoxRow = self.builder.get_object("row_status")
        self.row_themes_shell: Gtk.ListBoxRow = self.builder.get_object("row_themes_shell")
        self.row_themes_gtk: Gtk.ListBoxRow = self.builder.get_object("row_themes_gtk")
        self.row_themes_icon: Gtk.ListBoxRow = self.builder.get_object("row_themes_icon")
        self.row_themes_cursor: Gtk.ListBoxRow = self.builder.get_object("row_themes_cursor")
        self.row_global_themes: Gtk.ListBoxRow = self.builder.get_object("row_global_themes")
        self.row_editor: Gtk.ListBoxRow = self.builder.get_object("row_editor")
        self.row_fonts: Gtk.ListBoxRow = self.builder.get_object("row_fonts")
        self.row_terminal: Gtk.ListBoxRow = self.builder.get_object("row_terminal")
        self.row_store: Gtk.ListBoxRow = self.builder.get_object("row_store")
        self.row_extensions: Gtk.ListBoxRow = self.builder.get_object("row_extensions")
        self.row_installer: Gtk.ListBoxRow = self.builder.get_object("row_installer")
        self.row_sandbox: Gtk.ListBoxRow = self.builder.get_object("row_sandbox")

        self.set_content(self.toast_overlay)

        self._setup_breakpoint()

        # Page controllers
        self.status_page = StatusPage(manager=self.manager)
        self.themes_page = ThemesPage(manager=self.manager)
        self.global_themes_page = GlobalThemesPage(manager=self.manager)
        self.editor_page = ThemeEditorPage(manager=self.manager)
        self.fonts_page = FontsPage(manager=self.manager)
        self.terminal_page = TerminalPage(manager=self.manager)
        self.store_page = StorePage(manager=self.manager)
        self.extensions_page = ExtensionsPage(manager=self.manager)
        self.installer_page = InstallerPage(manager=self.manager)
        self.sandbox_page = SandboxPage(manager=self.manager)

        self.pages: dict[str, Any] = {
            "status": self.status_page,
            "themes": self.themes_page,
            "themes_shell": self.themes_page,
            "themes_gtk": self.themes_page,
            "themes_icon": self.themes_page,
            "themes_cursor": self.themes_page,
            "global_themes": self.global_themes_page,
            "editor": self.editor_page,
            "fonts": self.fonts_page,
            "terminal": self.terminal_page,
            "store": self.store_page,
            "extensions": self.extensions_page,
            "installer": self.installer_page,
            "sandbox": self.sandbox_page,
        }

        self.content_stack.add_named(self.status_page.get_widget(), "status")
        self.content_stack.add_named(self.themes_page.get_widget(), "themes")
        self.content_stack.add_named(self.global_themes_page.get_widget(), "global_themes")
        self.content_stack.add_named(self.editor_page.get_widget(), "editor")
        self.content_stack.add_named(self.fonts_page.get_widget(), "fonts")
        self.content_stack.add_named(self.terminal_page.get_widget(), "terminal")
        self.content_stack.add_named(self.store_page.get_widget(), "store")
        self.content_stack.add_named(self.extensions_page.get_widget(), "extensions")
        self.content_stack.add_named(self.installer_page.get_widget(), "installer")
        self.content_stack.add_named(self.sandbox_page.get_widget(), "sandbox")

        self._row_to_page_id: dict[Gtk.ListBoxRow, str] = {
            self.row_status: "status",
            self.row_themes_shell: "themes_shell",
            self.row_themes_gtk: "themes_gtk",
            self.row_themes_icon: "themes_icon",
            self.row_themes_cursor: "themes_cursor",
            self.row_global_themes: "global_themes",
            self.row_editor: "editor",
            self.row_fonts: "fonts",
            self.row_terminal: "terminal",
            self.row_store: "store",
            self.row_extensions: "extensions",
            self.row_installer: "installer",
            self.row_sandbox: "sandbox",
        }

        self._page_id_to_row: dict[str, Gtk.ListBoxRow] = {
            pid: row for row, pid in self._row_to_page_id.items()
        }
        self._page_id_to_row["themes"] = self.row_themes_gtk

        self._current_page_id: str | None = None

        self.sidebar_list_box.connect("row-selected", self._on_sidebar_row_selected)
        self.refresh_button.connect("clicked", self._on_refresh_button_clicked)

        # Auto-integrate desktop launcher and icons lazily in background
        if os.environ.get("APPIMAGE") or os.environ.get("APPDIR"):
            GLib.idle_add(self._lazy_desktop_integration)

        self.status_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "status", is_l
        )
        self.themes_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "themes", is_l
        )
        self.global_themes_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "global_themes", is_l
        )
        self.global_themes_page.on_notify_message = lambda msg, is_err: self.add_toast(
            msg, is_error=is_err
        )
        self.global_themes_page.on_edit_requested = lambda theme: (
            self._on_edit_global_theme_requested(theme)
        )

        self.status_page.on_notify_message = lambda msg, is_err: self.add_toast(
            msg, is_error=is_err
        )
        self.fonts_page.on_notify_message = lambda msg, is_err: self.add_toast(msg, is_error=is_err)
        self.terminal_page.on_notify_message = lambda msg, is_err: self.add_toast(
            msg, is_error=is_err
        )
        self.store_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "store", is_l
        )
        self.store_page.on_notify_message = lambda msg, is_err: self.add_toast(msg, is_error=is_err)
        self.extensions_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "extensions", is_l
        )
        self.extensions_page.on_notify_message = lambda msg, is_err: self.add_toast(
            msg, is_error=is_err
        )

        self.editor_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "editor", is_l
        )
        self.editor_page.on_notify_message = lambda msg, is_err: self.add_toast(
            msg, is_error=is_err
        )
        self.editor_page.on_theme_saved = lambda saved: self.global_themes_page.refresh()

        def _on_global_theme_applied_callback(theme_id: str, result: Any) -> None:
            self.status_page.refresh()
            self.global_themes_page.refresh()
            if self.themes_page.current_snapshot is not None or not self.themes_page.is_loading:
                self.themes_page.refresh()

        self.global_themes_page.on_theme_applied = _on_global_theme_applied_callback

        def _on_theme_applied_callback(item: Any, result: Any) -> None:
            self.status_page.refresh()
            self.global_themes_page.refresh()

        self.themes_page.on_theme_applied = _on_theme_applied_callback

        def _on_theme_installed_callback() -> None:
            self.themes_page.refresh()

        self.installer_page.on_theme_installed = _on_theme_installed_callback

        def _on_theme_installed_and_applied_callback() -> None:
            self.status_page.refresh()
            self.themes_page.refresh()
            self.global_themes_page.refresh()

        self.installer_page.on_theme_applied = _on_theme_installed_and_applied_callback

        def _on_sandbox_propagated_callback() -> None:
            self.status_page.refresh()

        self.sandbox_page.on_sandbox_propagated = _on_sandbox_propagated_callback

        # Real-time GSettings synchronization (Task 4.8.4)
        if self.manager.gsettings is not None:
            self.manager.gsettings.connect_changed(self._on_gsettings_changed)

        self.select_page("status")

        self._setup_shortcuts(app)
        self._setup_focus_behavior()

    def _setup_custom_styling(self) -> None:
        """Inject CSS styles for enhanced readability, larger font scale, and comfortable spacing."""
        from gi.repository import Gdk

        css_provider = Gtk.CssProvider()
        css_data = """
        /* Typography scale enhancement */
        window.main-window {
            font-size: 1.04rem;
        }

        /* ActionRow titles & subtitles comfortable scale */
        row.activatable, preferencesgroup list {
            min-height: 52px;
        }

        /* Slightly larger sidebar icons and rows */
        .navigation-sidebar > row {
            min-height: 44px;
            padding: 4px 6px;
        }

        /* Modern Libadwaita GtkDropDown styling */
        dropdown > button {
            min-width: 180px;
            min-height: 38px;
            padding: 4px 14px;
            border-radius: 8px;
            font-weight: 500;
        }

        dropdown > button image {
            margin-left: 8px;
        }

        dropdown > button label {
            font-weight: 500;
        }

        /* Standard input / entry text colors adhering to current Libadwaita theme */
        entry,
        searchentry,
        editable,
        entry text,
        searchentry text,
        entry > text,
        searchentry > text,
        entry.numeric {
            color: @window_fg_color;
        }

        entry:focus-within,
        searchentry:focus-within {
            color: @window_fg_color;
        }

        /* Popover list styling for dropdown menus */
        popover.menu listview row, popover.menu listview > row {
            min-height: 38px;
            padding: 6px 12px;
        }

        /* Color picker HEX entries & buttons */
        entry.numeric {
            min-height: 36px;
            border-radius: 8px;
            font-family: monospace;
            font-weight: 500;
        }

        /* Card list padding and border radius */
        .boxed-list {
            margin-top: 6px;
            margin-bottom: 6px;
        }

        /* Online Store Cards & Banners */
        .store-hub-category-card {
            background-color: alpha(@card_bg_color, 0.75);
            border: 1px solid alpha(@borders, 0.45);
            border-radius: 16px;
            padding: 4px;
            transition: all 200ms ease-in-out;
        }

        .store-hub-category-card:hover {
            background-color: alpha(@card_bg_color, 0.95);
            border-color: alpha(@accent_color, 0.7);
        }

        .store-theme-card {
            background-color: alpha(@card_bg_color, 0.75);
            border: 1px solid alpha(@borders, 0.45);
            border-radius: 16px;
            padding: 12px;
        }

        .store-theme-card:hover {
            background-color: alpha(@card_bg_color, 0.95);
            border-color: alpha(@accent_color, 0.6);
        }

        .store-banner-box {
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
            border-radius: 12px;
            min-height: 150px;
        }

        .store-banner-box picture, .store-banner-box image {
            border-radius: 12px;
        }

        .store-detail-preview-frame {
            background-color: alpha(@window_bg_color, 0.5);
            border: 1px solid alpha(@borders, 0.3);
            border-radius: 14px;
            padding: 16px;
        }

        .store-thumb-btn {
            border-radius: 8px;
            padding: 2px;
            border: 2px solid transparent;
        }

        .store-thumb-btn.suggested-action {
            border-color: @accent_color;
        }

        .store-lightbox-bg {
            background-color: #0b0d13;
            padding: 16px;
        }

        /* Solid opaque background for status pages and loading stacks to completely prevent bleed-through */
        adwstatuspage,
        .solid-loading-page,
        stack#content_stack,
        stack#extensions_root,
        stack#page_root,
        #loading_page {
            background-color: @window_bg_color;
            opacity: 1;
        }
        """
        try:
            if hasattr(css_provider, "load_from_string"):
                css_provider.load_from_string(css_data)
            else:
                css_provider.load_from_data(css_data.encode("utf-8"))
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        except Exception as err:
            logger.debug("Failed to apply custom CSS styling: %s", err)

    def _setup_shortcuts(self, app: Adw.Application) -> None:
        """Configure actions and accelerators for close (Ctrl+W) and quit (Ctrl+Q)."""
        from gi.repository import Gio

        action_close = Gio.SimpleAction.new("close", None)
        action_close.connect("activate", lambda *_: self.close())
        self.add_action(action_close)
        app.set_accels_for_action("win.close", ["<Control>w"])

        if not app.has_action("quit"):
            action_quit = Gio.SimpleAction.new("quit", None)
            action_quit.connect("activate", lambda *_: app.quit())
            app.add_action(action_quit)
        app.set_accels_for_action("app.quit", ["<Control>q"])

    def _setup_focus_behavior(self) -> None:
        """Add GestureClick to window to clear input focus and reset selections on outside click."""
        gesture = Gtk.GestureClick.new()

        def _on_pressed(gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
            clicked_widget = self.pick(x, y, Gtk.PickFlags.DEFAULT)

            if clicked_widget is not None:
                w = clicked_widget
                while w is not None:
                    if isinstance(w, Gtk.Button) or w.get_css_name() == "button":
                        return
                    if (
                        hasattr(self, "themes_page")
                        and self.themes_page is not None
                        and (
                            w == self.themes_page.themes_list_box
                            or w == self.themes_page.active_theme_row
                            or w == self.themes_page.apply_button
                        )
                    ):
                        return
                    w = w.get_parent()

            self.set_focus(None)
            if (
                hasattr(self, "themes_page")
                and self.themes_page is not None
                and self.themes_page.themes_list_box is not None
            ):
                self.themes_page.themes_list_box.select_row(None)

        gesture.connect("pressed", _on_pressed)
        self.add_controller(gesture)

    def _setup_breakpoint(self) -> None:
        """Configure Libadwaita responsive breakpoint for automatic collapse."""
        try:
            condition = Adw.BreakpointCondition.parse(f"max-width: {COLLAPSE_BREAKPOINT_WIDTH}px")
            breakpoint = Adw.Breakpoint.new(condition)
            breakpoint.add_setter(self.split_view, "collapsed", True)
            self.add_breakpoint(breakpoint)
        except (GLib.GError, AttributeError, TypeError, ValueError) as err:
            logger.warning(
                "Unable to register Adw.Breakpoint: %s",
                err,
            )

    def _on_sidebar_row_selected(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Handle 'row-selected' signal on sidebar list box."""
        if row is None:
            return

        page_id = self._row_to_page_id.get(row)
        if page_id is not None:
            self.select_page(page_id)
        else:
            logger.warning("Selected sidebar row without page_id: %s", row)

    def _on_refresh_button_clicked(self, button: Gtk.Button) -> None:
        """Handle click on header refresh button."""
        if self._current_page_id == "status":
            self.status_page.refresh()
        elif self._current_page_id and (
            self._current_page_id == "themes" or self._current_page_id.startswith("themes_")
        ):
            self.themes_page.refresh()

    def _on_edit_global_theme_requested(self, theme: Any) -> None:
        """Navigate to the editor page and load a user Global Theme for editing."""
        if self.editor_page is None:
            return
        self.editor_page.refresh(sync=True)
        self.editor_page.load_global_theme_for_editing(theme)
        self.select_page("editor")

    def _on_page_loading_changed(self, page_id: str, is_loading: bool) -> None:
        """Update refresh button sensitivity during page loading."""
        if self._current_page_id == page_id or (
            page_id == "themes"
            and self._current_page_id
            and self._current_page_id.startswith("themes_")
        ):
            self.refresh_button.set_sensitive(not is_loading)

    def select_page(self, page_id: str) -> None:
        """Select and display specified page in content Gtk.Stack.

        Args:
            page_id: Identifier of page ('status', 'themes_shell', 'themes_gtk', etc.).
        """
        self.clear_feedback()

        if page_id == "themes":
            page_id = "themes_gtk"

        if page_id not in self.pages:
            logger.warning(
                "Attempted to select unknown or invalid page_id: '%s'",
                page_id,
            )
            return

        if page_id == "themes_shell":
            self.themes_page.set_category(ThemeType.SHELL)
            stack_id = "themes"
            page_title = _("GNOME Shell")
        elif page_id == "themes_gtk":
            self.themes_page.set_category(ThemeType.GTK)
            stack_id = "themes"
            page_title = _("Applications (GTK)")
        elif page_id == "themes_icon":
            self.themes_page.set_category(ThemeType.ICON)
            stack_id = "themes"
            page_title = _("Icons")
        elif page_id == "themes_cursor":
            self.themes_page.set_category(ThemeType.CURSOR)
            stack_id = "themes"
            page_title = _("Cursors")
        else:
            stack_id = page_id
            page_title = self.pages[page_id].title

        self.content_stack.set_visible_child_name(stack_id)
        self.content_page.set_title(page_title)
        self._current_page_id = page_id

        is_refreshable = page_id in (
            "status",
            "themes_shell",
            "themes_gtk",
            "themes_icon",
            "themes_cursor",
        )
        self.refresh_button.set_visible(is_refreshable)
        if is_refreshable:
            ctrl = self.pages[page_id]
            if hasattr(ctrl, "is_loading"):
                self.refresh_button.set_sensitive(not ctrl.is_loading)

        if page_id.startswith("themes") and not self.themes_page.is_loading:
            self.themes_page.refresh()
        elif page_id == "status" and not self.status_page.is_loading:
            self.status_page.refresh()
        elif page_id == "global_themes" and not self.global_themes_page.is_loading:
            self.global_themes_page.refresh()
        elif (
            page_id == "editor"
            and not self.editor_page.is_loaded
            and not self.editor_page.is_loading
        ):
            self.editor_page.refresh()
        elif page_id == "sandbox" and not self.sandbox_page._is_loading:
            self.sandbox_page.refresh()
        elif page_id == "fonts":
            self.fonts_page.refresh()
        elif page_id == "terminal":
            self.terminal_page.refresh()
        elif page_id == "extensions":
            self.extensions_page.refresh()

        target_row = self._page_id_to_row.get(page_id)
        if target_row is not None and self.sidebar_list_box.get_selected_row() != target_row:
            self.sidebar_list_box.select_row(target_row)

        if self.split_view.get_collapsed():
            self.split_view.set_show_content(True)

    def _on_gsettings_changed(self, key: str) -> None:
        """Handle real-time GSettings changes from system, CLI, or settings."""
        logger.debug("Live GSettings modification detected on key: %s", key)
        GLib.idle_add(self._sync_live_gsettings_pages)

    def _sync_live_gsettings_pages(self) -> bool:
        """Synchronize active GUI view with live GSettings state."""
        if self._current_page_id == "status" and not self.status_page.is_loading:
            self.status_page.refresh()
        elif self._current_page_id == "global_themes" and not self.global_themes_page.is_loading:
            self.global_themes_page.refresh()
        elif (
            self._current_page_id
            and self._current_page_id.startswith("themes")
            and not self.themes_page.is_loading
        ):
            self.themes_page.refresh()
        elif self._current_page_id == "sandbox" and not self.sandbox_page._is_loading:
            self.sandbox_page.refresh()
        return GLib.SOURCE_REMOVE

    @property
    def current_page_id(self) -> str | None:
        """Return identifier of currently viewed page."""
        return self._current_page_id

    def clear_feedback(self) -> None:
        """Dismiss current top feedback notification."""
        if self._feedback_timeout_id is not None:
            GLib.source_remove(self._feedback_timeout_id)
            self._feedback_timeout_id = None
        if self.feedback_revealer is not None:
            self.feedback_revealer.set_reveal_child(False)

    def _on_feedback_close_clicked(self, _btn: Gtk.Button | None = None) -> None:
        """Dismiss top feedback notification on close button click."""
        self.clear_feedback()

    def add_toast(self, message: str, timeout: int = 0, is_error: bool = False) -> None:
        """Display a feedback notification in top area of window.

        Args:
            message: Message text to display.
            timeout: Seconds before dismissal (0 = persistent until next user action).
            is_error: Explicit flag indicating whether this is an error notification.
        """
        if self._feedback_timeout_id is not None:
            GLib.source_remove(self._feedback_timeout_id)
            self._feedback_timeout_id = None

        if self.feedback_label is not None:
            self.feedback_label.set_label(message)

        msg_lower = message.lower()
        has_error_kw = (
            is_error
            or "error" in msg_lower
            or "failed" in msg_lower
            or "unable" in msg_lower
            or "impossibile" in msg_lower
            or "errore" in msg_lower
            or "fallit" in msg_lower
            or "invalid" in msg_lower
            or "non valid" in msg_lower
        )
        has_warning_kw = (
            "warning" in msg_lower
            or "partial" in msg_lower
            or "avvis" in msg_lower
            or "incompleto" in msg_lower
        )
        has_deleted_kw = (
            "deleted" in msg_lower
            or "removed" in msg_lower
            or "rimoss" in msg_lower
            or "eliminat" in msg_lower
        )

        if self.feedback_icon is not None:
            if has_error_kw:
                self.feedback_icon.set_from_icon_name("dialog-error-symbolic")
            elif has_warning_kw:
                self.feedback_icon.set_from_icon_name("dialog-warning-symbolic")
            elif has_deleted_kw:
                self.feedback_icon.set_from_icon_name("edit-delete-symbolic")
            else:
                self.feedback_icon.set_from_icon_name("emblem-ok-symbolic")

        if self.feedback_box is not None:
            if has_error_kw:
                self.feedback_box.add_css_class("error")
                self.feedback_box.remove_css_class("warning")
                self.feedback_box.remove_css_class("success")
            elif has_warning_kw:
                self.feedback_box.add_css_class("warning")
                self.feedback_box.remove_css_class("error")
                self.feedback_box.remove_css_class("success")
            else:
                self.feedback_box.add_css_class("success")
                self.feedback_box.remove_css_class("error")
                self.feedback_box.remove_css_class("warning")

        if self.feedback_revealer is not None:
            self.feedback_revealer.set_reveal_child(True)

        if timeout > 0:

            def _auto_hide() -> bool:
                if self.feedback_revealer is not None:
                    self.feedback_revealer.set_reveal_child(False)
                self._feedback_timeout_id = None
                return GLib.SOURCE_REMOVE

            self._feedback_timeout_id = GLib.timeout_add_seconds(timeout, _auto_hide)

        if self.feedback_revealer is None and self.toast_overlay is not None:
            toast = Adw.Toast.new(message)
            if timeout > 0:
                toast.set_timeout(timeout)
            self.toast_overlay.add_toast(toast)

    def _lazy_desktop_integration(self) -> bool:
        """Run desktop integration in background without blocking UI startup."""
        if Path("/.flatpak-info").exists() or os.environ.get("FLATPAK_ID"):
            return GLib.SOURCE_REMOVE
        try:
            self.manager.integrate_desktop()
        except Exception as err:
            logger.debug("Lazy desktop integration error: %s", err)
        return GLib.SOURCE_REMOVE


# Backward compatibility alias for tests
GnomeThemeWindow = MainWindow
