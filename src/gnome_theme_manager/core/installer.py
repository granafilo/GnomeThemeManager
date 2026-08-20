# SPDX-License-Identifier: GPL-3.0-or-later

"""Safe extraction, validation, and installation of themes from archives and directories.

This module implements:
1. Safe archive extraction (.zip, .tar.*) with Path Traversal / Zip Slip prevention.
2. Archive tree inspection (flat, single-root, or multi-root layouts).
3. Automatic theme type detection (GTK, Shell, Icons, Cursors).
4. User-scoped theme installation and uninstallation (~/.local/share/...).
"""

import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from .constants import USER_ICONS_DIRS, USER_THEMES_DIRS
from .errors import ArchiveExtractionError, ThemeNotFoundError, ThemeValidationError
from .models import Theme, ThemeType


def safe_extract(archive_path: Path, target_dir: Path) -> Path:
    """Safely extract an archive (.zip, .tar.*) into target_dir.

    Enforces anti-Path Traversal / Zip Slip checks to guarantee no files
    are extracted outside the target directory.

    Args:
        archive_path: Path of the archive file to decompress.
        target_dir: Destination directory.

    Returns:
        The target_dir where the archive was extracted.

    Raises:
        ArchiveExtractionError: If the file does not exist, has an unsupported format,
            is corrupted, or contains malicious path traversal entries.
    """
    archive_path = Path(archive_path)
    target_dir = Path(target_dir).resolve()

    if not archive_path.exists() or not archive_path.is_file():
        raise ArchiveExtractionError(
            f"Archive file '{archive_path}' does not exist or is not a valid file."
        )

    filename_lower = archive_path.name.lower()

    if filename_lower.endswith(".zip"):
        _extract_zip(archive_path, target_dir)
    elif filename_lower.endswith(
        (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar")
    ):
        _extract_tar(archive_path, target_dir)
    else:
        raise ArchiveExtractionError(
            f"Unsupported archive format for '{archive_path.name}'. "
            "Supported formats: .zip, .tar.gz, .tar.xz, .tar.bz2, .tar"
        )

    return target_dir


def _is_within_directory(directory: Path, target: Path) -> bool:
    """Check if target path resides within the specified directory."""
    try:
        target.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _extract_zip(archive_path: Path, target_dir: Path) -> None:
    """Extract a ZIP archive with security checks against Zip Slip."""
    try:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                member_path = target_dir / member.filename
                if not _is_within_directory(target_dir, member_path):
                    raise ArchiveExtractionError(
                        f"Detected Path Traversal attempt in ZIP archive: '{member.filename}'"
                    )
            zip_ref.extractall(target_dir)
    except zipfile.BadZipFile as err:
        raise ArchiveExtractionError(
            f"Invalid or corrupted ZIP file '{archive_path.name}': {err}"
        ) from err
    except ArchiveExtractionError:
        raise
    except Exception as err:
        raise ArchiveExtractionError(
            f"Error extracting ZIP archive '{archive_path.name}': {err}"
        ) from err


def _extract_tar(archive_path: Path, target_dir: Path) -> None:
    """Extract a TAR archive with security checks against Path Traversal."""
    try:
        with tarfile.open(archive_path, "r:*") as tar_ref:
            for member in tar_ref.getmembers():
                member_path = target_dir / member.name
                if not _is_within_directory(target_dir, member_path):
                    raise ArchiveExtractionError(
                        f"Detected Path Traversal attempt in TAR archive: '{member.name}'"
                    )

            if hasattr(tarfile, "data_filter"):
                tar_ref.extractall(target_dir, filter="data")
            else:
                tar_ref.extractall(target_dir)
    except ArchiveExtractionError:
        raise
    except tarfile.TarError as err:
        raise ArchiveExtractionError(
            f"Invalid or corrupted TAR file '{archive_path.name}': {err}"
        ) from err
    except Exception as err:
        raise ArchiveExtractionError(
            f"Error extracting TAR archive '{archive_path.name}': {err}"
        ) from err


def detect_theme_types(theme_dir: Path) -> list[ThemeType]:
    """Auto-detect theme types present in a directory.

    Args:
        theme_dir: Directory of an extracted theme.

    Returns:
        List of detected ThemeType values for the directory.
    """
    detected: list[ThemeType] = []

    # 1. Check GTK Theme
    gtk_subdirs = ["gtk-2.0", "gtk-3.0", "gtk-4.0"]
    has_gtk_dir = any((theme_dir / sub).is_dir() for sub in gtk_subdirs)
    index_theme = theme_dir / "index.theme"

    is_gtk = has_gtk_dir
    if index_theme.is_file() and not is_gtk:
        try:
            content = index_theme.read_text(encoding="utf-8", errors="ignore")
            if "[Desktop Entry]" in content or "[GtkTheme]" in content:
                is_gtk = True
        except (OSError, UnicodeDecodeError):
            pass

    if is_gtk:
        detected.append(ThemeType.GTK)

    # 2. Check GNOME Shell Theme
    shell_css = theme_dir / "gnome-shell" / "gnome-shell.css"
    if shell_css.is_file() or (theme_dir / "gnome-shell").is_dir():
        detected.append(ThemeType.SHELL)

    # 3. Check Cursor Theme
    if (theme_dir / "cursors").is_dir():
        detected.append(ThemeType.CURSOR)

    # 4. Check Icon Pack
    is_icon = False
    if index_theme.is_file():
        try:
            content = index_theme.read_text(encoding="utf-8", errors="ignore")
            if "[Icon Theme]" in content:
                is_icon = True
        except (OSError, UnicodeDecodeError):
            pass

    if not is_icon and not (theme_dir / "cursors").is_dir():
        icon_subdirs = [
            "scalable",
            "16x16",
            "22x22",
            "24x24",
            "32x32",
            "48x48",
            "64x64",
            "128x128",
            "256x256",
            "512x512",
        ]
        if any((theme_dir / sub).is_dir() for sub in icon_subdirs):
            is_icon = True

    if is_icon and ThemeType.ICON not in detected:
        detected.append(ThemeType.ICON)

    return detected


def inspect_extracted_tree(
    extracted_root: Path, fallback_name: str
) -> list[tuple[str, Path, ThemeType]]:
    """Inspect extracted directory tree to identify themes and their types.

    Handles:
    - Flat layout (configuration files directly in extracted_root).
    - Single root layout (e.g. ThemeName/gtk-3.0/...).
    - Multi-theme layout (multiple subdirectories each containing a theme).

    Args:
        extracted_root: Root path of extracted archive.
        fallback_name: Name assigned to theme in case of flat layout.

    Returns:
        List of tuples (theme_name, directory_path, theme_type).

    Raises:
        ThemeValidationError: If the archive contains no recognized theme structure.
    """
    targets: list[tuple[str, Path, ThemeType]] = []

    # 1. Check flat layout directly at root
    flat_types = detect_theme_types(extracted_root)
    if flat_types:
        for t_type in flat_types:
            targets.append((fallback_name, extracted_root, t_type))
        return targets

    # 2. Check subdirectories (single root or multi-theme)
    subdirs = [
        p
        for p in extracted_root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "__MACOSX"
    ]

    for sub in subdirs:
        sub_types = detect_theme_types(sub)
        if sub_types:
            for t_type in sub_types:
                targets.append((sub.name, sub, t_type))
        else:
            # Check nested folders (e.g. Archive/NestedFolder/ThemeFolder)
            nested_dirs = [
                n
                for n in sub.iterdir()
                if n.is_dir() and not n.name.startswith(".") and n.name != "__MACOSX"
            ]
            for nested in nested_dirs:
                nested_types = detect_theme_types(nested)
                for t_type in nested_types:
                    targets.append((nested.name, nested, t_type))

    if not targets:
        raise ThemeValidationError(
            "Archive does not contain a recognized theme structure (GTK, Shell, Icon pack, or Cursor theme)."
        )

    return targets


class ThemeInstaller:
    """Manages safe installation and uninstallation of user themes."""

    def __init__(
        self,
        user_themes_dir: Path | None = None,
        user_icons_dir: Path | None = None,
    ) -> None:
        """Initialize installer with user destination paths.

        Args:
            user_themes_dir: User directory for GTK and Shell themes (default: ~/.local/share/themes).
            user_icons_dir: User directory for Icon and Cursor themes (default: ~/.local/share/icons).
        """
        self.user_themes_dir = (
            Path(user_themes_dir).expanduser() if user_themes_dir else USER_THEMES_DIRS[0]
        )
        self.user_icons_dir = (
            Path(user_icons_dir).expanduser() if user_icons_dir else USER_ICONS_DIRS[0]
        )

    def ensure_user_directories(self) -> list[Path]:
        """Ensure all standard user theme directories exist on the filesystem.

        Creates ~/.local/share/themes, ~/.themes, ~/.local/share/icons, and ~/.icons
        if they do not already exist.

        Returns:
            List of Path objects that were verified/created.
        """
        dirs_to_ensure: list[Path] = [self.user_themes_dir, self.user_icons_dir]

        for d in USER_THEMES_DIRS:
            expanded = d.expanduser()
            if expanded not in dirs_to_ensure:
                dirs_to_ensure.append(expanded)

        for d in USER_ICONS_DIRS:
            expanded = d.expanduser()
            if expanded not in dirs_to_ensure:
                dirs_to_ensure.append(expanded)

        for directory in dirs_to_ensure:
            directory.mkdir(parents=True, exist_ok=True)

        return dirs_to_ensure

    def inspect_source(
        self,
        source_path: Path,
        fallback_name: str | None = None,
    ) -> list[tuple[str, Path, ThemeType]]:
        """Inspect a source (directory or archive) to identify themes and components.

        Does not modify the original source. If the source is an archive, temporarily
        extracts it into a secure directory for inspection.

        Args:
            source_path: Path to archive file or theme directory.
            fallback_name: Optional name for flat-layout themes.

        Returns:
            List of tuples (theme_name, source_path, theme_type).

        Raises:
            FileNotFoundError: If source_path does not exist.
            ArchiveExtractionError: If archive is invalid or corrupted.
            ThemeValidationError: If no valid theme structure is detected.
        """
        source_path = Path(source_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source '{source_path}' does not exist.")

        if source_path.is_dir():
            name = fallback_name or source_path.name
            return inspect_extracted_tree(source_path, fallback_name=name)

        # Archive file
        name = fallback_name or source_path.name
        for ext in [".tar.gz", ".tar.xz", ".tar.bz2", ".tgz", ".txz", ".tbz2", ".zip", ".tar"]:
            if name.lower().endswith(ext):
                name = name[: -len(ext)]
                break

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            safe_extract(source_path, tmp_dir)
            targets = inspect_extracted_tree(tmp_dir, fallback_name=name)
            return [(t_name, source_path, t_type) for t_name, _, t_type in targets]

    def install_directory(
        self,
        directory_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
        target_dir: str | Path | None = None,
    ) -> list[Theme]:
        """Inspect and install themes from a local directory into user directories.

        Does not modify or delete the original source directory.

        Args:
            directory_path: Path to theme directory to install.
            theme_type: Optional theme type filter.
            custom_name: Custom destination folder name.
            overwrite: If True, overwrite existing themes.
            target_dir: Custom destination ('xdg' for ~/.local/share, 'legacy' for ~/.themes and ~/.icons, or a custom Path).

        Returns:
            List of installed Theme instances.

        Raises:
            FileNotFoundError: If source directory does not exist.
            ThemeValidationError: If theme structure is invalid or incompatible.
            FileExistsError: If theme already exists and overwrite=False.
        """
        directory_path = Path(directory_path).resolve()
        if not directory_path.exists() or not directory_path.is_dir():
            raise FileNotFoundError(
                f"Source directory '{directory_path}' does not exist or is not a directory."
            )

        fallback_name = custom_name or directory_path.name
        targets = inspect_extracted_tree(directory_path, fallback_name=fallback_name)

        if theme_type is not None:
            filtered = [t for t in targets if t[2] == theme_type]
            if not filtered:
                raise ThemeValidationError(
                    f"Directory does not contain a theme matching requested type '{theme_type.value}'."
                )
            targets = filtered

        if custom_name and len({t[1] for t in targets}) == 1:
            targets = [(custom_name, t[1], t[2]) for t in targets]

        # Determine target base directories (XDG vs Legacy)
        self.ensure_user_directories()
        if isinstance(target_dir, str) and target_dir.lower() == "legacy":
            base_themes_dir = USER_THEMES_DIRS[1]
            base_icons_dir = USER_ICONS_DIRS[1]
        elif isinstance(target_dir, (str, Path)) and target_dir not in (None, "xdg"):
            custom_path = Path(target_dir).expanduser()
            base_themes_dir = custom_path
            base_icons_dir = custom_path
        else:
            base_themes_dir = self.user_themes_dir
            base_icons_dir = self.user_icons_dir

        # Pass 1: Conflict pre-validation across all components
        if not overwrite:
            conflicts: list[str] = []
            checked_dirs: set[tuple[str, Path]] = set()
            for name, source_dir, t_type in targets:
                target_base_dir = (
                    base_themes_dir
                    if t_type in (ThemeType.GTK, ThemeType.SHELL)
                    else base_icons_dir
                )
                dest_dir = target_base_dir / name
                dir_key = (name, source_dir)
                if dir_key not in checked_dirs:
                    if dest_dir.exists():
                        conflicts.append(f"'{name}' in '{dest_dir}'")
                    checked_dirs.add(dir_key)

            if conflicts:
                conflicts_str = ", ".join(conflicts)
                raise FileExistsError(
                    f"Theme already exists. Cannot install: the following themes already exist: {conflicts_str}. Use overwrite=True to overwrite."
                )

        # Pass 2: Installation
        installed_themes: list[Theme] = []
        processed_dirs: set[tuple[str, Path]] = set()

        for name, source_dir, t_type in targets:
            target_base_dir = (
                base_themes_dir if t_type in (ThemeType.GTK, ThemeType.SHELL) else base_icons_dir
            )
            dest_dir = target_base_dir / name

            dir_key = (name, source_dir)
            if dir_key not in processed_dirs:
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)

                target_base_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_dir, dest_dir)
                processed_dirs.add(dir_key)

            installed_themes.append(
                Theme(
                    name=name,
                    theme_type=t_type,
                    path=dest_dir,
                    is_user_level=True,
                )
            )

        return installed_themes

    def install(
        self,
        archive_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
        target_dir: str | Path | None = None,
    ) -> list[Theme]:
        """Extract, validate, and install themes from an archive or directory into user directories.

        If archive_path is a directory, delegates to install_directory. If it is an archive file,
        performs safe extraction in a temporary directory and installs discovered themes.

        Args:
            archive_path: Path to archive file (.zip, .tar.*) or theme directory.
            theme_type: Optional theme type filter.
            custom_name: Custom destination folder name.
            overwrite: If True, overwrite existing themes.
            target_dir: Custom destination ('xdg' for ~/.local/share, 'legacy' for ~/.themes and ~/.icons, or a custom Path).

        Returns:
            List of installed Theme instances.

        Raises:
            FileNotFoundError: If file or directory does not exist.
            ArchiveExtractionError: If extraction fails or a security threat is detected.
            ThemeValidationError: If archive structure is invalid or incompatible.
            FileExistsError: If theme already exists and overwrite=False.
        """
        source_path = Path(archive_path)
        if source_path.is_dir():
            return self.install_directory(
                directory_path=source_path,
                theme_type=theme_type,
                custom_name=custom_name,
                overwrite=overwrite,
                target_dir=target_dir,
            )

        fallback_name = custom_name or source_path.name
        for ext in [".tar.gz", ".tar.xz", ".tar.bz2", ".tgz", ".txz", ".tbz2", ".zip", ".tar"]:
            if fallback_name.lower().endswith(ext):
                fallback_name = fallback_name[: -len(ext)]
                break

        installed_themes: list[Theme] = []

        # Determine target base directories (XDG vs Legacy)
        if isinstance(target_dir, str) and target_dir.lower() == "legacy":
            base_themes_dir = USER_THEMES_DIRS[1]
            base_icons_dir = USER_ICONS_DIRS[1]
        elif isinstance(target_dir, (str, Path)) and target_dir not in (None, "xdg"):
            custom_path = Path(target_dir).expanduser()
            base_themes_dir = custom_path
            base_icons_dir = custom_path
        else:
            base_themes_dir = self.user_themes_dir
            base_icons_dir = self.user_icons_dir

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            safe_extract(source_path, tmp_dir)

            targets = inspect_extracted_tree(tmp_dir, fallback_name=fallback_name)

            if theme_type is not None:
                filtered = [t for t in targets if t[2] == theme_type]
                if not filtered:
                    raise ThemeValidationError(
                        f"Archive does not contain a theme matching requested type '{theme_type.value}'."
                    )
                targets = filtered

            if custom_name and len({t[1] for t in targets}) == 1:
                targets = [(custom_name, t[1], t[2]) for t in targets]

            # Pass 1: Conflict pre-validation across all components
            if not overwrite:
                conflicts: list[str] = []
                checked_dirs: set[tuple[str, Path]] = set()
                for name, source_dir, t_type in targets:
                    target_base_dir = (
                        base_themes_dir
                        if t_type in (ThemeType.GTK, ThemeType.SHELL)
                        else base_icons_dir
                    )
                    dest_dir = target_base_dir / name
                    dir_key = (name, source_dir)
                    if dir_key not in checked_dirs:
                        if dest_dir.exists():
                            conflicts.append(f"'{name}' in '{dest_dir}'")
                        checked_dirs.add(dir_key)

                if conflicts:
                    conflicts_str = ", ".join(conflicts)
                    raise FileExistsError(
                        f"Theme already exists. Cannot install: the following themes already exist: {conflicts_str}. Use overwrite=True to overwrite."
                    )

            # Pass 2: Installation
            processed_dirs: set[tuple[str, Path]] = set()

            for name, source_dir, t_type in targets:
                target_base_dir = (
                    base_themes_dir
                    if t_type in (ThemeType.GTK, ThemeType.SHELL)
                    else base_icons_dir
                )
                dest_dir = target_base_dir / name

                dir_key = (name, source_dir)
                if dir_key not in processed_dirs:
                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)

                    target_base_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_dir, dest_dir)
                    processed_dirs.add(dir_key)

                installed_themes.append(
                    Theme(
                        name=name,
                        theme_type=t_type,
                        path=dest_dir,
                        is_user_level=True,
                    )
                )

        return installed_themes

    def uninstall(self, theme_name: str, theme_type: ThemeType) -> bool:
        """Uninstall a user theme by removing it exclusively from user directories.

        Args:
            theme_name: Directory name of the theme to remove.
            theme_type: Theme type (GTK, SHELL, ICON, CURSOR).

        Returns:
            True if uninstallation was successful.

        Raises:
            ThemeNotFoundError: If theme is not found in user directories.
        """
        base_user_dirs = (
            USER_THEMES_DIRS if theme_type in (ThemeType.GTK, ThemeType.SHELL) else USER_ICONS_DIRS
        )

        custom_dir = (
            self.user_themes_dir
            if theme_type in (ThemeType.GTK, ThemeType.SHELL)
            else self.user_icons_dir
        )

        user_dirs: list[Path] = [custom_dir]
        for d in base_user_dirs:
            if d.expanduser() not in [ud.expanduser() for ud in user_dirs]:
                user_dirs.append(d)

        found_user_path: Path | None = None
        for base_dir in user_dirs:
            candidate = base_dir.expanduser() / theme_name
            if candidate.exists() and candidate.is_dir():
                found_user_path = candidate
                break

        if not found_user_path:
            raise ThemeNotFoundError(
                f"Cannot uninstall theme '{theme_name}' of type '{theme_type.value}': "
                "theme not found in user directories (~/.local/share/... or ~/.themes, ~/.icons)."
            )

        shutil.rmtree(found_user_path)
        return True
