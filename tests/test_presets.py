"""Test di unità per la gestione dei preset e i modelli ThemeSet, ApplyResult, SystemStatus."""

from pathlib import Path

import pytest

from gnome_theme_manager.core.models import ApplyResult, SystemStatus, ThemeSet
from gnome_theme_manager.core.presets import PresetManager


def test_theme_set_to_dict_and_from_dict() -> None:
    """Verifica la corretta serializzazione e deserializzazione di ThemeSet."""
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
    """Verifica il metodo is_empty() di ThemeSet."""
    empty_set = ThemeSet()
    assert empty_set.is_empty() is True

    empty_set_explicit = ThemeSet(gtk_theme=None, icon_theme=None)
    assert empty_set_explicit.is_empty() is True

    partially_set = ThemeSet(gtk_theme="Adwaita")
    assert partially_set.is_empty() is False


def test_theme_set_merge() -> None:
    """Verifica la fusione di due oggetti ThemeSet con precedenza a 'other'."""
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
    assert merged.gtk_theme == "Nordic"  # Mantenuto da base
    assert merged.icon_theme == "Papirus-Dark"  # Sovrascritto da update
    assert merged.cursor_theme == "Adwaita"  # Mantenuto da base
    assert merged.color_scheme == "prefer-dark"  # Sovrascritto da update
    assert merged.shell_theme == "Nordic-Shell"  # Aggiunto da update


def test_preset_save_and_load(tmp_path: Path) -> None:
    """Verifica il salvataggio e il successivo caricamento di un preset JSON."""
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
    assert saved_path.name == "GruvboxProfile.json"

    loaded_set = manager.load_preset("GruvboxProfile")
    assert loaded_set == theme_set


def test_preset_save_overwrite_protection(tmp_path: Path) -> None:
    """Verifica che save_preset prevenga sovrascritture accidentali se overwrite=False."""
    manager = PresetManager(presets_dir=tmp_path)
    theme_set_1 = ThemeSet(gtk_theme="Theme1")
    theme_set_2 = ThemeSet(gtk_theme="Theme2")

    manager.save_preset("MyPreset", theme_set_1)

    with pytest.raises(FileExistsError, match="esiste già"):
        manager.save_preset("MyPreset", theme_set_2, overwrite=False)

    # Con overwrite=True deve sovrascrivere
    manager.save_preset("MyPreset", theme_set_2, overwrite=True)
    loaded = manager.load_preset("MyPreset")
    assert loaded.gtk_theme == "Theme2"


def test_preset_save_empty_raises_value_error(tmp_path: Path) -> None:
    """Verifica che non sia possibile salvare un ThemeSet completamente vuoto."""
    manager = PresetManager(presets_dir=tmp_path)
    empty_set = ThemeSet()

    with pytest.raises(ValueError, match="privo di qualsiasi configurazione"):
        manager.save_preset("EmptyPreset", empty_set)


def test_preset_list_presets(tmp_path: Path) -> None:
    """Verifica l'elenco ordinato alfabeticamente dei preset disponibili."""
    manager = PresetManager(presets_dir=tmp_path)

    assert manager.list_presets() == []

    manager.save_preset("Zebra", ThemeSet(gtk_theme="ZebraTheme"))
    manager.save_preset("Alpha", ThemeSet(gtk_theme="AlphaTheme"))
    manager.save_preset("Beta", ThemeSet(gtk_theme="BetaTheme"))

    presets = manager.list_presets()
    assert presets == ["Alpha", "Beta", "Zebra"]


def test_preset_list_presets_non_existent_dir(tmp_path: Path) -> None:
    """Verifica che list_presets restituisca lista vuota se la directory non esiste."""
    non_existent = tmp_path / "does_not_exist"
    manager = PresetManager(presets_dir=non_existent)
    assert manager.list_presets() == []


