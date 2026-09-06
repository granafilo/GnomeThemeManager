# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for safe archive extraction and theme installer."""

import io
import os
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
    """Helper to create a ZIP archive with test contents.

    Args:
        zip_path: Path where the zip file should be saved.
        files: Dictionary of {rel_path: content}.

    Returns:
        Path of the created zip file.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel_path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(rel_path, content)
    return zip_path


def create_mock_tar(tar_path: Path, files: dict[str, str | bytes], mode: str = "w:gz") -> Path:
    """Helper to create a TAR archive (.tar.gz, etc.) with test contents.

    Args:
        tar_path: Path of the tar file.
        files: Dictionary of {rel_path: content}.
        mode: Open mode for tarfile (e.g. 'w:gz', 'w:xz').

    Returns:
        Path of the created tar file.
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
# 1. Safe Extraction Tests (safe_extract)
# =============================================================================


def test_safe_extract_valid_zip(tmp_path: Path) -> None:
    """Verify correct extraction of a valid ZIP archive."""
    archive_file = tmp_path / "valid_theme.zip"
    create_mock_zip(archive_file, {"MyTheme/gtk-3.0/gtk.css": "/* CSS */"})

    target_dir = tmp_path / "extracted"
    result = safe_extract(archive_file, target_dir)

    assert result == target_dir
    assert (target_dir / "MyTheme" / "gtk-3.0" / "gtk.css").exists()


def test_safe_extract_valid_targz(tmp_path: Path) -> None:
    """Verify correct extraction of a valid TAR.GZ archive."""
    archive_file = tmp_path / "valid_theme.tar.gz"
    create_mock_tar(archive_file, {"MyTheme/cursors/arrow": b"CURSOR"})

    target_dir = tmp_path / "extracted"
    result = safe_extract(archive_file, target_dir)

    assert result == target_dir
    assert (target_dir / "MyTheme" / "cursors" / "arrow").exists()


def test_safe_extract_tar_with_symlinks(tmp_path: Path) -> None:
    """Verify extraction of a TAR archive with symlinks and absolute paths (typical in icon themes)."""
    archive_file = tmp_path / "icons_with_symlinks.tar.xz"
    with tarfile.open(archive_file, "w:xz") as tf:
        # Real file
        base_file = tarfile.TarInfo(name="Slot-Dark-Icons/status/32/appointment.svg")
        base_content = b"<svg>test</svg>"
        base_file.size = len(base_content)
        tf.addfile(base_file, io.BytesIO(base_content))

        # Symlink with absolute path / leading slash
        sym_link = tarfile.TarInfo(name="Slot-Dark-Icons/status/32/appointment-symbolic.svg")
        sym_link.type = tarfile.SYMTYPE
        sym_link.linkname = "/Slot-Dark-Icons/status/32/appointment.svg"
        tf.addfile(sym_link)

    target_dir = tmp_path / "extracted_icons"
    result = safe_extract(archive_file, target_dir)

    assert result == target_dir
    assert (target_dir / "Slot-Dark-Icons" / "status" / "32" / "appointment.svg").exists()
    assert (target_dir / "Slot-Dark-Icons" / "status" / "32" / "appointment-symbolic.svg").exists()


def test_safe_extract_zip_path_traversal(tmp_path: Path) -> None:
    """Verify that Zip Slip / Path Traversal attempts raise ArchiveExtractionError."""
    archive_file = tmp_path / "malicious.zip"
    # File with relative path attempting to escape extraction directory
    create_mock_zip(archive_file, {"../../evil.txt": "hacked"})

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Path Traversal"):
        safe_extract(archive_file, target_dir)


def test_safe_extract_tar_path_traversal(tmp_path: Path) -> None:
    """Verify that Path Traversal attempts in a TAR archive raise ArchiveExtractionError."""
    archive_file = tmp_path / "malicious.tar.gz"
    create_mock_tar(archive_file, {"../../evil.txt": "hacked"})

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Path Traversal"):
        safe_extract(archive_file, target_dir)


def test_safe_extract_corrupted_file(tmp_path: Path) -> None:
    """Verify that a corrupted archive raises ArchiveExtractionError."""
    corrupted_file = tmp_path / "broken.zip"
    corrupted_file.write_bytes(b"NOT A ZIP FILE CONTENT")

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError):
        safe_extract(corrupted_file, target_dir)


