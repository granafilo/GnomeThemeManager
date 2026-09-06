# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for OS and package manager detection module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.os_detector import (
    OSInfo,
    _detect_from_lsb_release,
    _detect_from_uname,
    _resolve_package_manager,
    detect_os,
    parse_os_release_text,
)

UBUNTU_OS_RELEASE = """
NAME="Ubuntu"
VERSION="24.04.1 LTS (Noble Numbat)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 24.04.1 LTS"
VERSION_ID="24.04"
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
"""

FEDORA_OS_RELEASE = """
NAME="Fedora Linux"
VERSION="40 (Workstation Edition)"
ID=fedora
VERSION_ID=40
VERSION_CODENAME=""
PLATFORM_ID="platform:f40"
PRETTY_NAME="Fedora Linux 40 (Workstation Edition)"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=fedora-logo-icon
CPE_NAME="cpe:/o:fedoraproject:fedora:40"
HOME_URL="https://fedoraproject.org/"
DOCUMENTATION_URL="https://docs.fedoraproject.org/en-US/fedora/f40/system-administrators-guide/"
SUPPORT_URL="https://ask.fedoraproject.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
REDHAT_BUGZILLA_PRODUCT="Fedora"
REDHAT_BUGZILLA_PRODUCT_VERSION=40
REDHAT_SUPPORT_PRODUCT="Fedora"
REDHAT_SUPPORT_PRODUCT_VERSION=40
SUPPORT_END=2025-05-13
"""

ARCH_OS_RELEASE = """
NAME="Arch Linux"
PRETTY_NAME="Arch Linux"
ID=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://archlinux.org/"
DOCUMENTATION_URL="https://wiki.archlinux.org/"
SUPPORT_URL="https://bbs.archlinux.org/"
BUG_REPORT_URL="https://gitlab.archlinux.org/groups/archlinux/-/issues"
PRIVACY_POLICY_URL="https://terms.archlinux.org/docs/privacy-policy/"
LOGO=archlinux-logo
"""

OPENSUSE_OS_RELEASE = """
NAME="openSUSE Tumbleweed"
# VERSION="20260901"
ID="opensuse-tumbleweed"
ID_LIKE="opensuse suse"
VERSION_ID="20260901"
PRETTY_NAME="openSUSE Tumbleweed"
ANSI_COLOR="0;32"
CPE_NAME="cpe:/o:opensuse:tumbleweed:20260901"
BUG_REPORT_URL="https://bugzilla.opensuse.org"
SUPPORT_URL="https://bugs.opensuse.org"
HOME_URL="https://www.opensuse.org"
DOCUMENTATION_URL="https://en.opensuse.org/Portal:Tumbleweed"
LOGO="distributor-logo-Tumbleweed"
"""

ZORIN_OS_RELEASE = """
NAME="Zorin OS"
VERSION="17.2"
ID=zorin
ID_LIKE="ubuntu debian"
VERSION_ID="17"
PRETTY_NAME="Zorin OS 17.2"
"""

CACHYOS_OS_RELEASE = """
NAME="CachyOS"
ID=cachyos
ID_LIKE=arch
PRETTY_NAME="CachyOS Rolling"
"""

NOBARA_OS_RELEASE = """
NAME="Nobara Linux"
ID=nobara
ID_LIKE="fedora rhel"
VERSION_ID="40"
PRETTY_NAME="Nobara Linux 40"
"""


def test_parse_os_release_text() -> None:
    """Verify parser strips quotes, unescapes, and skips comments."""
    raw = """
    # Comment line
    ID="ubuntu"
    VERSION='24.04'
    UNQUOTED=noble
    EMPTY=
    WITH_SPACES="Ubuntu Linux LTS"
    ESCAPED="Line with \\"quote\\""
    """
    parsed = parse_os_release_text(raw)
    assert parsed["ID"] == "ubuntu"
    assert parsed["VERSION"] == "24.04"
    assert parsed["UNQUOTED"] == "noble"
    assert parsed["EMPTY"] == ""
    assert parsed["WITH_SPACES"] == "Ubuntu Linux LTS"
    assert parsed["ESCAPED"] == 'Line with "quote"'


def test_detect_os_ubuntu() -> None:
    """Verify Ubuntu detection returns apt package manager and 24.04 version."""
    info = detect_os(os_release_text=UBUNTU_OS_RELEASE)
    assert info.distro == "ubuntu"
    assert info.version == "24.04"
    assert info.package_manager == "apt"
    assert "Ubuntu 24.04" in info.pretty_name


def test_detect_os_fedora() -> None:
    """Verify Fedora detection returns dnf package manager and 40 version."""
    info = detect_os(os_release_text=FEDORA_OS_RELEASE)
    assert info.distro == "fedora"
    assert info.version == "40"
    assert info.package_manager == "dnf"
    assert "Fedora" in info.pretty_name


