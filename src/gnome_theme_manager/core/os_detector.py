# SPDX-License-Identifier: GPL-3.0-or-later

"""Operating system and package manager detection module.

Provides robust detection of the host Linux distribution, version, and default
package manager (apt, dnf, pacman, zypper) with multi-strategy resolution
(/etc/os-release, lsb_release, uname) and graceful fallback for unknown systems.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard candidate paths for os-release files
DEFAULT_OS_RELEASE_PATHS: tuple[Path, ...] = (
    Path("/run/host/etc/os-release"),
    Path("/etc/os-release"),
    Path("/run/host/usr/lib/os-release"),
    Path("/usr/lib/os-release"),
)

# Known package managers
SUPPORTED_PACKAGE_MANAGERS: tuple[str, ...] = ("apt", "dnf", "pacman", "zypper")

# Mapping of distro ID and ID_LIKE tokens to package managers
DISTRO_PM_MAP: dict[str, str] = {
    # Debian / Ubuntu family
    "ubuntu": "apt",
    "debian": "apt",
    "linuxmint": "apt",
    "pop": "apt",
    "zorin": "apt",
    "elementary": "apt",
    "kali": "apt",
    "raspbian": "apt",
    "pureos": "apt",
    "neon": "apt",
    # Red Hat / Fedora family
    "fedora": "dnf",
    "rhel": "dnf",
    "centos": "dnf",
    "almalinux": "dnf",
    "rocky": "dnf",
    "nobara": "dnf",
    "ol": "dnf",
    "amzn": "dnf",
    # Arch Linux family
    "arch": "pacman",
    "manjaro": "pacman",
    "endeavouros": "pacman",
    "cachyos": "pacman",
    "garuda": "pacman",
    "artix": "pacman",
    "arcolinux": "pacman",
    # SUSE family
    "suse": "zypper",
    "opensuse": "zypper",
    "opensuse-tumbleweed": "zypper",
    "opensuse-leap": "zypper",
    "sles": "zypper",
    "sled": "zypper",
}

# Command installation templates by package manager
PACKAGE_MANAGER_INSTALL_TEMPLATES: dict[str, str] = {
    "apt": "sudo apt install -y {packages}",
    "dnf": "sudo dnf install -y {packages}",
    "pacman": "sudo pacman -S --noconfirm {packages}",
    "zypper": "sudo zypper install -y {packages}",
}

# Mapping: dependency_id -> { package_manager: package_names }
DEPENDENCY_PACKAGE_MAP: dict[str, dict[str, str]] = {
    "gtk4": {
        "apt": "python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1",
        "dnf": "python3-gobject gtk4 libadwaita",
        "pacman": "python-gobject gtk4 libadwaita",
        "zypper": "python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1",
    },
    "flatpak": {
        "apt": "flatpak",
        "dnf": "flatpak",
        "pacman": "flatpak",
        "zypper": "flatpak",
    },
    "user-theme": {
        "apt": "gnome-shell-extension-user-theme",
        "dnf": "gnome-shell-extension-user-theme",
        "pacman": "gnome-shell-extensions",
        "zypper": "gnome-shell-extension-user-theme",
    },
    "extension-manager": {
        "apt": "gnome-shell-extension-manager",
        "dnf": "gnome-shell-extension-manager",
        "pacman": "extension-manager",
        "zypper": "extension-manager",
    },
    "gnome-extensions-app": {
        "apt": "gnome-shell-extension-prefs",
        "dnf": "gnome-extensions-app",
        "pacman": "gnome-shell-extensions",
        "zypper": "gnome-shell-extensions-common",
    },
    "snap-tools": {
        "apt": "snapd squashfs-tools",
        "dnf": "snapd squashfs-tools",
        "pacman": "snapd squashfs-tools",
        "zypper": "snapd squashfs-tools",
    },
    "ptyxis": {
        "apt": "ptyxis",
        "dnf": "ptyxis",
        "pacman": "ptyxis",
        "zypper": "ptyxis",
    },
    "gnome-terminal": {
        "apt": "gnome-terminal",
        "dnf": "gnome-terminal",
        "pacman": "gnome-terminal",
        "zypper": "gnome-terminal",
    },
    "kgx": {
        "apt": "gnome-console",
        "dnf": "gnome-console",
        "pacman": "gnome-console",
        "zypper": "gnome-console",
    },
    "konsole": {
        "apt": "konsole",
        "dnf": "konsole",
        "pacman": "konsole",
        "zypper": "konsole",
    },
    "xfce4-terminal": {
        "apt": "xfce4-terminal",
        "dnf": "xfce4-terminal",
        "pacman": "xfce4-terminal",
        "zypper": "xfce4-terminal",
    },
    "mate-terminal": {
        "apt": "mate-terminal",
        "dnf": "mate-terminal",
        "pacman": "mate-terminal",
        "zypper": "mate-terminal",
    },
    "tilix": {
        "apt": "tilix",
        "dnf": "tilix",
        "pacman": "tilix",
        "zypper": "tilix",
    },
    "terminator": {
        "apt": "terminator",
        "dnf": "terminator",
        "pacman": "terminator",
        "zypper": "terminator",
    },
    "alacritty": {
        "apt": "alacritty",
        "dnf": "alacritty",
        "pacman": "alacritty",
        "zypper": "alacritty",
    },
    "kitty": {
        "apt": "kitty",
        "dnf": "kitty",
        "pacman": "kitty",
        "zypper": "kitty",
    },
    "warp": {
        "apt": "warp-terminal",
        "dnf": "warp-terminal",
        "pacman": "warp-terminal",
        "zypper": "warp-terminal",
    },
    "wezterm": {
        "apt": "wezterm",
        "dnf": "wezterm",
        "pacman": "wezterm",
        "zypper": "wezterm",
    },
    "xterm": {
        "apt": "xterm",
        "dnf": "xterm",
        "pacman": "xterm",
        "zypper": "xterm",
    },
    "urxvt": {
        "apt": "rxvt-unicode",
        "dnf": "rxvt-unicode",
        "pacman": "rxvt-unicode",
        "zypper": "rxvt-unicode",
    },
    "requests": {
        "apt": "python3-requests",
        "dnf": "python3-requests",
        "pacman": "python-requests",
        "zypper": "python3-requests",
    },
}


@dataclass(frozen=True)
class OSInfo:
    """Represents detected operating system details."""

    distro: str
    version: str
    package_manager: str
    pretty_name: str = ""

    def __iter__(self) -> Iterator[str]:
        """Allow 3-tuple unpacking: distro, version, package_manager = detect_os()."""
        return iter((self.distro, self.version, self.package_manager))

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary representation."""
        return asdict(self)