def test_preset_delete_success(tmp_path: Path) -> None:
    """Verifica l'eliminazione con successo di un preset."""
    manager = PresetManager(presets_dir=tmp_path)
    manager.save_preset("ToDelete", ThemeSet(gtk_theme="Theme"))

    assert (tmp_path / "ToDelete.json").exists()

    result = manager.delete_preset("ToDelete")
    assert result is True
    assert not (tmp_path / "ToDelete.json").exists()


def test_preset_delete_non_existent(tmp_path: Path) -> None:
    """Verifica che l'eliminazione di un preset inesistente sollevi FileNotFoundError."""
    manager = PresetManager(presets_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="non esiste"):
        manager.delete_preset("GhostPreset")


def test_preset_load_non_existent(tmp_path: Path) -> None:
    """Verifica che il caricamento di un preset inesistente sollevi FileNotFoundError."""
    manager = PresetManager(presets_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="non è stato trovato"):
        manager.load_preset("NonExistent")


def test_preset_corrupt_json(tmp_path: Path) -> None:
    """Verifica la gestione di errori in caso di file JSON corrotto."""
    manager = PresetManager(presets_dir=tmp_path)
    corrupt_file = tmp_path / "Corrupt.json"
    corrupt_file.write_text("{ questo non e un json valido }", encoding="utf-8")

    with pytest.raises(ValueError, match="corrotto o illeggibile"):
        manager.load_preset("Corrupt")


def test_preset_invalid_name_validation(tmp_path: Path) -> None:
    """Verifica che nomi contenenti caratteri malevoli o vuoti vengano rifiutati."""
    manager = PresetManager(presets_dir=tmp_path)
    theme_set = ThemeSet(gtk_theme="Test")

    with pytest.raises(ValueError, match="non può essere vuoto"):
        manager.save_preset("   ", theme_set)

    with pytest.raises(ValueError, match="caratteri di percorso"):
        manager.save_preset("../evil_preset", theme_set)

    with pytest.raises(ValueError, match="caratteri di percorso"):
        manager.save_preset("sub/dir/preset", theme_set)


def test_apply_result_and_system_status_dataclasses() -> None:
    """Verifica la creazione e i campi predefiniti di ApplyResult e SystemStatus."""
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
# Test per ThemeManager.load_preset — API pubblica
# =============================================================================


def _build_manager_with_presets_dir(tmp_path: Path):
    """Crea un ThemeManager reale con PresetManager in una directory temporanea."""
    from gnome_theme_manager.core.manager import ThemeManager
    from gnome_theme_manager.core.presets import PresetManager

    # Usiamo i componenti interni reali solo nell'infrastruttura del test,
    # mai nella GUI. La GUI userà solo le API pubbliche del manager.
    pm = PresetManager(presets_dir=tmp_path)
    return ThemeManager(presets=pm), pm


def test_manager_load_preset_valid(tmp_path: Path) -> None:
    """Verifica che manager.load_preset() restituisca il ThemeSet corretto."""
    manager, pm = _build_manager_with_presets_dir(tmp_path)
    expected = ThemeSet(gtk_theme="Nordic", icon_theme="Papirus", cursor_theme="Bibata")
    pm.save_preset("MioStile", expected)

    loaded = manager.load_preset("MioStile")

    assert loaded.gtk_theme == "Nordic"
    assert loaded.icon_theme == "Papirus"
    assert loaded.cursor_theme == "Bibata"


def test_manager_load_preset_returns_themeset(tmp_path: Path) -> None:
    """Verifica che load_preset() restituisca sempre un'istanza di ThemeSet."""
    manager, pm = _build_manager_with_presets_dir(tmp_path)
    pm.save_preset("Test", ThemeSet(gtk_theme="Adwaita"))

    result = manager.load_preset("Test")
    assert isinstance(result, ThemeSet)


