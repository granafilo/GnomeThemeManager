"""GNOME version detection and theme structure requirements.

Provides utilities to detect the active GNOME Shell version and determine
the corresponding theme structure required for compatibility (notably GNOME 50+
which requires dedicated Libadwaita stylesheets and GTK4 assets).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def detect_gnome_version() -> tuple[int, int] | None:
    """Detect the current GNOME major and minor version.

    Detection order:
    1. `GNOME_VERSION` environment variable (e.g. '50.1' -> (50, 1)).
    2. Gio DBus query to org.gnome.Shell.
    3. `gnome-shell --version` command.
    4. /usr/share/gnome/gnome-version.xml file parsing.

    Returns:
        tuple[int, int] | None: (major, minor) version tuple or None if undetectable.
    """
    # 1. Environment variable override
    env_ver = os.environ.get("GNOME_VERSION", "").strip()
    if env_ver:
        parsed = _parse_version_string(env_ver)
        if parsed:
            return parsed

    # 2. Gio DBus query to org.gnome.Shell
    try:
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.gnome.Shell",
            "/org/gnome/Shell",
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", ("org.gnome.Shell", "ShellVersion")),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
        )
        if reply:
            version_variant = reply.get_child_value(0).get_variant()
            ver_str = version_variant.get_string()
            parsed = _parse_version_string(ver_str)
            if parsed:
                return parsed
    except Exception as exc:
        logger.debug("Gio DBus ShellVersion query failed: %s", exc)

    # 3. Subprocess gnome-shell --version
    try:
        res = subprocess.run(
            ["gnome-shell", "--version"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            parsed = _parse_version_string(res.stdout)
            if parsed:
                return parsed
    except Exception as exc:
        logger.debug("gnome-shell --version execution failed: %s", exc)

    # 4. XML fallback (/usr/share/gnome/gnome-version.xml)
    xml_path = "/usr/share/gnome/gnome-version.xml"
    if os.path.isfile(xml_path):
        try:
            with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            match = re.search(r"<platform>(\d+)</platform>", content)
            minor_match = re.search(r"<minor>(\d+)</minor>", content)
            if match:
                major = int(match.group(1))
                minor = int(minor_match.group(1)) if minor_match else 0
                return (major, minor)
        except Exception as exc:
            logger.debug("Parsing %s failed: %s", xml_path, exc)

    return None


def detect_gnome_version_string() -> str:
    """Return the detected GNOME version as a human-readable string (e.g. '50.0').

    Returns:
        str: Version string like '50.0' or 'unknown'.
    """
    ver = detect_gnome_version()
    if ver is None:
        return "unknown"
    return f"{ver[0]}.{ver[1]}"


def is_gnome_50_plus(version: tuple[int, int] | None = None) -> bool:
    """Return True if the specified or detected GNOME version is >= 50.0."""
    if version is None:
        version = detect_gnome_version()
    if version is None:
        return False
    return version[0] >= 50


def get_required_theme_structure(
    version: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Return expected theme file structure and compatibility criteria for the given GNOME version.

    Parameters:
        version: Optional (major, minor) version tuple. If None, detected automatically.

    Returns:
        dict[str, Any]: Metadata detailing required files, recommended files,
                        and compatibility notes.
    """
    if version is None:
        version = detect_gnome_version()

    major = version[0] if version else 46

    if major >= 50:
        return {
            "gnome_version": f"{major}.{version[1] if version else 0}",
            "is_gnome_50_plus": True,
            "required_gtk_directories": ["gtk-4.0"],
            "required_gtk_files": ["gtk-4.0/gtk.css"],
            "required_libadwaita_files": ["gtk-4.0/libadwaita.css"],
            "alternative_libadwaita_files": [
                "libadwaita.css",
                "libadwaita/libadwaita.css",
                "libadwaita/gtk.css",
            ],
            "shell_theme_directories": ["gnome-shell"],
            "shell_theme_files": ["gnome-shell/gnome-shell.css"],
            "summary": (
                "GNOME 50+ requires Libadwaita stylesheets (gtk-4.0/libadwaita.css "
                "or libadwaita.css) alongside GTK4 (gtk-4.0/gtk.css) and Shell CSS."
            ),
            "description": (
                "GNOME 50+ enforces strict Libadwaita theming. Modern GTK4/Libadwaita "
                "applications ignore GTK_THEME and require libadwaita.css overrides "
                "linked into ~/.config/gtk-4.0/libadwaita.css and gtk.css."
            ),
        }
    elif major >= 42:
        return {
            "gnome_version": f"{major}.{version[1] if version else 0}",
            "is_gnome_50_plus": False,
            "required_gtk_directories": ["gtk-4.0"],
            "required_gtk_files": ["gtk-4.0/gtk.css"],
            "required_libadwaita_files": [],
            "alternative_libadwaita_files": [
                "gtk-4.0/libadwaita.css",
                "libadwaita.css",
            ],
            "shell_theme_directories": ["gnome-shell"],
            "shell_theme_files": ["gnome-shell/gnome-shell.css"],
            "summary": "GNOME 42-49 requires GTK 4.0 (gtk-4.0/gtk.css) and GTK 3.0 support.",
            "description": (
                "GNOME 42-49 uses GTK 4.0 and Libadwaita overrides via ~/.config/gtk-4.0/gtk.css. "
                "libadwaita.css is optional but recommended."
            ),
        }
    else:
        return {
            "gnome_version": f"{major}.{version[1] if version else 0}",
            "is_gnome_50_plus": False,
            "required_gtk_directories": ["gtk-3.0"],
            "required_gtk_files": ["gtk-3.0/gtk.css"],
            "required_libadwaita_files": [],
            "alternative_libadwaita_files": [],
            "shell_theme_directories": ["gnome-shell"],
            "shell_theme_files": ["gnome-shell/gnome-shell.css"],
            "summary": "Legacy GNOME (< 42) relies on GTK 3.0 (gtk-3.0/gtk.css).",
            "description": "Legacy GNOME uses standard GTK 3.0 theme directories.",
        }


def _parse_version_string(ver_str: str) -> tuple[int, int] | None:
    """Extract major and minor integers from a GNOME Shell version string.

    Supports patterns like:
    - '50.0' -> (50, 0)
    - '50.alpha' -> (50, 0)
    - '50.beta.1' -> (50, 0)
    - 'GNOME Shell 46.0' -> (46, 0)
    - '45.1' -> (45, 1)
    """
    match = re.search(r"(\d+)(?:\.(\d+|alpha|beta|rc\d*))?", ver_str)
    if not match:
        return None
    try:
        major = int(match.group(1))
        minor_raw = match.group(2)
        if minor_raw and minor_raw.isdigit():
            minor = int(minor_raw)
        else:
            minor = 0
        return (major, minor)
    except (ValueError, TypeError):
        return None