def parse_os_release_text(content: str) -> dict[str, str]:
    """Parse the content of a standard os-release file into key-value pairs.

    Args:
        content: Raw text content of os-release.

    Returns:
        Dictionary containing parsed key-value attributes.
    """
    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _sep, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Remove surrounding single or double quotes
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        # Unescape escaped characters like \$ or \"
        val = val.replace('\\"', '"').replace("\\$", "$")
        result[key] = val
    return result


def _find_binary_on_system(binary_name: str) -> bool:
    """Check if a binary exists on the host or inside the current execution path."""
    if shutil.which(binary_name) is not None:
        return True
    # In sandbox or container, check /run/host
    for host_prefix in (Path("/run/host/usr/bin"), Path("/run/host/bin")):
        cand = host_prefix / binary_name
        if cand.is_file() and os.access(cand, os.X_OK):
            return True
    return False


def _detect_installed_package_manager() -> str | None:
    """Probe the filesystem for known package manager binaries."""
    for pm in SUPPORTED_PACKAGE_MANAGERS:
        if _find_binary_on_system(pm):
            return pm
    return None


def _resolve_package_manager(
    distro_id: str,
    id_like: str = "",
    explicit_pm: str | None = None,
) -> str:
    """Resolve the appropriate package manager for a distribution.

    Args:
        distro_id: Primary distribution identifier (e.g. 'ubuntu', 'fedora').
        id_like: Secondary space-separated distribution identifiers (e.g. 'rhel fedora').
        explicit_pm: Pre-specified package manager if known.

    Returns:
        Package manager name ('apt', 'dnf', 'pacman', 'zypper') or 'unknown'.
    """
    if explicit_pm and explicit_pm in SUPPORTED_PACKAGE_MANAGERS:
        return explicit_pm

    # 1. Match primary ID
    low_id = distro_id.lower().strip()
    if low_id in DISTRO_PM_MAP:
        return DISTRO_PM_MAP[low_id]

    # 2. Match tokens in ID_LIKE
    for token in id_like.lower().split():
        if token in DISTRO_PM_MAP:
            return DISTRO_PM_MAP[token]

    # 3. Fallback: probe available binary on the system
    detected = _detect_installed_package_manager()
    if detected is not None:
        return detected

    return "unknown"


