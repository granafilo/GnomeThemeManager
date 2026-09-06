# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for preset management and ThemeSet, ApplyResult, SystemStatus models."""

from pathlib import Path

import pytest

from gnome_theme_manager.core.models import ApplyResult, SystemStatus, ThemeSet
from gnome_theme_manager.core.presets import PresetManager


def test_theme_set_to_dict_and_from_dict() -> None:
    """Verify correct serialization and deserialization of ThemeSet."""
    original = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus-Dark",
        cursor_theme="Bibata-Modern-Classic",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )

    data = original.to_dict()
    assert data["gtk_theme"] == "Nordic"
    assert data["icon_theme"] == "Papirus-Dark"
    assert data["cursor_theme"] == "Bibata-Modern-Classic"
    assert data["color_scheme"] == "prefer-dark"
    assert data["shell_theme"] == "Nordic"

    reconstructed = ThemeSet.from_dict(data)
    assert reconstructed == original
    assert reconstructed.as_dict() == data


def test_theme_set_is_empty() -> None:
    """Verify the is_empty() method of ThemeSet."""
    empty_set = ThemeSet()
    assert empty_set.is_empty() is True

    empty_set_explicit = ThemeSet(gtk_theme=None, icon_theme=None)
    assert empty_set_explicit.is_empty() is True

    partially_set = ThemeSet(gtk_theme="Adwaita")
    assert partially_set.is_empty() is False


def test_theme_set_merge() -> None:
    """Verify merging of two ThemeSet objects with precedence to 'other'."""
    base = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        color_scheme="default",
    )
    update = ThemeSet(
        icon_theme="Papirus-Dark",
        color_scheme="prefer-dark",
        shell_theme="Nordic-Shell",
    )

    merged = base.merge(update)
    assert merged.gtk_theme == "Nordic"  # Kept from base
    assert merged.icon_theme == "Papirus-Dark"  # Overwritten by update
    assert merged.cursor_theme == "Adwaita"  # Kept from base
    assert merged.color_scheme == "prefer-dark"  # Overwritten by update
    assert merged.shell_theme == "Nordic-Shell"  # Added from update


def test_preset_save_and_load(tmp_path: Path) -> None:
    """Verify saving and subsequent loading of a JSON preset."""
    manager = PresetManager(presets_dir=tmp_path)
    theme_set = ThemeSet(
        gtk_theme="Gruvbox",
        icon_theme="Gruvbox-Plus",
        cursor_theme="Capitaine",
        color_scheme="prefer-dark",
        shell_theme="Gruvbox-Shell",
    )

    saved_path = manager.save_preset("GruvboxProfile", theme_set)
    assert saved_path.is_file()
    assert saved_path.name == "presets.json"

    loaded_set = manager.load_preset("GruvboxProfile")
    assert loaded_set.gtk_theme == "Gruvbox"
    assert loaded_set.icon_theme == "Gruvbox-Plus"
    assert loaded_set.cursor_theme == "Capitaine"
    assert loaded_set.shell_theme == "Gruvbox-Shell"


def test_preset_save_overwrite_protection(tmp_path: Path) -> None:
    """Verify that save_preset prevents accidental overwrites when overwrite=False."""
    manager = PresetManager(presets_dir=tmp_path)
    theme_set_1 = ThemeSet(gtk_theme="Theme1")
    theme_set_2 = ThemeSet(gtk_theme="Theme2")

    manager.save_preset("MyPreset", theme_set_1)

    with pytest.raises(FileExistsError, match="already exists"):
        manager.save_preset("MyPreset", theme_set_2, overwrite=False)

    # With overwrite=True it must overwrite
    manager.save_preset("MyPreset", theme_set_2, overwrite=True)
    loaded = manager.load_preset("MyPreset")
    assert loaded.gtk_theme == "Theme2"


def test_preset_save_empty_raises_value_error(tmp_path: Path) -> None:
    """Verify that saving a completely empty ThemeSet is not allowed."""
    manager = PresetManager(presets_dir=tmp_path)
    empty_set = ThemeSet()

    with pytest.raises(ValueError, match="Cannot save an empty preset"):
        manager.save_preset("EmptyPreset", empty_set)


