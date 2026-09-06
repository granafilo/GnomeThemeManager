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
    get_install_command,
    get_missing_dependency_hint,
    get_os_install_commands,
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
    mock_run.stdout = "Distributor ID:\tUbuntu\nDescription:\tUbuntu 24.04 LTS\nRelease:\t24.04\nCodename:\tnoble\n"

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


def test_get_install_command_multi_os() -> None:
    """Verify exact installation commands generated for apt, dnf, pacman, and zypper."""
    # 1. Ubuntu (apt)
    assert (
        get_install_command("gtk4", distro="ubuntu")
        == "sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1"
    )
    assert (
        get_install_command("user-theme", distro="ubuntu")
        == "sudo apt install -y gnome-shell-extension-user-theme"
    )
    assert (
        get_install_command("gnome-extensions-app", distro="ubuntu")
        == "sudo apt install -y gnome-shell-extension-prefs"
    )
    assert (
        get_install_command("snap-tools", distro="ubuntu")
        == "sudo apt install -y snapd squashfs-tools"
    )
    assert get_install_command("ptyxis", distro="ubuntu") == "sudo apt install -y ptyxis"

    # 2. Fedora (dnf)
    assert (
        get_install_command("gtk4", distro="fedora")
        == "sudo dnf install -y python3-gobject gtk4 libadwaita"
    )
    assert (
        get_install_command("user-theme", distro="fedora")
        == "sudo dnf install -y gnome-shell-extension-user-theme"
    )
    assert (
        get_install_command("gnome-extensions-app", distro="fedora")
        == "sudo dnf install -y gnome-extensions-app"
    )
    assert (
        get_install_command("snap-tools", distro="fedora")
        == "sudo dnf install -y snapd squashfs-tools"
    )
    assert get_install_command("ptyxis", distro="fedora") == "sudo dnf install -y ptyxis"

    # 3. Arch Linux (pacman)
    assert (
        get_install_command("gtk4", distro="arch")
        == "sudo pacman -S --noconfirm python-gobject gtk4 libadwaita"
    )
    assert (
        get_install_command("user-theme", distro="arch")
        == "sudo pacman -S --noconfirm gnome-shell-extensions"
    )
    assert (
        get_install_command("gnome-extensions-app", distro="arch")
        == "sudo pacman -S --noconfirm gnome-shell-extensions"
    )
    assert (
        get_install_command("snap-tools", distro="arch")
        == "sudo pacman -S --noconfirm snapd squashfs-tools"
    )
    assert get_install_command("ptyxis", distro="arch") == "sudo pacman -S --noconfirm ptyxis"

    # 4. openSUSE (zypper)
    assert (
        get_install_command("gtk4", distro="opensuse")
        == "sudo zypper install -y python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1"
    )
    assert (
        get_install_command("user-theme", distro="opensuse")
        == "sudo zypper install -y gnome-shell-extension-user-theme"
    )
    assert (
        get_install_command("gnome-extensions-app", distro="opensuse")
        == "sudo zypper install -y gnome-shell-extensions-common"
    )
    assert (
        get_install_command("snap-tools", distro="opensuse")
        == "sudo zypper install -y snapd squashfs-tools"
    )
    assert get_install_command("ptyxis", distro="opensuse") == "sudo zypper install -y ptyxis"


def test_get_install_command_with_os_info() -> None:
    """Verify get_install_command uses OSInfo instance."""
    fedora_info = OSInfo("fedora", "40", "dnf", "Fedora 40")
    arch_info = OSInfo("arch", "rolling", "pacman", "Arch Linux")

    assert (
        get_install_command("user-theme", os_info=fedora_info)
        == "sudo dnf install -y gnome-shell-extension-user-theme"
    )
    assert (
        get_install_command("user-theme", os_info=arch_info)
        == "sudo pacman -S --noconfirm gnome-shell-extensions"
    )


def test_get_install_command_fallback_and_custom() -> None:
    """Verify unmapped dependency and unknown package manager fallback."""
    # Arbitrary package with known package manager
    assert get_install_command("htop", package_manager="apt") == "sudo apt install -y htop"
    assert get_install_command("htop", package_manager="dnf") == "sudo dnf install -y htop"
    assert (
        get_install_command("htop", package_manager="pacman") == "sudo pacman -S --noconfirm htop"
    )
    assert get_install_command("htop", package_manager="zypper") == "sudo zypper install -y htop"

    # Unknown package manager
    assert get_install_command("htop", package_manager="brew") == "sudo brew install htop"


