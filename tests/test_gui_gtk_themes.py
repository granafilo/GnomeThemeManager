# SPDX-License-Identifier: GPL-3.0-or-later

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import (
    GnomeThemeManagerError,
)
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import (
    ThemeItemPresentation,
    ThemesPage,
)

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Pango", "1.0")
    from gi.repository import Adw, Gdk, GLib, Gtk, Pango
else:
    Adw = None  # type: ignore[assignment]
    Gdk = None  # type: ignore[assignment]
    Gtk = None  # type: ignore[assignment]
    GLib = None  # type: ignore[assignment]
    Pango = None  # type: ignore[assignment]

# Path to the directory containing UI files
UI_DIR = Path(__file__).parent.parent / "src" / "gnome_theme_manager" / "gui_gtk" / "ui"


def test_themes_page_ui_structure_and_scrolling() -> None:
    """Verify the declarative structure of themes_page.ui and its controls."""
    themes_ui_path = UI_DIR / "themes_page.ui"
    tree = ET.parse(themes_ui_path)
    root = tree.getroot()

    object_ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]

    assert "page_root" in object_ids
    assert "loading_page" in object_ids
    assert "loading_spinner" in object_ids
    assert "ready_box" in object_ids
    assert "category_title_label" in object_ids
    assert "active_theme_group" in object_ids
    assert "active_theme_row" in object_ids
    assert "row_color_scheme" in object_ids
    assert "available_section_title" in object_ids
    assert "search_entry" in object_ids
    assert "themes_scrolled_window" in object_ids
    assert "count_label" in object_ids
    assert "themes_list_box" in object_ids
    assert "no_results_page" in object_ids
    assert "action_box" in object_ids
    assert "apply_button" in object_ids
    assert "empty_page" in object_ids
    assert "empty_refresh_button" in object_ids
    assert "error_page" in object_ids
    assert "error_retry_button" in object_ids
    assert "category_dropdown" not in object_ids

    page_root_obj = next(
        elem for elem in root.iter("object") if elem.attrib.get("id") == "page_root"
    )
    root_props = {p.attrib.get("name"): p.text for p in page_root_obj.findall("property")}
    assert root_props.get("vexpand") == "true"
    assert root_props.get("hexpand") == "true"


def test_themes_page_ready_state_and_active_card(mock_theme_manager: MagicMock) -> None:
    """Verify that ThemesPage displays the Active Theme Card and excludes it from the available list."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    assert page.page_id == "themes"

    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    # The active theme for GTK in mock is 'Yaru'
    assert page.active_theme_row.get_title() == "Yaru"
    assert "In use" in page.active_theme_badge.get_text()

    # The alternatives list contains only 'Nordic' ('Yaru' is excluded)
    assert "1 other applications (gtk) available" in page.count_label.get_text()
    assert page.themes_list_box.get_visible() is True
    assert page.apply_button.get_sensitive() is False


def test_themes_page_categories_navigation(mock_theme_manager: MagicMock) -> None:
    """Verify navigation across categories with proper active card and alternatives display."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # 1. GNOME Shell category (active: Yaru [not in local list], 1 alternative: Nordic-Shell)
    page.set_category(ThemeType.SHELL)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "not found" in page.active_theme_row.get_subtitle().lower()
    assert "1 other gnome shell available" in page.count_label.get_text()

    # 2. Cursor category (active: Yaru [not in local list], 1 alternative: Bibata-Modern-Classic)
    page.set_category(ThemeType.CURSOR)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "not found" in page.active_theme_row.get_subtitle().lower()
    assert "1 other cursors available" in page.count_label.get_text()

    # 3. Icon category (active: Yaru [not in local list], 1 alternative: Papirus)
    page.set_category(ThemeType.ICON)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "not found" in page.active_theme_row.get_subtitle().lower()
    assert "1 other icons available" in page.count_label.get_text()

    # 4. GTK category (active: Yaru, 1 alternative: Nordic)
    page.set_category(ThemeType.GTK)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "1 other applications (gtk) available" in page.count_label.get_text()


