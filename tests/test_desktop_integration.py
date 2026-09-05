# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for core desktop integration."""

from pathlib import Path

from gnome_theme_manager.core.desktop_integration import (
    APP_ID,
    ICON_SIZES,
    MIME_ICON_NAME,
    MIME_TYPE,
    generate_desktop_entry_content,
    integrate_desktop,
)


def test_generate_desktop_entry_content() -> None:
    """Verify desktop entry generation contains exact App ID, MimeType, and valid keys."""
    content = generate_desktop_entry_content(exec_path="/custom/path/app.AppImage")
    assert "[Desktop Entry]" in content
    assert f"Icon={APP_ID}" in content
    assert "Exec=/custom/path/app.AppImage" in content
    assert f"MimeType={MIME_TYPE};" in content
    assert "Type=Application" in content


def test_integrate_desktop_idempotent(tmp_path: Path) -> None:
    """Verify integrate_desktop copies .desktop, MIME definitions, and multi-size icons."""
    custom_apps = tmp_path / "applications"
    custom_icons = tmp_path / "icons" / "hicolor"
    custom_mime = tmp_path / "mime"

    success = integrate_desktop(
        custom_target_apps_dir=custom_apps,
        custom_target_icons_dir=custom_icons,
        custom_target_mime_dir=custom_mime,
        custom_exec_path="/opt/gnome-theme-manager.AppImage",
    )
    assert success is True

    # Verify .desktop file
    desktop_file = custom_apps / f"{APP_ID}.desktop"
    assert desktop_file.is_file()
    content = desktop_file.read_text(encoding="utf-8")
    assert f"Icon={APP_ID}" in content
    assert "Exec=/opt/gnome-theme-manager.AppImage" in content
    assert f"MimeType={MIME_TYPE};" in content

    # Verify MIME definition
    mime_file = custom_mime / "packages" / "gtm-appimage.xml"
    assert mime_file.is_file()
    mime_content = mime_file.read_text(encoding="utf-8")
    assert f'<mime-type type="{MIME_TYPE}">' in mime_content
    assert 'glob pattern="GNOMEThemeManager-*.AppImage"' in mime_content

    # Verify app and mimetype icons in hicolor
    for size in ICON_SIZES:
        app_icon = custom_icons / size / "apps" / f"{APP_ID}.png"
        assert app_icon.is_file(), f"Missing app PNG icon for {size}: {app_icon}"

        mime_icon = custom_icons / size / "mimetypes" / f"{MIME_ICON_NAME}.png"
        assert mime_icon.is_file(), f"Missing mimetype PNG icon for {size}: {mime_icon}"

    # Verify SVG scalable icons
    app_svg = custom_icons / "scalable" / "apps" / f"{APP_ID}.svg"
    assert app_svg.is_file(), f"Missing app SVG icon: {app_svg}"

    mime_svg = custom_icons / "scalable" / "mimetypes" / f"{MIME_ICON_NAME}.svg"
    assert mime_svg.is_file(), f"Missing mimetype SVG icon: {mime_svg}"

    # Idempotent re-run overwrites cleanly
    success_rerun = integrate_desktop(
        custom_target_apps_dir=custom_apps,
        custom_target_icons_dir=custom_icons,
        custom_target_mime_dir=custom_mime,
        custom_exec_path="/opt/gnome-theme-manager-v2.AppImage",
    )
    assert success_rerun is True
    updated_content = desktop_file.read_text(encoding="utf-8")
    assert "Exec=/opt/gnome-theme-manager-v2.AppImage" in updated_content


def test_repo_desktop_entry_validity() -> None:
    """Verify repository .desktop file meets FreeDesktop standards for app launcher menus."""
    repo_root = Path(__file__).resolve().parent.parent
    desktop_path = repo_root / "data" / "desktop" / f"{APP_ID}.desktop"
    assert desktop_path.is_file(), f"Missing desktop file: {desktop_path}"

    content = desktop_path.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=GNOME Theme Manager" in content
    assert f"Icon={APP_ID}" in content
    assert "Exec=gnome-theme-manager --gui" in content
    assert "Categories=" in content
    assert "Settings;" in content
    assert "DesktopSettings;" in content
    assert f"StartupWMClass={APP_ID}" in content


def test_repo_metainfo_stock_icon_and_launchable() -> None:
    """Verify repository metainfo.xml contains stock icon and coherent launchable ID."""
    repo_root = Path(__file__).resolve().parent.parent
    metainfo_path = repo_root / "data" / "metainfo" / f"{APP_ID}.metainfo.xml"
    assert metainfo_path.is_file(), f"Missing metainfo file: {metainfo_path}"

    content = metainfo_path.read_text(encoding="utf-8")
    assert f"<id>{APP_ID}</id>" in content
    assert f'<icon type="stock">{APP_ID}</icon>' in content
    assert f'<launchable type="desktop-id">{APP_ID}.desktop</launchable>' in content
    assert '<release version="1.5.0"' in content


def test_repo_hicolor_icons_coverage() -> None:
    """Verify all standard FreeDesktop icon resolutions exist in data/icons/hicolor/."""
    repo_root = Path(__file__).resolve().parent.parent
    hicolor = repo_root / "data" / "icons" / "hicolor"

    for size in ["16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "256x256", "512x512"]:
        icon_file = hicolor / size / "apps" / f"{APP_ID}.png"
        assert icon_file.is_file(), f"Missing standard icon PNG {size}: {icon_file}"

    svg_file = hicolor / "scalable" / "apps" / f"{APP_ID}.svg"
    assert svg_file.is_file(), f"Missing scalable SVG icon: {svg_file}"
