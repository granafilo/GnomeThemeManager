# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal emulator detection module (Prompt 2.1).

Provides robust identification of the currently active terminal session or
the system default terminal emulator using a prioritized cascade:
1. Environment variables ($PTYXIS_VERSION, $TERM_PROGRAM, $TERMINAL, etc.)
2. Process tree inspection (/proc/$PPID)
3. FreeDesktop xdg-terminal-exec --print
4. GNOME desktop default terminal GSettings
5. System alternatives (/etc/alternatives/x-terminal-emulator)
6. Prioritized binary search (which / /run/host)
7. Desktop entry discovery (Categories=TerminalEmulator)
8. Graceful fallback for headless or unknown systems
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try importing Gio safely
try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    _GIO_AVAILABLE = True
except (ImportError, ValueError, AttributeError):  # pragma: no cover
    Gio = None
    _GIO_AVAILABLE = False


@dataclass(frozen=True)
class TerminalInfo:
    """Represents a detected system terminal emulator."""

    terminal_id: str
    terminal_name: str
    binary: str
    desktop_file: str
    detection_method: str
    is_installed: bool
    is_default: bool
    supports_gsettings: bool = False
    schema_id: str | None = None
    schema_accessible: bool = False

    @property
    def display_name(self) -> str:
        """Backward-compatible alias for terminal_name."""
        return self.terminal_name

    @property
    def terminal_type(self) -> str:
        """Backward-compatible alias for terminal_id."""
        return self.terminal_id

    @property
    def binary_path(self) -> Path | None:
        """Backward-compatible alias for binary path."""
        return _find_binary(self.binary) if self.binary else None

    def __bool__(self) -> bool:
        """Truth value: True if terminal is known and installed."""
        return self.terminal_id != "unknown" and self.is_installed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching the Prompt 2.1 specification."""
        return {
            "terminal_id": self.terminal_id,
            "terminal_name": self.terminal_name,
            "binary": self.binary,
            "desktop_file": self.desktop_file,
            "detection_method": self.detection_method,
            "is_installed": self.is_installed,
            "is_default": self.is_default,
            "supports_gsettings": self.supports_gsettings,
            "schema_id": self.schema_id,
            "schema_accessible": self.schema_accessible,
        }

    def __getitem__(self, item: str) -> Any:
        """Allow dict-like indexing access: info['terminal_id']."""
        return getattr(self, item)


# Catalog of supported Linux terminal emulators
KNOWN_TERMINALS: dict[str, dict[str, Any]] = {
    "ptyxis": {
        "terminal_id": "ptyxis",
        "terminal_name": "Ptyxis",
        "binary": "ptyxis",
        "desktop_file": "org.gnome.Ptyxis.desktop",
        "env_vars": ("PTYXIS_VERSION",),
        "schema_id": "org.gnome.Ptyxis",
        "supports_gsettings": True,
        "aliases": ("org.gnome.Ptyxis",),
    },
    "gnome-terminal": {
        "terminal_id": "gnome-terminal",
        "terminal_name": "GNOME Terminal",
        "binary": "gnome-terminal",
        "desktop_file": "org.gnome.Terminal.desktop",
        "env_vars": ("GNOME_TERMINAL_SCREEN", "GNOME_TERMINAL_SERVICE"),
        "schema_id": "org.gnome.Terminal.Legacy.Profile",
        "supports_gsettings": True,
        "aliases": ("gnome-terminal-server", "org.gnome.Terminal"),
    },
    "kgx": {
        "terminal_id": "kgx",
        "terminal_name": "GNOME Console",
        "binary": "kgx",
        "desktop_file": "org.gnome.Console.desktop",
        "env_vars": ("KGX_PID",),
        "schema_id": "org.gnome.Console",
        "supports_gsettings": True,
        "aliases": ("gnome-console", "org.gnome.Console"),
    },
    "konsole": {
        "terminal_id": "konsole",
        "terminal_name": "Konsole",
        "binary": "konsole",
        "desktop_file": "org.kde.konsole.desktop",
        "env_vars": ("KONSOLE_VERSION", "KONSOLE_DBUS_SERVICE"),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": ("org.kde.konsole",),
    },
    "xfce4-terminal": {
        "terminal_id": "xfce4-terminal",
        "terminal_name": "XFCE Terminal",
        "binary": "xfce4-terminal",
        "desktop_file": "xfce4-terminal.desktop",
        "env_vars": (),
        "schema_id": "org.xfce.terminal",
        "supports_gsettings": True,
        "aliases": (),
    },
    "mate-terminal": {
        "terminal_id": "mate-terminal",
        "terminal_name": "MATE Terminal",
        "binary": "mate-terminal",
        "desktop_file": "mate-terminal.desktop",
        "env_vars": ("MATE_TERMINAL_SCREEN",),
        "schema_id": "org.mate.terminal",
        "supports_gsettings": True,
        "aliases": (),
    },
    "tilix": {
        "terminal_id": "tilix",
        "terminal_name": "Tilix",
        "binary": "tilix",
        "desktop_file": "com.gexperts.Tilix.desktop",
        "env_vars": ("TILIX_ID",),
        "schema_id": "com.gexperts.Tilix",
        "supports_gsettings": True,
        "aliases": ("com.gexperts.Tilix",),
    },
    "terminator": {
        "terminal_id": "terminator",
        "terminal_name": "Terminator",
        "binary": "terminator",
        "desktop_file": "terminator.desktop",
        "env_vars": ("TERMINATOR_UUID",),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": (),
    },
    "alacritty": {
        "terminal_id": "alacritty",
        "terminal_name": "Alacritty",
        "binary": "alacritty",
        "desktop_file": "Alacritty.desktop",
        "env_vars": ("ALACRITTY_WINDOW_ID", "ALACRITTY_LOG"),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": ("Alacritty",),
    },
    "kitty": {
        "terminal_id": "kitty",
        "terminal_name": "Kitty",
        "binary": "kitty",
        "desktop_file": "kitty.desktop",
        "env_vars": ("KITTY_PID", "KITTY_WINDOW_ID"),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": (),
    },
    "warp": {
        "terminal_id": "warp",
        "terminal_name": "Warp",
        "binary": "warp-terminal",
        "desktop_file": "dev.warp.Warp.desktop",
        "env_vars": (),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": ("warp-terminal", "dev.warp.Warp"),
    },
    "wezterm": {
        "terminal_id": "wezterm",
        "terminal_name": "WezTerm",
        "binary": "wezterm",
        "desktop_file": "org.wezfurlong.wezterm.desktop",
        "env_vars": ("WEZTERM_PANE", "WEZTERM_EXECUTABLE"),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": ("wezterm-gui",),
    },
    "xterm": {
        "terminal_id": "xterm",
        "terminal_name": "xterm",
        "binary": "xterm",
        "desktop_file": "xterm.desktop",
        "env_vars": ("XTERM_VERSION",),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": (),
    },
    "urxvt": {
        "terminal_id": "urxvt",
        "terminal_name": "rxvt-unicode",
        "binary": "urxvt",
        "desktop_file": "urxvt.desktop",
        "env_vars": (),
        "schema_id": None,
        "supports_gsettings": False,
        "aliases": ("rxvt",),
    },
}

# Preferred scan order when probing installed binaries
TERMINAL_PRIORITY_ORDER: tuple[str, ...] = (
    "ptyxis",
    "gnome-terminal",
    "kgx",
    "tilix",
    "terminator",
    "konsole",
    "xfce4-terminal",
    "mate-terminal",
    "alacritty",
    "kitty",
    "wezterm",
    "warp",
    "xterm",
    "urxvt",
)


def _schema_exists(schema_name: str | None) -> bool:
    """Check if a GSettings schema is installed and accessible."""
    if not schema_name:
        return False

    if _GIO_AVAILABLE and Gio is not None:
        try:
            source = Gio.SettingsSchemaSource.get_default()
            if source is not None and source.lookup(schema_name, True) is not None:
                return True
        except Exception:
            pass

        for host_schema_dir in (
            Path("/run/host/usr/share/glib-2.0/schemas"),
            Path("/run/host/usr/local/share/glib-2.0/schemas"),
            Path("/run/host/share/glib-2.0/schemas"),
        ):
            if (host_schema_dir / "gschemas.compiled").is_file():
                try:
                    src = Gio.SettingsSchemaSource.new_from_directory(
                        str(host_schema_dir),
                        Gio.SettingsSchemaSource.get_default(),
                        False,
                    )
                    if src.lookup(schema_name, True) is not None:
                        return True
                except Exception:
                    pass

    try:
        res = subprocess.run(
            ["gsettings", "list-keys", schema_name],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    return False


def _find_binary(name: str) -> Path | None:
    """Find a binary in PATH or container host directories."""
    bin_path = shutil.which(name)
    if bin_path:
        return Path(bin_path)

    for prefix in (
        Path("/run/host/usr/bin"),
        Path("/run/host/bin"),
        Path("/run/host/usr/local/bin"),
        Path("/var/lib/flatpak/exports/bin"),
        Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin",
    ):
        cand = prefix / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand

    return None


def is_terminal_installed(binary: str, desktop_file: str = "") -> bool:
    """Check if a terminal is installed by binary or desktop file existence."""
    if binary and _find_binary(binary) is not None:
        return True

    desktop_candidates: list[str] = []
    if desktop_file:
        desktop_candidates.append(desktop_file)
    if binary == "ptyxis" or "ptyxis" in desktop_file.lower():
        for ptyxis_id in ("app.devsuite.Ptyxis.desktop", "org.gnome.Ptyxis.desktop"):
            if ptyxis_id not in desktop_candidates:
                desktop_candidates.append(ptyxis_id)
    if (
        binary == "wezterm" or "wezterm" in desktop_file.lower()
    ) and "org.wezfurlong.wezterm.desktop" not in desktop_candidates:
        desktop_candidates.append("org.wezfurlong.wezterm.desktop")

    app_dirs = (
        Path("/usr/share/applications"),
        Path("/run/host/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path.home() / ".local" / "share" / "applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/run/host/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
    )

    for cand in desktop_candidates:
        for app_dir in app_dirs:
            if (app_dir / cand).is_file():
                return True

    return False


def _build_terminal_info(
    terminal_id: str,
    detection_method: str,
    is_default: bool = False,
    override_installed: bool | None = None,
) -> TerminalInfo:
    """Build a complete TerminalInfo object for a known terminal ID."""
    entry = KNOWN_TERMINALS.get(terminal_id)
    if not entry:
        return TerminalInfo(
            terminal_id="unknown",
            terminal_name="Unknown Terminal",
            binary="",
            desktop_file="",
            detection_method=detection_method,
            is_installed=False,
            is_default=False,
            supports_gsettings=False,
            schema_id=None,
            schema_accessible=False,
        )

    binary = str(entry["binary"])
    desktop_file = str(entry["desktop_file"])
    is_installed = (
        override_installed
        if override_installed is not None
        else is_terminal_installed(binary, desktop_file)
    )

    schema_id = entry.get("schema_id")
    supports_gsettings = bool(entry.get("supports_gsettings", False))
    schema_accessible = _schema_exists(schema_id) if (supports_gsettings and schema_id) else False

    return TerminalInfo(
        terminal_id=str(entry["terminal_id"]),
        terminal_name=str(entry["terminal_name"]),
        binary=binary,
        desktop_file=desktop_file,
        detection_method=detection_method,
        is_installed=is_installed,
        is_default=is_default,
        supports_gsettings=supports_gsettings,
        schema_id=schema_id,
        schema_accessible=schema_accessible,
    )


def _match_terminal_token(token: str) -> str | None:
    """Match a binary, command line, or desktop filename to a known terminal_id."""
    clean = token.lower().strip()
    # Remove file path and .desktop extension
    base = Path(clean).stem.lower()

    for term_id, spec in KNOWN_TERMINALS.items():
        if base == term_id or clean == term_id:
            return term_id
        if base == spec["binary"].lower() or clean == spec["binary"].lower():
            return term_id
        desktop_stem = Path(spec["desktop_file"]).stem.lower()
        if base == desktop_stem:
            return term_id
        for alias in spec.get("aliases", ()):
            if base == alias.lower() or clean == alias.lower():
                return term_id

    return None


def _detect_from_environment() -> TerminalInfo | None:
    """Check environment variables for an active terminal session."""
    # 1. Check specific terminal indicator env vars
    for term_id in (
        "ptyxis",
        "kitty",
        "alacritty",
        "tilix",
        "kgx",
        "gnome-terminal",
        "konsole",
        "mate-terminal",
        "wezterm",
        "xterm",
    ):
        spec = KNOWN_TERMINALS[term_id]
        for var in spec.get("env_vars", ()):
            val = os.environ.get(var)
            if val:
                logger.debug(
                    "Terminal detected via environment variable %s=%s: %s", var, val, term_id
                )
                return _build_terminal_info(term_id, detection_method="env")

    # 2. Check TERM_PROGRAM
    term_prog = os.environ.get("TERM_PROGRAM", "").strip()
    if term_prog:
        matched = _match_terminal_token(term_prog)
        if matched:
            logger.debug("Terminal detected via TERM_PROGRAM=%s: %s", term_prog, matched)
            return _build_terminal_info(matched, detection_method="env")

    # 3. Check explicit $TERMINAL or $XDG_TERMINAL
    for var in ("TERMINAL", "XDG_TERMINAL"):
        val = os.environ.get(var, "").strip()
        if val:
            matched = _match_terminal_token(val)
            if matched:
                logger.debug("Terminal detected via %s=%s: %s", var, val, matched)
                return _build_terminal_info(matched, detection_method="env")

    return None


def _detect_from_process_tree(max_depth: int = 6) -> TerminalInfo | None:
    """Walk up parent processes via /proc to detect parent terminal emulator."""
    curr_pid = os.getppid()
    depth = 0

    while curr_pid > 1 and depth < max_depth:
        proc_path = Path(f"/proc/{curr_pid}")
        if not proc_path.is_dir():
            break

        comm = ""
        comm_file = proc_path / "comm"
        if comm_file.is_file():
            try:
                comm = comm_file.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                comm = ""

        if comm:
            matched = _match_terminal_token(comm)
            if matched:
                logger.debug(
                    "Terminal detected via process tree (PID %d, comm '%s'): %s",
                    curr_pid,
                    comm,
                    matched,
                )
                return _build_terminal_info(matched, detection_method="proc_tree")

        # Read parent PID from /proc/{curr_pid}/status
        status_file = proc_path / "status"
        parent_pid = 0
        if status_file.is_file():
            try:
                content = status_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if line.startswith("PPid:"):
                        parent_pid = int(line.split()[1])
                        break
            except Exception:
                break

        if parent_pid <= 1 or parent_pid == curr_pid:
            break

        curr_pid = parent_pid
        depth += 1

    return None


def detect_default_terminal() -> TerminalInfo:
    """Detect the system default terminal emulator."""
    # 1. xdg-terminal-exec --print
    try:
        res = subprocess.run(
            ["xdg-terminal-exec", "--print"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            target = res.stdout.strip().splitlines()[0]
            matched = _match_terminal_token(target)
            if matched:
                logger.debug("Default terminal detected via xdg-terminal-exec: %s", matched)
                return _build_terminal_info(
                    matched, detection_method="xdg-terminal-exec", is_default=True
                )
    except Exception as exc:
        logger.debug("xdg-terminal-exec detection skipped or failed: %s", exc)

    # 2. GNOME GSettings: org.gnome.desktop.default-applications.terminal exec
    if _schema_exists("org.gnome.desktop.default-applications.terminal"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.default-applications.terminal", "exec"],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                raw = res.stdout.strip().strip("'\"")
                matched = _match_terminal_token(raw)
                if matched:
                    logger.debug("Default terminal detected via GNOME GSettings: %s", matched)
                    return _build_terminal_info(
                        matched, detection_method="gsettings", is_default=True
                    )
        except Exception as exc:
            logger.debug("GSettings default terminal check failed: %s", exc)

    # 3. System alternatives /etc/alternatives/x-terminal-emulator
    alt_path = Path("/etc/alternatives/x-terminal-emulator")
    if alt_path.is_symlink() or alt_path.is_file():
        try:
            target = str(alt_path.resolve())
            matched = _match_terminal_token(target)
            if matched:
                logger.debug("Default terminal detected via /etc/alternatives: %s", matched)
                return _build_terminal_info(
                    matched, detection_method="alternatives", is_default=True
                )
        except Exception as exc:
            logger.debug("Resolving /etc/alternatives/x-terminal-emulator failed: %s", exc)

    # 4. Prioritized scan of installed binaries
    for term_id in TERMINAL_PRIORITY_ORDER:
        spec = KNOWN_TERMINALS[term_id]
        if is_terminal_installed(spec["binary"], spec["desktop_file"]):
            logger.debug("Default terminal detected via prioritized binary scan: %s", term_id)
            return _build_terminal_info(term_id, detection_method="which", is_default=True)

    # 5. Fallback: unknown
    logger.debug("No supported terminal detected on system.")
    return _build_terminal_info("unknown", detection_method="fallback", is_default=False)


def detect_terminal() -> TerminalInfo:
    """Detect active terminal in the current session or fall back to system default."""
    # 1. Environment variables
    info = _detect_from_environment()
    if info is not None:
        return info

    # 2. Parent process tree walk
    info = _detect_from_process_tree()
    if info is not None:
        return info

    # 3. Fallback: System default terminal
    default_info = detect_default_terminal()
    return default_info
