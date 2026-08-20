# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Wallpaper Adaptive Color Extraction (Task 2.6).

Tests extracting dominant color palette from wallpaper images and GSettings wallpaper path.
"""

from pathlib import Path
from unittest.mock import MagicMock

from gnome_theme_manager.core.wallpaper_color import (
    WallpaperColorExtractor,
    extract_dominant_colors_from_image,
    rgb_to_hex,
)


def test_rgb_to_hex() -> None:
    """Test RGB tuple to HEX string conversion."""
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"
    assert rgb_to_hex((0, 255, 0)) == "#00ff00"
    assert rgb_to_hex((0, 0, 255)) == "#0000ff"
    assert rgb_to_hex((30, 30, 46)) == "#1e1e2e"


def test_extract_dominant_colors_synthetic_ppm(tmp_path: Path) -> None:
    """Test k-means palette extraction on a synthetic PPM image."""
    ppm_file = tmp_path / "test.ppm"
    # Create simple 4x4 PPM image with 2 red, 2 blue pixels
    ppm_content = (
        b"P6\n2 2\n255\n"
        b"\xff\x00\x00\xff\x00\x00"  # Row 1: 2 red pixels
        b"\x00\x00\xff\x00\x00\xff"  # Row 2: 2 blue pixels
    )
    ppm_file.write_bytes(ppm_content)

    palette = extract_dominant_colors_from_image(ppm_file, k=2)
    assert len(palette) > 0
    # Palette should contain a red-ish and blue-ish color
    hexes = [c.lower() for c in palette]
    assert any(h.startswith(("#ff", "#fe")) for h in hexes)


def test_extract_wallpaper_palette_with_missing_file() -> None:
    """Test extractor returns default fallback colors when file does not exist."""
    palette = extract_dominant_colors_from_image(Path("/non/existent/wallpaper.jpg"))
    assert isinstance(palette, list)
    assert len(palette) >= 4
    assert all(c.startswith("#") for c in palette)


def test_wallpaper_color_extractor_with_gsettings(tmp_path: Path) -> None:
    """Test WallpaperColorExtractor fetches current wallpaper path and extracts colors."""
    mock_gsettings = MagicMock()
    mock_gsettings.get_wallpaper_path.return_value = None

    extractor = WallpaperColorExtractor(gsettings=mock_gsettings)
    palette = extractor.get_current_wallpaper_palette(k=5)
    assert len(palette) >= 4
    assert all(c.startswith("#") for c in palette)
