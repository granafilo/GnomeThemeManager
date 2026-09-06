# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for terminal detection and cascade strategies (Prompt 2.1 Step 2)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.terminal_detector import (
    TerminalInfo,
    _detect_from_environment,
    _detect_from_process_tree,
    _match_terminal_token,
    detect_default_terminal,
    detect_terminal,
)


def test_match_terminal_token() -> None:
    """Verify matching of binary names, desktop files, and aliases."""
    assert _match_terminal_token("ptyxis") == "ptyxis"
    assert _match_terminal_token("org.gnome.Ptyxis.desktop") == "ptyxis"
    assert _match_terminal_token("/usr/bin/gnome-terminal") == "gnome-terminal"
    assert _match_terminal_token("gnome-terminal-server") == "gnome-terminal"
    assert _match_terminal_token("kgx") == "kgx"
    assert _match_terminal_token("gnome-console") == "kgx"
    assert _match_terminal_token("alacritty") == "alacritty"
    assert _match_terminal_token("kitty") == "kitty"
    assert _match_terminal_token("warp-terminal") == "warp"
    assert _match_terminal_token("wezterm-gui") == "wezterm"
    assert _match_terminal_token("nonexistent-terminal") is None


def test_terminal_info_dict_and_props() -> None:
    """Check TerminalInfo serialization, dict-like access, and backward compatibility."""
    info = TerminalInfo(
        terminal_id="ptyxis",
        terminal_name="Ptyxis",
        binary="ptyxis",
        desktop_file="org.gnome.Ptyxis.desktop",
        detection_method="which",
        is_installed=True,
        is_default=True,
        supports_gsettings=True,
        schema_id="org.gnome.Ptyxis",
        schema_accessible=True,
    )
    d = info.to_dict()
    assert d["terminal_id"] == "ptyxis"
    assert d["terminal_name"] == "Ptyxis"
    assert d["binary"] == "ptyxis"
    assert d["desktop_file"] == "org.gnome.Ptyxis.desktop"
    assert d["detection_method"] == "which"
    assert d["is_installed"] is True
    assert d["is_default"] is True

    # Dict-like access
    assert info["terminal_id"] == "ptyxis"
    assert info["binary"] == "ptyxis"

    # Backward-compatible property aliases
    assert info.display_name == "Ptyxis"
    assert info.terminal_type == "ptyxis"
    assert bool(info) is True


def test_case_a_ptyxis_installed_and_default() -> None:
    """Mock Case A: Environment where Ptyxis is installed and default via xdg-terminal-exec."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "org.gnome.Ptyxis.desktop\n"

    with patch.dict("os.environ", {}, clear=True):
        with patch("subprocess.run", return_value=mock_run):
            with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
                info = detect_default_terminal()
                assert info.terminal_id == "ptyxis"
                assert info.terminal_name == "Ptyxis"
                assert info.binary == "ptyxis"
                assert info.detection_method == "xdg-terminal-exec"
                assert info.is_installed is True
                assert info.is_default is True


def test_case_b_gnome_terminal_no_ptyxis() -> None:
    """Mock Case B: Environment with GNOME Terminal installed, but no Ptyxis."""
    # xdg-terminal-exec not available
    def mock_installed(binary: str, desktop_file: str = "") -> bool:
        return binary == "gnome-terminal"

    with patch.dict("os.environ", {}, clear=True):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("gnome_theme_manager.core.terminal_detector._schema_exists", return_value=False):
                with patch("pathlib.Path.is_symlink", return_value=False):
                    with patch("pathlib.Path.is_file", return_value=False):
                        with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", side_effect=mock_installed):
                            info = detect_default_terminal()
                            assert info.terminal_id == "gnome-terminal"
                            assert info.terminal_name == "GNOME Terminal"
                            assert info.binary == "gnome-terminal"
                            assert info.detection_method == "which"
                            assert info.is_installed is True
                            assert info.is_default is True


def test_case_c_headless_no_terminals() -> None:
    """Mock Case C: Headless server with no terminal installed or detectable."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("gnome_theme_manager.core.terminal_detector._schema_exists", return_value=False):
                with patch("pathlib.Path.is_symlink", return_value=False):
                    with patch("pathlib.Path.is_file", return_value=False):
                        with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=False):
                            info = detect_terminal()
                            assert info.terminal_id == "unknown"
                            assert info.terminal_name == "Unknown Terminal"
                            assert info.binary == ""
                            assert info.detection_method == "fallback"
                            assert info.is_installed is False
                            assert info.is_default is False
                            assert bool(info) is False


