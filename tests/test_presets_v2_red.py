# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Preset 2.0 — Explicit snapshots and valid JSON format."""

import json
from pathlib import Path

from gnome_theme_manager.core.models import ThemeSet
from gnome_theme_manager.core.presets import PresetManager


def test_preset_explicit_snapshot_format(tmp_path: Path) -> None:
    """Verify that stored preset follows '{presets: [ {name, components: {gtk3, gtk4, shell, icons, cursors}, created_at} ]}' structure."""
    presets_file = tmp_path / "presets.json"
    manager = PresetManager(presets_dir=tmp_path)

    # Since we load from a unified presets.json instead of individual files,
    # set an explicit file path in the manager (or mock presets.json)
    manager.presets_file = presets_file

    theme_set = ThemeSet(
        gtk_theme="Nordic",
        shell_theme="Nordic",
        icon_theme="Nordic-folders",
        cursor_theme="Nordzy",
    )

    # Save the preset
    manager.save_preset("My Nord", theme_set)

    # The file must be presets.json
    assert presets_file.is_file()

    with open(presets_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "presets" in data
    presets_list = data["presets"]
    assert len(presets_list) == 1
    preset_entry = presets_list[0]
    assert preset_entry["name"] == "My Nord"
    assert "created_at" in preset_entry

    components = preset_entry["components"]
    # Per Task 0.5 requirements: gtk3, gtk4, shell, icons, cursors
    assert components["gtk3"] == "Nordic"
    assert components["gtk4"] == "Nordic"
    assert components["shell"] == "Nordic"
    assert components["icons"] == "Nordic-folders"
    assert components["cursors"] == "Nordzy"
