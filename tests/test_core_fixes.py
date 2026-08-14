# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari e di integrazione per i nuovi comportamenti di backup GTK4 e validazione sandbox."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import (
    ThemeApplyError,
    ThemeValidationError,
)
from gnome_theme_manager.core.gtk4_linker import GTK4ThemeLinker
from gnome_theme_manager.core.sandbox_bridge import SandboxBridge, validate_theme_name


@pytest.fixture
def temp_env(tmp_path: Path):
    """Crea una struttura fittizia per i test."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Mock delle directory XDG impostando le variabili d'ambiente nei test
    xdg_config_dir = tmp_path / "xdg_config"
    xdg_data_dir = tmp_path / "xdg_data"

    xdg_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_data_dir.mkdir(parents=True, exist_ok=True)

    # Sorgenti del tema
    theme_dir = tmp_path / "themes" / "Nordic"
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True, exist_ok=True)
    (gtk4_dir / "gtk.css").write_text("/* theme css */")
    (gtk4_dir / "gtk-dark.css").write_text("/* theme dark css */")
    (gtk4_dir / "assets").mkdir(parents=True, exist_ok=True)
    (gtk4_dir / "assets" / "icon.png").write_text("dummy")

    # Altro tema
    other_theme_dir = tmp_path / "themes" / "Adwaita"
    other_gtk4_dir = other_theme_dir / "gtk-4.0"
    other_gtk4_dir.mkdir(parents=True, exist_ok=True)
    (other_gtk4_dir / "gtk.css").write_text("/* adwaita css */")

    return {
        "config_dir": config_dir,
        "theme_dir": theme_dir,
        "other_theme_dir": other_theme_dir,
        "xdg_config_dir": xdg_config_dir,
        "xdg_data_dir": xdg_data_dir,
    }


@pytest.fixture
def linker(temp_env, monkeypatch):
    """Istanzia il linker isolato configurando le variabili d'ambiente XDG."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_env["xdg_config_dir"]))
    monkeypatch.setenv("XDG_DATA_HOME", str(temp_env["xdg_data_dir"]))
    return GTK4ThemeLinker(config_dir=temp_env["config_dir"])


# -----------------------------------------------------------------------------
# Test GTK4 Linker (Backup, Rollback, Manifest)
# -----------------------------------------------------------------------------


def test_gtk4_linker_no_initial_file(linker, temp_env):
    """Verifica il comportamento in assenza iniziale di gtk.css."""
    assert linker.is_override_active() is False
    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True
    assert linker.is_override_active() is True

    manifest = linker._load_manifest()
    assert manifest["active_theme"] == "Nordic"
    assert manifest["entries"]["gtk.css"]["kind"] == "missing"
    assert manifest["entries"]["gtk.css"]["backup"] is None


def test_gtk4_linker_backup_original_file(linker, temp_env):
    """Verifica che un file gtk.css originale venga correttamente salvato in backup."""
    original_file = temp_env["config_dir"] / "gtk.css"
    original_file.write_text("/* original user css */")

    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True

    manifest = linker._load_manifest()
    entry = manifest["entries"]["gtk.css"]
    assert entry["kind"] == "file"
    assert entry["backup"] is not None

    backup_path = Path(entry["backup"])
    assert backup_path.is_file()
    assert backup_path.read_text() == "/* original user css */"


def test_gtk4_linker_backup_original_directory(linker, temp_env):
    """Verifica il backup di una cartella assets originale dell'utente."""
    original_assets = temp_env["config_dir"] / "assets"
    original_assets.mkdir(parents=True, exist_ok=True)
    (original_assets / "my_pic.png").write_text("user pic")

    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True

    manifest = linker._load_manifest()
    entry = manifest["entries"]["assets"]
    assert entry["kind"] == "directory"
    assert entry["backup"] is not None

    backup_path = Path(entry["backup"])
    assert backup_path.is_dir()
    assert (backup_path / "my_pic.png").read_text() == "user pic"