def _detect_from_os_release_data(data: dict[str, str]) -> OSInfo | None:
    """Build an OSInfo instance from parsed os-release data."""
    distro_id = data.get("ID", "").strip().lower()
    if not distro_id:
        # Fallback to NAME if ID is missing
        name = data.get("NAME", "").strip()
        if name:
            distro_id = re.sub(r"[^a-z0-9_-]", "", name.lower())

    if not distro_id:
        return None

    id_like = data.get("ID_LIKE", "")
    version = data.get("VERSION_ID", "").strip()
    if not version:
        # Rolling release distributions often use BUILD_ID or simply 'rolling'
        if data.get("BUILD_ID", "").strip().lower() == "rolling" or distro_id in (
            "arch",
            "cachyos",
            "manjaro",
            "endeavouros",
        ):
            version = "rolling"
        elif data.get("VERSION", ""):
            version = data["VERSION"].strip()
        else:
            version = "unknown"

    pretty_name = data.get("PRETTY_NAME", data.get("NAME", distro_id))
    pm = _resolve_package_manager(distro_id, id_like)

    return OSInfo(
        distro=distro_id,
        version=version,
        package_manager=pm,
        pretty_name=pretty_name,
    )


def _detect_from_lsb_release() -> OSInfo | None:
    """Attempt OS detection via lsb_release command."""
    try:
        res = subprocess.run(
            ["lsb_release", "-a"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode != 0 or not res.stdout:
            return None

        fields: dict[str, str] = {}
        for line in res.stdout.splitlines():
            if ":" in line:
                k, _sep, v = line.partition(":")
                fields[k.strip().lower()] = v.strip()

        distro = fields.get("distributor id", "").lower()
        version = fields.get("release", "unknown")
        desc = fields.get("description", distro)

        if not distro:
            return None

        pm = _resolve_package_manager(distro)
        return OSInfo(
            distro=distro,
            version=version,
            package_manager=pm,
            pretty_name=desc,
        )
    except Exception as exc:
        logger.debug("lsb_release detection failed: %s", exc)
        return None


def _detect_from_uname() -> OSInfo:
    """Fallback detection via platform / uname."""
    sys_name = platform.system().lower()
    release = platform.release()
    pm = _detect_installed_package_manager() or "unknown"
    return OSInfo(
        distro=sys_name if sys_name else "linux",
        version=release if release else "unknown",
        package_manager=pm,
        pretty_name=f"{platform.system()} {release}".strip(),
    )


def detect_os(
    os_release_path: Path | str | None = None,
    os_release_text: str | None = None,
) -> OSInfo:
    """Detect host Linux distribution, version, and package manager.

    Args:
        os_release_path: Optional path to an os-release file (useful for testing).
        os_release_text: Optional raw os-release content string (useful for testing).

    Returns:
        OSInfo containing distro, version, package_manager, and pretty_name.
    """
    # 1. Custom or injected os-release text
    if os_release_text is not None:
        parsed = parse_os_release_text(os_release_text)
        detected = _detect_from_os_release_data(parsed)
        if detected:
            return detected
        logger.warning(
            "Unrecognized os-release content provided; falling back to generic Linux profile."
        )
        return OSInfo(
            distro="linux",
            version="unknown",
            package_manager="unknown",
            pretty_name="Generic Linux",
        )

    # 2. Custom or standard os-release file
    candidate_paths = [Path(os_release_path)] if os_release_path else list(DEFAULT_OS_RELEASE_PATHS)
    for path in candidate_paths:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                parsed = parse_os_release_text(content)
                detected = _detect_from_os_release_data(parsed)
                if detected:
                    return detected
            except Exception as exc:
                logger.debug("Error reading %s: %s", path, exc)

    # 3. Fallback: lsb_release
    lsb_result = _detect_from_lsb_release()
    if lsb_result is not None:
        return lsb_result

    # 4. Fallback: uname / platform
    uname_result = _detect_from_uname()
    if uname_result.distro in ("linux", "unknown") or uname_result.package_manager == "unknown":
        logger.warning(
            "Unrecognized or non-standard OS distribution (%s, %s); falling back to generic Linux.",
            uname_result.distro,
            uname_result.version,
        )

    return uname_result


def _is_ubuntu_noble_or_earlier(version_str: str) -> bool:
    """Check if Ubuntu version is 24.04 (Noble Numbat) or earlier."""
    if not version_str:
        return False
    clean = version_str.strip().lower()
    if clean in ("noble", "jammy", "focal", "bionic", "xenial"):
        return True
    match = re.match(r"^(\d+)(?:\.(\d+))?", clean)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) is not None else 0
        return bool(major < 24 or (major == 24 and minor <= 4))
    return False


def _resolve_special_dependency_command(
    dependency: str,
    target_pm: str,
    target_distro: str = "",
    target_version: str = "",
) -> str | None:
    """Resolve custom installation commands for special packages not in standard repos."""
    clean_dep = dependency.strip().lower()

    if clean_dep == "ptyxis":
        if target_pm == "pacman":
            return "sudo pacman -S --noconfirm ptyxis"
        if target_pm == "dnf":
            return "sudo dnf install -y ptyxis"
        if target_pm == "zypper":
            return "sudo zypper install -y ptyxis"
        if target_pm == "apt":
            distro_lower = target_distro.lower()
            if distro_lower in ("zorin", "linuxmint", "mint", "pop", "elementary"):
                return "flatpak install -y flathub app.devsuite.Ptyxis"
            if distro_lower == "debian":
                if not target_version or target_version in (
                    "10",
                    "11",
                    "12",
                    "bookworm",
                    "bullseye",
                ):
                    return "flatpak install -y flathub app.devsuite.Ptyxis"
                if target_version.isdigit() and int(target_version) <= 12:
                    return "flatpak install -y flathub app.devsuite.Ptyxis"
            if distro_lower == "ubuntu":
                if _is_ubuntu_noble_or_earlier(target_version):
                    return "flatpak install -y flathub app.devsuite.Ptyxis"
                return "sudo apt install -y ptyxis"
            return "sudo apt install -y ptyxis"

    if clean_dep == "wezterm":
        if target_pm == "pacman":
            return "sudo pacman -S --noconfirm wezterm"
        return "flatpak install -y flathub org.wezfurlong.wezterm"

    if clean_dep == "warp":
        if target_pm == "pacman":
            return "yay -S --noconfirm warp-terminal-bin"
        if target_pm == "dnf":
            return "sudo dnf install -y https://app.warp.dev/download?package=rpm"
        if target_pm == "zypper":
            return "sudo zypper install -y https://app.warp.dev/download?package=rpm"
        return (
            "curl -fsSL https://app.warp.dev/download?package=deb -o /tmp/warp.deb "
            "&& sudo apt install -y /tmp/warp.deb && rm /tmp/warp.deb"
        )

    return None


def get_install_command(
    dependency: str,
    package_manager: str | None = None,
    distro: str | None = None,
    os_info: OSInfo | None = None,
) -> str:
    """Generate the exact distribution-specific installation command for a dependency.

    Resolves the package manager via explicit parameter, distribution name,
    provided OSInfo, or automatic runtime system detection, and generates
    the corresponding terminal installation command.

    Args:
        dependency: Identifier or name of the dependency (e.g. 'gtk4', 'user-theme', 'ptyxis').
        package_manager: Optional package manager override ('apt', 'dnf', 'pacman', 'zypper').
        distro: Optional Linux distribution name or ID (e.g. 'fedora', 'arch', 'ubuntu').
        os_info: Optional OSInfo instance. If None and no pm/distro provided, auto-detected.

    Returns:
        Exact shell command string (e.g. 'sudo dnf install -y gnome-shell-extension-user-theme').
    """
    clean_dep = dependency.strip().lower()
    target_pm = "unknown"
    target_distro = ""
    target_version = ""

    if os_info is not None:
        target_pm = os_info.package_manager.strip().lower()
        target_distro = os_info.distro.strip().lower()
        target_version = os_info.version.strip().lower()
    elif distro and distro.strip():
        target_distro = distro.strip().lower()
        target_pm = (
            package_manager.strip().lower()
            if package_manager and package_manager.strip()
            else _resolve_package_manager(target_distro)
        )
    elif package_manager and package_manager.strip():
        target_pm = package_manager.strip().lower()
    else:
        detected = detect_os()
        target_pm = detected.package_manager.strip().lower()
        target_distro = detected.distro.strip().lower()
        target_version = detected.version.strip().lower()

    if package_manager and package_manager.strip():
        target_pm = package_manager.strip().lower()
    if distro and distro.strip():
        target_distro = distro.strip().lower()

    special_cmd = _resolve_special_dependency_command(
        clean_dep,
        target_pm,
        target_distro=target_distro,
        target_version=target_version,
    )
    if special_cmd is not None:
        return special_cmd

    # Determine package specification for this package manager
    pkg_spec = DEPENDENCY_PACKAGE_MAP.get(clean_dep, {}).get(target_pm, dependency.strip())

    if target_pm in PACKAGE_MANAGER_INSTALL_TEMPLATES:
        template = PACKAGE_MANAGER_INSTALL_TEMPLATES[target_pm]
        return template.format(packages=pkg_spec)

    return f"sudo {target_pm} install {pkg_spec}"


def get_os_install_commands(dependency: str) -> dict[str, str]:
    """Return a mapping of major distributions and package managers to install commands.

    Args:
        dependency: Identifier of the dependency (e.g. 'gtk4', 'user-theme', 'ptyxis').

    Returns:
        Dictionary mapping distribution identifiers ('ubuntu', 'fedora', 'arch', 'opensuse')
        to their exact shell install command strings.
    """
    return {
        "ubuntu": get_install_command(dependency, distro="ubuntu"),
        "fedora": get_install_command(dependency, distro="fedora"),
        "arch": get_install_command(dependency, distro="arch"),
        "opensuse": get_install_command(dependency, distro="opensuse"),
    }


def get_missing_dependency_hint(
    dependency: str,
    os_info: OSInfo | None = None,
) -> str:
    """Generate a formatted hint showing the exact installation command for the detected OS.

    Args:
        dependency: Identifier of the missing dependency.
        os_info: Optional OSInfo instance.

    Returns:
        Formatted hint string (e.g. 'Install with: sudo dnf install -y ...').
    """
    cmd = get_install_command(dependency, os_info=os_info)
    return f"Install with: {cmd}"


def get_extension_manager_install_options(
    distro: str | None = None,
    package_manager: str | None = None,
    os_info: OSInfo | None = None,
) -> list[dict[str, str]]:
    """Return multiple installation options for Extension Manager across package formats.

    Provides a choice between:
    1. Distribution native package manager (APT/DNF/Pacman/Zypper)
    2. Flatpak via Flathub (universal sandbox)
    3. Standalone Extension Manager native package

    Args:
        distro: Optional Linux distribution name.
        package_manager: Optional package manager override.
        os_info: Optional OSInfo instance.

    Returns:
        List of dictionaries with 'id', 'name', 'command', and 'description'.
    """
    clean_pm = "unknown"
    if package_manager and package_manager.strip():
        clean_pm = package_manager.strip().lower()
    elif distro and distro.strip():
        clean_pm = _resolve_package_manager(distro)
    elif os_info is not None:
        clean_pm = os_info.package_manager.strip().lower()
    else:
        clean_pm = detect_os().package_manager.strip().lower()

    ext_mgr_cmd = get_install_command("extension-manager", package_manager=clean_pm)
    basic_cmd = get_install_command("gnome-extensions-app", package_manager=clean_pm)

    return [
        {
            "id": "flatpak",
            "name": "Extension Manager (Flatpak Flathub)",
            "command": "flatpak install flathub com.mattjakeman.ExtensionManager",
            "description": "Official Extension Manager release in sandbox from Flathub.",
        },
        {
            "id": "system",
            "name": f"Extension Manager ({clean_pm.upper()})",
            "command": ext_mgr_cmd,
            "description": "Recommended native package for Extension Manager.",
        },
        {
            "id": "gnome-extensions-app",
            "name": f"GNOME Extensions Basic ({clean_pm.upper()})",
            "command": basic_cmd,
            "description": "Basic GNOME Extensions utility without online extension browsing.",
        },
    ]


__all__ = [
    "DEFAULT_OS_RELEASE_PATHS",
    "DEPENDENCY_PACKAGE_MAP",
    "DISTRO_PM_MAP",
    "PACKAGE_MANAGER_INSTALL_TEMPLATES",
    "SUPPORTED_PACKAGE_MANAGERS",
    "OSInfo",
    "detect_os",
    "get_extension_manager_install_options",
    "get_install_command",
    "get_missing_dependency_hint",
    "get_os_install_commands",
    "parse_os_release_text",
]
