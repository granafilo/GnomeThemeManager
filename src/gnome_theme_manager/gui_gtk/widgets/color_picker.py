# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom color picker button and dialog wrapper."""

import logging
import re
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GObject, Gtk

from gnome_theme_manager import _

logger = logging.getLogger("gnome_theme_manager.gui_gtk.widgets.color_picker")


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    """Convert Gdk.RGBA to hex color string (#rrggbb)."""
    r = int(rgba.red * 255 + 0.5)
    g = int(rgba.green * 255 + 0.5)
    b = int(rgba.blue * 255 + 0.5)
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgba(hex_str: str) -> Gdk.RGBA:
    """Convert hex string to Gdk.RGBA."""
    rgba = Gdk.RGBA()
    if not rgba.parse(hex_str):
        rgba.parse("#000000")
    return rgba


class ColorPickerButton(Gtk.Box):
    """Widget with an editable HEX entry and a clickable color picker button with preview swatch."""

    __gtype_name__ = "ColorPickerButton"

    __gsignals__: ClassVar[dict[str, Any]] = {
        "color-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, title: str, default_hex: str = "#3584e4") -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._current_hex = default_hex
        self._updating_entry = False

        # 1. Direct editable HEX entry
        self.entry = Gtk.Entry()
        self.entry.set_max_length(9)
        self.entry.set_width_chars(8)
        self.entry.set_placeholder_text("#RRGGBB")
        self.entry.add_css_class("numeric")
        self.entry.set_text(default_hex)
        self.entry.connect("changed", self._on_entry_changed)
        self.append(self.entry)

        # 2. Clickable Swatch & Pick Button (opens Gtk.ColorDialog)
        self.button = Gtk.Button()
        self.button.set_tooltip_text(title)
        self.button.add_css_class("flat")

        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.swatch = Gtk.Box()
        self.swatch.set_size_request(22, 22)
        self.swatch.add_css_class("card")
        self.swatch.set_valign(Gtk.Align.CENTER)
        self._swatch_provider = Gtk.CssProvider()
        display = Gdk.Display.get_default() or Gdk.DisplayManager.get().get_default_display()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._swatch_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
        btn_content.append(self.swatch)

        self.btn_label = Gtk.Label(label=_("Pick"))
        self.btn_label.add_css_class("caption")
        btn_content.append(self.btn_label)

        self.button.set_child(btn_content)
        self.append(self.button)

        self.dialog = Gtk.ColorDialog.new()
        self.dialog.set_title(title)
        self.dialog.set_with_alpha(False)

        self._widget_id = f"picker_{id(self)}"
        self.swatch.add_css_class(self._widget_id)

        self.button.connect("clicked", self._on_button_clicked)
        self.set_color_hex(default_hex)

    def get_color_hex(self) -> str:
        """Return current hex color string."""
        return self._current_hex

    def set_color_hex(self, hex_color: str) -> None:
        """Set current color from hex string with validation."""
        cleaned = hex_color.strip() if hex_color else ""
        if not cleaned:
            cleaned = "#3584e4"
        elif not cleaned.startswith("#"):
            cleaned = f"#{cleaned}"

        if not re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", cleaned):
            return

        self._current_hex = cleaned
        if not self._updating_entry:
            self._updating_entry = True
            try:
                self.entry.set_text(cleaned)
            finally:
                self._updating_entry = False

        css = f".{self._widget_id} {{ background-color: {cleaned}; border-radius: 6px; border: 1px solid rgba(127,127,127,0.4); }}"
        try:
            if hasattr(self._swatch_provider, "load_from_string"):
                self._swatch_provider.load_from_string(css)
            else:
                self._swatch_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            pass

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        """Handle manual hex input from user."""
        if self._updating_entry:
            return

        text = entry.get_text().strip()
        if not text:
            return

        if not text.startswith("#"):
            text = f"#{text}"

        # Validate hex pattern
        if re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", text):
            self._current_hex = text
            css = f".{self._widget_id} {{ background-color: {text}; border-radius: 6px; border: 1px solid rgba(127,127,127,0.4); }}"
            try:
                if hasattr(self._swatch_provider, "load_from_string"):
                    self._swatch_provider.load_from_string(css)
                else:
                    self._swatch_provider.load_from_data(css.encode("utf-8"))
            except Exception:
                pass
            self.emit("color-changed", text)

    def _on_button_clicked(self, _btn: Gtk.Button) -> None:
        """Open ColorDialog to choose color."""
        root = self.get_root()
        parent_window = root if isinstance(root, Gtk.Window) else None
        initial_rgba = hex_to_rgba(self._current_hex)

        def _on_color_chosen(dialog: Gtk.ColorDialog, result: GObject.Object) -> None:
            try:
                rgba = dialog.choose_rgba_finish(result)
                if rgba:
                    hex_val = rgba_to_hex(rgba)
                    self.set_color_hex(hex_val)
                    self.emit("color-changed", hex_val)
            except Exception as err:
                logger.debug("Color dialog dismissed or error: %s", err)

        self.dialog.choose_rgba(parent_window, initial_rgba, None, _on_color_chosen)
