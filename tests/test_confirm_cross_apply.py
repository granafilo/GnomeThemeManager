# SPDX-License-Identifier: GPL-3.0-or-later

"""Test for cross-applying GTK and Shell themes in the confirmation dialog."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.models import Theme, ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import ThemeItemPresentation, ThemesPage

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk


def test_themes_page_confirm_gtk_asks_to_apply_as_shell(mock_theme_manager) -> None:
    """Verify that when applying a GTK theme, the dialog asks whether to also apply it for Shell if available."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applications (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="System",
        is_user_level=False,
    )

    # Mock so that Nordic is also found as Shell
    mock_theme_manager.scanner.find_theme.side_effect = lambda name, theme_type: Theme(
        "Nordic", theme_type, Path("/usr/share/themes/Nordic"), False
    )

    dialog_instances = []
    real_init = Adw.AlertDialog.new if hasattr(Adw, "AlertDialog") else Adw.MessageDialog.new

    def fake_new(*args, **kwargs):
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(
            Adw.AlertDialog if hasattr(Adw, "AlertDialog") else Adw.MessageDialog,
            "new",
            side_effect=fake_new,
        ),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
        patch.object(page, "apply_theme"),
    ):
        page.confirm_and_apply_theme(item, sync=True)

        assert len(dialog_instances) == 1
        # Dialog must contain a CheckButton or similar widget to choose also applying to Shell
        # Look for a Gtk.CheckButton widget in dialog's extra child
        extra_child = dialog_instances[0].get_extra_child()
        assert extra_child is not None

        # Look for a CheckButton inside the extra child container
        check_button = None
        child = extra_child.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.CheckButton):
                check_button = child
                break
            child = child.get_next_sibling()

        assert check_button is not None
        assert "Shell" in check_button.get_label()