def test_preset_list_presets(tmp_path: Path) -> None:
    """Verify alphabetically sorted list of available presets."""
    manager = PresetManager(presets_dir=tmp_path)
    assert manager.list_presets() == []

    manager.save_preset("Zebra", ThemeSet(gtk_theme="ZebraTheme"))
    manager.save_preset("Alpha", ThemeSet(gtk_theme="AlphaTheme"))
    manager.save_preset("Beta", ThemeSet(gtk_theme="BetaTheme"))

    presets = manager.list_presets()
    assert presets == ["Alpha", "Beta", "Zebra"]


def test_preset_list_presets_non_existent_dir(tmp_path: Path) -> None:
    """Verify that list_presets returns an empty list if directory does not exist."""
    non_existent = tmp_path / "does_not_exist"
    manager = PresetManager(presets_dir=non_existent)
    assert manager.list_presets() == []


def test_preset_delete_success(tmp_path: Path) -> None:
    """Verify successful deletion of a preset."""
    manager = PresetManager(presets_dir=tmp_path)
    manager.save_preset("ToDelete", ThemeSet(gtk_theme="Theme"))

    assert (tmp_path / "presets.json").exists()

    result = manager.delete_preset("ToDelete")
    assert result is True
    # presets.json should exist but empty (empty presets list)
    assert (tmp_path / "presets.json").exists()
    assert manager.list_presets() == []


def test_preset_delete_non_existent(tmp_path: Path) -> None:
    """Verify that deleting a non-existent preset raises FileNotFoundError."""
    manager = PresetManager(presets_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        manager.delete_preset("GhostPreset")


def test_preset_load_non_existent(tmp_path: Path) -> None:
    """Verify that loading a non-existent preset raises FileNotFoundError."""
    manager = PresetManager(presets_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="not found"):
        manager.load_preset("NonExistent")


def test_preset_corrupt_json(tmp_path: Path) -> None:
    """Verify error handling in case of corrupted JSON file."""
    manager = PresetManager(presets_dir=tmp_path)
    corrupt_file = tmp_path / "presets.json"
    corrupt_file.write_text("{ questo non e un json valido }", encoding="utf-8")

    with pytest.raises(ValueError, match="[Cc]orrupted or unreadable"):
        manager.load_preset("Corrupt")


def test_manager_load_preset_corrupt_json(tmp_path: Path) -> None:
    """Verify that load_preset() raises ValueError on corrupted JSON."""
    manager, pm = _build_manager_with_presets_dir(tmp_path)
    pm.presets_file.write_text("{not: valid json}", encoding="utf-8")

    with pytest.raises(ValueError, match="[Cc]orrupted or unreadable"):
        manager.load_preset("Corrupt")


def test_manager_load_preset_incomplete_json(tmp_path: Path) -> None:
    """Verify that an incomplete JSON returns a ThemeSet with None on missing fields."""
    import json

    manager, pm = _build_manager_with_presets_dir(tmp_path)

    # Write presets.json with an incomplete entry
    data = {"presets": [{"name": "Parziale", "components": {"gtk3": "Nordic"}}]}
    pm.presets_file.write_text(json.dumps(data), encoding="utf-8")

    loaded = manager.load_preset("Parziale")
    assert loaded.gtk_theme == "Nordic"
    assert loaded.icon_theme is None
    assert loaded.cursor_theme is None


def test_preset_invalid_name_validation(tmp_path: Path) -> None:
    """Verify that names containing malicious characters or empty names are rejected."""
    manager = PresetManager(presets_dir=tmp_path)
    theme_set = ThemeSet(gtk_theme="Test")

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.save_preset("   ", theme_set)

    with pytest.raises(ValueError, match="Path characters are not allowed"):
        manager.save_preset("../evil_preset", theme_set)

    with pytest.raises(ValueError, match="Path characters are not allowed"):
        manager.save_preset("sub/dir/preset", theme_set)


def test_apply_result_and_system_status_dataclasses() -> None:
    """Verify creation and default fields of ApplyResult and SystemStatus."""
    result = ApplyResult(gtk_theme="Nordic", gtk4_override_applied=True)
    assert result.gtk_theme == "Nordic"
    assert result.gtk4_override_applied is True
    assert result.warnings == []

    status = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.themes"),
        user_icons_path=Path("/home/user/.icons"),
    )
    assert status.gsettings_available is True
    assert status.shell_theme_supported is True


# =============================================================================
# Tests for ThemeManager.load_preset — public API
# =============================================================================