def test_themes_page_search_filtering_in_available_list(mock_theme_manager: MagicMock) -> None:
    """Verify that text search operates exclusively on available alternative themes."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    # Search for 'nordic' (available)
    page.search_entry.set_text("nordic")
    assert "1 other applications (gtk) available" in page.count_label.get_text()

    # Search for 'yaru' (which is already active and excluded from the available list)
    page.search_entry.set_text("yaru")
    assert page.no_results_page.get_visible() is True
    assert page.themes_list_box.get_visible() is False

    # Clear search
    page.search_entry.set_text("")
    assert "1 other applications (gtk) available" in page.count_label.get_text()
    assert page.no_results_page.get_visible() is False
    assert page.themes_list_box.get_visible() is True


def test_themes_page_apply_theme_updates_card_and_available_list(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that applying a new theme:
    1. Creates a new immutable snapshot;
    2. Displays the new active theme in the card;
    3. Removes the new active theme from the available list;
    4. Reinserts the previous active theme into the available list.
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    snapshot_before = page.current_snapshot
    assert snapshot_before is not None
    assert snapshot_before.active_themes[ThemeType.GTK] == "Yaru"

    item_nordic = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/home/user/.local/share/themes/Nordic",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item_nordic, sync=True)

    # Verify immutability and new snapshot creation
    snapshot_after = page.current_snapshot
    assert snapshot_after is not None
    assert snapshot_after is not snapshot_before
    assert snapshot_after.active_themes[ThemeType.GTK] == "Nordic"

    # Card updated with the new theme
    assert page.active_theme_row.get_title() == "Nordic"

    # Updated list: now contains 'Yaru' ('Nordic' was removed)
    assert "1 other applications (gtk) available" in page.count_label.get_text()
    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    assert first_row.get_title() == "Yaru"


def test_themes_page_single_click_selects_only(mock_theme_manager: MagicMock) -> None:
    """Verify that a single click only selects the row without triggering confirm/apply."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        # Single click emits row-selected
        page.themes_list_box.select_row(first_row)
        assert page.selected_theme is not None
        assert page.selected_theme.name == "Nordic"
        mock_confirm.assert_not_called()


def test_themes_page_double_click_triggers_confirm_and_apply(mock_theme_manager: MagicMock) -> None:
    """Verify that double click (row-activated) triggers theme confirmation/application."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        # Double click emits row-activated
        page.themes_list_box.emit("row-activated", first_row)
        assert page.selected_theme is not None
        assert page.selected_theme.name == "Nordic"
        mock_confirm.assert_called_once()


def test_themes_page_double_click_blocked_during_application(mock_theme_manager: MagicMock) -> None:
    """Verify that double click during an ongoing application is ignored."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    page._is_applying = True

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        page.themes_list_box.emit("row-activated", first_row)
        mock_confirm.assert_not_called()


