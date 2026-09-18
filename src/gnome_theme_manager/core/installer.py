# SPDX-License-Identifier: GPL-3.0-or-later

"""Safe extraction, validation, and installation of themes from archives and directories.

This module implements:
1. Safe archive extraction (.zip, .tar.*) with Path Traversal / Zip Slip prevention.
2. Archive tree inspection (flat, single-root, or multi-root layouts).
3. Automatic theme type detection (GTK, Shell, Icons, Cursors).
4. User-scoped theme installation and uninstallation (~/.local/share/...).
"""

import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

from .constants import USER_ICONS_DIRS, USER_THEMES_DIRS
from .errors import ArchiveExtractionError, ThemeNotFoundError, ThemeValidationError
from .models import Theme, ThemeType

logger = logging.getLogger("gnome_theme_manager.core.installer")


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


def _theme_tar_filter(member: tarfile.TarInfo, dest_path: str) -> tarfile.TarInfo | None:
    """Security filter for extracting theme and icon archives safely.

    Protects against Path Traversal while permitting intra-archive relative symlinks
    and sanitizing absolute symlink targets common in community icon packs.
    """
    dest = Path(dest_path).resolve()
    target = (dest / member.name).resolve()

    # 1. Prevent Path Traversal
    try:
        target.relative_to(dest)
    except ValueError:
        raise ArchiveExtractionError(
            f"Detected Path Traversal attempt in TAR archive: '{member.name}'"
        )

    # 2. Sanitize Symlinks and Hard Links (crucial for icon packs)
    if member.issym() or member.islnk():
        link = member.linkname
        if link.startswith("/"):
            # Target is rooted at archive root: compute relative path from member's parent directory
            target_in_archive = Path(link.lstrip("/"))
            member_dir = Path(member.name).parent
            member.linkname = os.path.relpath(target_in_archive, member_dir)

        # Prevent symlinks escaping target directory
        member_dir_abs = target.parent
        resolved_link = (member_dir_abs / member.linkname).resolve()
        try:
            resolved_link.relative_to(dest)
        except ValueError:
            logger.debug("Skipping external symlink '%s' -> '%s'", member.name, member.linkname)
            return None

    # 3. Strip special permissions (SUID/SGID)
    member.mode &= 0o777

    return member


def _extract_tar(archive_path: Path, target_dir: Path) -> None:
    """Extract a TAR archive with security checks against Path Traversal and support for icon symlinks."""
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir.resolve()

    try:
        with tarfile.open(archive_path, "r:*") as tar_ref:
            deferred_links: list[tarfile.TarInfo] = []

            for member in tar_ref:
                target = (dest / member.name).resolve()
                try:
                    target.relative_to(dest)
                except ValueError:
                    raise ArchiveExtractionError(
                        f"Detected Path Traversal attempt in TAR archive: '{member.name}'"
                    )

                member.mode &= 0o777

                if member.issym() or member.islnk():
                    deferred_links.append(member)
                else:
                    try:
                        tar_ref.extract(
                            member,
                            path=dest,
                            filter="fully_trusted"
                            if hasattr(tarfile, "fully_trusted_filter")
                            else None,
                        )
                    except Exception as err:
                        logger.debug("Non-fatal: could not extract member %s: %s", member.name, err)

            # Second pass for links after all directory structures and target files are unpacked
            for link_member in deferred_links:
                target = (dest / link_member.name).resolve()
                link = link_member.linkname
                if link.startswith("/"):
                    target_in_archive = Path(link.lstrip("/"))
                    member_dir = Path(link_member.name).parent
                    link_member.linkname = os.path.relpath(target_in_archive, member_dir)

                resolved_link = (target.parent / link_member.linkname).resolve()
                try:
                    resolved_link.relative_to(dest)
                except ValueError:
                    logger.debug(
                        "Skipping external symlink '%s' -> '%s'",
                        link_member.name,
                        link_member.linkname,
                    )
                    continue

                try:
                    tar_ref.extract(
                        link_member,
                        path=dest,
                        filter="fully_trusted"
                        if hasattr(tarfile, "fully_trusted_filter")
                        else None,
                    )
                except Exception as err:
                    logger.debug(
                        "Non-fatal: could not extract link %s -> %s: %s",
                        link_member.name,
                        link_member.linkname,
                        err,
                    )
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

    # 1. Check GTK Theme / Libadwaita
    gtk_subdirs = ["gtk-2.0", "gtk-3.0", "gtk-4.0", "libadwaita"]
    has_gtk_dir = any((theme_dir / sub).is_dir() for sub in gtk_subdirs)
    has_gtk_file = (
        (theme_dir / "gtk.css").is_file()
        or (theme_dir / "libadwaita.css").is_file()
        or (theme_dir / "gtk-4.0" / "libadwaita.css").is_file()
        or (theme_dir / "gtk-4.0" / "gtk.css").is_file()
    )
    index_theme = theme_dir / "index.theme"

    is_gtk = has_gtk_dir or has_gtk_file
    if index_theme.is_file() and not is_gtk:
        try:
            content = index_theme.read_text(encoding="utf-8", errors="ignore")
            if (
                "[Desktop Entry]" in content
                or "[GtkTheme]" in content
                or "[X-GNOME-Metatheme]" in content
            ):
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


