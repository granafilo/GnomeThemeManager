#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Deterministic icon rendering script using GdkPixbuf and BFS flood-fill.

Replaces neutral/transparent outer background with full-bleed vertical gradient:
top #3F8AE0 -> bottom #1C5AA6.
"""

import collections
import sys
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib


def process_icon_full_bleed() -> bool:
    """Process master icon into a full-bleed gradient PNG (512, 256, 128)."""
    repo_root = Path(__file__).resolve().parent.parent
    svg_source = (
        repo_root
        / "data"
        / "icons"
        / "hicolor"
        / "scalable"
        / "apps"
        / "io.github.granafilo.ThemeManager.svg"
    )
    png_source = (
        repo_root
        / "data"
        / "icons"
        / "hicolor"
        / "512x512"
        / "apps"
        / "io.github.granafilo.ThemeManager.png"
    )

    app_id = "io.github.granafilo.ThemeManager"

    # 1. Load Pixbuf 512x512
    if svg_source.is_file():
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(svg_source), 512, 512)
    elif png_source.is_file():
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(png_source), 512, 512)
    else:
        print("Error: No source icon found!", file=sys.stderr)
        return False

    w, h = pixbuf.get_width(), pixbuf.get_height()
    n_channels = pixbuf.get_n_channels()
    rowstride = pixbuf.get_rowstride()
    raw_pixels = bytearray(pixbuf.get_pixels())

    # 2. Maschera sfondo: flood-fill BFS dai pixel di BORDO
    visited: set[tuple[int, int]] = set()
    queue: collections.deque[tuple[int, int]] = collections.deque()

    def is_background_pixel(x: int, y: int) -> bool:
        idx = y * rowstride + x * n_channels
        r = raw_pixels[idx]
        g = raw_pixels[idx + 1]
        b = raw_pixels[idx + 2]
        a = raw_pixels[idx + 3] if n_channels >= 4 else 255

        # Se trasparente -> sfondo
        if a < 200:
            return True
        # Se quasi-neutro e chiaro: max(r,g,b)-min(r,g,b) < 12 and r > 140
        diff = max(r, g, b) - min(r, g, b)
        return bool(diff < 12 and r > 140)

    # Aggiungi tutti i pixel perimetrali alla BFS se corrispondono a sfondo
    for x in range(w):
        for y in [0, h - 1]:
            if is_background_pixel(x, y):
                queue.append((x, y))
                visited.add((x, y))
    for y in range(h):
        for x in [0, w - 1]:
            if (x, y) not in visited and is_background_pixel(x, y):
                queue.append((x, y))
                visited.add((x, y))

    # Esegui BFS flood-fill
    while queue:
        cx, cy = queue.popleft()
        for nx, ny in [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]:
            if (
                0 <= nx < w
                and 0 <= ny < h
                and (nx, ny) not in visited
                and is_background_pixel(nx, ny)
            ):
                visited.add((nx, ny))
                queue.append((nx, ny))

    print(f"Flood-fill matched {len(visited)} background pixels out of {w * h}.")

    # 3. Sostituisci i pixel mascherati con gradiente verticale:
    # top #3F8AE0 (63, 138, 224) -> bottom #1C5AA6 (28, 90, 166)
    top_rgb = (63, 138, 224)
    bottom_rgb = (28, 90, 166)

    for x, y in visited:
        idx = y * rowstride + x * n_channels
        factor = y / float(h - 1)
        nr = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * factor)
        ng = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * factor)
        nb = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * factor)

        raw_pixels[idx] = nr
        raw_pixels[idx + 1] = ng
        raw_pixels[idx + 2] = nb
        if n_channels >= 4:
            raw_pixels[idx + 3] = 255

    # Crea Pixbuf 512 modificato
    gbytes = GLib.Bytes.new(bytes(raw_pixels))
    pixbuf_512 = GdkPixbuf.Pixbuf.new_from_bytes(
        gbytes,
        GdkPixbuf.Colorspace.RGB,
        n_channels == 4,
        8,
        w,
        h,
        rowstride,
    )

    # 4. Deriva 256 e 128
    pixbuf_256 = pixbuf_512.scale_simple(256, 256, GdkPixbuf.InterpType.BILINEAR)
    pixbuf_128 = pixbuf_512.scale_simple(128, 128, GdkPixbuf.InterpType.BILINEAR)

    if not pixbuf_256 or not pixbuf_128:
        print("Error: Failed to scale pixbuf!", file=sys.stderr)
        return False

    targets: dict[int, list[Path]] = {
        128: [
            repo_root / "data" / "icons" / "hicolor" / "128x128" / "apps" / f"{app_id}.png",
            repo_root
            / "data"
            / "icons"
            / "hicolor"
            / "128x128"
            / "mimetypes"
            / "application-vnd.appimage.png",
        ],
        256: [
            repo_root / "data" / "icons" / "hicolor" / "256x256" / "apps" / f"{app_id}.png",
            repo_root
            / "data"
            / "icons"
            / "hicolor"
            / "256x256"
            / "mimetypes"
            / "application-vnd.appimage.png",
        ],
        512: [
            repo_root / "data" / "icons" / "hicolor" / "512x512" / "apps" / f"{app_id}.png",
            repo_root
            / "data"
            / "icons"
            / "hicolor"
            / "512x512"
            / "apps"
            / "gnome-theme-manager.png",
            repo_root
            / "data"
            / "icons"
            / "hicolor"
            / "512x512"
            / "mimetypes"
            / "application-vnd.appimage.png",
            repo_root / "data" / "icons" / f"{app_id}.png",
            repo_root / "data" / "icons" / "gnome-theme-manager.png",
            repo_root / "appimage" / f"{app_id}.png",
        ],
    }

    pixbufs_map = {128: pixbuf_128, 256: pixbuf_256, 512: pixbuf_512}

    for size, paths in targets.items():
        pbuf = pixbufs_map[size]
        for dest in paths:
            dest.parent.mkdir(parents=True, exist_ok=True)
            pbuf.savev(str(dest), "png", [], [])
            print(f"✓ Saved full-bleed {size}x{size}: {dest}")

    print("=== Full-bleed gradient icons generated successfully! ===")
    return True


if __name__ == "__main__":
    if not process_icon_full_bleed():
        sys.exit(1)
