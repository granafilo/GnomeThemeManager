# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller for the 'Fonts' page (FASE 4 Task 4.3).

Implements presentation logic for choosing and applying GNOME fonts via
native Gtk.FontDialogButton selectors, consuming exclusively the public API of `ThemeManager`.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gtk, Pango

from ...core.errors import GSettingsUnavailableError
from ...core.fonts import (
    DEFAULT_DOCUMENT_FONT,
    DEFAULT_INTERFACE_FONT,
    DEFAULT_MONOSPACE_FONT,
    FontConfig,
)

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.fonts")

UI_FILE = Path(__file__).parent.parent / "ui" / "fonts_page.ui"


class FontsPage:
    """Controller for the Fonts page widget."""

    def __init__(self, manager: "ThemeManager") -> None:
        """Initialize the Fonts page controller.

        Args:
            manager: Facade providing the font management API.
        """
        self.manager = manager
        self.page_id = "fonts"
        self.title = _("Fonts")

        builder = Gtk.Builder()
        builder.set_translation_domain("gnomethememanager")
        builder.add_from_file(str(UI_FILE))

        self.widget: Gtk.Stack = builder.get_object("page_root")
        self.ready_view: Adw.ToolbarView = builder.get_object("ready")
        self.error_view: Gtk.CenterBox = builder.get_object("error")
        self.error_label: Gtk.Label = builder.get_object("error_label")

        self.interface_font_btn: Gtk.FontDialogButton = builder.get_object("interface_font_btn")
        self.document_font_btn: Gtk.FontDialogButton = builder.get_object("document_font_btn")
        self.monospace_font_btn: Gtk.FontDialogButton = builder.get_object("monospace_font_btn")
        self.scale_spin: Gtk.SpinButton = builder.get_object("scale_spin")

        self.apply_button: Gtk.Button = builder.get_object("apply_button")
        self.reset_button: Gtk.Button = builder.get_object("reset_button")

        if self.apply_button:
            self.apply_button.connect("clicked", self.on_apply_button_clicked)
        if self.reset_button:
            self.reset_button.connect("clicked", self.on_reset_button_clicked)

        self._available: bool = True
        self.on_notify_message: Callable[[str, bool], None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_widget(self) -> Gtk.Widget:
        """Return the top-level widget of this page."""
        return self.widget

    def refresh(self, sync: bool = False) -> None:
        """Load the active font configuration into the form.

        Args:
            sync: Reserved for interface compatibility; refresh is always sync.
        """
        self._load_current()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def on_apply_button_clicked(self, _btn: Gtk.Button) -> None:
        """Apply the entered font configuration to the desktop."""
        if not self._available:
            return
        fonts = self._read_form()
        try:
            applied = self.manager.apply_fonts(fonts)
        except GSettingsUnavailableError as err:
            logger.warning("Cannot apply fonts: %s", err)
            self._notify(_("Cannot apply fonts: GSettings unavailable."), is_error=True)
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to apply fonts")
            self._notify(_("Failed to apply fonts."), is_error=True)
            return

        if applied:
            self._notify(_("Font configuration applied."), is_error=False)
            self.refresh()
        else:
            self._notify(_("No font settings were changed."), is_error=True)

    def on_reset_button_clicked(self, _btn: Gtk.Button) -> None:
        """Discard form edits and reload the active configuration."""
        self._load_current()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _font_desc_to_string(desc: Pango.FontDescription | None, default: str) -> str:
        """Convert Pango.FontDescription to standard font string."""
        if desc is None:
            return default
        name = desc.to_string()
        return name if name and name.strip() else default

    @staticmethod
    def _set_button_font(btn: Gtk.FontDialogButton, font_str: str | None, default: str) -> None:
        """Safely set Pango.FontDescription on a Gtk.FontDialogButton."""
        spec = (font_str or default).strip()
        try:
            desc = Pango.FontDescription.from_string(spec)
            btn.set_font_desc(desc)
        except Exception as err:
            logger.warning("Failed to parse font spec '%s': %s", spec, err)
            btn.set_font_desc(Pango.FontDescription.from_string(default))

    def _load_current(self) -> None:
        """Populate the form from the active system font configuration."""
        try:
            fonts = self.manager.get_current_fonts()
        except GSettingsUnavailableError as err:
            logger.warning("Fonts unavailable: %s", err)
            self._available = False
            self.widget.set_visible_child(self.error_view)
            self.error_label.set_text(_("Font settings are unavailable: {}").format(err))
            return

        self._available = True
        self._set_button_font(self.interface_font_btn, fonts.interface_font, DEFAULT_INTERFACE_FONT)
        self._set_button_font(self.document_font_btn, fonts.document_font, DEFAULT_DOCUMENT_FONT)
        self._set_button_font(self.monospace_font_btn, fonts.monospace_font, DEFAULT_MONOSPACE_FONT)

        if fonts.text_scaling_factor is not None:
            self.scale_spin.set_value(float(fonts.text_scaling_factor))
        self.widget.set_visible_child(self.ready_view)

    def _read_form(self) -> FontConfig:
        """Build a FontConfig from the current form values."""
        interface_str = self._font_desc_to_string(
            self.interface_font_btn.get_font_desc(), DEFAULT_INTERFACE_FONT
        )
        document_str = self._font_desc_to_string(
            self.document_font_btn.get_font_desc(), DEFAULT_DOCUMENT_FONT
        )
        monospace_str = self._font_desc_to_string(
            self.monospace_font_btn.get_font_desc(), DEFAULT_MONOSPACE_FONT
        )

        return FontConfig(
            interface_font=interface_str,
            document_font=document_str,
            monospace_font=monospace_str,
            text_scaling_factor=self.scale_spin.get_value(),
        )

    def _notify(self, message: str, is_error: bool) -> None:
        """Forward a user-facing message to the window (if wired)."""
        if self.on_notify_message is not None:
            self.on_notify_message(message, is_error)
