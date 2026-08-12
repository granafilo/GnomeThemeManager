"""Test di unità per il modulo SandboxBridge e l'integrazione con Snap e Flatpak."""

from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.core.sandbox_bridge import SandboxBridge


# =============================================================================
# 1. Test Rilevamento Disponibilità Binari ($PATH)
# =============================================================================


def test_snap_available_detection() -> None:
    """Verifica che is_snap_available() ritorni True quando snap è presente."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value="/usr/bin/snap"):
        assert bridge.is_snap_available() is True


def test_snap_not_available() -> None:
    """Verifica che is_snap_available() ritorni False quando snap non è installato."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        assert bridge.is_snap_available() is False


def test_flatpak_available_detection() -> None:
    """Verifica che is_flatpak_available() ritorni True quando flatpak è presente."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value="/usr/bin/flatpak"):
        assert bridge.is_flatpak_available() is True


def test_flatpak_not_available() -> None:
    """Verifica che is_flatpak_available() ritorni False quando flatpak non è installato."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        assert bridge.is_flatpak_available() is False


# =============================================================================
# 2. Test get_sandbox_status()
# =============================================================================


def test_sandbox_status_all_active() -> None:
    """Verifica la corretta generazione di SandboxStatus quando entrambi i runtime sono attivi."""
    bridge = SandboxBridge()

    def mock_subprocess_run(cmd: list[str], **kwargs) -> MagicMock:  # noqa: ARG001
        res = MagicMock()
        res.returncode = 0
        if cmd[:3] == ["snap", "list", "gtk-common-themes"]:
            res.stdout = "Name               Version    Rev   Tracking  Publisher   Notes\ngtk-common-themes  0.1-81     2125  latest/stable  canonical✓  -"
        elif cmd[:4] == ["flatpak", "override", "--user", "--show"]:
            res.stdout = "[Context]\nfilesystems=~/.local/share/themes;~/.icons;\n"
        return res

    with patch("shutil.which", side_effect=lambda bin_name: f"/usr/bin/{bin_name}"), \
         patch("subprocess.run", side_effect=mock_subprocess_run):
        status: SandboxStatus = bridge.get_sandbox_status()
        assert status.snap_available is True
        assert status.flatpak_available is True
        assert status.snap_gtk_common_themes_installed is True
        assert status.flatpak_filesystem_override_active is True


def test_sandbox_status_not_available() -> None:
    """Verifica SandboxStatus quando né Snap né Flatpak sono installati."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        status: SandboxStatus = bridge.get_sandbox_status()
        assert status.snap_available is False
        assert status.flatpak_available is False
        assert status.snap_gtk_common_themes_installed is False
        assert status.flatpak_filesystem_override_active is False


# =============================================================================
# 3. Test Propagazione Flatpak
# =============================================================================


def test_propagate_to_flatpak_success() -> None:
    """Verifica che propagate_to_flatpak esegua i comandi corretti e ritorni flatpak_success=True."""
    bridge = SandboxBridge()
    executed_commands: list[list[str]] = []

    def mock_run(cmd: list[str], **kwargs) -> MagicMock:  # noqa: ARG001
        executed_commands.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stdout = ""
        res.stderr = ""
        return res

    with patch("shutil.which", return_value="/usr/bin/flatpak"), \
         patch("subprocess.run", side_effect=mock_run):
        result = bridge.propagate_to_flatpak(gtk_theme="Nordic", icon_theme="Papirus")

        assert result.flatpak_success is True
        assert len(result.warnings) == 0
        assert len(result.flatpak_messages) > 0
        # Verifica che tutti i comandi di override e le variabili d'ambiente siano stati eseguiti
        assert ["flatpak", "override", "--user", "--filesystem=~/.local/share/themes:ro"] in executed_commands
        assert ["flatpak", "override", "--user", "--filesystem=~/.themes:ro"] in executed_commands
        assert ["flatpak", "override", "--user", "--filesystem=~/.local/share/icons:ro"] in executed_commands
        assert ["flatpak", "override", "--user", "--filesystem=~/.icons:ro"] in executed_commands
        assert ["flatpak", "override", "--user", "--env=GTK_THEME=Nordic"] in executed_commands
        assert ["flatpak", "override", "--user", "--env=ICON_THEME=Papirus"] in executed_commands


def test_propagate_to_flatpak_not_installed() -> None:
    """Verifica che propagate_to_flatpak ritorni False senza chiamare subprocess se flatpak non esiste."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None), \
         patch("subprocess.run") as mock_run:
        result = bridge.propagate_to_flatpak(gtk_theme="Adwaita")
        assert result.flatpak_success is False
        mock_run.assert_not_called()


