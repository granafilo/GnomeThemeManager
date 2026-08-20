# SPDX-License-Identifier: GPL-3.0-or-later

"""Adaptive Color Extraction from Desktop Wallpaper (Task 2.6).

Extracts dominant color palette (k-means clustering with k=5) from the current
GNOME wallpaper image and generates suggested palette colors (background, foreground, accent, accent-fg)
for use in the Theme Editor.
"""

import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger("gnome_theme_manager.core.wallpaper_color")

DEFAULT_FALLBACK_PALETTE: list[str] = [
    "#3584e4",  # GNOME Blue
    "#1e1e2e",  # Dark Background
    "#ffffff",  # Pure White Text
    "#33d17a",  # Accent Green
    "#f6d32d",  # Accent Yellow
    "#e01b24",  # Accent Red
]


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert (R, G, B) integer tuple to lowercase hex string '#rrggbb'."""
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex string '#rrggbb' or '#rgb' to (R, G, B) tuple."""
    cleaned = hex_str.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(c * 2 for c in cleaned)
    if len(cleaned) != 6:
        return (128, 128, 128)
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def _sample_pixels_from_file(image_path: Path, max_samples: int = 2000) -> list[tuple[int, int, int]]:
    """Sample RGB pixels from an image file using GdkPixbuf (if available) or basic byte parsing."""
    try:
        import gi  # type: ignore[import-untyped]

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf  # type: ignore[import-untyped]

        # Load image (downscale only if larger than 64x64)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        if pixbuf is not None and (pixbuf.get_width() > 64 or pixbuf.get_height() > 64):
            pixbuf = pixbuf.scale_simple(64, 64, GdkPixbuf.InterpType.BILINEAR)

        if pixbuf is not None:
            n_channels = pixbuf.get_n_channels()
            rowstride = pixbuf.get_rowstride()
            pixels = pixbuf.get_pixels()
            width = pixbuf.get_width()
            height = pixbuf.get_height()

            samples: list[tuple[int, int, int]] = []
            step_y = max(1, height // 32)
            step_x = max(1, width // 32)
            for y in range(0, height, step_y):
                row_start = y * rowstride
                for x in range(0, width, step_x):
                    pos = row_start + x * n_channels
                    if pos + 2 < len(pixels):
                        r = int(pixels[pos])
                        g = int(pixels[pos + 1])
                        b = int(pixels[pos + 2])
                        samples.append((r, g, b))
            if samples:
                return samples
    except Exception as err:
        logger.debug("GdkPixbuf downscaled sampling failed for %s: %s", image_path, err)

    # PPM / raw fallback if GdkPixbuf is unavailable
    try:
        data = image_path.read_bytes()
        if data.startswith(b"P6"):
            lines = data.split(b"\n", 3)
            if len(lines) >= 4:
                raw_pixels = lines[3]
                samples = []
                for i in range(0, min(len(raw_pixels) - 2, max_samples * 3), 3):
                    samples.append((raw_pixels[i], raw_pixels[i + 1], raw_pixels[i + 2]))
                if samples:
                    return samples
    except Exception:
        pass

    return []


def _kmeans(pixels: list[tuple[int, int, int]], k: int = 5, max_iters: int = 10) -> list[tuple[int, int, int]]:
    """Simple, deterministic k-means clustering in RGB color space."""
    if not pixels:
        return []
    if len(pixels) <= k:
        return pixels

    # Deterministic seed for reproducible palettes
    random.seed(42)
    centroids: list[list[float]] = [[float(c[0]), float(c[1]), float(c[2])] for c in random.sample(pixels, k)]

    for _ in range(max_iters):
        clusters: list[list[tuple[int, int, int]]] = [[] for _ in range(k)]

        for p in pixels:
            # Find closest centroid (Euclidean distance)
            min_dist = float("inf")
            best_idx = 0
            for i, c in enumerate(centroids):
                dist = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
            clusters[best_idx].append(p)

        # Update centroids
        new_centroids: list[list[float]] = []
        for i in range(k):
            cluster = clusters[i]
            if cluster:
                avg_r = float(sum(p[0] for p in cluster) / len(cluster))
                avg_g = float(sum(p[1] for p in cluster) / len(cluster))
                avg_b = float(sum(p[2] for p in cluster) / len(cluster))
                new_centroids.append([avg_r, avg_g, avg_b])
            else:
                new_centroids.append(list(centroids[i]))

        centroids = new_centroids

    # Sort centroids by perceptual saturation and distinctiveness (prefer vibrant accent colors first)
    def _score_color(rgb: tuple[int, int, int]) -> float:
        r, g, b = rgb
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        delta = max_c - min_c
        # Chromatic delta (saturation weight)
        if max_c == 0:
            return 0.0
        sat = delta / max_c
        val = max_c / 255.0
        # Penalize near-black or washed-out near-white colors for accent ranking
        if val < 0.15 or val > 0.95 and sat < 0.1:
            return 0.05
        return sat * 0.7 + (1.0 - abs(val - 0.5)) * 0.3

    centroids.sort(key=lambda c: _score_color((int(c[0]), int(c[1]), int(c[2]))), reverse=True)
    result = [(int(c[0]), int(c[1]), int(c[2])) for c in centroids]
    return result


def extract_dominant_colors_from_image(image_path: Path, k: int = 5) -> list[str]:
    """Extract dominant hex colors from image file using k-means clustering."""
    if not image_path.is_file():
        return list(DEFAULT_FALLBACK_PALETTE)

    pixels = _sample_pixels_from_file(image_path)
    if not pixels:
        return list(DEFAULT_FALLBACK_PALETTE)

    # Use k+2 clusters and pick the most distinctive k colors
    centroids = _kmeans(pixels, k=max(k, 5))
    if not centroids:
        return list(DEFAULT_FALLBACK_PALETTE)

    return [rgb_to_hex(c) for c in centroids[:k]]


def extract_wallpaper_palette(wallpaper_path: Path | None, k: int = 5) -> list[str]:
    """Extract palette from wallpaper path with fallback."""
    if not wallpaper_path or not wallpaper_path.is_file():
        return list(DEFAULT_FALLBACK_PALETTE)
    return extract_dominant_colors_from_image(wallpaper_path, k=k)


class WallpaperColorExtractor:
    """Service to discover current GNOME desktop wallpaper and extract adaptive colors."""

    def __init__(self, gsettings: Any | None = None) -> None:
        """Initialize WallpaperColorExtractor.

        Args:
            gsettings: Optional GSettingsClient facade instance.
        """
        self._gsettings = gsettings

    def get_current_wallpaper_path(self) -> Path | None:
        """Query GSettings for active wallpaper image path."""
        if self._gsettings is not None and hasattr(self._gsettings, "get_wallpaper_path"):
            res = self._gsettings.get_wallpaper_path()
            return res if isinstance(res, Path) else None
        return None

    def get_current_wallpaper_palette(self, k: int = 5) -> list[str]:
        """Extract dominant palette colors from current wallpaper image.

        Args:
            k: Number of dominant colors to extract (default: 5).

        Returns:
            List of hex color strings (e.g. ['#3584e4', '#1e1e2e', ...]).
        """
        wp_path = self.get_current_wallpaper_path()
        return extract_wallpaper_palette(wp_path, k=k)