def test_get_os_install_commands() -> None:
    """Verify dictionary map OS -> install command."""
    commands = get_os_install_commands("user-theme")
    assert "ubuntu" in commands
    assert "fedora" in commands
    assert "arch" in commands
    assert "opensuse" in commands
    assert commands["ubuntu"] == "sudo apt install -y gnome-shell-extension-user-theme"
    assert commands["fedora"] == "sudo dnf install -y gnome-shell-extension-user-theme"
    assert commands["arch"] == "sudo pacman -S --noconfirm gnome-shell-extensions"
    assert commands["opensuse"] == "sudo zypper install -y gnome-shell-extension-user-theme"


def test_get_missing_dependency_hint() -> None:
    """Verify missing dependency hint string."""
    fedora_info = OSInfo("fedora", "40", "dnf", "Fedora 40")
    hint = get_missing_dependency_hint("ptyxis", os_info=fedora_info)
    assert hint == "Install with: sudo dnf install -y ptyxis"


def test_theme_manager_install_command_methods() -> None:
    """Verify ThemeManager facade provides install command helpers."""
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
        return_value=OSInfo("fedora", "40", "dnf", "Fedora 40"),
    ):
        cmd = tm.get_install_command("user-theme")
        assert cmd == "sudo dnf install -y gnome-shell-extension-user-theme"

    os_cmds = tm.get_os_install_commands("gtk4")
    assert "fedora" in os_cmds
    assert os_cmds["fedora"] == "sudo dnf install -y python3-gobject gtk4 libadwaita"

    with patch(
        "gnome_theme_manager.core.os_detector.detect_os",
        return_value=OSInfo("ubuntu", "24.04", "apt", "Ubuntu 24.04 LTS"),
    ):
        ext_opts = tm.get_extension_manager_install_options()
        assert len(ext_opts) == 3
        ids = [opt["id"] for opt in ext_opts]
        assert "system" in ids
        assert "flatpak" in ids
        assert "gnome-extensions-app" in ids


def test_get_extension_manager_install_options_distros() -> None:
    """Verify multiple install options generated across distributions."""
    from gnome_theme_manager.core.os_detector import get_extension_manager_install_options

    # Ubuntu
    ubuntu_opts = get_extension_manager_install_options(distro="ubuntu")
    assert any("apt" in opt["command"] for opt in ubuntu_opts)
    assert any("flatpak" in opt["command"] for opt in ubuntu_opts)

    # Fedora
    fedora_opts = get_extension_manager_install_options(distro="fedora")
    assert any("dnf" in opt["command"] for opt in fedora_opts)

    # Arch
    arch_opts = get_extension_manager_install_options(distro="arch")
    assert any("pacman" in opt["command"] for opt in arch_opts)

    # openSUSE
    opensuse_opts = get_extension_manager_install_options(distro="opensuse")
    assert any("zypper" in opt["command"] for opt in opensuse_opts)

    # Unknown / fallback
    unknown_opts = get_extension_manager_install_options(package_manager="unknown")
    assert len(unknown_opts) == 3


def test_requests_dependency_mapping() -> None:
    """Verify requests mapping is defined for all supported package managers."""
    from gnome_theme_manager.core.os_detector import DEPENDENCY_PACKAGE_MAP, get_os_install_commands

    assert "requests" in DEPENDENCY_PACKAGE_MAP
    assert DEPENDENCY_PACKAGE_MAP["requests"]["apt"] == "python3-requests"
    assert DEPENDENCY_PACKAGE_MAP["requests"]["pacman"] == "python-requests"
    assert DEPENDENCY_PACKAGE_MAP["requests"]["dnf"] == "python3-requests"
    assert DEPENDENCY_PACKAGE_MAP["requests"]["zypper"] == "python3-requests"

    commands = get_os_install_commands("requests")
    assert "arch" in commands
    assert commands["arch"] == "sudo pacman -S --noconfirm python-requests"