# =============================================================================
# 4. Test Propagazione e Compatibilità Snap
# =============================================================================


def test_propagate_to_snap_with_gtk_common_themes() -> None:
    """Verifica che un tema standard (es. Yaru) con gtk-common-themes installato dia esito positivo."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/snap"), \
         patch("subprocess.run", return_value=mock_res):
        result = bridge.propagate_to_snap(gtk_theme="Yaru", icon_theme="Yaru")
        assert result.snap_success is True
        assert len(result.warnings) == 0
        assert any("supportato nativamente" in m for m in result.snap_messages)


def test_propagate_to_snap_custom_theme_warning() -> None:
    """Verifica che un tema personalizzato non in gtk-common-themes produca un avviso informativo."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/snap"), \
         patch("subprocess.run", return_value=mock_res):
        result = bridge.propagate_to_snap(gtk_theme="Nordic-Darker", icon_theme="Papirus")
        assert result.snap_success is True
        assert len(result.warnings) == 1
        assert "non è incluso nel pacchetto standard" in result.warnings[0]
        assert "snap install nordic-darker-themes" in result.warnings[0]


def test_propagate_to_snap_not_installed() -> None:
    """Verifica che propagate_to_snap ritorni False se snap non è disponibile."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None), \
         patch("subprocess.run") as mock_run:
        result = bridge.propagate_to_snap(gtk_theme="Yaru")
        assert result.snap_success is False
        mock_run.assert_not_called()


def test_propagate_to_snap_no_gtk_common_themes() -> None:
    """Verifica che propagate_to_snap segnali warning se gtk-common-themes non è installato."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 1  # snap list fallito

    with patch("shutil.which", return_value="/usr/bin/snap"), \
         patch("subprocess.run", return_value=mock_res):
        result = bridge.propagate_to_snap(gtk_theme="Yaru")
        assert result.snap_success is False
        assert len(result.warnings) > 0
        assert "gtk-common-themes" in result.warnings[0]


# =============================================================================
# 5. Test propagate_all() e Unione Risultati
# =============================================================================


def test_propagate_all_combines_results() -> None:
    """Verifica che propagate_all unisca correttamente messaggi, warning e stati di Flatpak e Snap."""
    bridge = SandboxBridge()

    flatpak_stub = PropagationResult(
        flatpak_success=True,
        flatpak_messages=["Flatpak configurato."],
        warnings=[],
    )
    snap_stub = PropagationResult(
        snap_success=True,
        snap_messages=["Snap verificato."],
        warnings=["Avviso Snap custom theme."],
    )

    with patch.object(bridge, "propagate_to_flatpak", return_value=flatpak_stub), \
         patch.object(bridge, "propagate_to_snap", return_value=snap_stub):
        result = bridge.propagate_all(gtk_theme="Nordic", icon_theme="Papirus")

        assert result.flatpak_success is True
        assert result.snap_success is True
        assert result.flatpak_messages == ["Flatpak configurato."]
        assert result.snap_messages == ["Snap verificato."]
        assert result.warnings == ["Avviso Snap custom theme."]


# =============================================================================
# 6. Test Gestione Eccezioni e Timeout in Subprocess
# =============================================================================