def test_gtk4_linker_broken_symlink(linker, temp_env):
    """Verifica la corretta gestione di un symlink rotto preesistente."""
    original_symlink = temp_env["config_dir"] / "gtk.css"
    # punta a un file inesistente
    original_symlink.symlink_to(temp_env["xdg_data_dir"] / "non_existent.css")

    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True

    assert (temp_env["config_dir"] / "gtk.css").exists()
    assert "theme css" in (temp_env["config_dir"] / "gtk.css").read_text()


def test_gtk4_linker_non_empty_directory_backup(linker, temp_env):
    """Verifica il backup di una directory non vuota."""
    assets_dir = temp_env["config_dir"] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "file1").write_text("data1")
    (assets_dir / "file2").write_text("data2")

    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True

    manifest = linker._load_manifest()
    backup_path = Path(manifest["entries"]["assets"]["backup"])
    assert (backup_path / "file1").read_text() == "data1"
    assert (backup_path / "file2").read_text() == "data2"


def test_gtk4_linker_apply_same_theme_idempotent(linker, temp_env):
    """Verifica che l'applicazione ripetuta dello stesso tema non duplichi il backup."""
    original_file = temp_env["config_dir"] / "gtk.css"
    original_file.write_text("/* user style */")

    # Prima applicazione
    assert linker.apply_override(temp_env["theme_dir"]) is True
    manifest_1 = linker._load_manifest()
    backup_1 = manifest_1["entries"]["gtk.css"]["backup"]

    # Seconda applicazione
    assert linker.apply_override(temp_env["theme_dir"]) is True
    manifest_2 = linker._load_manifest()
    backup_2 = manifest_2["entries"]["gtk.css"]["backup"]

    assert backup_1 == backup_2  # Il backup non deve cambiare o duplicarsi


def test_gtk4_linker_apply_different_theme(linker, temp_env):
    """Verifica l'applicazione di un tema differente mantenendo il backup iniziale."""
    original_file = temp_env["config_dir"] / "gtk.css"
    original_file.write_text("/* original user */")

    # Primo tema
    assert linker.apply_override(temp_env["theme_dir"]) is True
    backup_1 = linker._load_manifest()["entries"]["gtk.css"]["backup"]

    # Secondo tema
    assert linker.apply_override(temp_env["other_theme_dir"]) is True
    manifest_2 = linker._load_manifest()
    backup_2 = manifest_2["entries"]["gtk.css"]["backup"]

    assert backup_1 == backup_2
    assert manifest_2["active_theme"] == "Adwaita"


def test_gtk4_linker_external_modification_after_backup(linker, temp_env):
    """Verifica che se un file gestito viene modificato esternamente dall'utente, venga rilevato come conflitto."""
    # Applica tema
    linker.apply_override(temp_env["theme_dir"])

    # Modifica esternamente il file
    gtk_file = temp_env["config_dir"] / "gtk.css"
    gtk_file.unlink()
    gtk_file.write_text("/* modified manually by user */")

    # Rimuovi l'override: non deve toccare il file modificato dall'utente
    linker.remove_override()
    assert gtk_file.read_text() == "/* modified manually by user */"


def test_gtk4_linker_deactivate_and_restore(linker, temp_env):
    """Verifica che remove_override rimuova gli elementi gestiti e ripristini quelli originari."""
    original_file = temp_env["config_dir"] / "gtk.css"
    original_file.write_text("/* original css */")

    linker.apply_override(temp_env["theme_dir"])
    assert (temp_env["config_dir"] / "gtk.css").read_text() == "/* theme css */"

    linker.remove_override()
    assert original_file.exists()
    assert original_file.read_text() == "/* original css */"


def test_gtk4_linker_backup_original_symlink(linker, temp_env):
    """Verifica il backup di un symlink originale creato dall'utente."""
    original_target = temp_env["xdg_data_dir"] / "some_file.css"
    original_target.write_text("/* some target */")

    original_symlink = temp_env["config_dir"] / "gtk.css"
    original_symlink.symlink_to(original_target)

    success = linker.apply_override(temp_env["theme_dir"])
    assert success is True

    manifest = linker._load_manifest()
    entry = manifest["entries"]["gtk.css"]
    assert entry["kind"] == "symlink"

    # Il backup deve essere un symlink che punta a original_target
    backup_path = Path(entry["backup"])
    assert backup_path.is_symlink()
    assert os.readlink(backup_path) == str(original_target)

    # Rimuovendo l'override, deve ripristinare il symlink originale
    linker.remove_override()
    assert (temp_env["config_dir"] / "gtk.css").is_symlink()
    assert os.readlink(temp_env["config_dir"] / "gtk.css") == str(original_target)


