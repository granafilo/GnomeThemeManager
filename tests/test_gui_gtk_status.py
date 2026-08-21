# SPDX-License-Identifier: GPL-3.0-or-later

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import (
    GSettingsUnavailableError,
)
from gnome_theme_manager.core.gsettings import Gtk4OverrideStatus
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.status import (
    StatusPage,
    format_boolean,
    format_color_scheme,
    format_optional_value,
    format_path,
    format_sandbox_status,
    format_shell_theme,
)
from gnome_theme_manager.gui_gtk.pages.themes import (
    build_theme_presentation,
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

# Directory containing UI files
UI_DIR = Path(__file__).parent.parent / "src" / "gnome_theme_manager" / "gui_gtk" / "ui"


def test_status_page_ui_structure_and_scrolling() -> None:
    """Check status_page.ui structure and properties."""
    status_ui_path = UI_DIR / "status_page.ui"
    tree = ET.parse(status_ui_path)
    root = tree.getroot()

    object_ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]
    assert "page_root" in object_ids
    assert "ready_page" in object_ids
    assert "group_themes" in object_ids
    assert "group_sandbox" in object_ids

    assert "row_gtk_theme" in object_ids
    assert "row_icon_theme" in object_ids
    assert "row_cursor_theme" in object_ids
    assert "row_shell_theme" in object_ids
    assert "row_color_scheme" in object_ids
    assert "row_gtk4_override" in object_ids
    assert "row_gsettings_status" in object_ids
    assert "row_user_themes_path" in object_ids
    assert "row_user_icons_path" in object_ids
    assert "row_flatpak_status" in object_ids
    assert "row_snap_status" in object_ids

    ready_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "ready_page")
    props = {p.attrib.get("name"): p.text for p in ready_obj.findall("property")}
    assert props.get("vexpand") == "true"

    group_sandbox_obj = next(
        elem for elem in root.iter("object") if elem.attrib.get("id") == "group_sandbox"
    )
    sandbox_props = {p.attrib.get("name"): p.text for p in group_sandbox_obj.findall("property")}
    assert "&amp;" in sandbox_props.get("title", ""), (
        "Sandbox title must contain &amp; for Pango markup"
    )


def test_format_optional_value() -> None:
    """Check formatting of optional values."""
    assert format_optional_value("Yaru-dark") == "Yaru-dark"
    assert format_optional_value(None) == "Not set"
    assert format_optional_value("", default="Default") == "Default"
    assert format_optional_value("   ", default="N/A") == "N/A"


def test_format_boolean() -> None:
    """Check formatting of booleans into user strings."""
    assert format_boolean(True) == "Yes"
    assert format_boolean(False) == "No"
    assert format_boolean(None) == "Not available"
    assert format_boolean(True, true_label="Active", false_label="Inactive") == "Active"


def test_format_path() -> None:
    """Check conversion and formatting of Path paths."""
    p = Path("/home/user/.local/share/themes")
    assert format_path(p) == "/home/user/.local/share/themes"
    assert format_path(None) == "Not available"


def test_format_color_scheme() -> None:
    """Check formatting of color scheme variants."""
    assert format_color_scheme("prefer-dark") == "Dark (Prefer dark)"
    assert format_color_scheme("default") == "Default (Light)"
    assert format_color_scheme(None) == "Default (Light)"
    assert format_color_scheme("prefer-light") == "Light (Prefer light)"


def test_format_shell_theme() -> None:
    """Check GNOME Shell theme formatting."""
    assert format_shell_theme("Nordic", is_supported=True) == "Nordic"
    assert format_shell_theme(None, is_supported=True) == "System Default"
    assert (
        format_shell_theme("Nordic", is_supported=False)
        == "Not managed ('User Themes' extension inactive)"
    )


def test_format_sandbox_status() -> None:
    """Check sandbox runtime status formatting."""
    res_avail = format_sandbox_status(
        available=True,
        active_or_installed=True,
        active_label="Override active",
        inactive_label="Override inactive",
    )
    assert res_avail == "Available (Override active)"

    res_not_installed = format_sandbox_status(
        available=False,
        active_or_installed=False,
        active_label="OK",
        inactive_label="No",
    )
    assert res_not_installed == "Not available (not installed)"