def test_safe_extract_unsupported_extension(tmp_path: Path) -> None:
    """Verify that an unsupported extension raises ArchiveExtractionError."""
    txt_file = tmp_path / "archive.rar"
    txt_file.write_text("dummy")

    target_dir = tmp_path / "extracted"
    with pytest.raises(ArchiveExtractionError, match="Unsupported archive format"):
        safe_extract(txt_file, target_dir)


def test_safe_extract_non_existent_file(tmp_path: Path) -> None:
    """Verify handling of a non-existent archive file."""
    missing = tmp_path / "missing.zip"
    with pytest.raises(ArchiveExtractionError, match="does not exist"):
        safe_extract(missing, tmp_path / "out")


# =============================================================================
# 2. Type & Structure Detection Tests (detect_theme_types & inspect_extracted_tree)
# =============================================================================


def test_detect_theme_types_gtk(tmp_path: Path) -> None:
    """Verify detection of a GTK theme with gtk-3.0 subdirectory."""
    theme_dir = tmp_path / "TestGtk"
    (theme_dir / "gtk-3.0").mkdir(parents=True)
    (theme_dir / "gtk-3.0" / "gtk.css").write_text("/* CSS */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.GTK in types


def test_detect_theme_types_shell(tmp_path: Path) -> None:
    """Verify detection of a GNOME Shell theme."""
    theme_dir = tmp_path / "TestShell"
    (theme_dir / "gnome-shell").mkdir(parents=True)
    (theme_dir / "gnome-shell" / "gnome-shell.css").write_text("/* CSS */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.SHELL in types


def test_detect_theme_types_icon_and_cursor(tmp_path: Path) -> None:
    """Verify detection of icon and cursor themes."""
    theme_dir = tmp_path / "TestIcon"
    (theme_dir / "cursors").mkdir(parents=True)
    (theme_dir / "index.theme").write_text("[Icon Theme]\nName=TestIcon\n")

    types = detect_theme_types(theme_dir)
    assert ThemeType.CURSOR in types
    assert ThemeType.ICON in types


def test_inspect_extracted_tree_single_root(tmp_path: Path) -> None:
    """Verify single root layout (e.g. Nord-GTK/gtk-3.0)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "Nord-GTK" / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="Fallback")
    assert len(targets) == 1
    assert targets[0][0] == "Nord-GTK"
    assert targets[0][2] == ThemeType.GTK


def test_inspect_extracted_tree_flat_layout(tmp_path: Path) -> None:
    """Verify flat layout (theme files directly in archive root)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="CustomFlatTheme")
    assert len(targets) == 1
    assert targets[0][0] == "CustomFlatTheme"
    assert targets[0][2] == ThemeType.GTK


def test_inspect_extracted_tree_multi_root(tmp_path: Path) -> None:
    """Verify multi-theme layout (e.g. Theme-Light/ and Theme-Dark/)."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "Nord-Light" / "gtk-3.0").mkdir(parents=True)
    (extracted_root / "Nord-Dark" / "gtk-3.0").mkdir(parents=True)

    targets = inspect_extracted_tree(extracted_root, fallback_name="Fallback")
    assert len(targets) == 2
    names = {t[0] for t in targets}
    assert names == {"Nord-Light", "Nord-Dark"}


def test_inspect_extracted_tree_invalid(tmp_path: Path) -> None:
    """Verify that an archive without valid theme directories raises ThemeValidationError."""
    extracted_root = tmp_path / "extracted"
    (extracted_root / "random_folder").mkdir(parents=True)
    (extracted_root / "random_folder" / "hello.txt").write_text("world")

    with pytest.raises(ThemeValidationError):
        inspect_extracted_tree(extracted_root, fallback_name="Fallback")


# =============================================================================
# 3. ThemeInstaller Tests (Install & Uninstall)
# =============================================================================


def test_installer_install_gtk_theme(tmp_path: Path) -> None:
    """Test installing a GTK theme into a temporary user directory."""
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
    """Test installation with custom name (custom_name)."""
    user_themes = tmp_path / "user_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    archive = tmp_path / "theme.zip"
    create_mock_zip(archive, {"gtk-3.0/gtk.css": "/* Flat CSS */"})

    installed = installer.install(archive, custom_name="MyCustomNord")
    assert len(installed) == 1
    assert installed[0].name == "MyCustomNord"
    assert (user_themes / "MyCustomNord" / "gtk-3.0" / "gtk.css").exists()


def test_installer_install_overwrite_conflict(tmp_path: Path) -> None:
    """Test conflict handling if theme already exists and overwrite=False."""
    user_themes = tmp_path / "user_themes"
    (user_themes / "Nordic").mkdir(parents=True)
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    archive = tmp_path / "Nordic.zip"
    create_mock_zip(archive, {"Nordic/gtk-3.0/gtk.css": "/* CSS */"})

    with pytest.raises(FileExistsError, match="already exists"):
        installer.install(archive, overwrite=False)

    # With overwrite=True it must successfully overwrite
    installed = installer.install(archive, overwrite=True)
    assert len(installed) == 1
    assert (user_themes / "Nordic" / "gtk-3.0" / "gtk.css").exists()


def test_installer_uninstall_success(tmp_path: Path) -> None:
    """Test uninstalling an existing user theme."""
    user_themes = tmp_path / "user_themes"
    target_theme = user_themes / "ThemeToRemove"
    (target_theme / "gtk-3.0").mkdir(parents=True)

    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    result = installer.uninstall("ThemeToRemove", ThemeType.GTK)
    assert result is True
    assert not target_theme.exists()


def test_installer_uninstall_non_existent(tmp_path: Path) -> None:
    """Test uninstalling a non-existent theme raises ThemeNotFoundError."""
    user_themes = tmp_path / "user_themes"
    user_themes.mkdir(parents=True)
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    with pytest.raises(ThemeNotFoundError, match="Cannot uninstall theme"):
        installer.uninstall("NonExistentTheme", ThemeType.GTK)


def test_installer_install_modern_unified_theme(tmp_path: Path) -> None:
    """Test installing a modern unified theme (GTK3, GTK4, Libadwaita and GNOME Shell in a single archive)."""
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
    # Must detect both GTK and SHELL from the same folder
    types = {t.theme_type for t in installed}
    assert ThemeType.GTK in types
    assert ThemeType.SHELL in types

    dest_folder = user_themes / "Nordic-Unified"
    assert (dest_folder / "gtk-3.0" / "gtk.css").exists()
    assert (dest_folder / "gtk-4.0" / "gtk.css").exists()
    assert (dest_folder / "gnome-shell" / "gnome-shell.css").exists()


# =============================================================================
# 6. Local Directory Inspection & Installation Tests
# =============================================================================


def test_installer_inspect_source_archive(tmp_path: Path) -> None:
    """Verify that inspect_source inspects an archive without installing it."""
    archive = tmp_path / "InspectTheme.zip"
    create_mock_zip(archive, {"InspectTheme/gtk-3.0/gtk.css": "/* CSS */"})

    installer = ThemeInstaller(
        user_themes_dir=tmp_path / "themes", user_icons_dir=tmp_path / "icons"
    )
    results = installer.inspect_source(archive)

    assert len(results) == 1
    assert results[0][0] == "InspectTheme"
    assert results[0][2] == ThemeType.GTK
    # Verify that nothing was installed
    assert not (tmp_path / "themes" / "InspectTheme").exists()


def test_installer_inspect_source_directory(tmp_path: Path) -> None:
    """Verify that inspect_source inspects a directory without modifying it."""
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
    # Original source directory must remain intact
    assert (source_dir / "gtk-3.0" / "gtk.css").exists()


def test_installer_inspect_source_non_existent(tmp_path: Path) -> None:
    """Verify that inspect_source raises FileNotFoundError if the source does not exist."""
    installer = ThemeInstaller(
        user_themes_dir=tmp_path / "themes", user_icons_dir=tmp_path / "icons"
    )
    with pytest.raises(FileNotFoundError):
        installer.inspect_source(tmp_path / "NonExistentPath")


def test_installer_install_directory_success(tmp_path: Path) -> None:
    """Verify installing a theme from a local folder."""
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

    # Verify destination
    assert (user_themes / "MyFolderTheme" / "gtk-3.0" / "gtk.css").exists()
    # Verify that the source was not deleted or moved
    assert (source_dir / "gtk-3.0" / "gtk.css").exists()


def test_installer_install_directory_conflict_and_overwrite(tmp_path: Path) -> None:
    """Verify handling of overwrite conflict from a folder."""
    user_themes = tmp_path / "user_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=tmp_path / "icons")

    source_dir = tmp_path / "ConflictTheme"
    (source_dir / "gtk-3.0").mkdir(parents=True)
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* v1 */")

    installer.install_directory(source_dir)

    # New attempt with overwrite=False
    with pytest.raises(FileExistsError, match="already exists"):
        installer.install_directory(source_dir, overwrite=False)

    # Overwrite with overwrite=True
    (source_dir / "gtk-3.0" / "gtk.css").write_text("/* v2 */")
    installed = installer.install_directory(source_dir, overwrite=True)
    assert len(installed) == 1
    assert (user_themes / "ConflictTheme" / "gtk-3.0" / "gtk.css").read_text() == "/* v2 */"


def test_installer_atomic_install_multi_component_conflict(tmp_path: Path) -> None:
    """Verify that if a multi-component archive/folder encounters a late conflict, no files are written with overwrite=False."""
    user_themes = tmp_path / "user_themes"
    user_icons = tmp_path / "user_icons"
    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    # Archive with two components: ThemeGTK (GTK) and ThemeIcons (Icons)
    archive = tmp_path / "MultiTheme.zip"
    create_mock_zip(
        archive,
        {
            "ThemeGTK/gtk-3.0/gtk.css": "/* GTK */",
            "ThemeIcons/index.theme": "[Icon Theme]\nName=ThemeIcons\nDirectories=16x16\n",
            "ThemeIcons/16x16/icon.png": "PNG",
        },
    )

    # Pre-create only the destination folder of the SECOND component (ThemeIcons) to simulate a late conflict
    (user_icons / "ThemeIcons").mkdir(parents=True)
    (user_icons / "ThemeIcons" / "index.theme").write_text("/* Pre-existing Icon Theme */")

    # 1. With overwrite=False it must raise FileExistsError before copying ThemeGTK
    with pytest.raises(FileExistsError, match="already exists"):
        installer.install(archive, overwrite=False)

    # Verify atomicity: ThemeGTK must NOT have been created/written in the first step
    assert not (user_themes / "ThemeGTK").exists()

    # 2. With overwrite=True, both components must be installed successfully
    installed = installer.install(archive, overwrite=True)
    assert len(installed) == 2
    assert (user_themes / "ThemeGTK" / "gtk-3.0" / "gtk.css").exists()
    assert (user_icons / "ThemeIcons" / "16x16" / "icon.png").exists()


def test_installer_install_legacy_target_dir(tmp_path: Path) -> None:
    """Verify that specifying target_dir='legacy' installs themes in legacy directories (~/.themes and ~/.icons)."""
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

        # Verify that files were saved in legacy directories and not XDG
        assert (legacy_themes / "LegacyGTK" / "gtk-3.0" / "gtk.css").exists()
        assert (legacy_icons / "LegacyIcons" / "16x16" / "icon.png").exists()
        assert not (user_themes / "LegacyGTK").exists()
        assert not (user_icons / "LegacyIcons").exists()


def test_installer_ensure_user_directories(tmp_path: Path) -> None:
    """Verify that ensure_user_directories creates ~/.themes, ~/.local/share/themes, ~/.icons, ~/.local/share/icons."""
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
        mp.setattr("gnome_theme_manager.core.installer.USER_ICONS_DIRS", [user_icons, legacy_icons])
        mp.setattr(
            "gnome_theme_manager.core.constants.USER_THEMES_DIRS", [user_themes, legacy_themes]
        )
        mp.setattr("gnome_theme_manager.core.constants.USER_ICONS_DIRS", [user_icons, legacy_icons])

        created = installer.ensure_user_directories()
        assert len(created) == 4
        assert user_themes.is_dir()
        assert legacy_themes.is_dir()
        assert user_icons.is_dir()
        assert legacy_icons.is_dir()

        # Idempotent call
        created_again = installer.ensure_user_directories()
        assert len(created_again) == 4


def test_installer_with_dangling_symlinks(tmp_path: Path) -> None:
    """Verify that the installer handles packages with orphaned symbolic links gracefully."""
    user_icons = tmp_path / "icons"
    installer = ThemeInstaller(user_icons_dir=user_icons)

    # Create directory with a symlink pointing to a non-existent file
    source_theme = tmp_path / "BrokenIconTheme"
    (source_theme / "16x16").mkdir(parents=True)
    (source_theme / "index.theme").write_text("[Icon Theme]\nName=BrokenIconTheme\n")
    (source_theme / "16x16" / "real.png").write_bytes(b"PNG")

    # Manual creation of dangling symlink
    os.symlink("non_existent_file.png", source_theme / "16x16" / "dangling.png")

    installed = installer.install_directory(source_theme, overwrite=True)
    assert len(installed) == 1
    assert (user_icons / "BrokenIconTheme" / "index.theme").exists()
    assert (user_icons / "BrokenIconTheme" / "16x16" / "real.png").exists()
