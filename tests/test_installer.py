# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per la gestione sicura degli archivi e per l'installer dei temi."""

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from gnome_theme_manager.core.errors import (
    ArchiveExtractionError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from gnome_theme_manager.core.installer import (
    ThemeInstaller,
    detect_theme_types,
    inspect_extracted_tree,
    safe_extract,
)
from gnome_theme_manager.core.models import ThemeType


def create_mock_zip(zip_path: Path, files: dict[str, str | bytes]) -> Path:
    """Helper per creare un archivio ZIP con contenuti di test.

    Args:
        zip_path: Percorso in cui salvare lo zip.
        files: Dizionario {rel_path: contenuto}.

    Returns:
        Path del file zip creato.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel_path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(rel_path, content)
    return zip_path


def create_mock_tar(tar_path: Path, files: dict[str, str | bytes], mode: str = "w:gz") -> Path:
    """Helper per creare un archivio TAR (.tar.gz, ecc.) con contenuti di test.

    Args:
        tar_path: Percorso del file tar.
        files: Dizionario {rel_path: contenuto}.
        mode: Modalità di apertura per tarfile (es. 'w:gz', 'w:xz').

    Returns:
        Path del file tar creato.
    """
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode) as tf:
        for rel_path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            info = tarfile.TarInfo(name=rel_path)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    return tar_path


# =============================================================================
# 1. Test Estrazione Sicura (safe_extract)
# =============================================================================


def test_safe_extract_valid_zip(tmp_path: Path) -> None:
    """Verifica l'estrazione corretta di un archivio ZIP valido."""
    archive_file = tmp_path / "valid_theme.zip"
    create_mock_zip(archive_file, {"MyTheme/gtk-3.0/gtk.css": "/* CSS */"})

    target_dir = tmp_path / "extracted"
    result = safe_extract(archive_file, target_dir)

    assert result == target_dir
    assert (target_dir / "MyTheme" / "gtk-3.0" / "gtk.css").exists()


def test_safe_extract_valid_targz(tmp_path: Path) -> None:
    """Verifica l'estrazione corretta di un archivio TAR.GZ valido."""
    archive_file = tmp_path / "valid_theme.tar.gz"
    create_mock_tar(archive_file, {"MyTheme/cursors/arrow": b"CURSOR"})

    target_dir = tmp_path / "extracted"
    result = safe_extract(archive_file, target_dir)

    assert result == target_dir
    assert (target_dir / "MyTheme" / "cursors" / "arrow").exists()


def test_safe_extract_zip_path_traversal(tmp_path: Path) -> None:
    """Verifica che tentativi di Zip Slip / Path Traversal sollevino ArchiveExtractionError."""
    archive_file = tmp_path / "malicious.zip"
    # File con percorso relativo che tenta di uscire dalla directory di estrazione
    create_mock_zip(archive_file, {"../../evil.txt": "hacked"})

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Path Traversal"):
        safe_extract(archive_file, target_dir)


def test_safe_extract_tar_path_traversal(tmp_path: Path) -> None:
    """Verifica che tentativi di Path Traversal in un archivio TAR sollevino ArchiveExtractionError."""
    archive_file = tmp_path / "malicious.tar.gz"
    create_mock_tar(archive_file, {"../../evil.txt": "hacked"})

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Path Traversal"):
        safe_extract(archive_file, target_dir)


def test_safe_extract_corrupted_file(tmp_path: Path) -> None:
    """Verifica che un archivio corrotto sollevi ArchiveExtractionError."""
    corrupted_file = tmp_path / "broken.zip"
    corrupted_file.write_bytes(b"NOT A ZIP FILE CONTENT")

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError):
        safe_extract(corrupted_file, target_dir)


def test_safe_extract_unsupported_extension(tmp_path: Path) -> None:
    """Verifica che un'estensione non supportata sollevi ArchiveExtractionError."""
    txt_file = tmp_path / "archive.rar"
    txt_file.write_text("dummy")

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Unsupported archive format"):
        safe_extract(txt_file, target_dir)