def test_gtk4_linker_apply_error_and_rollback(linker, temp_env):
    """Simula un errore durante la creazione del symlink per verificare il rollback."""
    original_file = temp_env["config_dir"] / "gtk.css"
    original_file.write_text("/* original user */")

    # Mockiamo sia symlink_to che shutil.copy2 per costringere a fallire l'applicazione
    with (
        patch.object(Path, "symlink_to", side_effect=OSError("Permission denied")),
        patch("shutil.copy2", side_effect=OSError("Copy failed")),
        pytest.raises(ThemeApplyError),
    ):
        linker.apply_override(temp_env["theme_dir"])

    # Il file originario deve essere intatto
    assert original_file.exists()
    assert original_file.read_text() == "/* original user */"


def test_gtk4_linker_corrupted_manifest(linker, temp_env):
    """Verifica la corretta ripartenza da un manifest corrotto/invalido."""
    linker.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    linker.manifest_path.write_text("{invalid json", encoding="utf-8")

    manifest = linker._load_manifest()
    assert manifest["version"] == 1
    assert manifest["entries"] == {}


def test_gtk4_linker_unsupported_manifest_version(linker, temp_env):
    """Verifica che versioni del manifest non supportate vengano scartate."""
    linker.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    linker.manifest_path.write_text(json.dumps({"version": 999, "entries": {}}), encoding="utf-8")

    manifest = linker._load_manifest()
    assert manifest["version"] == 1
    assert manifest["entries"] == {}


# -----------------------------------------------------------------------------
# Test Sandbox Bridge (Validazione e Comandi)
# -----------------------------------------------------------------------------


def test_validate_theme_name_valid():
    """Verifica nomi di tema validi."""
    assert validate_theme_name("Adwaita-dark") == "Adwaita-dark"
    assert validate_theme_name("Nordic Dark") == "Nordic Dark"
    assert validate_theme_name("Yaru_light") == "Yaru_light"


def test_validate_theme_name_invalid():
    """Verifica i vari casi di nomi tema non validi."""
    with pytest.raises(ThemeValidationError):
        validate_theme_name("")  # vuoto

    with pytest.raises(ThemeValidationError):
        validate_theme_name("Theme/Name")  # slash

    with pytest.raises(ThemeValidationError):
        validate_theme_name("Theme\\Name")  # backslash

    with pytest.raises(ThemeValidationError):
        validate_theme_name("Theme\nName")  # newline

    with pytest.raises(ThemeValidationError):
        validate_theme_name("Theme\x00Name")  # control character

    with pytest.raises(ThemeValidationError):
        validate_theme_name("-Nordic")  # inizia con -


def test_build_commands():
    """Verifica la corretta costruzione dei comandi Flatpak e Snap."""
    bridge = SandboxBridge()
    flatpak_cmd = bridge.build_flatpak_command("org.mozilla.firefox", "Nordic", "Papirus")
    assert flatpak_cmd == [
        "flatpak",
        "override",
        "--user",
        "--env=GTK_THEME=Nordic",
        "--env=ICON_THEME=Papirus",
        "org.mozilla.firefox",
    ]

    snap_cmd = bridge.build_snap_command("firefox")
    assert snap_cmd == ["snap", "list", "firefox"]


