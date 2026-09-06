# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for GTK font dialog utilities and GLib critical warning filter."""

from unittest.mock import patch

import pytest

from gnome_theme_manager.gui_gtk import is_gtk_available


def test_font_utils_filter_logic() -> None:
    """Verify _glib_gio_log_filter selectively suppresses only the upstream GTK bug."""
    if not is_gtk_available():
        pytest.skip("GTK4 unavailable")

    from gi.repository import GLib

    from gnome_theme_manager.gui_gtk.widgets.font_utils import _glib_gio_log_filter

    with patch.object(GLib, "log_default_handler") as mock_default:
        # The specific upstream GTK bug assertion should be suppressed (no forwarding to default handler)
        _glib_gio_log_filter(
            "GLib-GIO",
            GLib.LogLevelFlags.LEVEL_CRITICAL,
            "g_list_model_get_n_items: assertion 'G_IS_LIST_MODEL (list)' failed",
            None,
        )
        mock_default.assert_not_called()

        # Other messages from GLib-GIO should be forwarded
        _glib_gio_log_filter(
            "GLib-GIO",
            GLib.LogLevelFlags.LEVEL_CRITICAL,
            "some_other_assertion: assertion failed",
            None,
        )
        mock_default.assert_called_once()

    with patch.object(GLib, "log_default_handler") as mock_default:
        # Messages from other domains should also be forwarded
        _glib_gio_log_filter(
            "Gtk",
            GLib.LogLevelFlags.LEVEL_CRITICAL,
            "g_list_model_get_n_items: assertion 'G_IS_LIST_MODEL (list)' failed",
            None,
        )
        mock_default.assert_called_once()


def test_safe_set_font_desc_sets_font_description() -> None:
    """Verify safe_set_font_desc sets the font description on a GtkFontDialogButton."""
    if not is_gtk_available():
        pytest.skip("GTK4 unavailable")

    from gi.repository import Gtk, Pango

    from gnome_theme_manager.gui_gtk.widgets.font_utils import safe_set_font_desc

    dialog = Gtk.FontDialog.new()
    btn = Gtk.FontDialogButton.new(dialog)

    desc = Pango.FontDescription.from_string("Cantarell 11")
    safe_set_font_desc(btn, desc)

    result_desc = btn.get_font_desc()
    assert result_desc is not None
    assert "Cantarell" in result_desc.to_string()
    assert "11" in result_desc.to_string()


def test_install_glib_font_dialog_filter() -> None:
    """Verify install_glib_font_dialog_filter installs GLib handler."""
    if not is_gtk_available():
        pytest.skip("GTK4 unavailable")

    from gi.repository import GLib

    from gnome_theme_manager.gui_gtk.widgets.font_utils import install_glib_font_dialog_filter

    with patch.object(GLib, "log_set_handler") as mock_set:
        install_glib_font_dialog_filter()
        mock_set.assert_called_once()
        assert mock_set.call_args[0][0] == "GLib-GIO"
        assert mock_set.call_args[0][1] == GLib.LogLevelFlags.LEVEL_CRITICAL