def test_env_ptyxis_detection() -> None:
    """Verify active session detected via PTYXIS_VERSION env var."""
    with patch.dict("os.environ", {"PTYXIS_VERSION": "47.0"}):
        with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
            info = _detect_from_environment()
            assert info is not None
            assert info.terminal_id == "ptyxis"
            assert info.detection_method == "env"


def test_env_term_program_detection() -> None:
    """Verify active session detected via TERM_PROGRAM env var."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "WezTerm"}):
        with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
            info = _detect_from_environment()
            assert info is not None
            assert info.terminal_id == "wezterm"
            assert info.detection_method == "env"


def test_env_custom_terminal_detection() -> None:
    """Verify active session detected via $TERMINAL env var."""
    with patch.dict("os.environ", {"TERMINAL": "alacritty"}):
        with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
            info = _detect_from_environment()
            assert info is not None
            assert info.terminal_id == "alacritty"
            assert info.detection_method == "env"


def test_process_tree_detection(tmp_path: Path) -> None:
    """Verify process tree inspection walks up to parent terminal."""
    fake_pid_dir = tmp_path / "12345"
    fake_pid_dir.mkdir(parents=True)
    (fake_pid_dir / "comm").write_text("ptyxis\n", encoding="utf-8")
    (fake_pid_dir / "status").write_text("PPid:\t1\n", encoding="utf-8")

    with patch("os.getppid", return_value=12345):
        with patch(
            "gnome_theme_manager.core.terminal_detector.Path",
            side_effect=lambda p: fake_pid_dir if "12345" in str(p) else Path(p),
        ):
            with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
                info = _detect_from_process_tree()
                assert info is not None
                assert info.terminal_id == "ptyxis"
                assert info.detection_method == "proc_tree"


def test_gsettings_default_terminal() -> None:
    """Verify default terminal detected via GNOME GSettings."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "'tilix'\n"

    with patch.dict("os.environ", {}, clear=True):
        with patch("gnome_theme_manager.core.terminal_detector._schema_exists", return_value=True):
            with patch("subprocess.run", return_value=mock_run):
                with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
                    info = detect_default_terminal()
                    assert info.terminal_id == "tilix"
                    assert info.detection_method == "gsettings"


def test_alternatives_default_terminal() -> None:
    """Verify default terminal detected via /etc/alternatives symlink."""
    fake_path = MagicMock()
    fake_path.is_symlink.return_value = True
    fake_path.is_file.return_value = True
    fake_path.resolve.return_value = Path("/usr/bin/xfce4-terminal.wrapper")

    with patch.dict("os.environ", {}, clear=True):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("gnome_theme_manager.core.terminal_detector._schema_exists", return_value=False):
                with patch(
                    "gnome_theme_manager.core.terminal_detector.Path",
                    side_effect=lambda p: fake_path if "x-terminal-emulator" in str(p) else Path(p),
                ):
                    with patch("gnome_theme_manager.core.terminal_detector.is_terminal_installed", return_value=True):
                        info = detect_default_terminal()
                        assert info.terminal_id == "xfce4-terminal"
                        assert info.detection_method == "alternatives"


def test_theme_manager_terminal_methods() -> None:
    """Verify ThemeManager facade delegates detect_terminal and detect_default_terminal."""
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
        "gnome_theme_manager.core.terminal_detector.detect_terminal",
        return_value=TerminalInfo("ptyxis", "Ptyxis", "ptyxis", "org.gnome.Ptyxis.desktop", "which", True, True),
    ):
        info = tm.detect_terminal()
        assert info.terminal_id == "ptyxis"

    with patch(
        "gnome_theme_manager.core.terminal_detector.detect_default_terminal",
        return_value=TerminalInfo("gnome-terminal", "GNOME Terminal", "gnome-terminal", "org.gnome.Terminal.desktop", "which", True, True),
    ):
        info_def = tm.detect_default_terminal()
        assert info_def.terminal_id == "gnome-terminal"
