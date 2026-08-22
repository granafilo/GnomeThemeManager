# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for ContentSnapBuilder in theme_snap_manager."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.theme_snap_manager.builder import ContentSnapBuilder
from gnome_theme_manager.core.theme_snap_manager.exceptions import BuildError


def test_builder_directory_structure_and_yaml_generation(tmp_path: Path) -> None:
    """Test creating directory structure, copying files, and writing snapcraft.yaml."""
    source_theme = tmp_path / "My Theme"
    (source_theme / "gtk-3.0").mkdir(parents=True)
    (source_theme / "gtk-3.0" / "gtk.css").write_text("window { color: blue; }")
    (source_theme / "icons").mkdir(parents=True)
    (source_theme / "icons" / "icon.png").write_text("fake_png")

    builder = ContentSnapBuilder("My Theme", source_theme)
    assert builder.snap_name == "custom-theme-my-theme"

    build_dir = tmp_path / "build_temp"
    build_dir.mkdir()
    dirs = builder._create_directory_structure(build_dir)

    assert dirs["meta"].is_dir()
    assert (build_dir / "share" / "themes" / "My Theme").parent.is_dir()

    slots = builder._copy_theme_files(dirs)
    assert "gtk-3-themes" in slots
    assert "icon-themes" in slots

    yaml_path = builder._generate_snapcraft_yaml(dirs["meta"], slots)
    assert yaml_path.is_file()
    assert yaml_path.name == "snap.yaml"

    content = yaml_path.read_text(encoding="utf-8")
    assert "name: custom-theme-my-theme" in content
    assert "base: core22" in content
    assert "gtk-3-themes:" in content
    assert "icon-themes:" in content
    assert "interface: content" in content


def test_builder_nonexistent_theme_raises_build_error(tmp_path: Path) -> None:
    """Test builder raising BuildError when source directory doesn't exist."""
    builder = ContentSnapBuilder("Ghost", tmp_path / "nonexistent")
    with pytest.raises(BuildError):
        builder.build()


def test_builder_mock_compile(tmp_path: Path) -> None:
    """Test successful compilation flow with mocked subprocess and snapcraft."""
    source_theme = tmp_path / "Nordic"
    source_theme.mkdir()
    (source_theme / "gtk.css").write_text("/* theme */")

    builder = ContentSnapBuilder("Nordic", source_theme)

    def mock_compile_snap(b_dir: Path) -> Path:
        fake_snap = b_dir / f"{builder.snap_name}_1.0_amd64.snap"
        fake_snap.write_text("mock_snap_binary")
        return fake_snap

    with patch.object(builder, "_compile_snap", side_effect=mock_compile_snap):
        snap_file, slots = builder.build()
        assert snap_file.is_file()
        assert snap_file.name.endswith(".snap")
        assert "gtk-3-themes" in slots
        builder.cleanup()
        assert builder.temp_dir is None


def test_builder_with_external_icons_dir(tmp_path: Path) -> None:
    """Test packaging external icon/cursor directory from ~/.icons."""
    source_theme = tmp_path / "Colloid"
    source_theme.mkdir()
    (source_theme / "gtk.css").write_text("/* theme */")

    source_icons = tmp_path / "Colloid-Icons"
    source_icons.mkdir()
    (source_icons / "index.theme").write_text("[Icon Theme]\nName=Colloid-Icons")

    builder = ContentSnapBuilder(
        "Colloid",
        source_theme,
        icon_name="Colloid-Icons",
        icon_path=source_icons,
    )

    build_dir = tmp_path / "build_icons_temp"
    build_dir.mkdir()
    dirs = builder._create_directory_structure(build_dir)
    slots = builder._copy_theme_files(dirs)

    assert "gtk-3-themes" in slots
    assert "icon-themes" in slots
    assert (build_dir / "share" / "icons" / "Colloid-Icons" / "index.theme").is_file()