def test_themes_page_sorting_user_first_then_alphabetical() -> None:
    """Verify themes are sorted by priority:
    1. User themes
    2. System themes
    3. Case-insensitive alphabetical order
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.get_current_themes.return_value = ThemeSet(gtk_theme="ActiveTheme")
    mock_mgr.list_themes.return_value = [
        Theme(
            name="Zeta-Sys",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/Zeta-Sys"),
            is_user_level=False,
        ),
        Theme(
            name="alpha-sys",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/alpha-sys"),
            is_user_level=False,
        ),
        Theme(
            name="Zeta-User",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/Zeta-User"),
            is_user_level=True,
        ),
        Theme(
            name="alpha-user",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/alpha-user"),
            is_user_level=True,
        ),
        Theme(
            name="ActiveTheme",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/ActiveTheme"),
            is_user_level=False,
        ),
    ]

    page = ThemesPage(manager=mock_mgr)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    # Collect row titles from the list
    rendered_titles: list[str] = []
    child = page.themes_list_box.get_first_child()
    while child is not None:
        if hasattr(child, "get_title"):
            rendered_titles.append(child.get_title())
        child = child.get_next_sibling()

    # Expected order: User (alpha-user, Zeta-User) then System (alpha-sys, Zeta-Sys)
    assert rendered_titles == ["alpha-user", "Zeta-User", "alpha-sys", "Zeta-Sys"]


def test_themes_page_cursor_application_shows_informative_toast(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that cursor theme application emits persistent feedback with an informative note."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.CURSOR)

    item_cursor = ThemeItemPresentation(
        name="Bibata-Modern-Classic",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata-Modern-Classic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "_show_toast") as mock_toast:
        page.apply_theme(item_cursor, sync=True)
        # Dedicated informative toast must appear
        mock_toast.assert_called_once()
        msg = mock_toast.call_args[0][0]
        assert "Bibata-Modern-Classic" in msg
        assert "switch windows" in msg.lower() or "restart" in msg.lower()
        # Controls re-enabled
        assert page.is_applying is False


def test_themes_page_cursor_application_error_shows_error_toast(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that on cursor theme application failure an error toast is displayed."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.apply_themes.side_effect = GnomeThemeManagerError("Errore dconf")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.CURSOR)

    item_cursor = ThemeItemPresentation(
        name="Bibata-Modern-Classic",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata-Modern-Classic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "_show_toast") as mock_toast:
        page.apply_theme(item_cursor, sync=True)
        mock_toast.assert_called_once()
        assert "Impossibile" in mock_toast.call_args[0][0] or "Errore" in mock_toast.call_args[0][0]
        assert page.is_applying is False


def test_themes_page_double_click_blocked_when_dialog_already_open(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that if a confirmation dialog is already open, further activations/double-clicks are ignored."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    assert first_row.get_activatable() is True

    page._confirm_dialog_open = True

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        page.themes_list_box.emit("row-activated", first_row)
        mock_confirm.assert_not_called()


def test_themes_page_confirm_dialog_cancel_resets_flag_and_no_apply(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that canceling the confirmation dialog resets _confirm_dialog_open and applies nothing."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

    captured_callback: Any = None

    def fake_connect(signal: str, callback: Any) -> None:
        nonlocal captured_callback
        if signal == "response":
            captured_callback = callback

    with (
        patch.object(page, "apply_theme") as mock_apply,
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect)
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
    ):
        page.confirm_and_apply_theme(item, sync=False)
        assert page._confirm_dialog_open is True

        # Second open attempt while already open: must be ignored
        page.confirm_and_apply_theme(item, sync=False)

        # Simulate 'cancel' response from dialog
        if captured_callback is not None:
            captured_callback(MagicMock(), "cancel")

        assert page._confirm_dialog_open is False
        mock_apply.assert_not_called()


def test_themes_page_confirm_dialog_interactive_apply_resets_flag(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that 'apply' response from interactive dialog resets _confirm_dialog_open and calls apply_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

    captured_callback: Any = None

    def fake_connect(signal: str, callback: Any) -> None:
        nonlocal captured_callback
        if signal == "response":
            captured_callback = callback

    with (
        patch.object(page, "apply_theme") as mock_apply,
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect)
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
    ):
        page.confirm_and_apply_theme(item, sync=False)
        assert page._confirm_dialog_open is True

        # Simulate 'apply' response from dialog
        if captured_callback is not None:
            captured_callback(MagicMock(), "apply")

        assert page._confirm_dialog_open is False
        mock_apply.assert_called_once()


def test_themes_page_confirm_dialog_sync_mode_resets_flag_and_applies(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that with sync=True dialog is still created and on 'apply' response calls apply_theme(sync=True)."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

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
        patch.object(page, "apply_theme") as mock_apply,
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        assert page._confirm_dialog_open is True

        # Simulate 'apply' response
        dialog_instances[0].emit("response", "apply")
        assert page._confirm_dialog_open is False
        mock_apply.assert_called_once_with(item, on_complete=None, sync=True)


def test_themes_page_active_theme_backend_unavailable(mock_theme_manager: MagicMock) -> None:
    """Verify that if backend fails to retrieve the active theme, the card shows 'Not available'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_current_themes.side_effect = GnomeThemeManagerError(
        "GSettings unavailable."
    )

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.active_theme_row.get_title() == "Not available"
    assert page.active_theme_badge.get_visible() is False


def test_themes_page_cursor_propagate_fallback_error(mock_theme_manager: MagicMock) -> None:
    """Verify that an error in GtkSettings during cursor propagation is handled without exceptions."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)

    with patch(
        "gi.repository.Gdk.Display.get_default", side_effect=RuntimeError("Display unavailable")
    ):
        # Must not raise exceptions
        res = page._propagate_cursor_theme_in_process("Bibata-Modern-Classic")
        assert res is False


def test_themes_page_selection_enables_apply_button(mock_theme_manager: MagicMock) -> None:
    """Verify that selecting an alternative theme from the list enables the Apply button."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    assert page.selected_theme is None
    assert page.apply_button.get_sensitive() is False

    # Select available theme from list ('Nordic')
    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    page.themes_list_box.select_row(first_row)

    assert page.selected_theme is not None
    assert page.selected_theme.name == "Nordic"
    assert page.apply_button.get_sensitive() is True