def test_manager_load_preset_not_found(tmp_path: Path) -> None:
    """Verifica che manager.load_preset() sollevi FileNotFoundError per preset inesistente."""
    manager, _ = _build_manager_with_presets_dir(tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.load_preset("GhostPreset")


def test_manager_load_preset_invalid_name(tmp_path: Path) -> None:
    """Verifica che manager.load_preset() rifiuti nomi non validi."""
    manager, _ = _build_manager_with_presets_dir(tmp_path)

    # Nome vuoto o solo spazi
    with pytest.raises(ValueError):
        manager.load_preset("   ")

    # Path traversal
    with pytest.raises(ValueError):
        manager.load_preset("../evil")

    # Separatore di percorso
    with pytest.raises(ValueError):
        manager.load_preset("sub/preset")


def test_manager_load_preset_corrupt_json(tmp_path: Path) -> None:
    """Verifica che load_preset() sollevi ValueError su JSON corrotto."""
    manager, _ = _build_manager_with_presets_dir(tmp_path)
    (tmp_path / "Corrupt.json").write_text("{not: valid json}", encoding="utf-8")

    with pytest.raises(ValueError, match="corrotto o illeggibile"):
        manager.load_preset("Corrupt")


def test_manager_load_preset_incomplete_json(tmp_path: Path) -> None:
    """Verifica che un JSON incompleto restituisca un ThemeSet con None sui campi assenti."""
    import json

    manager, _ = _build_manager_with_presets_dir(tmp_path)

    # Solo gtk_theme presente; gli altri devono restare None
    (tmp_path / "Parziale.json").write_text(json.dumps({"gtk_theme": "Nordic"}), encoding="utf-8")

    loaded = manager.load_preset("Parziale")
    assert loaded.gtk_theme == "Nordic"
    assert loaded.icon_theme is None
    assert loaded.cursor_theme is None


# =============================================================================
# Test validazione nomi — coerenza tra save/load/delete
# =============================================================================


def test_preset_name_with_spaces_and_accents(tmp_path: Path) -> None:
    """Verifica che nomi con spazi, accenti e caratteri Unicode siano accettati."""
    manager = PresetManager(presets_dir=tmp_path)
    # Nomi validi per un utente normale
    valid_names = [
        "Il mio preset",
        "Tema-scuro",
        "Configurazione_lavoro",
        "Stile 2025",
    ]
    ts = ThemeSet(gtk_theme="Nordic")
    for name in valid_names:
        path = manager.save_preset(name, ts)
        assert path.is_file(), f"Il file non è stato creato per: {name!r}"
        loaded = manager.load_preset(name)
        assert loaded.gtk_theme == "Nordic"
        manager.delete_preset(name)


def test_preset_name_reject_path_separators(tmp_path: Path) -> None:
    """Verifica il rifiuto di nomi che contengono separatori di percorso."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["sub/dir", "..\\evil", "../escape", "a\\b"]:
        with pytest.raises(ValueError):
            manager.save_preset(bad_name, ts)


def test_preset_name_reject_dot_and_dotdot(tmp_path: Path) -> None:
    """Verifica il rifiuto di nomi che sono '.' o '..'."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["..", "."]:
        with pytest.raises(ValueError):
            manager.save_preset(bad_name, ts)


def test_preset_name_empty_or_whitespace(tmp_path: Path) -> None:
    """Verifica il rifiuto di nomi vuoti o composti solo da spazi."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Nordic")

    for bad_name in ["", "   ", "\t\n"]:
        with pytest.raises(ValueError, match="non può essere vuoto"):
            manager.save_preset(bad_name, ts)


def test_preset_name_coherence_save_load_delete(tmp_path: Path) -> None:
    """Verifica che save, load e delete usino regole di normalizzazione coerenti."""
    manager = PresetManager(presets_dir=tmp_path)
    ts = ThemeSet(gtk_theme="Adwaita")
    name = "Tema Lavoro"

    # Salvataggio
    path = manager.save_preset(name, ts)
    assert "Tema Lavoro.json" in path.name

    # Caricamento con lo stesso nome
    loaded = manager.load_preset(name)
    assert loaded.gtk_theme == "Adwaita"

    # Lista include il nome corretto
    listing = manager.list_presets()
    assert name in listing

    # Eliminazione con lo stesso nome
    result = manager.delete_preset(name)
    assert result is True
    assert manager.list_presets() == []