def test_build_theme_presentation() -> None:
    """Check transformation from Theme to ThemeItemPresentation."""
    theme = Theme(
        name="Nordic-Darker",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic-Darker"),
        is_user_level=True,
    )
    pres = build_theme_presentation(theme)
    assert pres.name == "Nordic-Darker"
    assert pres.category_display == "Applications (GTK)"
    assert pres.origin_display == "User (~/.local/share/...)"
    assert pres.icon_name == "app-logo-symbolic"
    assert pres.is_user_level is True


@pytest.fixture
def mock_theme_manager() -> MagicMock:
    """Fixture returning a mock ThemeManager."""
    mgr = MagicMock(spec=ThemeManager)
    mgr.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        shell_theme="Yaru",
        color_scheme="default",
    )
    mgr.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=SandboxStatus(
            snap_available=True,
            flatpak_available=True,
            snap_gtk_common_themes_installed=True,
            flatpak_filesystem_override_active=True,
        ),
        gtk4_override_active=True,
        gtk4_override_status=Gtk4OverrideStatus.ACTIVE,
    )
    mgr.find_theme.side_effect = lambda name, theme_type: Theme(
        name=name,
        theme_type=theme_type,
        path=Path(f"/home/user/.local/share/themes/{name}"),
        is_user_level=True,
    )
    return mgr


def test_status_page_ready_state_success(mock_theme_manager: MagicMock) -> None:
    """Check that refresh with valid data leads to READY state."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = StatusPage(manager=mock_theme_manager)
    assert page.page_id == "status"
    assert page.title == "Current Status"

    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Yaru" in page.row_gtk_theme.get_subtitle()
    assert "Yaru" in page.row_icon_theme.get_subtitle()
    assert "Yaru" in page.row_cursor_theme.get_subtitle()
    assert "Yaru" in page.row_shell_theme.get_subtitle()
    assert "Default" in page.row_color_scheme.get_subtitle()
    assert "Active" in page.row_gtk4_override.get_subtitle()
    assert "Available" in page.row_gsettings_status.get_subtitle()
    assert "/home/user/.local/share/themes" in page.row_user_themes_path.get_subtitle()
    assert "Available" in page.row_flatpak_status.get_subtitle()
    assert "Available" in page.row_snap_status.get_subtitle()
    assert page.banner_warning.get_revealed() is False


def test_status_page_gtk4_override_inactive(mock_theme_manager: MagicMock) -> None:
    """Check that when gtk4_override_status is INACTIVE, row shows 'Inactive'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    status = mock_theme_manager.get_system_status.return_value
    status.gtk4_override_active = False
    status.gtk4_override_status = Gtk4OverrideStatus.INACTIVE

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Inactive" in page.row_gtk4_override.get_subtitle()


def test_status_page_ready_with_warnings(mock_theme_manager: MagicMock) -> None:
    """Check that environmental limitations trigger Adw.Banner."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=False,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=SandboxStatus(
            snap_available=True,
            flatpak_available=False,
            snap_gtk_common_themes_installed=False,
            flatpak_filesystem_override_active=False,
        ),
        gtk4_override_active=False,
    )

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert page.banner_warning.get_revealed() is True
    assert "User Themes" in page.banner_warning.get_title()
    assert "gtk-common-themes" in page.banner_warning.get_title()


def test_status_page_empty_state() -> None:
    """Check that empty configuration with no GSettings shows EMPTY state."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.get_current_themes.return_value = ThemeSet()
    mock_mgr.get_system_status.return_value = SystemStatus(
        gsettings_available=False,
        shell_theme_supported=False,
        color_scheme_supported=False,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=None,
        gtk4_override_active=False,
    )
    mock_mgr.find_theme.return_value = None

    page = StatusPage(manager=mock_mgr)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "empty"


def test_status_page_error_state_and_retry(mock_theme_manager: MagicMock) -> None:
    """Check that exception leads to ERROR state and retry button works."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_current_themes.side_effect = GSettingsUnavailableError(
        "Schema not found."
    )

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "GSettings is not available" in page.error_page.get_description()

    mock_theme_manager.get_current_themes.side_effect = None
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "ready"


def test_status_page_refresh_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Check that concurrent refresh calls are guarded."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = StatusPage(manager=mock_theme_manager)

    page._is_loading = True
    gen_before = page._generation_id
    page.refresh()
    assert page._generation_id == gen_before
