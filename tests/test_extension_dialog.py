# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for modal prompt to enable GNOME Shell extension."""

from unittest.mock import patch

import pytest

from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import ThemeItemPresentation, ThemesPage

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw


def test_themes_page_prompts_to_enable_extension_if_disabled(mock_theme_manager) -> None:
    """Verify that if the user-theme extension is disabled, the dialog offers to enable it upon clicking Save."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 not available.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    item = ThemeItemPresentation(
        name="Nordic-Shell",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/usr/share/themes/Nordic-Shell",
        origin_display="Sistema",
        is_user_level=False,
    )

    # Configura lo stato dell'estensione disabilitato
    mock_theme_manager.extensions.is_user_theme_enabled.return_value = False

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

        # The first dialog is the confirmation dialog (Apply ... to GNOME Shell?)
        assert len(dialog_instances) >= 1
        confirm_dlg = dialog_instances[0]

        # Simulate click on "Save" / "apply"
        confirm_dlg.emit("response", "apply")

        # Now the second dialog opens: extension enablement
        assert len(dialog_instances) == 2
        ext_dlg = dialog_instances[1]
        heading = ext_dlg.get_heading() if hasattr(ext_dlg, "get_heading") else ext_dlg.get_title()
        assert "disabilitata" in heading or "User Themes" in heading

        # Enable and continue
        ext_dlg.emit("response", "enable")
        mock_theme_manager.extensions.enable_user_theme.assert_called_once()
