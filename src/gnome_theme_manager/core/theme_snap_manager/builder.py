# SPDX-License-Identifier: GPL-3.0-or-later

"""Dynamic Content Snap builder for custom desktop themes."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .exceptions import BuildError

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager.builder")


class ContentSnapBuilder:
    """Generates and compiles local Content Snaps dynamically for custom themes."""

    def __init__(
        self,
        theme_name: str,
        theme_path: Path,
        icon_name: str | None = None,
        icon_path: Path | None = None,
    ) -> None:
        """Initialize builder with theme name and source directory.

        Args:
            theme_name: Name of the theme to package.
            theme_path: Source filesystem path of the theme.
            icon_name: Optional icon/cursor theme name.
            icon_path: Optional filesystem path of the icon/cursor theme (e.g. from ~/.icons).
        """
        self.theme_name = theme_name.strip()
        self.theme_path = Path(theme_path).expanduser().resolve()
        self.icon_name = icon_name.strip() if icon_name else None
        self.icon_path = Path(icon_path).expanduser().resolve() if icon_path else None
        self.snap_name = self._sanitize_snap_name(self.theme_name)
        self.temp_dir: Path | None = None

    @staticmethod
    def _sanitize_snap_name(name: str) -> str:
        """Sanitize theme name into a valid snap name identifier."""
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
        if not clean:
            clean = "theme"
        return f"custom-theme-{clean}"

    def _create_directory_structure(self, base_dir: Path) -> dict[str, Path]:
        """Create standard content snap directory hierarchy."""
        snap_meta_dir = base_dir / "meta"
        themes_dir = base_dir / "share" / "themes" / self.theme_name
        effective_icon_name = self.icon_name or self.theme_name
        icons_dir = base_dir / "share" / "icons" / effective_icon_name
        sounds_dir = base_dir / "share" / "sounds" / self.theme_name

        snap_meta_dir.mkdir(parents=True, exist_ok=True)
        themes_dir.parent.mkdir(parents=True, exist_ok=True)
        icons_dir.parent.mkdir(parents=True, exist_ok=True)
        sounds_dir.parent.mkdir(parents=True, exist_ok=True)
        return {
            "meta": snap_meta_dir,
            "themes": themes_dir,
            "icons": icons_dir,
            "sounds": sounds_dir,
        }

    def _copy_theme_files(self, dirs: dict[str, Path]) -> list[str]:
        """Copy existing theme files into corresponding content directories.

        Returns:
            List of populated slots.
        """
        populated_slots: list[str] = []

        # GTK theme files
        has_gtk = (
            (self.theme_path / "gtk-3.0").is_dir()
            or (self.theme_path / "gtk-4.0").is_dir()
            or (self.theme_path / "index.theme").is_file()
            or (self.theme_path / "gtk.css").is_file()
        )
        if has_gtk:
            dirs["themes"].mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.theme_path,
                dirs["themes"],
                symlinks=False,
                ignore_dangling_symlinks=True,
                dirs_exist_ok=True,
            )
            populated_slots.append("gtk-3-themes")

        # Explicit external icon / cursor package (from ~/.icons or /usr/share/icons)
        if self.icon_path is not None and self.icon_path.is_dir():
            dirs["icons"].mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.icon_path,
                dirs["icons"],
                symlinks=False,
                ignore_dangling_symlinks=True,
                dirs_exist_ok=True,
            )
            if "icon-themes" not in populated_slots:
                populated_slots.append("icon-themes")
        else:
            # Icons (if subfolder or standalone icon directory)
            has_icons = (
                (self.theme_path / "icons").is_dir()
                or (self.theme_path / "scalable").is_dir()
                or (self.theme_path / "cursors").is_dir()
            )
            if (self.theme_path / "icons").is_dir():
                dirs["icons"].mkdir(parents=True, exist_ok=True)
                shutil.copytree(
                    self.theme_path / "icons",
                    dirs["icons"],
                    symlinks=False,
                    ignore_dangling_symlinks=True,
                    dirs_exist_ok=True,
                )
                populated_slots.append("icon-themes")
            elif has_icons and not has_gtk:
                dirs["icons"].mkdir(parents=True, exist_ok=True)
                shutil.copytree(
                    self.theme_path,
                    dirs["icons"],
                    symlinks=False,
                    ignore_dangling_symlinks=True,
                    dirs_exist_ok=True,
                )
                populated_slots.append("icon-themes")

        # Sounds
        if (self.theme_path / "sounds").is_dir():
            dirs["sounds"].mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.theme_path / "sounds",
                dirs["sounds"],
                symlinks=False,
                ignore_dangling_symlinks=True,
                dirs_exist_ok=True,
            )
            populated_slots.append("sound-themes")

        # Default to gtk-3-themes if no specific subfolders were differentiated
        if not populated_slots and self.theme_path.is_dir():
            dirs["themes"].mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.theme_path,
                dirs["themes"],
                symlinks=False,
                ignore_dangling_symlinks=True,
                dirs_exist_ok=True,
            )
            populated_slots.append("gtk-3-themes")

        return populated_slots

    def _generate_snapcraft_yaml(self, meta_dir: Path, slots: list[str]) -> Path:
        """Generate a valid meta/snap.yaml file for instant packaging."""
        yaml_lines = [
            f"name: {self.snap_name}",
            'version: "1.0"',
            'summary: "Custom theme content snap"',
            'description: "Dynamically generated Content Snap for desktop theme compatibility"',
            "base: core22",
            "type: app",
            "grade: stable",
            "confinement: strict",
            "",
            "slots:",
        ]

        slot_mapping = {
            "gtk-3-themes": "share/themes",
            "icon-themes": "share/icons",
            "sound-themes": "share/sounds",
        }

        active_slots = [s for s in slots if s in slot_mapping] or ["gtk-3-themes"]
        for slot in active_slots:
            yaml_lines.extend(
                [
                    f"  {slot}:",
                    "    interface: content",
                    f"    content: {slot}",
                    "    read:",
                    f"      - {slot_mapping[slot]}",
                ]
            )

        yaml_path = meta_dir / "snap.yaml"
        yaml_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
        logger.debug("Generated snap.yaml at %s", yaml_path)
        return yaml_path

    def _compile_snap(self, build_dir: Path) -> Path:
        """Instantly compile Content Snap using `snap pack` or `mksquashfs` with fallback."""
        target_snap = build_dir.parent / f"{self.snap_name}_1.0_all.snap"

        # Snap requires root directory of the snap to be world-readable and executable (0o755)
        build_dir.chmod(0o755)
        for p in build_dir.rglob("*"):
            if p.is_dir():
                p.chmod(0o755)
            elif p.is_file():
                p.chmod(0o644)

        errors: list[str] = []

        # 1. Preferred fast method: snap pack (takes ~0.3s)
        snap_bin = shutil.which("snap")
        if snap_bin:
            cmd = [snap_bin, "pack", str(build_dir), str(build_dir.parent)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                snaps = list(build_dir.parent.glob(f"{self.snap_name}*.snap"))
                if snaps:
                    logger.info("Snap built instantly with 'snap pack': %s", snaps[0])
                    return snaps[0]
            else:
                errors.append(f"snap pack failed: {res.stderr.strip() or res.stdout.strip()}")

        # 2. Direct squashfs packaging method with mksquashfs
        mksquashfs_bin = shutil.which("mksquashfs")
        if mksquashfs_bin:
            cmd = [
                mksquashfs_bin,
                str(build_dir),
                str(target_snap),
                "-noappend",
                "-comp",
                "xz",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and target_snap.is_file():
                logger.info("Snap built instantly with 'mksquashfs': %s", target_snap)
                return target_snap
            else:
                errors.append(f"mksquashfs failed: {res.stderr.strip() or res.stdout.strip()}")

        detail = "; ".join(errors) if errors else "No packaging tool succeeded."
        raise BuildError(f"Snap packaging error: {detail}")

    def build(self) -> tuple[Path, list[str]]:
        """Create directory structure, generate metadata, and compile Content Snap.

        Returns:
            Tuple of (Path to the compiled .snap package, list of populated slots).
        """
        if not self.theme_path.is_dir():
            raise BuildError(f"Source theme directory not found: {self.theme_path}")

        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"gtm-snap-{self.snap_name}-"))
        try:
            dirs = self._create_directory_structure(self.temp_dir)
            slots = self._copy_theme_files(dirs)
            self._generate_snapcraft_yaml(dirs["meta"], slots)
            snap_path = self._compile_snap(self.temp_dir)
            logger.info("Content Snap built successfully: %s (slots: %s)", snap_path, slots)
            return snap_path, slots
        except Exception:
            self.cleanup()
            raise

    def cleanup(self) -> None:
        """Safely remove build artifacts and temporary directory."""
        if self.temp_dir is not None and self.temp_dir.is_dir():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug("Cleaned up build temp dir: %s", self.temp_dir)
            except Exception as err:
                logger.warning("Failed to clean up temp dir '%s': %s", self.temp_dir, err)
            finally:
                self.temp_dir = None
