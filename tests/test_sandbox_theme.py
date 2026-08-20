# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for system-wide theme preview session with auto-rollback (Task 1.5)."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from gnome_theme_manager.core.models import ApplyResult, Theme, ThemeSet, ThemeType
from gnome_theme_manager.core.sandbox_theme import SystemThemePreviewSession


def test_preview_session_lifecycle_start_and_cancel(tmp_path: Path) -> None:
    """Verifica che start_preview salvi lo snapshot e cancel_preview ripristini il sistema originale in < 100ms."""
    initial_set = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        shell_theme="Yaru",
    )

    applied_sets: list[ThemeSet] = []

    def mock_get_current() -> ThemeSet:
        return initial_set if not applied_sets else applied_sets[-1]

    def mock_apply(ts: ThemeSet, **kwargs: object) -> ApplyResult:
        applied_sets.append(ts)
        return ApplyResult(gtk_theme=ts.gtk_theme)

    session = SystemThemePreviewSession(
        get_current_themes_fn=mock_get_current,
        apply_themes_fn=mock_apply,
    )

    assert not session.is_preview_active

    preview_target = ThemeSet(gtk_theme="Colloid-Dark")
    success = session.start_preview(preview_target)

    assert success is True
    assert session.is_preview_active
    assert session.active_preview_set == preview_target
    assert applied_sets[-1] == preview_target

    start_cancel = time.perf_counter()
    cancel_success = session.cancel_preview()
    cancel_dur_ms = (time.perf_counter() - start_cancel) * 1000

    assert cancel_success is True
    assert not session.is_preview_active
    assert session.active_preview_set is None
    # Il sistema è stato ripristinato allo stato iniziale
    assert applied_sets[-1] == initial_set
    assert cancel_dur_ms < 100.0


def test_preview_session_commit(tmp_path: Path) -> None:
    """Verifica che commit_preview mantenga il tema applicato senza fare rollback."""
    initial_set = ThemeSet(gtk_theme="Yaru")
    applied_sets: list[ThemeSet] = []

    def mock_get_current() -> ThemeSet:
        return initial_set if not applied_sets else applied_sets[-1]

    def mock_apply(ts: ThemeSet, **kwargs: object) -> ApplyResult:
        applied_sets.append(ts)
        return ApplyResult(gtk_theme=ts.gtk_theme)

    session = SystemThemePreviewSession(
        get_current_themes_fn=mock_get_current,
        apply_themes_fn=mock_apply,
    )

    preview_target = ThemeSet(gtk_theme="Colloid-Dark")
    session.start_preview(preview_target)
    assert session.is_preview_active

    commit_res = session.commit_preview()
    assert commit_res is True
    assert not session.is_preview_active
    # Il tema rimane applicato (nessun secondo ripristino ad initial_set)
    assert applied_sets[-1] == preview_target


def test_preview_session_idempotent_cancel() -> None:
    """Verifica che cancel_preview quando nessuna sessione è attiva sia idempotente e restituisca False."""
    session = SystemThemePreviewSession(
        get_current_themes_fn=lambda: ThemeSet(),
        apply_themes_fn=lambda ts, **kw: ApplyResult(success=True, applied_themes=ts),
    )
    assert session.cancel_preview() is False
    assert not session.is_preview_active


def test_theme_manager_preview_session_integration(tmp_path: Path) -> None:
    """Verifica i metodi di facciata start_theme_preview, commit_theme_preview e cancel_theme_preview in ThemeManager."""
    from gnome_theme_manager.core.manager import ThemeManager

    mock_scanner = MagicMock()
    mock_scanner.find_theme.return_value = Theme(
        name="Colloid-Dark",
        theme_type=ThemeType.GTK,
        path=tmp_path / "Colloid-Dark",
        is_user_level=True,
    )

    mock_gsettings = MagicMock()
    mock_gsettings.get_current.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        color_scheme="default",
        shell_theme="Yaru",
    )
    mock_gsettings.apply.return_value = None

    manager = ThemeManager(scanner=mock_scanner, gsettings=mock_gsettings)

    # Inizia anteprima di sistema
    res_start = manager.start_theme_preview("Colloid-Dark", ThemeType.GTK)
    assert res_start is True
    assert manager.is_preview_active

    # Annulla anteprima di sistema (revert)
    res_cancel = manager.cancel_theme_preview()
    assert res_cancel is True
    assert not manager.is_preview_active


def test_theme_manager_preview_with_cross_opposite(tmp_path: Path) -> None:
    """Verifica che start_theme_preview con also_apply_opposite=True estenda l'anteprima anche a Shell/GTK."""
    from gnome_theme_manager.core.manager import ThemeManager

    mock_scanner = MagicMock()
    mock_scanner.find_theme.side_effect = lambda name, c_type: Theme(
        name=name,
        theme_type=c_type,
        path=tmp_path / name,
        is_user_level=True,
    )

    mock_gsettings = MagicMock()
    mock_gsettings.get_current.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        color_scheme="default",
        shell_theme="Yaru",
    )
    mock_gsettings.apply.return_value = None

    mock_validator = MagicMock()
    mock_validator.validate.return_value = MagicMock(valid=True, warnings=[])

    manager = ThemeManager(scanner=mock_scanner, gsettings=mock_gsettings, validator=mock_validator)

    # Inizia anteprima con estensione a tema Shell accoppiato
    res = manager.start_theme_preview("Colloid-Dark", ThemeType.GTK, also_apply_opposite=True)
    assert res is True
    assert manager.is_preview_active
    assert manager.theme_preview.active_preview_set is not None
    assert manager.theme_preview.active_preview_set.gtk_theme == "Colloid-Dark"
    assert manager.theme_preview.active_preview_set.shell_theme == "Colloid-Dark"

    # Deseleziona "applica anche come": disattiva solo Shell e ripristina Yaru da snapshot, mantenendo GTK su Colloid-Dark
    res_uncheck = manager.start_theme_preview(
        "Colloid-Dark", ThemeType.GTK, also_apply_opposite=False
    )
    assert res_uncheck is True
    assert manager.is_preview_active
    assert manager.theme_preview.active_preview_set is not None
    assert manager.theme_preview.active_preview_set.gtk_theme == "Colloid-Dark"
    assert manager.theme_preview.active_preview_set.shell_theme == "Yaru"

    # Rollback pulito finale
    manager.cancel_theme_preview()
    assert not manager.is_preview_active
