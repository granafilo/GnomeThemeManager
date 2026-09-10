#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Icon rendering and distribution script for GNOME Theme Manager.

Derives 512, 256, and 128 PNG icons and SVG scalable icons from the custom icon
with true alpha transparency using GdkPixbuf and distributes them across
the repository data, AppDir, and user ~/.local/share/icons/hicolor.
"""

import base64
import sys
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

APP_ID = "io.github.granafilo.ThemeManager"
SHORT_NAME = "gnome-theme-manager"
MIME_NAME = "application-vnd.appimage"


def generate_svg_from_png(png_bytes: bytes) -> str:
    """Wrap high-resolution PNG inside an SVG wrapper for scalable theme lookup."""
    b64_data = base64.b64encode(png_bytes).decode("ascii")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 512 512" width="512" height="512">\n'
        f'  <image width="512" height="512" href="data:image/png;base64,{b64_data}"/>\n'
        "</svg>\n"
    )


def render_and_distribute() -> bool:
    repo_root = Path(__file__).resolve().parent.parent
    user_home = Path.home()

    # Source candidate paths
    src_candidates = [
        repo_root / "data" / "icons" / "hicolor" / "512x512" / "apps" / f"{APP_ID}.png",
        repo_root / "appimage" / f"{APP_ID}.png",
        user_home / "Immagini" / f"{SHORT_NAME}.png",
        user_home / "Immagini" / f"{APP_ID}.png",
    ]

    src_file: Path | None = None
    for cand in src_candidates:
        if cand.is_file():
            src_file = cand
            break

    if not src_file:
        print("Error: Source PNG icon not found!", file=sys.stderr)
        return False

    print(f"Loading clean source icon from: {src_file}")
    pb_orig = GdkPixbuf.Pixbuf.new_from_file(str(src_file))
    if not pb_orig.get_has_alpha():
        print("Warning: Source image does not report alpha channel!", file=sys.stderr)

    # Derive all standard FreeDesktop sizes cleanly
    standard_sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    pixbufs: dict[int, GdkPixbuf.Pixbuf] = {}
    for sz in standard_sizes:
        if sz == 512 and pb_orig.get_width() == 512 and pb_orig.get_height() == 512:
            pixbufs[sz] = pb_orig
        else:
            scaled = pb_orig.scale_simple(sz, sz, GdkPixbuf.InterpType.BILINEAR)
            if not scaled:
                print(f"Error: GdkPixbuf scaling failed for size {sz}!", file=sys.stderr)
                return False
            pixbufs[sz] = scaled

    # PNG Destinations
    hicolor_user = user_home / ".local" / "share" / "icons" / "hicolor"
    hicolor_repo = repo_root / "data" / "icons" / "hicolor"

    # Remove invalid PNG in scalable directory if present
    invalid_scalable_png = hicolor_repo / "scalable" / "apps" / f"{APP_ID}.png"
    if invalid_scalable_png.exists():
        invalid_scalable_png.unlink()

    png_destinations: dict[int, list[Path]] = {}
    for sz in standard_sizes:
        dir_name = f"{sz}x{sz}"
        png_destinations[sz] = [
            hicolor_repo / dir_name / "apps" / f"{APP_ID}.png",
            hicolor_repo / dir_name / "apps" / f"{SHORT_NAME}.png",
            hicolor_user / dir_name / "apps" / f"{APP_ID}.png",
            hicolor_user / dir_name / "apps" / f"{SHORT_NAME}.png",
        ]

    png_destinations[512].extend(
        [
            repo_root / "data" / "icons" / f"{APP_ID}.png",
            repo_root / "data" / "icons" / f"{SHORT_NAME}.png",
            user_home / "Immagini" / f"{APP_ID}.png",
            user_home / "Immagini" / f"{SHORT_NAME}.png",
        ]
    )

    for size, paths in png_destinations.items():
        pb = pixbufs[size]
        for dest in paths:
            dest.parent.mkdir(parents=True, exist_ok=True)
            pb.savev(str(dest), "png", ["compression"], ["9"])
            print(f"✓ Written PNG [{size}x{size}]: {dest}")

    # Scalable SVG generation & distribution (using 256x256 base64 for lightweight vector container)
    png_256_bytes = (hicolor_repo / "256x256" / "apps" / f"{APP_ID}.png").read_bytes()
    svg_content = generate_svg_from_png(png_256_bytes)

    svg_destinations: list[Path] = [
        hicolor_repo / "scalable" / "apps" / f"{APP_ID}.svg",
        hicolor_repo / "scalable" / "apps" / f"{SHORT_NAME}.svg",
        hicolor_user / "scalable" / "apps" / f"{APP_ID}.svg",
        hicolor_user / "scalable" / "apps" / f"{SHORT_NAME}.svg",
        repo_root / "data" / "icons" / f"{APP_ID}.svg",
    ]

    for svg_path in svg_destinations:
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg_content, encoding="utf-8")
        print(f"✓ Written Scalable SVG: {svg_path}")

    print("=== Icon distribution completed successfully! ===")
    return True


if __name__ == "__main__":
    if not render_and_distribute():
        sys.exit(1)
