# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for corruption detection and pre-apply warnings in CLI and GUI (Task 1.3)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.models import ApplyResult, Theme, ThemeSet, ThemeType
from gnome_theme_manager.core.theme_validator import ThemeValidationResult
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import ThemeItemPresentation, ThemesPage

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw


# -----------------------------------------------------------------------------
# CLI Tests for Task 1.3: Warning + Interactive confirmation / -y flag
# -----------------------------------------------------------------------------


def test_cli_apply_corrupted_theme_with_yes_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica che applicando un tema corrotto/incompleto con -y/--yes, venga mostrato un warning e l'applicazione proceda con force=True."""
    mock_gtk = Theme(
        name="BrokenTheme",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/BrokenTheme"),
        is_user_level=False,
    )
    mock_val_res = ThemeValidationResult(
        valid=False,
        warnings=["Missing index.theme configuration file.", "No modern GTK stylesheet detected."],
        missing_files=["gtk-3.0/gtk.css or gtk-4.0/gtk.css"],
    )

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.find_theme.return_value = mock_gtk
        mock_mgr.validate_theme.return_value = mock_val_res
        mock_mgr.apply_themes.return_value = ApplyResult(gtk_theme="BrokenTheme")
        mock_manager_cls.return_value = mock_mgr

        # Launch apply with -y
        exit_code = main(["apply", "--gtk", "BrokenTheme", "-y"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "WARNING" in captured.out or "warning" in captured.out.lower()
        assert "BrokenTheme" in captured.out
        mock_mgr.apply_themes.assert_called_once_with(
            ThemeSet(gtk_theme="BrokenTheme"),
            apply_gtk4_override=True,
            propagate_sandbox=True,
            force=True,
        )


def test_cli_apply_corrupted_theme_prompt_confirmed(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica che applicando un tema corrotto senza -y, venga richiesto un prompt interattivo; se confermato (y), si procede con force=True."""
    mock_gtk = Theme(
        name="BrokenTheme",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/BrokenTheme"),
        is_user_level=False,
    )
    mock_val_res = ThemeValidationResult(
        valid=False,
        warnings=["No modern GTK stylesheet detected."],
        missing_files=["gtk-3.0/gtk.css or gtk-4.0/gtk.css"],
    )

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.find_theme.return_value = mock_gtk
        mock_mgr.validate_theme.return_value = mock_val_res
        mock_mgr.apply_themes.return_value = ApplyResult(gtk_theme="BrokenTheme")
        mock_manager_cls.return_value = mock_mgr

        monkeypatch.setattr("builtins.input", lambda prompt: "y")

        exit_code = main(["apply", "--gtk", "BrokenTheme"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "WARNING" in captured.out or "warning" in captured.out.lower()
        mock_mgr.apply_themes.assert_called_once_with(
            ThemeSet(gtk_theme="BrokenTheme"),
            apply_gtk4_override=True,
            propagate_sandbox=True,
            force=True,
        )


def test_cli_apply_corrupted_theme_prompt_cancelled(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica che se l'utente rifiuta il prompt interattivo (n), l'applicazione venga annullata."""
    mock_gtk = Theme(
        name="BrokenTheme",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/BrokenTheme"),
        is_user_level=False,
    )
    mock_val_res = ThemeValidationResult(
        valid=False,
        warnings=["No modern GTK stylesheet detected."],
        missing_files=["gtk-3.0/gtk.css or gtk-4.0/gtk.css"],
    )

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.find_theme.return_value = mock_gtk
        mock_mgr.validate_theme.return_value = mock_val_res
        mock_manager_cls.return_value = mock_mgr

        monkeypatch.setattr("builtins.input", lambda prompt: "n")

        exit_code = main(["apply", "--gtk", "BrokenTheme"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "cancelled" in captured.out.lower() or "annullat" in captured.out.lower()
        mock_mgr.apply_themes.assert_not_called()


# -----------------------------------------------------------------------------
# GUI Tests for Task 1.3: Adw.MessageDialog / Adw.AlertDialog "Apply anyway / Cancel"
# -----------------------------------------------------------------------------


def test_gui_confirm_corrupted_theme_shows_apply_anyway_dialog(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che nella GUI, tentando di applicare un tema corrotto/incompleto, venga mostrato un dialogo di warning con opzione 'Apply anyway'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    item = ThemeItemPresentation(
        name="CorruptedTheme",
        theme_type=ThemeType.GTK,
        category_display="Applications (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/CorruptedTheme",
        origin_display="System",
        is_user_level=False,
        is_invalid=True,
    )

    mock_theme_manager.scanner.find_theme.return_value = Theme(
        name="CorruptedTheme",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/CorruptedTheme"),
        is_user_level=False,
    )
    mock_theme_manager.validator.validate.return_value = ThemeValidationResult(
        valid=False,
        warnings=["Missing index.theme configuration file.", "No modern GTK stylesheet detected."],
        missing_files=["gtk-3.0/gtk.css"],
    )

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new if hasattr(Adw, "AlertDialog") else Adw.MessageDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
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
        patch.object(page, "apply_theme") as mock_apply_theme,
    ):
        page.confirm_and_apply_theme(item, sync=True)

        assert len(dialog_instances) == 1
        dlg = dialog_instances[0]

        heading = dlg.get_heading() if hasattr(dlg, "get_heading") else dlg.get_title()
        assert (
            "warning" in heading.lower()
            or "incomplete" in heading.lower()
            or "corrupted" in heading.lower()
            or "invalid" in heading.lower()
        )

        # Emit "apply_anyway" response
        dlg.emit("response", "apply_anyway")

        mock_apply_theme.assert_called_once_with(
            item,
            on_complete=None,
            sync=True,
            force=True,
        )
