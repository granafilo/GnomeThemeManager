# SPDX-License-Identifier: GPL-3.0-or-later

"""GNOME Shell Extensions browser page controller (Task 5.3)."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from ...core.extensions import GnomeExtension
from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")

UI_FILE = Path(__file__).parent.parent / "ui" / "extensions_page.ui"


class ExtensionsPage:
    """Controller for GNOME Shell Extensions management page."""

    PAGE_ID: str = "extensions"
    ICON_NAME: str = "application-x-addon-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
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
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.btn_refresh: Gtk.Button = self.builder.get_object("btn_refresh")
        self.status_stack: Gtk.Stack = self.builder.get_object("status_stack")
        self.user_extensions_group: Adw.PreferencesGroup = self.builder.get_object(
            "user_extensions_group"
        )
        self.system_extensions_group: Adw.PreferencesGroup = self.builder.get_object(
            "system_extensions_group"
        )
        self.empty_status_page: Adw.StatusPage = self.builder.get_object("empty_status_page")

        # Explicitly apply localized strings to all widgets
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

        if self.btn_open_app is not None:
            self.btn_open_app.set_label(_("Open Extension Manager"))
            self.btn_open_app.set_tooltip_text(
                _("Open GNOME Extensions application to manage installed extensions")
            )

        if self.btn_browse_portal is not None:
            self.btn_browse_portal.set_tooltip_text(_("Open official GNOME Extensions website"))

        if self.search_entry is not None:
            self.search_entry.set_placeholder_text(_("Search installed extensions..."))

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

        if self.empty_status_page is not None:
            self.empty_status_page.set_title(_("No Extensions Found"))
            self.empty_status_page.set_description(
                _("No extensions matched your filter or none are installed.")
            )

        self._extensions: list[GnomeExtension] = []
        self._filtered_extensions: list[GnomeExtension] = []
        self._is_loading: bool = False
        self._row_widgets: list[tuple[Adw.PreferencesGroup, Gtk.Widget]] = []

        self.widget.set_visible_child_name("loading")
        self._connect_signals()

    @property
    def is_loading(self) -> bool:
        """Return whether extension loading is active."""
        return self._is_loading

    def get_widget(self) -> Gtk.Stack:
        """Return root widget container."""
        return self.widget

    def _connect_signals(self) -> None:
        """Connect UI widget signals."""
        self.btn_refresh.connect("clicked", lambda _: self.refresh())
        self.btn_open_app.connect("clicked", lambda _: self._open_app())
        self.btn_browse_portal.connect("clicked", lambda _: self._open_portal())
        self.search_entry.connect("search-changed", self._on_search_changed)

    def refresh(self) -> None:
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
        self.widget.set_visible_child_name("ready")
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filter extensions when search query changes."""
        self._filter_extensions(entry.get_text().strip())

    def _filter_extensions(self, query: str) -> None:
        """Filter cached extensions list and update UI rows."""
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
            if link_url:
                btn_details = Gtk.Button(label=_("Details"))
                btn_details.set_valign(Gtk.Align.CENTER)
                btn_details.add_css_class("flat")
                btn_details.set_tooltip_text(_("Open extension website"))
                btn_details.connect("clicked", lambda _, u=link_url: self._open_url(u))
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

    def _open_app(self) -> None:
        """Launch official GNOME Extensions or Extension Manager app."""
        if not self.manager.extensions:
            return
        ok = self.manager.extensions.open_extensions_app()
        if not ok and self.on_notify_message:
            self.on_notify_message(
                _(
                    "To manage extensions, install the 'Extension Manager' or 'gnome-extensions-app' package."
                ),
                True,
            )

    def _open_prefs(self, uuid: str) -> None:
        """Launch preferences dialog for an extension."""
        if not self.manager.extensions:
            return
        ok = self.manager.extensions.open_prefs(uuid)
        if not ok and self.on_notify_message:
            self.on_notify_message(_("Could not open settings for this extension."), True)

    def _open_url(self, url: str) -> None:
        """Open web URL in default browser."""
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
        except Exception as err:
            logger.warning("Failed to open URL '%s': %s", url, err)

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