def test_subprocess_execution_handling():
    """Verifica la corretta gestione dei processi di subprocess, timeout ed errori in SandboxBridge."""
    bridge = SandboxBridge()

    # Mock flatpak disponibile
    with patch.object(bridge, "is_flatpak_available", return_value=True):
        # 1. Timeout
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="flatpak", timeout=10)
        ):
            res_timeout = bridge.propagate_to_flatpak("Nordic")
            assert res_timeout.flatpak_success is False
            assert any("Timeout" in w for w in res_timeout.warnings)

        # 2. Exit code non zero
        err = subprocess.CalledProcessError(returncode=1, cmd="flatpak", stderr="Permission denied")
        with patch("subprocess.run", side_effect=err):
            res_err = bridge.propagate_to_flatpak("Nordic")
            assert res_err.flatpak_success is False
            assert any("Permission denied" in w for w in res_err.warnings)

        # 3. Nessun shell=True e argomenti passati come lista
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bridge.propagate_to_flatpak("Nordic", "Papirus")

            # Verifichiamo che i comandi siano liste e shell=True non sia impostato
            for call in mock_run.call_args_list:
                args, kwargs = call
                cmd = args[0]
                assert isinstance(cmd, list)
                assert kwargs.get("shell") is not True


def test_gtk4_linker_comprehensive_filesystem_rollback(linker, temp_env):
    """Verifica l'intero ciclo di vita sul filesystem reale in caso di rollback e conservazione di modifiche manuali."""
    # 1. Configurazione originale dell'utente
    gtk_css = temp_env["config_dir"] / "gtk.css"
    gtk_css.write_text("/* original gtk.css */")

    gtk_dark_css = temp_env["config_dir"] / "gtk-dark.css"
    gtk_dark_css.write_text("/* original gtk-dark.css */")

    assets_dir = temp_env["config_dir"] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "logo.png").write_text("logo")

    # 2. Applicazione override parziale che fallisce
    original_symlink_to = Path.symlink_to
    original_copytree = shutil.copytree

    def mock_symlink_to(self_path, target_path):
        if "assets" in str(self_path):
            raise OSError("Errore simulato di scrittura assets")
        return original_symlink_to(self_path, target_path)

    def mock_copytree(src, dst, *args, **kwargs):
        if "assets" in str(dst):
            raise OSError("Errore simulato di scrittura assets copytree")
        return original_copytree(src, dst, *args, **kwargs)

    with (
        patch.object(Path, "symlink_to", mock_symlink_to),
        patch("shutil.copytree", mock_copytree),
        patch("shutil.copy2", side_effect=OSError("Copy failed")),
    ):
        with pytest.raises(ThemeApplyError):
            linker.apply_override(temp_env["theme_dir"])

    # 3. Verifica del rollback: il filesystem deve essere identico allo stato originale
    assert gtk_css.exists() and not gtk_css.is_symlink()
    assert gtk_css.read_text() == "/* original gtk.css */"

    assert gtk_dark_css.exists() and not gtk_dark_css.is_symlink()
    assert gtk_dark_css.read_text() == "/* original gtk-dark.css */"

    assert assets_dir.is_dir()
    assert (assets_dir / "logo.png").read_text() == "logo"

    # Nessun file temporaneo in config_dir o config_root
    temp_files = list(linker.config_dir.glob("*.tmp")) + list(linker.config_root.glob("*.tmp"))
    assert len(temp_files) == 0

    # Il manifest deve essere pulito / vuoto o coerente
    manifest = linker._load_manifest()
    assert manifest["active_theme"] is None


def test_cli_no_tkinter_references():
    """Verifica che le opzioni Tkinter e il comando gui-tk non siano più validi e non compaiano nell'help."""
    from gnome_theme_manager.cli.args import create_parser

    parser = create_parser()

    # 1. Verifica che gui-tk non sia tra i subcomandi
    import argparse

    subparsers_action = next(
        (action for action in parser._actions if isinstance(action, argparse._SubParsersAction)),
        None,
    )
    assert subparsers_action is not None
    assert "gui-tk" not in subparsers_action.choices

    # 2. Verifica che --tk-gui non sia tra le opzioni del parser
    option_strings = []
    for action in parser._actions:
        option_strings.extend(action.option_strings)
    assert "--tk-gui" not in option_strings

    # 3. Verifica l'output dell'help
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            parser.print_help()
        except SystemExit:
            pass
    help_text = f.getvalue().lower()
    assert "gui-tk" not in help_text
    assert "tkinter" not in help_text
    assert "tk-gui" not in help_text
    assert "tk_gui" not in help_text