def test_themes_page_empty_state() -> None:
    """Verify that when list_themes returns an empty list the EMPTY state is shown."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.list_themes.return_value = []
    mock_mgr.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        shell_theme="Yaru",
    )

    page = ThemesPage(manager=mock_mgr)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "empty"


def test_themes_page_error_state_and_retry(mock_theme_manager: MagicMock) -> None:
    """Verify transition to ERROR state on exception and retry behavior."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.list_themes.side_effect = GnomeThemeManagerError("Scansione fallita.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "Scansione fallita" in page.error_page.get_description()

    # Restore success condition and synchronous retry
    mock_theme_manager.list_themes.side_effect = None
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "ready"


def test_themes_page_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Verify that concurrent refresh requests on ThemesPage are blocked."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page._is_loading = True
    gen_before = page._generation_id
    page.refresh()
    assert page._generation_id == gen_before


def test_themes_page_apply_theme_mapping_gtk(mock_theme_manager: MagicMock) -> None:
    """Verify that applying a GTK theme configures only gtk_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    # Verify invocation with apply_component
    mock_theme_manager.apply_component.assert_called_once_with(
        component=ThemeType.GTK,
        theme_name="Nordic",
        apply_gtk4_override=True,
        propagate_sandbox=True,
    )


def test_themes_page_apply_theme_mapping_icon(mock_theme_manager: MagicMock) -> None:
    """Verify that applying an icon theme configures only icon_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Papirus",
        theme_type=ThemeType.ICON,
        category_display="Icone",
        icon_name="applications-graphics-symbolic",
        path_display="/usr/share/icons/Papirus",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    mock_theme_manager.apply_component.assert_called_once_with(
        component=ThemeType.ICON,
        theme_name="Papirus",
        apply_gtk4_override=True,
        propagate_sandbox=True,
    )


def test_themes_page_apply_theme_mapping_cursor(mock_theme_manager: MagicMock) -> None:
    """Verify that applying a cursor theme configures only cursor_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Bibata",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/home/user/.local/share/icons/Bibata",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    mock_theme_manager.apply_component.assert_called_once_with(
        component=ThemeType.CURSOR,
        theme_name="Bibata",
        apply_gtk4_override=True,
        propagate_sandbox=True,
    )


def test_themes_page_apply_theme_mapping_shell(mock_theme_manager: MagicMock) -> None:
    """Verify that applying a shell theme configures only shell_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic-Shell",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/home/user/.local/share/themes/Nordic-Shell",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    mock_theme_manager.apply_component.assert_called_once_with(
        component=ThemeType.SHELL,
        theme_name="Nordic-Shell",
        apply_gtk4_override=True,
        propagate_sandbox=True,
    )


def test_themes_page_apply_theme_success_notifies_listener(mock_theme_manager: MagicMock) -> None:
    """Verify that successful application notifies the on_theme_applied listener."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    mock_listener.assert_called_once()
    assert mock_listener.call_args[0][0] == item


def test_themes_page_apply_theme_error_handling(mock_theme_manager: MagicMock) -> None:
    """Verify that an error during application resets _is_applying and notifies the error."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.apply_themes.side_effect = GnomeThemeManagerError("GSettings write failed.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="ErrorTheme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/ErrorTheme",
        origin_display="Sistema",
        is_user_level=False,
    )

    on_complete_mock = MagicMock()
    page.apply_theme(item, on_complete=on_complete_mock, sync=True)

    assert page.is_applying is False
    on_complete_mock.assert_called_once()
    assert on_complete_mock.call_args[0][0] is None
    assert isinstance(on_complete_mock.call_args[0][1], GnomeThemeManagerError)


def test_themes_page_apply_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Verify that a second concurrent application is discarded if one is already running."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page._is_applying = True

    item = ThemeItemPresentation(
        name="ConcurrentTheme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/ConcurrentTheme",
        origin_display="Sistema",
        is_user_level=False,
    )

    on_complete_mock = MagicMock()
    page.apply_theme(item, on_complete=on_complete_mock, sync=True)

    on_complete_mock.assert_called_once()
    assert "already in progress" in str(on_complete_mock.call_args[0][1])


