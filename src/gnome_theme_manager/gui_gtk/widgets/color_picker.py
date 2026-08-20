# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom color picker button and dialog wrapper."""

import logging
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GObject, Gtk

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
    """Button with color preview swatch and title that opens a Gtk.ColorDialog."""

    __gtype_name__ = "ColorPickerButton"

    __gsignals__: ClassVar[dict[str, Any]] = {
        "color-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, title: str, default_hex: str = "#3584e4") -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._current_hex = default_hex

        self.button = Gtk.Button()
        self.button.set_tooltip_text(title)
        self.button.add_css_class("flat")

        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Color swatch preview
        self.swatch = Gtk.Box()
        self.swatch.set_size_request(24, 24)
        self.swatch.add_css_class("card")
        self._swatch_provider = Gtk.CssProvider()
        self.swatch.get_style_context().add_provider(
            self._swatch_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        self.label = Gtk.Label(label=default_hex)
        self.label.add_css_class("numeric")

        btn_content.append(self.swatch)
        btn_content.append(self.label)
        self.button.set_child(btn_content)
        self.append(self.button)

        self.dialog = Gtk.ColorDialog.new()
        self.dialog.set_title(title)
        self.dialog.set_with_alpha(False)

        self.button.connect("clicked", self._on_button_clicked)
        self.set_color_hex(default_hex)

    def get_color_hex(self) -> str:
        """Return current hex color string."""
        return self._current_hex

    def set_color_hex(self, hex_color: str) -> None:
        """Set current color from hex string."""
        self._current_hex = hex_color
        self.label.set_label(hex_color)
        css = f"box {{ background-color: {hex_color}; border-radius: 6px; border: 1px solid rgba(127,127,127,0.3); }}"
        try:
            self._swatch_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            pass

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
