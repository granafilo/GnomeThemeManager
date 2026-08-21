# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Task 3.2: User Themes auto-enable preference and handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.extensions import ExtensionsManager, UIPrefs
from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import ThemeItemPresentation, ThemesPage

if is_gtk_available():
    from gi.repository import Adw, Gtk


def test_ui_prefs_default_and_persistence(tmp_path: Path) -> None:
    """Test UIPrefs loading, defaults, and saving to ui_prefs.json."""
    prefs_file = tmp_path / "ui_prefs.json"
    mgr = ExtensionsManager(prefs_file=prefs_file)

    prefs = mgr.get_prefs()
    assert prefs.auto_enable_user_theme is False

    mgr.set_auto_enable_user_theme(True)
    assert prefs_file.is_file()

    reloaded = mgr.get_prefs()
    assert reloaded.auto_enable_user_theme is True

    # Test loading from corrupted JSON reverts to defaults
    prefs_file.write_text("invalid json", encoding="utf-8")
    safe_prefs = mgr.get_prefs()
    assert safe_prefs.auto_enable_user_theme is False


def test_themes_page_auto_enables_user_theme_when_preference_on(mock_theme_manager) -> None:
    """Test that when auto_enable_user_theme is True, confirming shell theme application enables extension silently."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    mock_theme_manager.extensions.is_user_theme_enabled.return_value = False
    mock_theme_manager.extensions.get_prefs.return_value = UIPrefs(auto_enable_user_theme=True)
    mock_theme_manager.extensions.enable_user_theme.return_value = True

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
        patch.object(page, "apply_theme"),
        patch.object(page, "_open_enable_extension_dialog") as mock_dialog,
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) >= 1
        confirm_dlg = dialog_instances[0]
        # Simulate click on "Save"
        confirm_dlg.emit("response", "apply")

        # Should enable silently without opening extension prompt dialog
        mock_theme_manager.extensions.enable_user_theme.assert_called_once()
        assert not mock_dialog.called


def test_themes_page_prompts_dialog_when_preference_off(mock_theme_manager) -> None:
    """Test that when auto_enable_user_theme is False, dialog is shown if extension is disabled upon clicking Save."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    mock_theme_manager.extensions.is_user_theme_enabled.return_value = False
    mock_theme_manager.extensions.get_prefs.return_value = UIPrefs(auto_enable_user_theme=False)

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
        patch.object(page, "apply_theme"),
        patch.object(page, "_open_enable_extension_dialog") as mock_dialog,
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) >= 1
        confirm_dlg = dialog_instances[0]
        # Simulate click on "Save"
        confirm_dlg.emit("response", "apply")

        # Dialog should be opened
        mock_dialog.assert_called_once()


def test_themes_page_cross_apply_gtk_with_shell_auto_enables_extension(mock_theme_manager) -> None:
    """Test that applying GTK theme with cross-apply shell checkbox checked triggers auto-enable on save."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    mock_theme_manager.extensions.is_user_theme_enabled.return_value = False
    mock_theme_manager.extensions.get_prefs.return_value = UIPrefs(auto_enable_user_theme=True)
    mock_theme_manager.extensions.enable_user_theme.return_value = True

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="GTK",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
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
        patch.object(page, "apply_theme"),
        patch.object(page, "_open_enable_extension_dialog") as mock_dialog,
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) >= 1
        confirm_dlg = dialog_instances[0]

        # Check cross-apply checkbox inside dialog
        extra_child = (
            confirm_dlg.get_extra_child() if hasattr(confirm_dlg, "get_extra_child") else None
        )
        if extra_child is not None:
            # Find checkbox in extra_box
            for child in extra_child:
                if isinstance(child, Gtk.CheckButton):
                    child.set_active(True)

        confirm_dlg.emit("response", "apply")

        mock_theme_manager.extensions.enable_user_theme.assert_called_once()
        assert not mock_dialog.called
