# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for 'Theme Installer' page.

Provides inspection, validation, extraction, and installation
of themes from local folders or compressed archives (.zip, .tar.gz, .tar.xz, .tar.bz2).
"""

import logging
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ...core.errors import (
    ArchiveExtractionError,
    ThemeValidationError,
)
from ...core.installer import inspect_extracted_tree, safe_extract
from ...core.models import ApplyResult, Theme, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.installer")

UI_FILE = Path(__file__).parent.parent / "ui" / "installer_page.ui"


def format_components_label(components: list[ThemeType]) -> str:
    """Format detected theme component types."""
    if not components:
        return _("No recognizable components")

    labels_map = {
        ThemeType.GTK: _("Applications (GTK)"),
        ThemeType.SHELL: _("GNOME Shell"),
        ThemeType.ICON: _("Icons"),
        ThemeType.CURSOR: _("Cursors"),
    }
    unique_types: list[ThemeType] = []
    for c in components:
        if c not in unique_types:
            unique_types.append(c)

    return ", ".join(labels_map.get(t, t.value) for t in unique_types)


class InstallerPage:
    """Controller for 'Theme Installer' GTK4/Libadwaita GUI view."""

    PAGE_ID: str = "installer"
    ICON_NAME: str = "system-software-install-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Initialize controller loading installer_page.ui template."""
        self.page_id: str = self.PAGE_ID
        self.title: str = _("Theme Installer")
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"UI template file not found: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        self.select_folder_button: Gtk.Button = self.builder.get_object("select_folder_button")
        self.select_archive_button: Gtk.Button = self.builder.get_object("select_archive_button")

        self.analyzing_spinner: Gtk.Spinner = self.builder.get_object("analyzing_spinner")
        self.analyzing_label: Gtk.Label = self.builder.get_object("analyzing_label")

        self.source_name_row: Adw.ActionRow = self.builder.get_object("source_name_row")
        self.source_type_row: Adw.ActionRow = self.builder.get_object("source_type_row")
        self.detected_theme_name_row: Adw.ActionRow = self.builder.get_object(
            "detected_theme_name_row"
        )
        self.detected_components_row: Adw.ActionRow = self.builder.get_object(
            "detected_components_row"
        )
        self.validation_status_row: Adw.ActionRow = self.builder.get_object(
            "validation_status_row"
        )
        self.validation_status_icon: Gtk.Image = self.builder.get_object(
            "validation_status_icon"
        )
        self.target_dir_switch: Gtk.Switch = self.builder.get_object("target_dir_switch")
        self.change_source_button: Gtk.Button = self.builder.get_object("change_source_button")
        self.install_button: Gtk.Button = self.builder.get_object("install_button")
        self.install_apply_button: Gtk.Button = self.builder.get_object("install_apply_button")

        self.installing_spinner: Gtk.Spinner = self.builder.get_object("installing_spinner")
        self.installing_status_label: Gtk.Label = self.builder.get_object("installing_status_label")

        self.success_status_page: Adw.StatusPage = self.builder.get_object("success_status_page")
        self.success_new_source_button: Gtk.Button = self.builder.get_object(
            "success_new_source_button"
        )

        self.error_status_page: Adw.StatusPage = self.builder.get_object("error_status_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")
        self.error_new_source_button: Gtk.Button = self.builder.get_object(
            "error_new_source_button"
        )

        self._selected_source: Path | None = None
        self._detected_name: str | None = None
        self._detected_components: list[ThemeType] = []
        self._is_analyzing: bool = False
        self._is_installing: bool = False
        self._analysis_generation: int = 0
        self._install_generation: int = 0
        self._confirm_dialog_open: bool = False

        self.on_theme_installed: Callable[[], None] | None = None
        self.on_theme_applied: Callable[[], None] | None = None

        self._button_configs: dict[str, tuple[str, str]] = {
            "select_folder_button": (_("Select Folder"), "folder-open-symbolic"),
            "select_archive_button": (_("Select Archive"), "package-x-generic-symbolic"),
            "change_source_button": (_("Change Source"), "edit-undo-symbolic"),
            "install_button": (_("Install"), "system-software-install-symbolic"),
            "install_apply_button": (_("Install and Apply"), "emblem-ok-symbolic"),
            "success_new_source_button": (
                _("Select Another Source"),
                "document-open-symbolic",
            ),
            "error_retry_button": (_("Retry"), "view-refresh-symbolic"),
            "error_new_source_button": (_("Select Another Source"), "document-open-symbolic"),
        }
        for btn_attr, (lbl, icon) in self._button_configs.items():
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                btn.set_label(lbl)
                btn._icon_name = icon
                btn.get_icon_name = lambda _b=btn, _ic=icon: _ic

        self.select_folder_button.connect("clicked", self._on_select_folder_clicked)
        self.select_archive_button.connect("clicked", self._on_select_archive_clicked)
        self.change_source_button.connect("clicked", self._on_reset_to_initial)
        self.install_button.connect("clicked", self._on_install_clicked)
        self.install_apply_button.connect("clicked", self._on_install_and_apply_clicked)
        self.success_new_source_button.connect("clicked", self._on_reset_to_initial)
        self.error_retry_button.connect("clicked", self._on_retry_clicked)
        self.error_new_source_button.connect("clicked", self._on_reset_to_initial)

    def get_widget(self) -> Gtk.Stack:
        """Return main Gtk.Stack widget."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indicate if inspection or installation is running."""
        return self._is_analyzing or self._is_installing

    def _set_state(self, state: str) -> None:
        """Set visible stack state."""
        self.widget.set_visible_child_name(state)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Enable or disable action controls."""
        self.install_button.set_sensitive(sensitive)
        self.install_apply_button.set_sensitive(sensitive)
        self.change_source_button.set_sensitive(sensitive)
        self.select_folder_button.set_sensitive(sensitive)
        self.select_archive_button.set_sensitive(sensitive)

    def _on_reset_to_initial(self, _button: Gtk.Button | None = None) -> None:
        """Reset view to initial selection state."""
        self._selected_source = None
        self._detected_name = None
        self._detected_components = []
        self._set_controls_sensitive(True)
        self._set_state("initial")

    def _on_select_folder_clicked(self, _button: Gtk.Button) -> None:
        """Open folder selection dialog."""
        self._open_folder_dialog()

    def _on_select_archive_clicked(self, _button: Gtk.Button) -> None:
        """Open archive selection dialog."""
        self._open_archive_dialog()

    def _open_folder_dialog(self) -> None:
        """Build and open folder selection dialog."""
        root_window = self._get_root_window()

        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title(_("Select theme folder"))
            dialog.select_folder(root_window, None, self._on_folder_dialog_finish)
        else:
            native = Gtk.FileChooserNative.new(
                _("Select theme folder"),
                root_window,
                Gtk.FileChooserAction.SELECT_FOLDER,
                _("Select"),
                _("Cancel"),
            )
            native.connect(
                "response",
                lambda d, res: self._on_legacy_chooser_response(d, res, is_folder=True),
            )
            native.show()

    def _open_archive_dialog(self) -> None:
        """Build and open archive selection dialog."""
        root_window = self._get_root_window()

        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title(_("Select theme archive"))

            filter_archives = Gtk.FileFilter.new()
            filter_archives.set_name(_("Theme archives (*.zip, *.tar.*)"))
            for pattern in [
                "*.zip",
                "*.tar.gz",
                "*.tgz",
                "*.tar.xz",
                "*.txz",
                "*.tar.bz2",
                "*.tbz2",
                "*.tar",
            ]:
                filter_archives.add_pattern(pattern)

            filter_all = Gtk.FileFilter.new()
            filter_all.set_name(_("All files"))
            filter_all.add_pattern("*")

            filters = gi.repository.Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_archives)
            filters.append(filter_all)
            dialog.set_filters(filters)
            dialog.set_default_filter(filter_archives)

            dialog.open(root_window, None, self._on_archive_dialog_finish)
        else:
            native = Gtk.FileChooserNative.new(
                _("Select theme archive"),
                root_window,
                Gtk.FileChooserAction.OPEN,
                _("Open"),
                _("Cancel"),
            )
            filter_archives = Gtk.FileFilter.new()
            filter_archives.set_name(_("Theme archives"))
            for pattern in [
                "*.zip",
                "*.tar.gz",
                "*.tgz",
                "*.tar.xz",
                "*.txz",
                "*.tar.bz2",
                "*.tar",
            ]:
                filter_archives.add_pattern(pattern)
            native.add_filter(filter_archives)
            native.connect(
                "response",
                lambda d, res: self._on_legacy_chooser_response(d, res, is_folder=False),
            )
            native.show()

    def _on_folder_dialog_finish(self, dialog: Any, result: Any) -> None:
        """Completion callback for Gtk.FileDialog.select_folder."""
        try:
            folder_file = dialog.select_folder_finish(result)
            if folder_file:
                path = Path(folder_file.get_path())
                self.select_source(path)
        except (GLib.GError, Exception) as err:
            logger.debug("Folder selection cancelled or failed: %s", err)

    def _on_archive_dialog_finish(self, dialog: Any, result: Any) -> None:
        """Completion callback for Gtk.FileDialog.open."""
        try:
            archive_file = dialog.open_finish(result)
            if archive_file:
                path = Path(archive_file.get_path())
                self.select_source(path)
        except (GLib.GError, Exception) as err:
            logger.debug("Archive selection cancelled or failed: %s", err)

    def _on_legacy_chooser_response(self, dialog: Any, response_id: int, is_folder: bool) -> None:
        """Response callback for legacy Gtk.FileChooserNative."""
        if response_id == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                path = Path(gfile.get_path())
                self.select_source(path)
        dialog.destroy()

    def select_source(self, source_path: Path, sync: bool = False) -> None:
        """Set and inspect source."""
        source_path = Path(source_path)
        self._selected_source = source_path
        self._analyze_source(source_path, sync=sync)

    def _on_retry_clicked(self, _button: Gtk.Button) -> None:
        """Retry analysis or installation of current source."""
        if self._selected_source is not None:
            self._analyze_source(self._selected_source)
        else:
            self._on_reset_to_initial()

    def _analyze_source(self, source_path: Path, sync: bool = False) -> None:
        """Inspect source detecting structure and components."""
        if self._is_analyzing and not sync:
            logger.debug("Analysis already in progress, request ignored.")
            return

        self._is_analyzing = True
        self._analysis_generation += 1
        current_gen = self._analysis_generation
        self._set_state("analyzing")
        self._set_controls_sensitive(False)

        def worker_inspect() -> tuple[list[tuple[str, ThemeType]] | None, list[str], Exception | None]:
            try:
                if self.manager is None:
                    return [], [], None

                # Inspect source components and inspect validation
                results = self.manager.inspect_theme_source(source_path)

                validation_warnings: list[str] = []
                if hasattr(self.manager, "validator") and self.manager.validator is not None:
                    if source_path.is_dir():
                        for name, t_type in results:
                            val_res = self.manager.validator.validate(source_path, t_type)
                            if not val_res.valid:
                                validation_warnings.extend(val_res.warnings or [f"Invalid {t_type.value} structure"])
                            elif val_res.warnings:
                                validation_warnings.extend(val_res.warnings)
                    else:
                        # For archive, extract into temp directory to validate actual structure
                        try:
                            with tempfile.TemporaryDirectory() as tmp_str:
                                tmp_p = Path(tmp_str)
                                safe_extract(source_path, tmp_p)
                                targets = inspect_extracted_tree(tmp_p, fallback_name=source_path.stem)
                                for t_name, t_dir, t_type in targets:
                                    val_res = self.manager.validator.validate(t_dir, t_type)
                                    if not val_res.valid:
                                        validation_warnings.extend(val_res.warnings or [f"Invalid {t_type.value} structure"])
                                    elif val_res.warnings:
                                        validation_warnings.extend(val_res.warnings)
                        except Exception as ex:
                            logger.debug("Archive pre-validation note: %s", ex)

                return results, validation_warnings, None
            except Exception as err:
                return None, [], err

        def on_inspect_completed(
            result: tuple[list[tuple[str, ThemeType]] | None, list[str], Exception | None],
        ) -> bool:
            if current_gen != self._analysis_generation:
                return GLib.SOURCE_REMOVE

            self._is_analyzing = False
            items, val_warnings, error = result

            if error is not None:
                logger.error("Error analyzing source '%s': %s", source_path, error)
                user_msg = str(error)
                if isinstance(error, ArchiveExtractionError):
                    user_msg = f"{_('Invalid or unsupported archive:')} {error}"
                elif isinstance(error, ThemeValidationError):
                    user_msg = f"{_('Unrecognized theme structure:')} {error}"
                elif isinstance(error, FileNotFoundError):
                    user_msg = f"{_('Source not found:')} {error}"

                self.error_status_page.set_description(user_msg)
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            if not items:
                self.error_status_page.set_description(
                    _("No supported themes (GTK, Shell, Icons, Cursors) detected in source.")
                )
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            theme_name = items[0][0]
            components = [t_type for _, t_type in items]

            self._detected_name = theme_name
            self._detected_components = components

            short_path = str(source_path)
            home_str = str(Path.home())
            if short_path.startswith(home_str):
                short_path = "~" + short_path[len(home_str) :]

            self.source_name_row.set_subtitle(short_path)
            self.source_type_row.set_subtitle(
                _("Folder") if source_path.is_dir() else _("Compressed archive")
            )
            self.detected_theme_name_row.set_subtitle(theme_name)
            self.detected_components_row.set_subtitle(format_components_label(components))

            if self.validation_status_row is not None:
                if val_warnings:
                    first_warn = val_warnings[0]
                    more = f" (+{len(val_warnings) - 1} {_('more')})" if len(val_warnings) > 1 else ""
                    self.validation_status_row.set_subtitle(f"{first_warn}{more}")
                    if self.validation_status_icon is not None:
                        self.validation_status_icon.set_from_icon_name("dialog-warning-symbolic")
                else:
                    self.validation_status_row.set_subtitle(_("Valid (all structure checks passed)"))
                    if self.validation_status_icon is not None:
                        self.validation_status_icon.set_from_icon_name("emblem-ok-symbolic")

            self._set_state("ready")
            self._set_controls_sensitive(True)
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_inspect()
            on_inspect_completed(res)
        else:

            def thread_target() -> None:
                res = worker_inspect()
                GLib.idle_add(on_inspect_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    def _on_install_clicked(self, _button: Gtk.Button) -> None:
        """Handle click on 'Install' button."""
        if self._selected_source is None or self._is_installing:
            return
        self._run_install(apply_after=False)

    def _on_install_and_apply_clicked(self, _button: Gtk.Button) -> None:
        """Handle click on 'Install and Apply' button."""
        if self._selected_source is None or self._is_installing:
            return
        self._run_install(apply_after=True)

    def _run_install(
        self,
        apply_after: bool = False,
        overwrite: bool = False,
        sync: bool = False,
    ) -> None:
        """Execute installation workflow."""
        if self._is_installing and not sync:
            logger.debug("Installation already in progress, request ignored.")
            return

        if self._selected_source is None:
            return

        source_path = self._selected_source
        self._is_installing = True
        self._install_generation += 1
        current_gen = self._install_generation

        self._set_state("installing")
        self._set_controls_sensitive(False)

        use_legacy = (
            self.target_dir_switch.get_active() if hasattr(self, "target_dir_switch") else False
        )
        target_dir_param = "legacy" if use_legacy else "xdg"

        def worker_install() -> tuple[list[Theme] | None, ApplyResult | None, Exception | None]:
            try:
                if self.manager is None:
                    return [], None, None

                installed_themes = self.manager.install_theme(
                    source_path=source_path,
                    overwrite=overwrite,
                    target_dir=target_dir_param,
                )

                apply_result: ApplyResult | None = None
                if apply_after and installed_themes:
                    theme_name = installed_themes[0].name
                    types = {t.theme_type for t in installed_themes}

                    target_set = ThemeSet(
                        gtk_theme=theme_name if ThemeType.GTK in types else None,
                        shell_theme=theme_name if ThemeType.SHELL in types else None,
                        icon_theme=theme_name if ThemeType.ICON in types else None,
                        cursor_theme=theme_name if ThemeType.CURSOR in types else None,
                    )
                    apply_result = self.manager.apply_themes(target_set)

                return installed_themes, apply_result, None
            except Exception as err:
                return None, None, err

        def on_install_completed(
            result: tuple[list[Theme] | None, ApplyResult | None, Exception | None],
        ) -> bool:
            if current_gen != self._install_generation:
                return GLib.SOURCE_REMOVE

            self._is_installing = False
            installed, apply_res, error = result

            if error is not None:
                if isinstance(error, FileExistsError):
                    self._set_state("ready")
                    self._set_controls_sensitive(True)
                    self._open_overwrite_confirm_dialog(apply_after=apply_after, sync=sync)
                    return GLib.SOURCE_REMOVE

                logger.error("Error during theme installation: %s", error)
                self.error_status_page.set_description(f"{_('Error during installation:')} {error}")
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            installed_list = installed or []
            theme_name = self._detected_name or (
                installed_list[0].name if installed_list else _("Theme")
            )

            if apply_after and apply_res is not None:
                if apply_res.warnings:
                    warnings_str = "; ".join(apply_res.warnings)
                    desc = f"{_('Theme')} '{theme_name}' {_('installed.')}\n{_('Some components were not applied:')} {warnings_str}"
                    self._show_toast(
                        f"{_('Theme')} '{theme_name}' {_('installed (partial application).')}"
                    )
                else:
                    desc = f"{_('Theme')} '{theme_name}' {_('installed and applied successfully.')}"
                    self._show_toast(f"{_('Theme')} '{theme_name}' {_('installed and applied.')}")

                if self.on_theme_applied:
                    try:
                        self.on_theme_applied()
                    except Exception as e:
                        logger.warning("Error in on_theme_applied callback: %s", e)
            else:
                desc = f"{_('Theme')} '{theme_name}' {_('installed successfully into user directories.')}"
                self._show_toast(f"{_('Theme')} '{theme_name}' {_('installed.')}")

                if self.on_theme_installed:
                    try:
                        self.on_theme_installed()
                    except Exception as e:
                        logger.warning("Error in on_theme_installed callback: %s", e)

            self._selected_source = None
            self._detected_name = None
            self._detected_components = []
            self._set_controls_sensitive(False)

            self.success_status_page.set_description(desc)
            self._set_state("success")
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_install()
            on_install_completed(res)
        else:

            def thread_target() -> None:
                res = worker_install()
                GLib.idle_add(on_install_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    def _open_overwrite_confirm_dialog(self, apply_after: bool, sync: bool = False) -> None:
        """Open confirmation dialog for theme overwrite."""
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True
        theme_name = self._detected_name or _("this theme")
        root_window = self._get_root_window()

        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cross_checkbox = None

        if apply_after and self.manager is not None and self._detected_components:
            types = set(self._detected_components)
            if ThemeType.GTK in types:
                has_opposite = bool(self.manager.scanner.find_theme(theme_name, ThemeType.SHELL))
                if has_opposite:
                    cross_checkbox = Gtk.CheckButton.new_with_label(
                        _("Also apply as GNOME Shell theme")
                    )
            elif ThemeType.SHELL in types:
                has_opposite = bool(self.manager.scanner.find_theme(theme_name, ThemeType.GTK))
                if has_opposite:
                    cross_checkbox = Gtk.CheckButton.new_with_label(_("Also apply as GTK theme"))

        if cross_checkbox is not None:
            cross_checkbox.set_margin_top(8)
            cross_checkbox.set_halign(Gtk.Align.CENTER)
            extra_box.append(cross_checkbox)

        def handle_overwrite_confirmed() -> None:
            do_cross = cross_checkbox is not None and cross_checkbox.get_active()
            self._run_install(apply_after=apply_after, overwrite=True, sync=sync)
            if do_cross and self.manager is not None:
                opposite_type = (
                    ThemeType.SHELL if ThemeType.GTK in self._detected_components else ThemeType.GTK
                )
                self.manager.apply_component(
                    component=opposite_type,
                    theme_name=theme_name,
                    apply_gtk4_override=True,
                    propagate_sandbox=True,
                )

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                _("Theme already exists"),
                f'{_("A theme named")} "{theme_name}" {_("already exists in user folder.")}\n\n{_("Do you want to overwrite it?")}',
            )
            if cross_checkbox is not None:
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("overwrite", _("Overwrite"))
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_dialog_response(d: Any, response_param: Any) -> None:
                try:
                    if hasattr(d, "choose_finish") and not isinstance(response_param, str):
                        try:
                            resp = d.choose_finish(response_param)
                        except (GLib.GError, TypeError, ValueError):
                            resp = str(response_param)
                    else:
                        resp = str(response_param)

                    if resp == "overwrite":
                        handle_overwrite_confirmed()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(root_window if isinstance(root_window, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                root_window if isinstance(root_window, Gtk.Window) else None,
                _("Theme already exists"),
                f'{_("A theme named")} "{theme_name}" {_("already exists in user folder.")}\n\n{_("Do you want to overwrite it?")}',
            )
            if cross_checkbox is not None:
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("overwrite", _("Overwrite"))
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_msg_response(_dlg: Any, response: str) -> None:
                try:
                    if response == "overwrite":
                        handle_overwrite_confirmed()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False
            handle_overwrite_confirmed()

    def _get_root_window(self) -> Gtk.Window | None:
        """Retrieve parent Gtk.Window."""
        root = self.widget.get_root()
        if isinstance(root, Gtk.Window):
            return root
        return None

    def _clear_toast(self) -> None:
        """Clear persistent feedback notification."""
        root_window = self._get_root_window()
        if root_window is not None and hasattr(root_window, "clear_feedback"):
            root_window.clear_feedback()

    def _show_toast(self, message: str, timeout: int = 0) -> None:
        """Show persistent feedback notification."""
        root_window = self._get_root_window()
        if root_window is not None and hasattr(root_window, "add_toast"):
            root_window.add_toast(message, timeout=timeout)
        else:
            logger.info("Feedback [InstallerPage]: %s", message)