def test_detect_os_arch() -> None:
    """Verify Arch Linux detection returns pacman package manager and rolling version."""
    info = detect_os(os_release_text=ARCH_OS_RELEASE)
    assert info.distro == "arch"
    assert info.version == "rolling"
    assert info.package_manager == "pacman"
    assert info.pretty_name == "Arch Linux"


def test_detect_os_opensuse() -> None:
    """Verify openSUSE detection returns zypper package manager."""
    info = detect_os(os_release_text=OPENSUSE_OS_RELEASE)
    assert info.distro == "opensuse-tumbleweed"
    assert info.version == "20260901"
    assert info.package_manager == "zypper"


def test_detect_os_derivatives() -> None:
    """Verify ID_LIKE mappings for derivatives (Zorin, CachyOS, Nobara)."""
    zorin = detect_os(os_release_text=ZORIN_OS_RELEASE)
    assert zorin.distro == "zorin"
    assert zorin.package_manager == "apt"

    cachy = detect_os(os_release_text=CACHYOS_OS_RELEASE)
    assert cachy.distro == "cachyos"
    assert cachy.package_manager == "pacman"

    nobara = detect_os(os_release_text=NOBARA_OS_RELEASE)
    assert nobara.distro == "nobara"
    assert nobara.package_manager == "dnf"


def test_os_info_unpacking_and_dict() -> None:
    """Check 3-tuple unpacking and dictionary serialization."""
    info = OSInfo(
        distro="ubuntu",
        version="24.04",
        package_manager="apt",
        pretty_name="Ubuntu 24.04 LTS",
    )
    distro, version, pm = info
    assert distro == "ubuntu"
    assert version == "24.04"
    assert pm == "apt"

    d = info.to_dict()
    assert d["distro"] == "ubuntu"
    assert d["package_manager"] == "apt"


def test_detect_os_from_file(tmp_path: Path) -> None:
    """Test reading from custom os-release file path."""
    fake_os_file = tmp_path / "os-release"
    fake_os_file.write_text(FEDORA_OS_RELEASE, encoding="utf-8")

    info = detect_os(os_release_path=fake_os_file)
    assert info.distro == "fedora"
    assert info.package_manager == "dnf"


def test_resolve_package_manager_fallback(monkeypatch: object) -> None:
    """Test resolution fallback checking binary on system."""
    assert _resolve_package_manager("unknown_distro", id_like="") in (
        "apt",
        "dnf",
        "pacman",
        "zypper",
        "unknown",
    )


def test_detect_from_lsb_release() -> None:
    """Test lsb_release command fallback parser."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = (
        "Distributor ID:\tUbuntu\nDescription:\tUbuntu 24.04 LTS\nRelease:\t24.04\nCodename:\tnoble\n"
    )

    with patch("subprocess.run", return_value=mock_run):
        info = _detect_from_lsb_release()
        assert info is not None
        assert info.distro == "ubuntu"
        assert info.version == "24.04"
        assert info.package_manager == "apt"


def test_detect_from_uname_and_warning() -> None:
    """Verify fallback to uname and warning when OS is not recognized."""
    with patch("platform.system", return_value="FreeBSD"):
        with patch("platform.release", return_value="14.0"):
            with patch(
                "gnome_theme_manager.core.os_detector._detect_installed_package_manager",
                return_value=None,
            ):
                info = _detect_from_uname()
                assert info.distro == "freebsd"
                assert info.version == "14.0"
                assert info.package_manager == "unknown"


def test_detect_os_edge_case_unknown_logs_warning() -> None:
    """Verify detect_os falls back to generic linux and warns for unrecognized OS."""
    with patch("pathlib.Path.is_file", return_value=False):
        with patch(
            "gnome_theme_manager.core.os_detector._detect_from_lsb_release",
            return_value=None,
        ):
            with patch("platform.system", return_value="Linux"):
                with patch("platform.release", return_value="6.8.0-generic"):
                    with patch(
                        "gnome_theme_manager.core.os_detector._detect_installed_package_manager",
                        return_value=None,
                    ):
                        with patch("logging.Logger.warning") as mock_warn:
                            info = detect_os()
                            assert info.distro == "linux"
                            assert info.package_manager == "unknown"
                            assert mock_warn.called


def test_theme_manager_detect_os() -> None:
    """Verify ThemeManager facade delegates to detect_os."""
    tm = ThemeManager(
        scanner=MagicMock(),
        gsettings=MagicMock(),
        gtk4_linker=MagicMock(),
        installer=MagicMock(),
        presets=MagicMock(),
        sandbox_bridge=MagicMock(),
        validator=MagicMock(),
        extensions=MagicMock(),
    )
    with patch(
        "gnome_theme_manager.core.os_detector.detect_os",
        return_value=OSInfo("ubuntu", "24.04", "apt", "Ubuntu 24.04"),
    ):
        info = tm.detect_os()
        assert info.distro == "ubuntu"
        assert info.version == "24.04"
        assert info.package_manager == "apt"
