# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Font configuration, parsing, and serialization (Task 4.3)."""

from pathlib import Path

import pytest

from gnome_theme_manager.core.fonts import (
    DEFAULT_DOCUMENT_FONT,
    DEFAULT_INTERFACE_FONT,
    DEFAULT_MONOSPACE_FONT,
    DEFAULT_TEXT_SCALING_FACTOR,
    FontConfig,
    family_of,
    format_font_spec,
    parse_font_spec,
    size_of,
)
from gnome_theme_manager.core.global_themes import GlobalTheme, GlobalThemeManager
from gnome_theme_manager.core.models import ThemeSet


def test_font_config_defaults() -> None:
    """Verify default values match GNOME / Ubuntu defaults."""
    cfg = FontConfig()
    assert cfg.interface_font == DEFAULT_INTERFACE_FONT
    assert cfg.document_font == DEFAULT_DOCUMENT_FONT
    assert cfg.monospace_font == DEFAULT_MONOSPACE_FONT
    assert cfg.text_scaling_factor == DEFAULT_TEXT_SCALING_FACTOR
    assert cfg.is_default is True


def test_font_config_serialization_roundtrip() -> None:
    """Verify FontConfig to_dict and from_dict roundtrip."""
    cfg = FontConfig(
        interface_font="Ubuntu 11",
        document_font="Ubuntu Sans 11",
        monospace_font="Ubuntu Mono 13",
        text_scaling_factor=1.25,
    )
    assert cfg.is_default is False

    d = cfg.to_dict()
    assert d["interface_font"] == "Ubuntu 11"
    assert d["document_font"] == "Ubuntu Sans 11"
    assert d["monospace_font"] == "Ubuntu Mono 13"
    assert d["text_scaling_factor"] == 1.25

    reconstructed = FontConfig.from_dict(d)
    assert reconstructed == cfg

    # None and empty dictionary handling
    empty_cfg = FontConfig.from_dict(None)
    assert empty_cfg.is_default is True

    # Bad scaling factor gracefully falls back to default
    bad_factor_cfg = FontConfig.from_dict({"text_scaling_factor": "invalid"})
    assert bad_factor_cfg.text_scaling_factor == 1.0


def test_parse_and_format_font_spec() -> None:
    """Verify parsing and formatting of GSettings font-name specifications."""
    fam, sz = parse_font_spec("Cantarell 11")
    assert fam == "Cantarell"
    assert sz == 11.0
    assert family_of("Cantarell 11") == "Cantarell"
    assert size_of("Cantarell 11") == 11.0
    assert format_font_spec(fam, sz) == "Cantarell 11"

    # Multi-word family with float size
    fam2, sz2 = parse_font_spec("JetBrains Mono SemiBold 12.5")
    assert fam2 == "JetBrains Mono SemiBold"
    assert sz2 == 12.5
    assert format_font_spec(fam2, sz2) == "JetBrains Mono SemiBold 12.5"

    # Invalid specs raise ValueError
    with pytest.raises(ValueError):
        parse_font_spec("")
    with pytest.raises(ValueError):
        parse_font_spec("NoSizeFont")
    with pytest.raises(ValueError):
        format_font_spec("", 11)


def test_global_theme_fonts_roundtrip(tmp_path: Path) -> None:
    """Verify GlobalTheme preserves FontConfig through save/load and to_dict/from_dict."""
    state_file = tmp_path / "global_themes.json"
    mgr = GlobalThemeManager(bundled_dir=tmp_path / "bundled", state_file=state_file)

    fonts = FontConfig(
        interface_font="Inter 10",
        document_font="Inter 10",
        monospace_font="Fira Code 12",
        text_scaling_factor=1.1,
    )

    theme = mgr.save_global_theme(
        name="Typography Setup",
        theme_set=ThemeSet(gtk_theme="Adwaita"),
        fonts=fonts,
    )
    assert theme.fonts == fonts

    # Reload from disk
    reloaded_mgr = GlobalThemeManager(bundled_dir=tmp_path / "bundled", state_file=state_file)
    loaded = reloaded_mgr.get_global_theme(theme.id)
    assert loaded is not None
    assert loaded.fonts == fonts


def test_global_theme_model_fonts_to_from_dict() -> None:
    """Verify fonts serialization in GlobalTheme model dictionary."""
    fonts = FontConfig(interface_font="Roboto 11")
    gt = GlobalTheme(
        id="t-fonts",
        name="Fonts Theme",
        description="Testing fonts",
        components=ThemeSet(gtk_theme="Adwaita"),
        origin="user",
        fonts=fonts,
    )
    d = gt.to_dict()
    assert d["fonts"]["interface_font"] == "Roboto 11"
    reconstructed = GlobalTheme.from_dict(d, is_bundled=False)
    assert reconstructed.fonts == fonts
