# SPDX-License-Identifier: GPL-3.0-or-later

"""Desktop integration module for GnomeThemeManager.

Installs and updates the desktop launcher (.desktop), hicolor application
icons, and custom AppImage MIME type definitions in the user's local directory:
- ~/.local/share/applications/io.github.granafilo.ThemeManager.desktop
- ~/.local/share/icons/hicolor/<size>/apps/io.github.granafilo.ThemeManager.png
- ~/.local/share/icons/hicolor/<size>/mimetypes/application-vnd.appimage.png
- ~/.local/share/icons/hicolor/scalable/apps/io.github.granafilo.ThemeManager.svg
- ~/.local/share/icons/hicolor/scalable/mimetypes/application-vnd.appimage.svg
- ~/.local/share/mime/packages/gtm-appimage.xml
"""

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("gnome_theme_manager.core.desktop_integration")

APP_ID: str = "io.github.granafilo.ThemeManager"
MIME_TYPE: str = "application/vnd.appimage"
MIME_ICON_NAME: str = "application-vnd.appimage"
ICON_SIZES: list[str] = [
    "16x16",
    "24x24",
    "32x32",
    "48x48",
    "64x64",
    "128x128",
    "256x256",
    "512x512",
]

MIME_XML_CONTENT: str = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/vnd.appimage">
    <comment>GNOME Theme Manager AppImage</comment>
    <icon name="io.github.granafilo.ThemeManager"/>
    <generic-icon name="application-vnd.appimage"/>
    <glob pattern="GNOMEThemeManager-*.AppImage"/>
    <glob pattern="gnome-theme-manager-*.AppImage"/>
    <glob pattern="*.AppImage"/>
    <glob pattern="*.appimage"/>
  </mime-type>