def test_safe_extract_non_existent_file(tmp_path: Path) -> None:
    """Verifica la gestione di file archivio inesistente."""
    missing = tmp_path / "missing.zip"
    with pytest.raises(ArchiveExtractionError, match="does not exist"):
        safe_extract(missing, tmp_path / "out")


# =============================================================================
# 2. Test Rilevamento Tipi e Struttura (detect_theme_types & inspect_extracted_tree)
# =============================================================================


def test_detect_theme_types_gtk(tmp_path: Path) -> None:
    """Verifica il rilevamento di un tema GTK con sottodirectory gtk-3.0."""
    theme_dir = tmp_path / "TestGtk"
    (theme_dir / "gtk-3.0").mkdir(parents=True)
    (theme_dir / "gtk-3.0" / "gtk.css").write_text("/* CSS */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.GTK in types


def test_detect_theme_types_shell(tmp_path: Path) -> None:
    """Verifica il rilevamento di un tema GNOME Shell."""
    theme_dir = tmp_path / "TestShell"
    (theme_dir / "gnome-shell").mkdir(parents=True)
    (theme_dir / "gnome-shell" / "gnome-shell.css").write_text("/* CSS */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.SHELL in types


def test_detect_theme_types_icon_and_cursor(tmp_path: Path) -> None:
    """Verifica il rilevamento di temi icone e cursori."""
    theme_dir = tmp_path / "TestIcon"
    (theme_dir / "cursors").mkdir(parents=True)
    (theme_dir / "index.theme").write_text("[Icon Theme]\nName=TestIcon\n")

    types = detect_theme_types(theme_dir)
    assert ThemeType.CURSOR in types
    assert ThemeType.ICON in types


def test_inspect_extracted_tree_single_root(tmp_path: Path) -> None:
    """Verifica layout a radice singola (es. Nord-GTK/gtk-3.0)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "Nord-GTK" / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="Fallback")
    assert len(targets) == 1
    assert targets[0][0] == "Nord-GTK"
    assert targets[0][2] == ThemeType.GTK


def test_inspect_extracted_tree_flat_layout(tmp_path: Path) -> None:
    """Verifica layout flat (file del tema direttamente nella radice dell'archivio)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="CustomFlatTheme")
    assert len(targets) == 1
    assert targets[0][0] == "CustomFlatTheme"
    assert targets[0][2] == ThemeType.GTK


def test_inspect_extracted_tree_multi_root(tmp_path: Path) -> None:
    """Verifica layout multi-tema (es. Tema-Light/ e Tema-Dark/)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "Nord-Light" / "gtk-3.0").mkdir(parents=True)
    (extracted_root / "Nord-Dark" / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="Fallback")
    assert len(targets) == 2
    names = {t[0] for t in targets}
    assert names == {"Nord-Light", "Nord-Dark"}


def test_inspect_extracted_tree_invalid(tmp_path: Path) -> None:
    """Verifica che un archivio privo di cartelle di temi valide sollevi ThemeValidationError."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "random_folder").mkdir(parents=True)
    (extracted_root / "random_folder" / "hello.txt").write_text("world")

    with pytest.raises(ThemeValidationError):
        inspect_extracted_tree(extracted_root, fallback_name="Fallback")


# =============================================================================
# 3. Test ThemeInstaller (Install & Uninstall)
# =============================================================================


def test_installer_install_gtk_theme(tmp_path: Path) -> None:
    """Test di installazione di un tema GTK in una directory utente temporanea."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    archive = tmp_path / "Nordic.zip"
    create_mock_zip(archive, {"Nordic/gtk-3.0/gtk.css": "/* Nordic CSS */"})

    installed = installer.install(archive)
    assert len(installed) == 1
    theme = installed[0]

    assert theme.name == "Nordic"
    assert theme.theme_type == ThemeType.GTK
    assert (user_themes / "Nordic" / "gtk-3.0" / "gtk.css").exists()


def test_installer_install_custom_name(tmp_path: Path) -> None:
    """Test di installazione con nome personalizzato (custom_name)."""
    user_themes = tmp_path / "user_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    archive = tmp_path / "theme.zip"
    create_mock_zip(archive, {"gtk-3.0/gtk.css": "/* Flat CSS */"})

    installed = installer.install(archive, custom_name="MyCustomNord")
    assert len(installed) == 1
    assert installed[0].name == "MyCustomNord"
    assert (user_themes / "MyCustomNord" / "gtk-3.0" / "gtk.css").exists()


def test_installer_install_overwrite_conflict(tmp_path: Path) -> None:
    """Test gestione conflitto se il tema esiste già e overwrite=False."""
    user_themes = tmp_path / "user_themes"
    (user_themes / "Nordic").mkdir(parents=True)
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    archive = tmp_path / "Nordic.zip"
    create_mock_zip(archive, {"Nordic/gtk-3.0/gtk.css": "/* CSS */"})

    with pytest.raises(FileExistsError, match="already exists"):
        installer.install(archive, overwrite=False)

    # Con overwrite=True deve sovrascrivere con successo
    installed = installer.install(archive, overwrite=True)
    assert len(installed) == 1
    assert (user_themes / "Nordic" / "gtk-3.0" / "gtk.css").exists()


def test_installer_uninstall_success(tmp_path: Path) -> None:
    """Test disinstallazione di un tema utente esistente."""
    user_themes = tmp_path / "user_themes"
    target_theme = user_themes / "ThemeToRemove"
    (target_theme / "gtk-3.0").mkdir(parents=True)

    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    result = installer.uninstall("ThemeToRemove", ThemeType.GTK)
    assert result is True
    assert not target_theme.exists()


def test_installer_uninstall_non_existent(tmp_path: Path) -> None:
    """Test disinstallazione tema inesistente solleva ThemeNotFoundError."""
    user_themes = tmp_path / "user_themes"
    user_themes.mkdir(parents=True)
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    with pytest.raises(ThemeNotFoundError, match="Cannot uninstall theme"):
        installer.uninstall("NonExistentTheme", ThemeType.GTK)


def test_installer_install_modern_unified_theme(tmp_path: Path) -> None:
    """Test di installazione di un tema moderno unificato (GTK3, GTK4, Libadwaita e GNOME Shell in unico archivio)."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    archive = tmp_path / "Nordic-Unified.zip"
    create_mock_zip(
        archive,
        {
            "Nordic-Unified/gtk-3.0/gtk.css": "/* GTK3 */",
            "Nordic-Unified/gtk-4.0/gtk.css": "/* GTK4 Libadwaita */",
            "Nordic-Unified/gnome-shell/gnome-shell.css": "/* GNOME Shell */",
            "Nordic-Unified/index.theme": "[Desktop Entry]\nName=Nordic-Unified\n",
        },
    )

    installed = installer.install(archive)
    # Deve rilevare sia GTK che SHELL dalla medesima cartella
    types = {t.theme_type for t in installed}
    assert ThemeType.GTK in types
    assert ThemeType.SHELL in types

    dest_folder = user_themes / "Nordic-Unified"
    assert (dest_folder / "gtk-3.0" / "gtk.css").exists()
    assert (dest_folder / "gtk-4.0" / "gtk.css").exists()
    assert (dest_folder / "gnome-shell" / "gnome-shell.css").exists()


# =============================================================================
# 6. Test Ispezione e Installazione da Cartella Locale
# =============================================================================


def test_installer_inspect_source_archive(tmp_path: Path) -> None:
    """Verifica che inspect_source analizzi un archivio senza installarlo."""
    archive = tmp_path / "InspectTheme.zip"
    create_mock_zip(archive, {"InspectTheme/gtk-3.0/gtk.css": "/* CSS */"})

    installer = ThemeInstaller(
        user_themes_dir=tmp_path / "themes", user_icons_dir=tmp_path / "icons"
    )
    results = installer.inspect_source(archive)

    assert len(results) == 1
    assert results[0][0] == "InspectTheme"
    assert results[0][2] == ThemeType.GTK
    # Verifica che non sia stato installato nulla
    assert not (tmp_path / "themes" / "InspectTheme").exists()


def test_installer_inspect_source_directory(tmp_path: Path) -> None:
    """Verifica che inspect_source analizzi una cartella senza modificarla."""
    source_dir = tmp_path / "LocalThemeDir"
    (source_dir / "gtk-3.0").mkdir(parents=True)
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* CSS */")

    installer = ThemeInstaller(
        user_themes_dir=tmp_path / "themes", user_icons_dir=tmp_path / "icons"
    )
    results = installer.inspect_source(source_dir)

    assert len(results) == 1
    assert results[0][0] == "LocalThemeDir"
    assert results[0][2] == ThemeType.GTK
    # La cartella sorgente originale deve rimanere intatta
    assert (source_dir / "gtk-3.0" / "gtk.css").exists()


def test_installer_inspect_source_non_existent(tmp_path: Path) -> None:
    """Verifica che inspect_source sollevi FileNotFoundError se la sorgente non esiste."""
    installer = ThemeInstaller(
        user_themes_dir=tmp_path / "themes", user_icons_dir=tmp_path / "icons"
    )
    with pytest.raises(FileNotFoundError):
        installer.inspect_source(tmp_path / "NonExistentPath")


def test_installer_install_directory_success(tmp_path: Path) -> None:
    """Verifica l'installazione di un tema da cartella locale."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    source_dir = tmp_path / "MyFolderTheme"
    (source_dir / "gtk-3.0").mkdir(parents=True)
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* CSS */")

    installed = installer.install_directory(source_dir)
    assert len(installed) == 1
    assert installed[0].name == "MyFolderTheme"
    assert installed[0].theme_type == ThemeType.GTK
    assert installed[0].is_user_level is True

    # Verifica destinazione
    assert (user_themes / "MyFolderTheme" / "gtk-3.0" / "gtk.css").exists()
    # Verifica che la sorgente non sia stata eliminata o spostata
    assert (source_dir / "gtk-3.0" / "gtk.css").exists()


def test_installer_install_directory_conflict_and_overwrite(tmp_path: Path) -> None:
    """Verifica gestione del conflitto di sovrascrittura da cartella."""
    user_themes = tmp_path / "user_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    source_dir = tmp_path / "ConflictTheme"
    (source_dir / "gtk-3.0").mkdir(parents=True)
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* v1 */")

    installer.install_directory(source_dir)

    # Nuovo tentativo con overwrite=False
    with pytest.raises(FileExistsError, match="already exists"):
        installer.install_directory(source_dir, overwrite=False)

    # Sovrascrittura con overwrite=True
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* v2 */")
    installed = installer.install_directory(source_dir, overwrite=True)
    assert len(installed) == 1
    assert (user_themes / "ConflictTheme" / "gtk-3.0" / "gtk.css").read_text() == "/* v2 */"


def test_installer_atomic_install_multi_component_conflict(tmp_path: Path) -> None:
    """Verifica che se un archivio/cartella multi-componente ha un conflitto tardivo, nessun file venga scritto su disco con overwrite=False."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    # Archivio con due componenti: ThemeGTK (GTK) e ThemeIcons (Icone)
    archive = tmp_path / "MultiTheme.zip"
    create_mock_zip(
        archive,
        {
            "ThemeGTK/gtk-3.0/gtk.css": "/* GTK */",
            "ThemeIcons/index.theme": "[Icon Theme]\nName=ThemeIcons\nDirectories=16x16\n",
            "ThemeIcons/16x16/icon.png": "PNG",
        },
    )

    # Pre-creiamo solo la cartella di destinazione del SECONDO componente (ThemeIcons) per simulare un conflitto tardivo
    (user_icons / "ThemeIcons").mkdir(parents=True)
    (user_icons / "ThemeIcons" / "index.theme").write_text("/* Pre-existing Icon Theme */")

    # 1. Con overwrite=False deve sollevare FileExistsError prima di copiare ThemeGTK
    with pytest.raises(FileExistsError, match="already exists"):
        installer.install(archive, overwrite=False)

    # Verifica atomicità: ThemeGTK NON deve essere stato creato/scritto nel primo passaggio
    assert not (user_themes / "ThemeGTK").exists()

    # 2. Con overwrite=True, entrambi i componenti devono venire installati correttamente
    installed = installer.install(archive, overwrite=True)
    assert len(installed) == 2
    assert (user_themes / "ThemeGTK" / "gtk-3.0" / "gtk.css").exists()
    assert (user_icons / "ThemeIcons" / "16x16" / "icon.png").exists()


def test_installer_install_legacy_target_dir(tmp_path: Path) -> None:
    """Verifica che specificando target_dir='legacy' i temi vengano installati nelle cartelle legacy (~/.themes e ~/.icons)."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    archive = tmp_path / "LegacyTheme.zip"
    create_mock_zip(
        archive,
        {
            "LegacyGTK/gtk-3.0/gtk.css": "/* GTK */",
            "LegacyIcons/index.theme": "[Icon Theme]\nName=LegacyIcons\nDirectories=16x16\n",
            "LegacyIcons/16x16/icon.png": "PNG",
        },
    )

    with pytest.MonkeyPatch.context() as mp:
        legacy_themes = tmp_path / "legacy_dot_themes"
        legacy_icons = tmp_path / "legacy_dot_icons"
        mp.setattr(
            "gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes, legacy_themes]
        )
        mp.setattr("gnome_theme_manager.core.installer.USER_ICONS_DIRS", [user_icons, legacy_icons])

        installed = installer.install(archive, target_dir="legacy")
        assert len(installed) == 2

        # Verifica che siano stati salvati nelle directory legacy e non XDG
        assert (legacy_themes / "LegacyGTK" / "gtk-3.0" / "gtk.css").exists()
        assert (legacy_icons / "LegacyIcons" / "16x16" / "icon.png").exists()
        assert not (user_themes / "LegacyGTK").exists()
        assert not (user_icons / "LegacyIcons").exists()


def test_installer_ensure_user_directories(tmp_path: Path) -> None:
    """Verifica che ensure_user_directories crei ~/.themes, ~/.local/share/themes, ~/.icons, ~/.local/share/icons."""
    mock_home = tmp_path / "home" / "user"
    user_themes = mock_home / ".local" / "share" / "themes"
    legacy_themes = mock_home / ".themes"
    user_icons = mock_home / ".local" / "share" / "icons"
    legacy_icons = mock_home / ".icons"

    assert not user_themes.exists()
    assert not legacy_themes.exists()
    assert not user_icons.exists()
    assert not legacy_icons.exists()

    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes, legacy_themes]
        )
        mp.setattr(
            "gnome_theme_manager.core.installer.USER_ICONS_DIRS", [user_icons, legacy_icons]
        )
        mp.setattr(
            "gnome_theme_manager.core.constants.USER_THEMES_DIRS", [user_themes, legacy_themes]
        )
        mp.setattr(
            "gnome_theme_manager.core.constants.USER_ICONS_DIRS", [user_icons, legacy_icons]
        )

        created = installer.ensure_user_directories()
        assert len(created) == 4
        assert user_themes.is_dir()
        assert legacy_themes.is_dir()
        assert user_icons.is_dir()
        assert legacy_icons.is_dir()

        # Invocazione idempotente
        created_again = installer.ensure_user_directories()
        assert len(created_again) == 4
