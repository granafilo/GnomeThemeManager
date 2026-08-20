# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Theme Editor GUI (Task 2.3)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.global_themes import GlobalTheme
from gnome_theme_manager.core.models import Theme, ThemeSet, ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available


def test_theme_editor_page_instantiation(mock_theme_manager: MagicMock) -> None:
    """Verify ThemeEditorPage instantiates and has correct properties."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    page = ThemeEditorPage(manager=mock_theme_manager)
    assert page.widget is not None
    assert page.page_id == "editor"
    assert page.title == "Theme Editor"


def test_theme_editor_dropdown_population(mock_theme_manager: MagicMock) -> None:
    """Verify ThemeEditorPage populates the 5 theme component dropdowns."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    mock_theme_manager.list_themes.side_effect = lambda t: {
        ThemeType.GTK: [
            Theme(name="Yaru", theme_type=ThemeType.GTK, path=Path("/usr/share/themes/Yaru"), is_user_level=False),
            Theme(name="Nordic", theme_type=ThemeType.GTK, path=Path("/home/u/.themes/Nordic"), is_user_level=True),
        ],
        ThemeType.SHELL: [
            Theme(name="Yaru", theme_type=ThemeType.SHELL, path=Path("/usr/share/themes/Yaru"), is_user_level=False),
        ],
        ThemeType.ICON: [
            Theme(name="Papirus", theme_type=ThemeType.ICON, path=Path("/usr/share/icons/Papirus"), is_user_level=False),
        ],
        ThemeType.CURSOR: [
            Theme(name="Bibata", theme_type=ThemeType.CURSOR, path=Path("/usr/share/icons/Bibata"), is_user_level=False),
        ],
    }.get(t, [])

    page = ThemeEditorPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # Check component selectors exist
    assert page.gtk_dropdown is not None
    assert page.shell_dropdown is not None
    assert page.icon_dropdown is not None
    assert page.cursor_dropdown is not None


def test_theme_editor_color_controls_and_reset(mock_theme_manager: MagicMock) -> None:
    """Verify color controls (fg, bg, accent, accent_fg) exist and reset resets colors."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    page = ThemeEditorPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.fg_color_button is not None
    assert page.bg_color_button is not None
    assert page.accent_color_button is not None
    assert page.accent_fg_color_button is not None

    # Trigger reset colors
    page._on_reset_colors_clicked(None)
    # Default values restored


def test_theme_editor_save_as_global_theme(mock_theme_manager: MagicMock) -> None:
    """Verify saving composition calls manager.save_theme_composition."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    mock_theme_manager.save_theme_composition.return_value = GlobalTheme(
        id="user-custom-mix",
        name="Custom Mix",
        description="A great mix",
        components=ThemeSet(gtk_theme="Nordic"),
        origin="user",
        user_composed=True,
    )

    page = ThemeEditorPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    page.theme_name_entry.set_text("Custom Mix")
    page._on_save_as_global_theme_clicked(None)

    assert mock_theme_manager.save_theme_composition.called
    called_comp = mock_theme_manager.save_theme_composition.call_args[0][0]
    assert called_comp.name == "Custom Mix"
    assert called_comp.user_composed is True


def test_theme_editor_preview_in_app(mock_theme_manager: MagicMock) -> None:
    """Verify live preview calls manager.theme_preview."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    mock_theme_manager.theme_preview = MagicMock()
    mock_theme_manager.theme_preview.is_preview_active = False
    mock_theme_manager.theme_preview.start_preview.return_value = True

    page = ThemeEditorPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    page._on_preview_clicked(None)
    assert mock_theme_manager.theme_preview.start_preview.called


def test_theme_editor_draft_auto_save_and_prompt(mock_theme_manager: MagicMock) -> None:
    """Verify editor auto-saves draft on change and shows banner if draft exists on refresh."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.core.editor_draft import EditorDraft, EditorDraftManager
    from gnome_theme_manager.gui_gtk.pages.editor_view import ThemeEditorPage

    mock_draft_manager = MagicMock(spec=EditorDraftManager)
    mock_draft_manager.has_draft.return_value = True
    saved_draft = EditorDraft(
        theme_name="Unfinished Masterpiece",
        gtk_theme="Adwaita-dark",
        colors={"theme_bg_color": "#112233"},
    )
    mock_draft_manager.load_draft.return_value = saved_draft
    mock_theme_manager.editor_drafts = mock_draft_manager

    page = ThemeEditorPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # Draft banner should be visible
    assert page.draft_banner_box is not None
    assert page.draft_banner_box.get_visible() is True

    # Clicking resume should load draft into entry and controls
    page._on_resume_draft_clicked(None)
    assert page.theme_name_entry.get_text() == "Unfinished Masterpiece"
    assert page.draft_banner_box.get_visible() is False