def test_themes_page_apply_shell_theme_missing_user_themes(mock_theme_manager: MagicMock) -> None:
    """Verify that if Shell theme cannot be applied (shell_theme=None), success is not notified."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.apply_themes.return_value = ApplyResult(
        shell_theme=None,
        warnings=["Impossibile applicare il tema GNOME Shell: estensione User Themes non attiva."],
    )

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Nordic-Shell",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/home/user/.local/share/themes/Nordic-Shell",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    # Success listener must NOT have been called
    mock_listener.assert_not_called()


def test_themes_page_apply_gtk_theme_without_gtk4_override(mock_theme_manager: MagicMock) -> None:
    """Verify that a GTK theme applied without GTK4 override still notifies the listener with the result."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.apply_themes.return_value = ApplyResult(
        gtk_theme="Classic-Theme",
        gtk4_override_applied=False,
        warnings=[],
    )

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Classic-Theme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Classic-Theme",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    mock_listener.assert_called_once()
    assert mock_listener.call_args[0][0] == item


def test_themes_page_confirm_dialog_clean_structure_and_sizing(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify clean confirmation dialog structure:
    - Title: "Apply 'NAME' to CATEGORY?"
    - No path or origin in main text
    - Category and active theme presence
    - Comfortable spacing (minimum width 500px)
    - Labels with wrap=False and ellipsize=END
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.SHELL)

    item = ThemeItemPresentation(
        name="Colloid",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/usr/share/themes/Colloid",
        origin_display="Sistema",
        is_user_level=False,
    )

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
        patch.object(Adw.AlertDialog, "present"),
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        dlg = dialog_instances[0]

        # Verify clean title
        assert dlg.get_heading() == "Apply “Colloid” to GNOME Shell?"

        # Verify extra_child content
        extra_child = dlg.get_extra_child()
        assert extra_child is not None
        assert isinstance(extra_child, Gtk.Box)

        # Verify comfortable minimum width (500px)
        width, _ = extra_child.get_size_request()
        assert width >= 480

        # Inspect inner labels
        labels: list[Gtk.Label] = []
        child = extra_child.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                labels.append(child)
            child = child.get_next_sibling()

        assert len(labels) >= 1
        cat_text = labels[0].get_text()
        assert cat_text == "Category: GNOME Shell"
        assert labels[0].get_wrap() is False
        assert labels[0].get_ellipsize() == Pango.EllipsizeMode.END

        # Verify absence of paths and technical details
        for lbl in labels:
            text = lbl.get_text()
            assert "/usr/share" not in text
            assert "~/.local" not in text
            assert "System" not in text
            assert "User" not in text