def _resolve_user_path(raw_path: str | Path | None, fallback: Path) -> Path:
    """Resolve a theme/icon destination directory to an absolute Path anchored at home if relative."""
    if raw_path is None:
        return fallback.resolve()
    p = Path(raw_path).expanduser()
    if not p.is_absolute():
        cleaned = str(p).strip().lstrip("/")
        if cleaned.startswith("home/"):
            p = Path("/" + cleaned)
        else:
            p = Path.home() / p
    return p.resolve()


def _is_dir_writable(path: Path) -> bool:
    """Check if a directory exists and is writable, or can be created as writable."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / f".write_test_{os.getpid()}"
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        return True
    except (OSError, PermissionError):
        return False


def _get_writable_dir(preferred: Path, fallbacks: list[Path]) -> Path:
    """Return preferred path if writable, otherwise the first writable fallback."""
    pref = preferred.resolve()
    if _is_dir_writable(pref):
        return pref
    for fb in fallbacks:
        expanded = fb.expanduser().resolve()
        if expanded != pref and _is_dir_writable(expanded):
            logger.warning(
                "Preferred theme directory '%s' is not writable; falling back to '%s'",
                pref,
                expanded,
            )
            return expanded
    return pref


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
        fallback_themes = (
            USER_THEMES_DIRS[0]
            if USER_THEMES_DIRS
            else (Path.home() / ".local" / "share" / "themes").resolve()
        )
        fallback_icons = (
            USER_ICONS_DIRS[0]
            if USER_ICONS_DIRS
            else (Path.home() / ".local" / "share" / "icons").resolve()
        )

        resolved_themes = (
            _resolve_user_path(user_themes_dir, fallback_themes)
            if user_themes_dir
            else _get_writable_dir(fallback_themes, USER_THEMES_DIRS)
        )
        resolved_icons = (
            _resolve_user_path(user_icons_dir, fallback_icons)
            if user_icons_dir
            else _get_writable_dir(fallback_icons, USER_ICONS_DIRS)
        )
        self.user_themes_dir = resolved_themes
        self.user_icons_dir = resolved_icons

    def ensure_user_directories(self) -> list[Path]:
        """Ensure all standard user theme directories exist on the filesystem.

        Creates ~/.local/share/themes, ~/.themes, ~/.local/share/icons, and ~/.icons
        if they do not already exist.

        Returns:
            List of Path objects that were verified/created.
        """
        dirs_to_ensure: list[Path] = [self.user_themes_dir, self.user_icons_dir]

        for d in USER_THEMES_DIRS:
            expanded = _resolve_user_path(d, d)
            if expanded not in dirs_to_ensure:
                dirs_to_ensure.append(expanded)

        for d in USER_ICONS_DIRS:
            expanded = _resolve_user_path(d, d)
            if expanded not in dirs_to_ensure:
                dirs_to_ensure.append(expanded)

        for directory in dirs_to_ensure:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as err:
                logger.debug("Could not create directory %s: %s", directory, err)

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

    def _safe_copy_or_fallback(
        self,
        source_dir: Path,
        dest_dir: Path,
        t_type: ThemeType,
    ) -> Path:
        """Copy theme directory with read-only filesystem fallback handling."""
        target_base_dir = dest_dir.parent
        try:
            target_base_dir.mkdir(parents=True, exist_ok=True)
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(source_dir, dest_dir, symlinks=True, ignore_dangling_symlinks=True)
            return dest_dir
        except OSError as err:
            is_ro = getattr(err, "errno", None) == 30 or isinstance(err, PermissionError)
            if not is_ro:
                raise

            logger.warning(
                "Destination directory '%s' is read-only (%s); attempting fallback user directory...",
                dest_dir,
                err,
            )
            # Try alternate standard user directory (e.g. ~/.themes <-> ~/.local/share/themes)
            alt_base = self._get_alternate_user_dir(target_base_dir, t_type)
            if alt_base and alt_base != target_base_dir:
                try:
                    alt_base.mkdir(parents=True, exist_ok=True)
                    alt_dest = alt_base / dest_dir.name
                    if alt_dest.exists():
                        shutil.rmtree(alt_dest)
                    shutil.copytree(
                        source_dir, alt_dest, symlinks=True, ignore_dangling_symlinks=True
                    )
                    logger.info(
                        "Successfully installed theme into fallback user directory: %s", alt_dest
                    )
                    return alt_dest
                except OSError as alt_err:
                    logger.warning("Fallback directory '%s' also failed: %s", alt_base, alt_err)

            # Flatpak Host Fallback: If sandbox filesystem is read-only, try flatpak-spawn host bridge
            from .sandbox_bridge import is_in_flatpak_sandbox

            if is_in_flatpak_sandbox() and shutil.which("flatpak-spawn"):
                logger.info(
                    "Attempting Flatpak host spawn extraction fallback for '%s'...", dest_dir
                )
                if self._install_via_host_tar(source_dir, dest_dir):
                    return dest_dir

            raise OSError(
                getattr(err, "errno", 30) or 30,
                f"Theme directory '{dest_dir}' is on a read-only file system or permission was denied. "
                f"Ensure Flatpak filesystem permissions (--filesystem=~/.themes:create and --filesystem=~/.local/share/themes:create) are active.",
                str(dest_dir),
            ) from err

    def _get_alternate_user_dir(self, current_base: Path, t_type: ThemeType) -> Path | None:
        """Find an alternative user directory if the current one is read-only."""
        home = Path.home().resolve()
        if t_type in (ThemeType.GTK, ThemeType.SHELL):
            standard = [
                (home / ".local" / "share" / "themes").resolve(),
                (home / ".themes").resolve(),
            ]
            candidates = list(dict.fromkeys(USER_THEMES_DIRS + standard))
        else:
            standard = [
                (home / ".local" / "share" / "icons").resolve(),
                (home / ".icons").resolve(),
            ]
            candidates = list(dict.fromkeys(USER_ICONS_DIRS + standard))

        curr_res = current_base.resolve()
        for c in candidates:
            c_res = _resolve_user_path(c, c)
            if c_res != curr_res and _is_dir_writable(c_res):
                return c_res
        return None

    @staticmethod
    def _install_via_host_tar(source_dir: Path, dest_dir: Path) -> bool:
        """Install directory via flatpak-spawn host bridge by piping tar stream."""
        try:
            tar_cmd = ["tar", "-cf", "-", "-C", str(source_dir), "."]
            host_cmd = [
                "flatpak-spawn",
                "--host",
                "sh",
                "-c",
                f'mkdir -p "{dest_dir}" && tar -xf - -C "{dest_dir}"',
            ]
            p_tar = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p_host = subprocess.Popen(
                host_cmd,
                stdin=p_tar.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if p_tar.stdout:
                p_tar.stdout.close()
            _, _err_host = p_host.communicate(timeout=20)
            p_tar.wait(timeout=5)
            return p_host.returncode == 0
        except Exception as ex:
            logger.debug("Failed host tar installation fallback: %s", ex)
            return False

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

        legacy_themes_pref = (
            USER_THEMES_DIRS[1]
            if len(USER_THEMES_DIRS) > 1
            else (Path.home() / ".themes").resolve()
        )
        legacy_icons_pref = (
            USER_ICONS_DIRS[1] if len(USER_ICONS_DIRS) > 1 else (Path.home() / ".icons").resolve()
        )

        if isinstance(target_dir, str) and target_dir.lower() == "legacy":
            base_themes_dir = _get_writable_dir(legacy_themes_pref, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(legacy_icons_pref, USER_ICONS_DIRS)
        elif isinstance(target_dir, (str, Path)) and str(target_dir).lower() not in (
            "",
            "xdg",
            "none",
        ):
            custom_path = _resolve_user_path(target_dir, self.user_themes_dir)
            base_themes_dir = _get_writable_dir(custom_path, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(custom_path, USER_ICONS_DIRS)
        else:
            base_themes_dir = _get_writable_dir(self.user_themes_dir, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(self.user_icons_dir, USER_ICONS_DIRS)

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
                dest_dir = self._safe_copy_or_fallback(source_dir, dest_dir, t_type)
                if t_type == ThemeType.GTK:
                    self._ensure_gtk4_libadwaita_symlinks(dest_dir)
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

    @staticmethod
    def _ensure_gtk4_libadwaita_symlinks(dest_dir: Path) -> None:
        """Ensure libadwaita files are symlinked into gtk-4.0 folder if required by the OS.

        If running on GNOME 50+ or GNOME 42+ and Libadwaita stylesheets exist in the theme
        (such as libadwaita.css, libadwaita/, etc.), ensure they are placed as symlinks
        inside <theme>/gtk-4.0/ alongside standard GTK4 stylesheets.
        """
        from .gnome_version import detect_gnome_version, is_gnome_50_plus

        ver = detect_gnome_version()
        requires_libadwaita = is_gnome_50_plus(ver) or (ver is not None and ver[0] >= 42)
        if not requires_libadwaita:
            return

        # Check for any libadwaita files in the theme
        has_libadw_root = (dest_dir / "libadwaita.css").is_file()
        has_libadw_dir_css = (dest_dir / "libadwaita" / "libadwaita.css").is_file()
        has_libadw_dir_gtk = (dest_dir / "libadwaita" / "gtk.css").is_file()
        has_libadw_dark_root = (dest_dir / "libadwaita-dark.css").is_file()
        has_libadw_dir_dark = (dest_dir / "libadwaita" / "libadwaita-dark.css").is_file()
        has_libadw_dir_gtk_dark = (dest_dir / "libadwaita" / "gtk-dark.css").is_file()

        has_any_libadwaita = (
            has_libadw_root
            or has_libadw_dir_css
            or has_libadw_dir_gtk
            or has_libadw_dark_root
            or has_libadw_dir_dark
            or has_libadw_dir_gtk_dark
        )

        gtk4_dir = dest_dir / "gtk-4.0"

        if has_any_libadwaita:
            gtk4_dir.mkdir(parents=True, exist_ok=True)

            # 1. Symlink libadwaita.css into gtk-4.0/ if not already present
            dest_libadw = gtk4_dir / "libadwaita.css"
            if not dest_libadw.exists():
                try:
                    if has_libadw_root:
                        dest_libadw.symlink_to("../libadwaita.css")
                    elif has_libadw_dir_css:
                        dest_libadw.symlink_to("../libadwaita/libadwaita.css")
                    elif has_libadw_dir_gtk:
                        dest_libadw.symlink_to("../libadwaita/gtk.css")
                except OSError as exc:
                    logger.debug("Failed creating libadwaita.css symlink in %s: %s", gtk4_dir, exc)

            # 2. Symlink libadwaita-dark.css into gtk-4.0/ if not already present
            dest_libadw_dark = gtk4_dir / "libadwaita-dark.css"
            if not dest_libadw_dark.exists():
                try:
                    if has_libadw_dark_root:
                        dest_libadw_dark.symlink_to("../libadwaita-dark.css")
                    elif has_libadw_dir_dark:
                        dest_libadw_dark.symlink_to("../libadwaita/libadwaita-dark.css")
                    elif has_libadw_dir_gtk_dark:
                        dest_libadw_dark.symlink_to("../libadwaita/gtk-dark.css")
                except OSError as exc:
                    logger.debug(
                        "Failed creating libadwaita-dark.css symlink in %s: %s", gtk4_dir, exc
                    )

            # 3. If gtk-4.0/gtk.css is missing, point it to libadwaita.css
            dest_gtk = gtk4_dir / "gtk.css"
            if not dest_gtk.exists() and dest_libadw.exists():
                try:
                    dest_gtk.symlink_to("libadwaita.css")
                except OSError:
                    pass

        # 4. If GNOME 50+ and theme has gtk-4.0/gtk.css but no libadwaita.css, create symlink
        if is_gnome_50_plus(ver) and gtk4_dir.is_dir():
            dest_libadw = gtk4_dir / "libadwaita.css"
            dest_gtk = gtk4_dir / "gtk.css"
            if dest_gtk.exists() and not dest_libadw.exists():
                try:
                    dest_libadw.symlink_to("gtk.css")
                except OSError:
                    pass
            dest_libadw_dark = gtk4_dir / "libadwaita-dark.css"
            dest_gtk_dark = gtk4_dir / "gtk-dark.css"
            if dest_gtk_dark.exists() and not dest_libadw_dark.exists():
                try:
                    dest_libadw_dark.symlink_to("gtk-dark.css")
                except OSError:
                    pass

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
        legacy_themes_pref = (
            USER_THEMES_DIRS[1]
            if len(USER_THEMES_DIRS) > 1
            else (Path.home() / ".themes").resolve()
        )
        legacy_icons_pref = (
            USER_ICONS_DIRS[1] if len(USER_ICONS_DIRS) > 1 else (Path.home() / ".icons").resolve()
        )

        if isinstance(target_dir, str) and target_dir.lower() == "legacy":
            base_themes_dir = _get_writable_dir(legacy_themes_pref, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(legacy_icons_pref, USER_ICONS_DIRS)
        elif isinstance(target_dir, (str, Path)) and str(target_dir).lower() not in (
            "",
            "xdg",
            "none",
        ):
            custom_path = _resolve_user_path(target_dir, self.user_themes_dir)
            base_themes_dir = _get_writable_dir(custom_path, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(custom_path, USER_ICONS_DIRS)
        else:
            base_themes_dir = _get_writable_dir(self.user_themes_dir, USER_THEMES_DIRS)
            base_icons_dir = _get_writable_dir(self.user_icons_dir, USER_ICONS_DIRS)

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
                    dest_dir = self._safe_copy_or_fallback(source_dir, dest_dir, t_type)
                    if t_type == ThemeType.GTK:
                        self._ensure_gtk4_libadwaita_symlinks(dest_dir)
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

        # Also clean up any recorded entry in theme_forks.json if applicable
        try:
            from .constants import THEME_FORKS_FILE

            state_file = THEME_FORKS_FILE.expanduser()
            if state_file.is_file():
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    forks = data.get("forks", [])
                    filtered_forks = [
                        f
                        for f in forks
                        if isinstance(f, dict)
                        and f.get("fork_name") != theme_name
                        and str(found_user_path) not in str(f.get("fork_path", ""))
                    ]
                    if len(filtered_forks) != len(forks):
                        state_file.write_text(
                            json.dumps({"forks": filtered_forks}, indent=2, sort_keys=True),
                            encoding="utf-8",
                        )
        except Exception as err:
            logger.debug("Could not clean up fork state on uninstall: %s", err)

        return True