</mime-info>
"""


def get_user_applications_dir() -> Path:
    """Return user-scoped applications directory (~/.local/share/applications)."""
    return Path.home() / ".local" / "share" / "applications"


def get_user_icons_dir() -> Path:
    """Return user-scoped hicolor icons directory (~/.local/share/icons/hicolor)."""
    return Path.home() / ".local" / "share" / "icons" / "hicolor"


def get_user_mime_dir() -> Path:
    """Return user-scoped MIME directory (~/.local/share/mime)."""
    return Path.home() / ".local" / "share" / "mime"


def find_bundled_assets_dir() -> Path | None:
    """Find bundled data/icons or usr/share/icons directory."""
    # 1. Check APPDIR from AppImage environment
    appdir_env = os.environ.get("APPDIR")
    if appdir_env:
        appdir = Path(appdir_env)
        candidate = appdir / "usr" / "share" / "icons" / "hicolor"
        if candidate.is_dir():
            return candidate
        candidate_data = appdir / "data" / "icons" / "hicolor"
        if candidate_data.is_dir():
            return candidate_data

    # 2. Check source tree
    source_root = Path(__file__).resolve().parent.parent.parent.parent
    candidate_source = source_root / "data" / "icons" / "hicolor"
    if candidate_source.is_dir():
        return candidate_source

    return None


def generate_desktop_entry_content(exec_path: str | None = None) -> str:
    """Generate .desktop entry file content with coherent Icon=, Exec=, and MimeType= lines."""
    if not exec_path:
        appimage_env = os.environ.get("APPIMAGE")
        if appimage_env and Path(appimage_env).is_file():
            exec_path = f'"{appimage_env}"'
        else:
            exec_path = "gnome-theme-manager --gui"

    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=GNOME Theme Manager\n"
        "Comment=Manage GTK, Shell, Icon, and Cursor themes on GNOME\n"
        f"Exec={exec_path}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Utility;Settings;DesktopSettings;GNOME;GTK;\n"
        "Keywords=theme;gtk;icon;cursor;gnome;settings;\n"
        f"MimeType={MIME_TYPE};\n"
        "StartupNotify=true\n"
    )


def generate_cached_appimage_thumbnails(appimage_file: Path, icon_source_png: Path) -> None:
    """Generate FreeDesktop-compliant thumbnail cache entries for the AppImage binary."""
    try:
        from PIL import Image, PngImagePlugin

        if not appimage_file.is_file() or not icon_source_png.is_file():
            return

        # Clear failure cache
        fail_dir = Path.home() / ".cache" / "thumbnails" / "fail"
        if fail_dir.is_dir():
            shutil.rmtree(fail_dir, ignore_errors=True)

        uri = appimage_file.resolve().as_uri()
        uri_md5 = hashlib.md5(uri.encode("utf-8")).hexdigest()
        mtime_str = str(int(appimage_file.stat().st_mtime))
        size_str = str(appimage_file.stat().st_size)

        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Thumb::URI", uri)
        pnginfo.add_text("Thumb::MTime", mtime_str)
        pnginfo.add_text("Thumb::Size", size_str)
        pnginfo.add_text("Thumb::Mimetype", MIME_TYPE)
        pnginfo.add_text("Software", "GNOME Theme Manager")

        with Image.open(icon_source_png) as img:
            for thumb_size, dirname in [
                (128, "normal"),
                (256, "large"),
                (512, "x-large"),
                (1024, "xx-large"),
            ]:
                target_dir = Path.home() / ".cache" / "thumbnails" / dirname
                target_dir.mkdir(parents=True, exist_ok=True)
                dest_file = target_dir / f"{uri_md5}.png"
                img_copy = img.copy()
                img_copy.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                img_copy.save(dest_file, "PNG", pnginfo=pnginfo)
    except Exception as err:
        logger.debug("Automatic thumbnail cache generation skipped or failed: %s", err)


def integrate_desktop(
    custom_target_apps_dir: Path | None = None,
    custom_target_icons_dir: Path | None = None,
    custom_target_mime_dir: Path | None = None,
    custom_exec_path: str | None = None,
) -> bool:
    """Install or update desktop launcher, hicolor application icons, and AppImage MIME type.

    Idempotently writes:
    - ~/.local/share/applications/io.github.granafilo.ThemeManager.desktop
    - ~/.local/share/icons/hicolor/{128x128,256x256,512x512}/apps/io.github.granafilo.ThemeManager.png
    - ~/.local/share/icons/hicolor/{128x128,256x256,512x512}/mimetypes/application-vnd.appimage.png
    - ~/.local/share/icons/hicolor/scalable/apps/io.github.granafilo.ThemeManager.svg
    - ~/.local/share/icons/hicolor/scalable/mimetypes/application-vnd.appimage.svg
    - ~/.local/share/mime/packages/gtm-appimage.xml

    Removes any failing thumbnailer entries and ensures valid FreeDesktop thumbnail cache.

    Returns:
        bool: True if integration succeeded.
    """
    if not custom_target_apps_dir and (
        Path("/.flatpak-info").exists() or os.environ.get("FLATPAK_ID")
    ):
        logger.debug("Flatpak sandbox detected; skipping AppImage desktop integration")
        return True

    apps_dir = custom_target_apps_dir or get_user_applications_dir()
    icons_dir = custom_target_icons_dir or get_user_icons_dir()
    mime_dir = custom_target_mime_dir or get_user_mime_dir()

    try:
        apps_dir.mkdir(parents=True, exist_ok=True)
        icons_dir.mkdir(parents=True, exist_ok=True)
        mime_packages_dir = mime_dir / "packages"
        mime_packages_dir.mkdir(parents=True, exist_ok=True)

        changed = False

        # 1. Install / overwrite .desktop entry if changed
        desktop_file = apps_dir / f"{APP_ID}.desktop"
        desktop_content = generate_desktop_entry_content(exec_path=custom_exec_path)
        if (
            not desktop_file.is_file()
            or desktop_file.read_text(encoding="utf-8") != desktop_content
        ):
            desktop_file.write_text(desktop_content, encoding="utf-8")
            changed = True
            logger.info("Wrote desktop launcher to %s", desktop_file)

        # 2. Install / overwrite MIME type definition if changed
        mime_xml_file = mime_packages_dir / "gtm-appimage.xml"
        if (
            not mime_xml_file.is_file()
            or mime_xml_file.read_text(encoding="utf-8") != MIME_XML_CONTENT
        ):
            mime_xml_file.write_text(MIME_XML_CONTENT, encoding="utf-8")
            changed = True
            logger.info("Wrote AppImage MIME definition to %s", mime_xml_file)

        # 3. Clean up any conflicting thumbnailer entries
        thumb_dir = Path.home() / ".local" / "share" / "thumbnailers"
        for thumb_name in ["gtm-appimage.thumbnailer", "appimage.thumbnailer"]:
            conflicting_thumb = thumb_dir / thumb_name
            if conflicting_thumb.is_file():
                try:
                    conflicting_thumb.unlink()
                    changed = True
                except OSError:
                    pass

        # 4. Copy PNG and SVG icons (apps and mimetypes)
        master_png_512: Path | None = None
        assets_hicolor = find_bundled_assets_dir()
        if assets_hicolor and assets_hicolor.is_dir():
            # Copy PNGs (128x128, 256x256, 512x512)
            for size_dir in ICON_SIZES:
                src_png = assets_hicolor / size_dir / "apps" / f"{APP_ID}.png"
                if src_png.is_file():
                    if size_dir == "512x512":
                        master_png_512 = src_png
                    # App icon
                    dest_apps_dir = icons_dir / size_dir / "apps"
                    dest_apps_dir.mkdir(parents=True, exist_ok=True)
                    dest_png = dest_apps_dir / f"{APP_ID}.png"
                    if not dest_png.is_file() or dest_png.stat().st_size != src_png.stat().st_size:
                        shutil.copy2(src_png, dest_png)
                        changed = True
                        logger.debug("Installed app icon %s to %s", src_png, dest_png)

                    # Mimetype icon
                    dest_mime_dir = icons_dir / size_dir / "mimetypes"
                    dest_mime_dir.mkdir(parents=True, exist_ok=True)
                    dest_mime_png = dest_mime_dir / f"{MIME_ICON_NAME}.png"
                    if (
                        not dest_mime_png.is_file()
                        or dest_mime_png.stat().st_size != src_png.stat().st_size
                    ):
                        shutil.copy2(src_png, dest_mime_png)
                        changed = True
                        logger.debug("Installed mimetype icon %s to %s", src_png, dest_mime_png)

            # Copy Scalable SVG (apps and mimetypes)
            src_svg = assets_hicolor / "scalable" / "apps" / f"{APP_ID}.svg"
            if src_svg.is_file():
                # App SVG
                dest_svg_dir = icons_dir / "scalable" / "apps"
                dest_svg_dir.mkdir(parents=True, exist_ok=True)
                dest_svg = dest_svg_dir / f"{APP_ID}.svg"
                if not dest_svg.is_file() or dest_svg.stat().st_size != src_svg.stat().st_size:
                    shutil.copy2(src_svg, dest_svg)
                    changed = True

                # Mimetype SVG
                dest_mime_svg_dir = icons_dir / "scalable" / "mimetypes"
                dest_mime_svg_dir.mkdir(parents=True, exist_ok=True)
                dest_mime_svg = dest_mime_svg_dir / f"{MIME_ICON_NAME}.svg"
                if (
                    not dest_mime_svg.is_file()
                    or dest_mime_svg.stat().st_size != src_svg.stat().st_size
                ):
                    shutil.copy2(src_svg, dest_mime_svg)
                    changed = True

        # 5. Remove any user-level index.theme in hicolor to avoid shadowing system hicolor theme
        user_hicolor_index = icons_dir / "index.theme"
        if user_hicolor_index.is_file():
            try:
                user_hicolor_index.unlink()
                changed = True
            except OSError:
                pass

        # 6. Refresh databases only if files were created or modified
        if changed:
            try:
                subprocess.run(
                    ["update-mime-database", str(mime_dir)],
                    capture_output=True,
                    check=False,
                )
            except Exception as err:
                logger.debug("update-mime-database execution skipped or failed: %s", err)

            try:
                subprocess.run(
                    ["gtk-update-icon-cache", "-f", "-t", str(icons_dir)],
                    capture_output=True,
                    check=False,
                )
            except Exception as err:
                logger.debug("gtk-update-icon-cache execution skipped or failed: %s", err)

            try:
                subprocess.run(
                    ["update-desktop-database", str(apps_dir)],
                    capture_output=True,
                    check=False,
                )
            except Exception as err:
                logger.debug("update-desktop-database execution skipped or failed: %s", err)

        # 7. Pre-generate cached thumbnails if AppImage path is available
        appimage_candidate: Path | None = None
        appimage_env = os.environ.get("APPIMAGE")
        if appimage_env and Path(appimage_env).is_file():
            appimage_candidate = Path(appimage_env)
        elif custom_exec_path and Path(custom_exec_path.strip('"')).is_file():
            appimage_candidate = Path(custom_exec_path.strip('"'))

        if appimage_candidate and master_png_512:
            generate_cached_appimage_thumbnails(appimage_candidate, master_png_512)

        return True
    except Exception as err:
        logger.error("Failed to perform desktop integration: %s", err)
        return False