def test_themes_page_confirm_dialog_long_name_and_active_theme(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify dialog behavior with long names and active theme populated."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    long_name = "Very-Long-Theme-Name-Variant-Dark-Custom-Build-Extended-Edition"
    item = ThemeItemPresentation(
        name=long_name,
        theme_type=ThemeType.GTK,
        category_display="Applications (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display=f"/usr/share/themes/{long_name}",
        origin_display="System",
        is_user_level=False,
    )

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
        patch.object(Adw.AlertDialog, "present"),
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        dlg = dialog_instances[0]

        assert dlg.get_heading() == f"Apply “{long_name}” to GTK?"

        extra_child = dlg.get_extra_child()
        assert extra_child is not None
        labels: list[Gtk.Label] = []
        child = extra_child.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                labels.append(child)
            child = child.get_next_sibling()

        assert len(labels) == 2
        assert labels[0].get_text() == "Category: GTK"
        assert labels[1].get_text() == "Currently active theme: Yaru"
        assert labels[1].get_wrap() is False

        assert labels[1].get_ellipsize() == Pango.EllipsizeMode.END


def test_themes_page_confirm_dialog_accept(mock_theme_manager: MagicMock) -> None:
    """Verify that confirming with 'apply' in the dialog invokes theme application."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "apply_theme") as mock_apply:
        dialog_instances = []
        real_init = Adw.AlertDialog.new

        def fake_new(*args: Any, **kwargs: Any) -> Any:
            dlg = real_init(*args, **kwargs)
            dialog_instances.append(dlg)
            return dlg

        with (
            patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
            patch.object(Adw.AlertDialog, "present"),
        ):
            page.confirm_and_apply_theme(item, sync=True)
            assert len(dialog_instances) == 1
            # Emit "apply" response
            dialog_instances[0].emit("response", "apply")
            mock_apply.assert_called_once_with(item, on_complete=None, sync=True)


def test_themes_page_confirm_dialog_cancel(mock_theme_manager: MagicMock) -> None:
    """Verify that canceling with 'cancel' in the dialog does not invoke theme application."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "apply_theme") as mock_apply:
        dialog_instances = []
        real_init = Adw.AlertDialog.new

        def fake_new(*args: Any, **kwargs: Any) -> Any:
            dlg = real_init(*args, **kwargs)
            dialog_instances.append(dlg)
            return dlg

        with (
            patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
            patch.object(Adw.AlertDialog, "present"),
        ):
            page.confirm_and_apply_theme(item, sync=True)
            assert len(dialog_instances) == 1
            # Emit "cancel" response
            dialog_instances[0].emit("response", "cancel")
            mock_apply.assert_not_called()


def test_themes_page_category_specific_feedback_messages(mock_theme_manager: MagicMock) -> None:
    """Verify that each category emits a clear and specific success message."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    toasts: list[str] = []
    page._show_toast = lambda msg, **kwargs: toasts.append(msg)

    # 1. GTK with override
    mock_theme_manager.apply_themes.return_value = ApplyResult(gtk4_override_applied=True)
    item_gtk = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applications (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="System",
        is_user_level=False,
    )
    page.apply_theme(item_gtk, sync=True)
    assert len(toasts) == 1
    assert "GTK theme «Nordic» applied" in toasts[-1]
    assert "GTK4" in toasts[-1]

    # 2. GNOME Shell
    mock_theme_manager.apply_themes.return_value = ApplyResult(shell_theme="Colloid")
    item_shell = ThemeItemPresentation(
        name="Colloid",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/usr/share/themes/Colloid",
        origin_display="System",
        is_user_level=False,
    )
    page.apply_theme(item_shell, sync=True)
    assert len(toasts) == 2
    assert "GNOME Shell theme «Colloid» applied" in toasts[-1]

    # 3. Icons
    mock_theme_manager.apply_themes.return_value = ApplyResult()
    item_icon = ThemeItemPresentation(
        name="Papirus",
        theme_type=ThemeType.ICON,
        category_display="Icons",
        icon_name="applications-graphics-symbolic",
        path_display="/usr/share/icons/Papirus",
        origin_display="System",
        is_user_level=False,
    )
    page.apply_theme(item_icon, sync=True)
    assert len(toasts) == 3
    assert "Icon theme «Papirus» applied" in toasts[-1]

    # 4. Cursor
    mock_theme_manager.apply_themes.return_value = ApplyResult()
    item_cursor = ThemeItemPresentation(
        name="Bibata",
        theme_type=ThemeType.CURSOR,
        category_display="Cursors",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata",
        origin_display="System",
        is_user_level=False,
    )
    page.apply_theme(item_cursor, sync=True)
    assert len(toasts) == 4
    assert "Cursor theme «Bibata» applied" in toasts[-1]
    assert "switch windows" in toasts[-1] or "restart" in toasts[-1]

    # 5. GNOME Shell partial (no user themes)
    mock_theme_manager.apply_themes.return_value = ApplyResult(shell_theme=None)
    page.apply_theme(item_shell, sync=True)
    assert len(toasts) == 5
    assert "partially" in toasts[-1].lower()
    assert "User Themes" in toasts[-1]


def test_themes_page_color_scheme_combo_row(mock_theme_manager: MagicMock) -> None:
    """Verify that the color_scheme selector is visible only for GTK and updates GSettings."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        color_scheme="prefer-dark",
    )
    mock_theme_manager.scanner.list_themes.return_value = []

    page = ThemesPage(manager=mock_theme_manager)
    page.set_category(ThemeType.GTK)
    page.refresh(sync=True)

    assert page.row_color_scheme is not None
    assert page.row_color_scheme.get_visible() is True
    # prefer-dark should correspond to index 1 ("Dark")
    assert page.row_color_scheme.get_selected() == 1

    # Switch to Icons -> row should be hidden
    page.set_category(ThemeType.ICON)
    page.refresh(sync=True)
    assert page.row_color_scheme.get_visible() is False

    # Switch back to GTK and change color scheme
    page.set_category(ThemeType.GTK)
    page.refresh(sync=True)
    assert page.row_color_scheme.get_visible() is True

    # Change selection to 2 ("prefer-light")
    page.row_color_scheme.set_selected(2)
    mock_theme_manager.gsettings.set_color_scheme.assert_called_with("prefer-light")
