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
