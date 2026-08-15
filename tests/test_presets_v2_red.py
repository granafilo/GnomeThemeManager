# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per il Preset 2.0 — Snapshot espliciti e formato JSON corretto (RED)."""

import json
from pathlib import Path

from gnome_theme_manager.core.models import ThemeSet
from gnome_theme_manager.core.presets import PresetManager


def test_preset_explicit_snapshot_format(tmp_path: Path) -> None:
    """Verifica che il preset memorizzato segua la struttura '{presets: [ {name, components: {gtk3, gtk4, shell, icons, cursors}, created_at} ]}'."""
    presets_file = tmp_path / "presets.json"
    manager = PresetManager(presets_dir=tmp_path)

    # Visto che carichiamo da un file unico presets.json anziché singoli file per preset,
    # impostiamo un file path esplicito nel manager (o simuliamo presets.json)
    manager.presets_file = presets_file

    theme_set = ThemeSet(
        gtk_theme="Nordic",
        shell_theme="Nordic",
        icon_theme="Nordic-folders",
        cursor_theme="Nordzy",
    )

    # Salvataggio del preset
    manager.save_preset("My Nord", theme_set)

    # Il file deve essere presets.json
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
    # Secondo requisiti Task 0.5: gtk3, gtk4, shell, icons, cursors
    assert components["gtk3"] == "Nordic"
    assert components["gtk4"] == "Nordic"
    assert components["shell"] == "Nordic"
    assert components["icons"] == "Nordic-folders"
    assert components["cursors"] == "Nordzy"
