# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for CSS Color Extractor (Task 2.2)."""

from pathlib import Path

from gnome_theme_manager.core.css_extractor import (
    ExtractedColors,
    extract_theme_colors,
    parse_css_define_colors,
)


def test_parse_css_define_colors_basic() -> None:
    """Test extracting @define-color definitions from CSS text."""
    css_content = """
    /* Theme color definitions */
    @define-color theme_fg_color #2e3436;
    @define-color theme_bg_color #f6f5f4;
    @define-color theme_selected_bg_color #3584e4;
    @define-color theme_selected_fg_color #ffffff;
    @define-color wm_title #2e3436;
    @define-color wm_bg_a #fafafa;
    @define-color custom_color rgba(255, 0, 0, 0.8);
    """
    colors = parse_css_define_colors(css_content)
    assert colors["theme_fg_color"] == "#2e3436"
    assert colors["theme_bg_color"] == "#f6f5f4"
    assert colors["theme_selected_bg_color"] == "#3584e4"
    assert colors["theme_selected_fg_color"] == "#ffffff"
    assert colors["wm_title"] == "#2e3436"
    assert colors["wm_bg_a"] == "#fafafa"
    assert colors["custom_color"] == "rgba(255, 0, 0, 0.8)"


def test_parse_css_with_comments_and_formatting() -> None:
    """Test extracting define colors with multiline formatting, trailing comments, and spaces."""
    css_content = """
    @define-color   theme_fg_color    rgb(46, 52, 54) ; /* Foreground */
    @define-color
        theme_bg_color
        #ffffff;
    /* @define-color commented_out #123456; */
    """
    colors = parse_css_define_colors(css_content)
    assert colors["theme_fg_color"] == "rgb(46, 52, 54)"
    assert colors["theme_bg_color"] == "#ffffff"
    assert "commented_out" not in colors


def test_extract_theme_colors_from_gtk4_file(tmp_path: Path) -> None:
    """Test extract_theme_colors preferentially reads gtk-4.0/gtk.css."""
    theme_dir = tmp_path / "MyTheme"
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True)
    (gtk4_dir / "gtk.css").write_text(
        """
        @define-color theme_fg_color #ffffff;
        @define-color theme_bg_color #1e1e2e;
        @define-color theme_selected_bg_color #cba6f7;
        @define-color theme_selected_fg_color #11111b;
        @define-color accent_color #89b4fa;
        @define-color accent_bg_color #89b4fa;
        @define-color accent_fg_color #11111b;
        """,
        encoding="utf-8",
    )

    extracted: ExtractedColors = extract_theme_colors(theme_dir)
    assert extracted.theme_fg_color == "#ffffff"
    assert extracted.theme_bg_color == "#1e1e2e"
    assert extracted.theme_selected_bg_color == "#cba6f7"
    assert extracted.theme_selected_fg_color == "#11111b"
    assert extracted.accent_color == "#89b4fa"
    assert extracted.accent_bg_color == "#89b4fa"
    assert extracted.accent_fg_color == "#11111b"
    assert extracted.raw_colors["theme_bg_color"] == "#1e1e2e"
    assert extracted.source_file == gtk4_dir / "gtk.css"


def test_extract_theme_colors_fallback_gtk3(tmp_path: Path) -> None:
    """Test extract_theme_colors falls back to gtk-3.0/gtk.css or gtk-3.0/gtk-main.css."""
    theme_dir = tmp_path / "Gtk3Theme"
    gtk3_dir = theme_dir / "gtk-3.0"
    gtk3_dir.mkdir(parents=True)
    (gtk3_dir / "gtk-main.css").write_text(
        """
        @define-color theme_fg_color #000000;
        @define-color theme_bg_color #ffffff;
        @define-color theme_selected_bg_color #0055ff;
        @define-color theme_selected_fg_color #ffffff;
        @define-color wm_title #000000;
        """,
        encoding="utf-8",
    )

    extracted = extract_theme_colors(theme_dir)
    assert extracted.theme_fg_color == "#000000"
    assert extracted.theme_bg_color == "#ffffff"
    assert extracted.theme_selected_bg_color == "#0055ff"
    assert extracted.theme_selected_fg_color == "#ffffff"
    assert extracted.wm_title == "#000000"
    assert extracted.source_file == gtk3_dir / "gtk-main.css"


def test_extract_theme_colors_with_imports(tmp_path: Path) -> None:
    """Test resolving @import url(...) statements in css files to find @define-color."""
    theme_dir = tmp_path / "ImportTheme"
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True)

    (gtk4_dir / "colors.css").write_text(
        """
        @define-color theme_fg_color #333333;
        @define-color theme_bg_color #eeeeee;
        @define-color theme_selected_bg_color #ff5500;
        @define-color theme_selected_fg_color #ffffff;
        """,
        encoding="utf-8",
    )
    (gtk4_dir / "gtk.css").write_text(
        """
        @import url("colors.css");
        @define-color extra_color #123456;
        """,
        encoding="utf-8",
    )

    extracted = extract_theme_colors(theme_dir)
    assert extracted.theme_fg_color == "#333333"
    assert extracted.theme_bg_color == "#eeeeee"
    assert extracted.theme_selected_bg_color == "#ff5500"
    assert extracted.raw_colors["extra_color"] == "#123456"


def test_extract_theme_colors_empty_or_nonexistent(tmp_path: Path) -> None:
    """Test behavior with non-existent theme directory or theme without css files."""
    empty_dir = tmp_path / "EmptyTheme"
    empty_dir.mkdir(parents=True)

    extracted = extract_theme_colors(empty_dir)
    assert extracted.is_empty() is True
    assert extracted.source_file is None
    assert extracted.theme_fg_color is None

    # Test direct file path
    non_existent = tmp_path / "NonExistent"
    extracted_none = extract_theme_colors(non_existent)
    assert extracted_none.is_empty() is True


def test_extracted_colors_to_dict() -> None:
    """Test serialization of ExtractedColors."""
    colors = ExtractedColors(
        theme_fg_color="#ffffff",
        theme_bg_color="#000000",
        theme_selected_bg_color="#007acc",
        theme_selected_fg_color="#ffffff",
        accent_color="#007acc",
        accent_bg_color="#007acc",
        accent_fg_color="#ffffff",
        wm_title="#ffffff",
        raw_colors={"theme_fg_color": "#ffffff", "custom": "#112233"},
        source_file=Path("/path/to/gtk.css"),
    )
    d = colors.to_dict()
    assert d["theme_fg_color"] == "#ffffff"
    assert d["theme_bg_color"] == "#000000"
    assert d["accent_color"] == "#007acc"
    assert d["source_file"] == "/path/to/gtk.css"
    assert d["raw_colors"]["custom"] == "#112233"