def test_subprocess_timeout_handling() -> None:
    """Verifica che TimeoutExpired in subprocess.run venga gestito con warning senza crash."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value="/usr/bin/flatpak"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="flatpak override", timeout=10)):
        result = bridge.propagate_to_flatpak(gtk_theme="Nordic")
        assert result.flatpak_success is False
        assert len(result.warnings) > 0
        assert any("Timeout" in w for w in result.warnings)


def test_subprocess_error_handling() -> None:
    """Verifica che CalledProcessError in subprocess.run venga gestito con warning senza crash."""
    bridge = SandboxBridge()
    err = subprocess.CalledProcessError(returncode=1, cmd="flatpak override", stderr="Permission denied")
    with patch("shutil.which", return_value="/usr/bin/flatpak"), \
         patch("subprocess.run", side_effect=err):
        result = bridge.propagate_to_flatpak(gtk_theme="Nordic")
        assert result.flatpak_success is False
        assert len(result.warnings) > 0
        assert any("Permission denied" in w or "Errore" in w for w in result.warnings)


# =============================================================================
# 7. Test Integrazione con ThemeManager
# =============================================================================


def test_apply_themes_with_sandbox_propagation() -> None:
    """Verifica che ThemeManager.apply_themes invochi SandboxBridge e popoli sandbox_propagation."""
    mock_scanner = MagicMock()
    mock_scanner.find_theme.return_value = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic"),
        is_user_level=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True
    mock_linker = MagicMock()
    mock_linker.apply_override.return_value = True

    mock_sandbox = MagicMock()
    mock_sandbox.propagate_all.return_value = PropagationResult(
        flatpak_success=True,
        snap_success=True,
        flatpak_messages=["Flatpak OK"],
        snap_messages=["Snap OK"],
        warnings=[],
    )

    manager = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=mock_linker,
        sandbox_bridge=mock_sandbox,
    )

    res: ApplyResult = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=True)

    assert res.sandbox_propagation is not None
    assert res.sandbox_propagation.flatpak_success is True
    mock_sandbox.propagate_all.assert_called_once_with(gtk_theme="Nordic", icon_theme=None)


def test_apply_themes_no_sandbox_flag() -> None:
    """Verifica che con propagate_sandbox=False la propagazione sandbox non venga eseguita."""
    mock_scanner = MagicMock()
    mock_scanner.find_theme.return_value = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic"),
        is_user_level=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True
    mock_sandbox = MagicMock()

    manager = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        sandbox_bridge=mock_sandbox,
    )

    res: ApplyResult = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=False)

    assert res.sandbox_propagation is None
    mock_sandbox.propagate_all.assert_not_called()


def test_manager_system_status_includes_sandbox() -> None:
    """Verifica che get_system_status() includa sandbox_status."""
    mock_sandbox = MagicMock()
    mock_sandbox.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=True,
        snap_gtk_common_themes_installed=True,
        flatpak_filesystem_override_active=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True

    manager = ThemeManager(
        gsettings=mock_gsettings,
        sandbox_bridge=mock_sandbox,
    )

    status: SystemStatus = manager.get_system_status()
    assert status.sandbox_status is not None
    assert status.sandbox_status.snap_available is True
    assert status.sandbox_status.flatpak_available is True


# =============================================================================
# 8. Test CLI: sandbox-status e flag --no-sandbox
# =============================================================================


def test_cli_sandbox_status_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica che il comando CLI 'gnome-theme-manager sandbox-status' stampi lo stato corretto."""
    with patch("gnome_theme_manager.core.manager.ThemeManager.get_system_status") as mock_status:
        mock_status.return_value = SystemStatus(
            gsettings_available=True,
            shell_theme_supported=True,
            color_scheme_supported=True,
            user_themes_path=Path("/home/user/.local/share/themes"),
            user_icons_path=Path("/home/user/.local/share/icons"),
            sandbox_status=SandboxStatus(
                snap_available=True,
                flatpak_available=True,
                snap_gtk_common_themes_installed=True,
                flatpak_filesystem_override_active=False,
            ),
        )

        exit_code = main(["sandbox-status"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Stato Integrazione Sandbox" in captured.out
        assert "Snap:" in captured.out
        assert "Flatpak:" in captured.out


def test_cli_apply_no_sandbox_flag() -> None:
    """Verifica che il comando apply con flag --no-sandbox passi propagate_sandbox=False al manager."""
    with patch("gnome_theme_manager.core.manager.ThemeManager.apply_themes") as mock_apply, \
         patch("gnome_theme_manager.core.manager.ThemeManager.find_theme", return_value=True):
        mock_apply.return_value = ApplyResult(gtk_theme="Nordic", warnings=[])

        exit_code = main(["apply", "--gtk", "Nordic", "--no-sandbox"])
        assert exit_code == 0
        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs.get("propagate_sandbox") is False
