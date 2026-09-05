# SPDX-License-Identifier: GPL-3.0-or-later

"""Automatic theme propagation module for sandboxed GNOME applications.

On modern Linux distributions (particularly Ubuntu), many applications
(such as Firefox, Chromium, App Center) run inside sandboxed environments
managed by Flatpak or Snap.
"""

import configparser
import logging
import os
import shutil
import subprocess
from pathlib import Path

from .errors import ThemeValidationError
from .models import PropagationResult, SandboxStatus

logger = logging.getLogger("gnome_theme_manager.core")


class _CaseSensitiveConfigParser(configparser.ConfigParser):
    """ConfigParser that preserves case sensitivity of option keys."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


KNOWN_SNAP_COMMON_THEMES: frozenset[str] = frozenset(
    {
        "adwaita",
        "adwaita-dark",
        "ambiance",
        "communitheme",
        "highcontrast",
        "highcontrastinverse",
        "mate",
        "mint-y",
        "mint-y-dark",
        "radiance",
        "yaru",
        "yaru-dark",
        "yaru-light",
        "yaru-bark",
        "yaru-bark-dark",
        "yaru-magenta",
        "yaru-magenta-dark",
        "yaru-olive",
        "yaru-olive-dark",
        "yaru-prussiangreen",
        "yaru-prussiangreen-dark",
        "yaru-purple",
        "yaru-purple-dark",
        "yaru-red",
        "yaru-red-dark",
        "yaru-sage",
        "yaru-sage-dark",
        "yaru-viridian",
        "yaru-viridian-dark",
    }
)


def validate_theme_name(name: str) -> str:
    """Validate theme name according to security guidelines."""
    if not name:
        raise ThemeValidationError("Theme name cannot be empty.")
    if "/" in name or "\\" in name:
        raise ThemeValidationError("Theme name cannot contain slashes or backslashes.")
    if "\n" in name or "\r" in name:
        raise ThemeValidationError("Theme name cannot contain newline characters.")
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ThemeValidationError("Theme name cannot contain control characters.")
    if name.startswith("-"):
        raise ThemeValidationError("Theme name cannot start with a hyphen.")
    return name


def is_in_flatpak_sandbox() -> bool:
    """Check if the current process is running inside a Flatpak sandbox."""
    return Path("/.flatpak-info").exists() or bool(os.environ.get("FLATPAK_ID"))


class SandboxBridge:
    """Propagates GNOME themes to sandboxed applications managed by Snap and Flatpak."""

    def __init__(self) -> None:
        """Initialize sandbox bridge."""
        logger.debug("Initializing SandboxBridge for Snap and Flatpak")

    def is_snap_available(self) -> bool:
        """Check if `snap` runtime or executable is available on system."""
        if shutil.which("snap") is not None:
            return True
        if is_in_flatpak_sandbox():
            return (
                (Path.home() / "snap").exists()
                or Path("/var/lib/snapd").exists()
                or Path("/snap").exists()
            )
        return False

    def is_flatpak_available(self) -> bool:
        """Check if `flatpak` runtime or executable is available on system."""
        if shutil.which("flatpak") is not None:
            return True
        return is_in_flatpak_sandbox()

    def get_sandbox_status(self) -> SandboxStatus:
        """Retrieve diagnostic status of detected sandbox runtimes."""
        snap_avail = self.is_snap_available()
        flatpak_avail = self.is_flatpak_available()
        snap_gtk_common_installed = False
        flatpak_override_active = False

        if snap_avail:
            if shutil.which("snap") is not None:
                try:
                    res = subprocess.run(
                        ["snap", "list", "gtk-common-themes"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    snap_gtk_common_installed = res.returncode == 0
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    snap_gtk_common_installed = False
            elif is_in_flatpak_sandbox():
                snap_gtk_common_installed = (
                    Path("/snap/gtk-common-themes").exists()
                    or (Path.home() / "snap/gtk-common-themes").exists()
                    or bool(
                        list(Path("/var/lib/snapd/snaps").glob("gtk-common-themes*"))
                        if Path("/var/lib/snapd/snaps").is_dir()
                        else []
                    )
                )

        if flatpak_avail:
            if shutil.which("flatpak") is not None:
                try:
                    res = subprocess.run(
                        ["flatpak", "override", "--user", "--show"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    out_lower = res.stdout.lower()
                    flatpak_override_active = res.returncode == 0 and (
                        "themes" in out_lower or "icons" in out_lower
                    )
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    flatpak_override_active = False
            elif is_in_flatpak_sandbox():
                override_file = Path.home() / ".local/share/flatpak/overrides/global"
                if override_file.is_file():
                    try:
                        content = override_file.read_text(encoding="utf-8", errors="ignore").lower()
                        flatpak_override_active = "themes" in content or "icons" in content
                    except OSError:
                        flatpak_override_active = False

        return SandboxStatus(
            snap_available=snap_avail,
            flatpak_available=flatpak_avail,
            snap_gtk_common_themes_installed=snap_gtk_common_installed,
            flatpak_filesystem_override_active=flatpak_override_active,
        )

    def build_flatpak_command(
        self,
        app_id: str | None,
        gtk_theme: str | None,
        icon_theme: str | None,
    ) -> list[str]:
        """Construct flatpak command argument list."""
        cmd = ["flatpak", "override", "--user"]
        if gtk_theme:
            cmd.append(f"--env=GTK_THEME={gtk_theme}")
        if icon_theme:
            cmd.append(f"--env=ICON_THEME={icon_theme}")
        if app_id:
            cmd.append(app_id)
        return cmd

    def build_snap_command(
        self,
        app_name: str,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> list[str]:
        """Construct snap command argument list."""
        return ["snap", "list", app_name]

    def _write_flatpak_global_override(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> None:
        """Write or update ~/.local/share/flatpak/overrides/global directly."""
        override_dir = Path.home() / ".local/share" / "flatpak" / "overrides"
        override_dir.mkdir(parents=True, exist_ok=True)
        override_file = override_dir / "global"

        parser = _CaseSensitiveConfigParser(interpolation=None)
        if override_file.is_file():
            try:
                parser.read(override_file, encoding="utf-8")
            except Exception:
                pass

        if not parser.has_section("Context"):
            parser.add_section("Context")

        existing_fs = parser.get("Context", "filesystems", fallback="")
        fs_list = [f.strip() for f in existing_fs.split(";") if f.strip()]
        for req in [
            "~/.local/share/themes:ro",
            "~/.themes:ro",
            "~/.local/share/icons:ro",
            "~/.icons:ro",
        ]:
            if req not in fs_list:
                fs_list.append(req)

        parser.set("Context", "filesystems", ";".join(fs_list) + ";")

        if gtk_theme or icon_theme:
            if not parser.has_section("Environment"):
                parser.add_section("Environment")
            if gtk_theme:
                parser.set("Environment", "GTK_THEME", gtk_theme)
            if icon_theme:
                parser.set("Environment", "ICON_THEME", icon_theme)

        with open(override_file, "w", encoding="utf-8") as f:
            parser.write(f)

    def propagate_to_flatpak(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Configure filesystem permissions and environment variables for Flatpak.

        Always returns a PropagationResult (capturing warnings on command failure/timeout
        without raising uncaught exceptions).
        """
        if not self.is_flatpak_available():
            logger.debug("Flatpak is not available on this system; propagation skipped.")
            return PropagationResult(
                flatpak_success=False,
                flatpak_messages=["Flatpak is not installed on this system."],
            )

        if gtk_theme:
            validate_theme_name(gtk_theme)
        if icon_theme:
            validate_theme_name(icon_theme)

        if shutil.which("flatpak") is not None:
            base_commands: list[list[str]] = [
                ["flatpak", "override", "--user", "--filesystem=~/.local/share/themes:ro"],
                ["flatpak", "override", "--user", "--filesystem=~/.themes:ro"],
                ["flatpak", "override", "--user", "--filesystem=~/.local/share/icons:ro"],
                ["flatpak", "override", "--user", "--filesystem=~/.icons:ro"],
            ]

            if gtk_theme:
                base_commands.append(self.build_flatpak_command(None, gtk_theme, None))
            if icon_theme:
                base_commands.append(self.build_flatpak_command(None, None, icon_theme))

            messages: list[str] = []
            warnings: list[str] = []
            has_error = False

            for cmd in base_commands:
                try:
                    subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=True,
                    )
                except subprocess.TimeoutExpired:
                    warn_msg = "Timeout while executing Flatpak command."
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    has_error = True
                    break
                except subprocess.CalledProcessError as err:
                    err_msg = err.stderr.strip() if err.stderr else str(err)
                    warn_msg = f"Error during Flatpak override: {err_msg}"
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    has_error = True
                    break
                except (FileNotFoundError, OSError):
                    warn_msg = "Unable to execute Flatpak command."
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    has_error = True
                    break

            if not has_error:
                messages.append(
                    "Flatpak filesystem overrides and environment variables configured successfully."
                )

            return PropagationResult(
                flatpak_success=not has_error,
                flatpak_messages=messages,
                warnings=warnings,
            )

        # Container fallback (when running inside Flatpak sandbox without flatpak CLI)
        try:
            self._write_flatpak_global_override(gtk_theme=gtk_theme, icon_theme=icon_theme)
            return PropagationResult(
                flatpak_success=True,
                flatpak_messages=[
                    "Flatpak filesystem overrides and environment variables configured successfully."
                ],
                warnings=[],
            )
        except Exception as err:
            logger.warning("Error writing Flatpak override file: %s", err)
            return PropagationResult(
                flatpak_success=False,
                flatpak_messages=[],
                warnings=[f"Error during Flatpak override: {err}"],
            )

    def propagate_to_snap(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Verify theme compatibility with Snap infrastructure.

        Always returns a PropagationResult (capturing warnings without raising exceptions).
        """
        if not self.is_snap_available():
            logger.debug("Snap is not available on this system; check skipped.")
            return PropagationResult(
                snap_success=False,
                snap_messages=["Snap is not installed on this system."],
            )

        if gtk_theme:
            validate_theme_name(gtk_theme)
        if icon_theme:
            validate_theme_name(icon_theme)

        messages: list[str] = []
        warnings: list[str] = []

        gtk_common_installed = False
        cmd = self.build_snap_command("gtk-common-themes")
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            gtk_common_installed = res.returncode == 0
        except subprocess.TimeoutExpired:
            warn_msg = "Timeout querying 'gtk-common-themes' snap."
            logger.warning(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Error querying Snap."],
                warnings=warnings,
            )
        except Exception:
            warn_msg = "Error querying Snap."
            logger.warning(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Error querying Snap."],
                warnings=warnings,
            )

        if not gtk_common_installed:
            warn_msg = (
                "Snap 'gtk-common-themes' is not installed. Snap applications "
                "might not display the selected visual theme correctly."
            )
            logger.info(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Snap 'gtk-common-themes' is not present on this system."],
                warnings=warnings,
            )

        if gtk_theme:
            from .theme_snap_manager.detector import ThemeDetector

            detector = ThemeDetector()
            is_compat, _ = detector.check_theme_compatibility(gtk_theme)
            theme_norm = gtk_theme.strip().lower()

            if is_compat or theme_norm in KNOWN_SNAP_COMMON_THEMES:
                messages.append(
                    f"Theme '{gtk_theme}' is natively supported by gtk-common-themes in Snap."
                )
            else:
                warn_msg = (
                    f"Custom theme '{gtk_theme}' is not included in the standard "
                    f"'gtk-common-themes' snap package. Use Theme Snap Manager to compile a local Content Snap."
                )
                logger.info(warn_msg)
                warnings.append(warn_msg)
                messages.append(f"Custom theme '{gtk_theme}' (local Content Snap available).")
        else:
            messages.append("Snap gtk-common-themes verification completed successfully.")

        return PropagationResult(
            snap_success=True,
            snap_messages=messages,
            warnings=warnings,
        )

    def propagate_all(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Propagate themes to both Flatpak and Snap environments."""
        logger.info(
            "Starting theme propagation to Snap and Flatpak (gtk=%s, icon=%s)",
            gtk_theme,
            icon_theme,
        )

        flatpak_res = self.propagate_to_flatpak(gtk_theme=gtk_theme, icon_theme=icon_theme)
        snap_res = self.propagate_to_snap(gtk_theme=gtk_theme, icon_theme=icon_theme)

        consolidated_warnings = flatpak_res.warnings + snap_res.warnings

        return PropagationResult(
            flatpak_success=flatpak_res.flatpak_success,
            snap_success=snap_res.snap_success,
            flatpak_messages=flatpak_res.flatpak_messages,
            snap_messages=snap_res.snap_messages,
            warnings=consolidated_warnings,
        )
