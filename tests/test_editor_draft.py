# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for persistent Theme Editor draft state (Task 2.5).

Tests saving, loading, clearing, and existence checks for editor drafts in `editor_draft.json`.
"""

from pathlib import Path

from gnome_theme_manager.core.editor_draft import EditorDraft, EditorDraftManager


def test_editor_draft_serialization() -> None:
    """Test EditorDraft serialization to and from dictionary."""
    draft = EditorDraft(
        theme_name="My Cool Draft",
        gtk_theme="Adwaita-dark",
        shell_theme="Adwaita",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        color_scheme="prefer-dark",
        colors={
            "theme_fg_color": "#ffffff",
            "theme_bg_color": "#1e1e2e",
            "theme_selected_bg_color": "#cba6f7",
            "theme_selected_fg_color": "#11111b",
        },
    )

    data = draft.to_dict()
    assert data["theme_name"] == "My Cool Draft"
    assert data["gtk_theme"] == "Adwaita-dark"
    assert data["colors"]["theme_bg_color"] == "#1e1e2e"

    reconstructed = EditorDraft.from_dict(data)
    assert reconstructed.theme_name == draft.theme_name
    assert reconstructed.colors == draft.colors
    assert reconstructed.icon_theme == "Papirus"


def test_editor_draft_manager_save_and_load(tmp_path: Path) -> None:
    """Test EditorDraftManager saves and reads from specified json file."""
    draft_file = tmp_path / "state" / "editor_draft.json"
    manager = EditorDraftManager(draft_file=draft_file)

    assert not manager.has_draft()
    assert manager.load_draft() is None

    draft = EditorDraft(
        theme_name="Working Draft",
        gtk_theme="Yaru-dark",
        colors={"theme_bg_color": "#121212"},
    )
    manager.save_draft(draft)

    assert manager.has_draft()
    assert draft_file.is_file()

    loaded = manager.load_draft()
    assert loaded is not None
    assert loaded.theme_name == "Working Draft"
    assert loaded.gtk_theme == "Yaru-dark"
    assert loaded.colors["theme_bg_color"] == "#121212"


def test_editor_draft_manager_clear(tmp_path: Path) -> None:
    """Test EditorDraftManager clear_draft removes file."""
    draft_file = tmp_path / "editor_draft.json"
    manager = EditorDraftManager(draft_file=draft_file)

    draft = EditorDraft(theme_name="To Delete")
    manager.save_draft(draft)
    assert manager.has_draft()

    manager.clear_draft()
    assert not manager.has_draft()
    assert manager.load_draft() is None


def test_editor_draft_manager_corrupted_file(tmp_path: Path) -> None:
    """Test EditorDraftManager handles corrupted JSON gracefully."""
    draft_file = tmp_path / "editor_draft.json"
    draft_file.write_text("invalid json {{{", encoding="utf-8")

    manager = EditorDraftManager(draft_file=draft_file)
    assert not manager.has_draft()
    assert manager.load_draft() is None