def _build_manager_with_presets_dir(tmp_path: Path):
    """Create a real ThemeManager with PresetManager in a temporary directory."""
    from gnome_theme_manager.core.manager import ThemeManager
    from gnome_theme_manager.core.presets import PresetManager

    # We use real internal components only in test infrastructure,
    # never in the GUI. The GUI will only use public manager APIs.
    pm = PresetManager(presets_dir=tmp_path)
    return ThemeManager(presets=pm), pm


def test_manager_load_preset_valid(tmp_path: Path) -> None:
    """Verify that manager.load_preset() returns the correct ThemeSet."""
    manager, pm = _build_manager_with_presets_dir(tmp_path)
    expected = ThemeSet(gtk_theme="Nordic", icon_theme="Papirus", cursor_theme="Bibata")
    pm.save_preset("MioStile", expected)

    loaded = manager.load_preset("MioStile")

    assert loaded.gtk_theme == "Nordic"
    assert loaded.icon_theme == "Papirus"
    assert loaded.cursor_theme == "Bibata"


def test_manager_load_preset_returns_themeset(tmp_path: Path) -> None:
    """Verify that load_preset() always returns a ThemeSet instance."""
    manager, pm = _build_manager_with_presets_dir(tmp_path)
    pm.save_preset("Test", ThemeSet(gtk_theme="Adwaita"))

    result = manager.load_preset("Test")
    assert isinstance(result, ThemeSet)


def test_manager_load_preset_not_found(tmp_path: Path) -> None:
    """Verify that manager.load_preset() raises FileNotFoundError for non-existent preset."""
    manager, _ = _build_manager_with_presets_dir(tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.load_preset("GhostPreset")


def test_manager_load_preset_invalid_name(tmp_path: Path) -> None:
    """Verify that manager.load_preset() rejects invalid names."""
    manager, _ = _build_manager_with_presets_dir(tmp_path)

    # Empty name or whitespace only
    with pytest.raises(ValueError):
        manager.load_preset("   ")

    # Path traversal
    with pytest.raises(ValueError):
        manager.load_preset("../evil")

    # Path separator
    with pytest.raises(ValueError):
        manager.load_preset("sub/preset")


# =============================================================================
# Name validation tests — consistency between save/load/delete
# =============================================================================


def test_preset_name_with_spaces_and_accents(tmp_path: Path) -> None:
    """Verify that names with spaces, accents, and Unicode characters are accepted."""
    manager = PresetManager(presets_dir=tmp_path)
    # Valid names for a normal user
    valid_names = [
        "Il mio preset",
        "Tema-scuro",
        "Configurazione_lavoro",
        "Stile 2025",
    ]
    ts = ThemeSet(gtk_theme="Nordic")
    for name in valid_names:
        path = manager.save_preset(name, ts)
        assert path.is_file(), f"File was not created for: {name!r}"
        loaded = manager.load_preset(name)
        assert loaded.gtk_theme == "Nordic"
        manager.delete_preset(name)


def test_preset_name_reject_path_separators(tmp_path: Path) -> None:
    """Verify rejection of names containing path separators."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["sub/dir", "..\\evil", "../escape", "a\\b"]:
        with pytest.raises(ValueError):
            manager.save_preset(bad_name, ts)


def test_preset_name_reject_dot_and_dotdot(tmp_path: Path) -> None:
    """Verify rejection of names that are '.' or '..'."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["..", "."]:
        with pytest.raises(ValueError):
            manager.save_preset(bad_name, ts)


def test_preset_name_empty_or_whitespace(tmp_path: Path) -> None:
    """Verify rejection of names that are empty or contain only whitespace."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["", "   ", "\t\n"]:
        with pytest.raises(ValueError, match="cannot be empty"):
            manager.save_preset(bad_name, ts)


def test_preset_name_coherence_save_load_delete(tmp_path: Path) -> None:
    """Verify that save, load, and delete use consistent normalization rules."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Adwaita")
    name = "Tema Lavoro"

    # Saving
    path = manager.save_preset(name, ts)
    assert "presets.json" in path.name

    # Loading with the same name
    loaded = manager.load_preset(name)
    assert loaded.gtk_theme == "Adwaita"

    # Listing includes the correct name
    listing = manager.list_presets()
    assert name in listing

    # Deletion with the same name
    result = manager.delete_preset(name)
    assert result is True
    assert manager.list_presets() == []
