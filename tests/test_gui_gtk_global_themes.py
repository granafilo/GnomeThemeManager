# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GlobalThemesPage GUI controller."""

from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.global_themes import GlobalTheme
from gnome_theme_manager.core.models import ApplyResult, ThemeSet
from gnome_theme_manager.gui_gtk import is_gtk_available


def test_global_themes_page_instantiation(mock_theme_manager: MagicMock) -> None:
    """Verify GlobalThemesPage instantiates and loads UI file."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import GlobalThemesPage

    page = GlobalThemesPage(manager=mock_theme_manager)
    assert page.widget is not None
    assert page.page_id == "global_themes"
    assert page.title == "Global Themes"


def test_global_themes_page_render_cards(mock_theme_manager: MagicMock) -> None:
    """Verify GlobalThemesPage loads and renders theme cards."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import GlobalThemesPage

    theme1 = GlobalTheme(
        id="nordic-night",
        name="Nordic Night",
        description="Arctic clean theme",
        components=ThemeSet(gtk_theme="Nordic", icon_theme="Papirus-Dark"),
        is_bundled=True,
    )
    theme2 = GlobalTheme(
        id="user-custom",
        name="Custom Preset",
        description="My preset",
        components=ThemeSet(gtk_theme="Yaru"),
        is_bundled=False,
    )

    mock_theme_manager.list_global_themes.return_value = [theme1, theme2]

    page = GlobalThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"


def test_global_themes_page_empty_state_when_no_match(mock_theme_manager: MagicMock) -> None:
    """Verify GlobalThemesPage shows empty state when search matches nothing."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import GlobalThemesPage

    theme1 = GlobalTheme(
        id="nordic-night",
        name="Nordic Night",
        description="Arctic clean theme",
        components=ThemeSet(gtk_theme="Nordic"),
        is_bundled=True,
    )
    mock_theme_manager.list_global_themes.return_value = [theme1]

    page = GlobalThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "ready"

    # Simulate search filter
    page.search_entry.set_text("NonExistentThemeName123")
    page._on_search_changed(page.search_entry)
    assert page.widget.get_visible_child_name() == "empty"


def test_global_themes_page_apply_theme(mock_theme_manager: MagicMock) -> None:
    """Verify applying a global theme invokes manager and notifications."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import GlobalThemesPage

    theme1 = GlobalTheme(
        id="nordic-night",
        name="Nordic Night",
        description="Arctic clean theme",
        components=ThemeSet(gtk_theme="Nordic"),
        is_bundled=True,
    )
    mock_theme_manager.list_global_themes.return_value = [theme1]
    mock_theme_manager.get_global_theme.return_value = theme1
    mock_theme_manager.apply_global_theme.return_value = ApplyResult(gtk_theme="Nordic")

    page = GlobalThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    notify_called = []
    applied_called = []
    page.on_notify_message = lambda msg, is_err: notify_called.append((msg, is_err))
    page.on_theme_applied = lambda tid, res: applied_called.append((tid, res))

    page._on_apply_success("nordic-night", ApplyResult(gtk_theme="Nordic"))

    assert len(notify_called) == 1
    assert "Nordic Night" in notify_called[0][0]
    assert notify_called[0][1] is False
    assert len(applied_called) == 1
    assert applied_called[0][0] == "nordic-night"


def test_global_themes_page_save_and_delete(mock_theme_manager: MagicMock) -> None:
    """Verify GlobalThemesPage save current and delete handlers."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import GlobalThemesPage

    user_theme = GlobalTheme(
        id="user-custom",
        name="Custom Preset",
        description="My preset",
        components=ThemeSet(gtk_theme="Yaru"),
        origin="user",
        is_bundled=False,
    )
    mock_theme_manager.list_global_themes.return_value = [user_theme]
    mock_theme_manager.get_global_theme.return_value = user_theme

    page = GlobalThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # Test save
    page._do_save_theme("My New Setup")
    mock_theme_manager.save_current_as_global_theme.assert_called_with(
        "My New Setup", overwrite=True
    )

    # Test delete
    page._do_delete_theme("user-custom", "Custom Preset")
    mock_theme_manager.delete_global_theme.assert_called_with("user-custom")


def test_global_theme_card_icon_fallback(mock_theme_manager: MagicMock) -> None:
    """Verify card renders with custom icon name/file when valid and falls back when missing."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gi.repository import Gtk

    from gnome_theme_manager.gui_gtk.pages.global_themes import _GlobalThemeCard

    # Custom icon override as system icon library name (e.g. 'starred-symbolic')
    custom_named_theme = GlobalTheme(
        id="t-named",
        name="Named Icon Theme",
        description="Icon name override test",
        components=ThemeSet(gtk_theme="Adwaita"),
        origin="user",
        icon_override="starred-symbolic",
    )
    card_named = _GlobalThemeCard(theme=custom_named_theme, on_apply=lambda _: None)
    assert card_named is not None
    img = _GlobalThemeCard._build_card_icon(custom_named_theme)
    assert img.get_icon_name() == "starred-symbolic"

    # No override => must fall back to default symbolic icon
    fallback_theme = GlobalTheme(
        id="t-fallback",
        name="Fallback Icon",
        description="Fallback icon test",
        components=ThemeSet(gtk_theme="Adwaita"),
        origin="bundled",
    )
    icon = _GlobalThemeCard._build_card_icon(fallback_theme)
    assert isinstance(icon, Gtk.Image)
    assert icon.get_icon_name() == "starred-symbolic"


def test_global_theme_card_active_state_detection(mock_theme_manager: MagicMock) -> None:
    """Verify card indicates active state when theme matches active GSettings."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.global_themes import _GlobalThemeCard

    theme_active = GlobalTheme(
        id="t-active",
        name="Nordic",
        description="Active theme",
        components=ThemeSet(gtk_theme="Nordic", icon_theme="Papirus"),
        origin="bundled",
    )
    theme_inactive = GlobalTheme(
        id="t-inactive",
        name="Yaru",
        description="Inactive theme",
        components=ThemeSet(gtk_theme="Yaru", icon_theme="Yaru"),
        origin="bundled",
    )

    current = ThemeSet(gtk_theme="Nordic", icon_theme="Papirus", cursor_theme="Adwaita")

    card_active = _GlobalThemeCard(
        theme=theme_active,
        on_apply=lambda _: None,
        current_themes=current,
    )
    assert card_active.is_active is True
    assert card_active.apply_btn.get_label() == "Applied"

    card_inactive = _GlobalThemeCard(
        theme=theme_inactive,
        on_apply=lambda _: None,
        current_themes=current,
    )
    assert card_inactive.is_active is False
    assert card_inactive.apply_btn.get_label() == "Apply"

