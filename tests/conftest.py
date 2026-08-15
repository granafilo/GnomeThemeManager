# SPDX-License-Identifier: GPL-3.0-or-later

"""Configurazione globale e fixture per pytest."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.gsettings import Gtk4OverrideStatus
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)


@pytest.fixture
def dummy_user_theme_dir(tmp_path: Path) -> Path:
    """Crea una directory temporanea con una finta struttura di temi utente."""
    themes_dir = tmp_path / ".local" / "share" / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)

    # Creazione tema GTK dummy
    nordic_dir = themes_dir / "Nordic" / "gtk-3.0"
    nordic_dir.mkdir(parents=True, exist_ok=True)
    (nordic_dir / "gtk.css").write_text("/* dummy gtk css */")

    return themes_dir


@pytest.fixture
def mock_theme_manager() -> MagicMock:
    """Crea un mock deterministico di ThemeManager con dati validi completi."""
    mgr = MagicMock(spec=ThemeManager)
    mgr.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        color_scheme="default",
        shell_theme="Yaru",
    )
    mgr.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=SandboxStatus(
            snap_available=True,
            flatpak_available=True,
            snap_gtk_common_themes_installed=True,
            flatpak_filesystem_override_active=True,
        ),
        gtk4_override_active=True,
        gtk4_override_status=Gtk4OverrideStatus.ACTIVE,
    )
    mgr.find_theme.return_value = Theme(
        name="Yaru",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/Yaru"),
        is_user_level=False,
    )
    mgr.list_themes.return_value = [
        Theme(
            name="Yaru",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/Yaru"),
            is_user_level=False,
        ),
        Theme(
            name="Nordic",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/Nordic"),
            is_user_level=True,
        ),
        Theme(
            name="Papirus",
            theme_type=ThemeType.ICON,
            path=Path("/usr/share/icons/Papirus"),
            is_user_level=False,
        ),
        Theme(
            name="Bibata-Modern-Classic",
            theme_type=ThemeType.CURSOR,
            path=Path("/home/user/.local/share/icons/Bibata-Modern-Classic"),
            is_user_level=True,
        ),
        Theme(
            name="Nordic-Shell",
            theme_type=ThemeType.SHELL,
            path=Path("/home/user/.local/share/themes/Nordic-Shell"),
            is_user_level=True,
        ),
    ]
    def mock_apply_component(component, theme_name, *args, **kwargs):
        res_kwargs = {
            "gtk_theme": theme_name if component == ThemeType.GTK else None,
            "icon_theme": theme_name if component == ThemeType.ICON else None,
            "cursor_theme": theme_name if component == ThemeType.CURSOR else None,
            "shell_theme": theme_name if component == ThemeType.SHELL else None,
            "gtk4_override_applied": component == ThemeType.GTK,
            "warnings": [],
        }
        # In caso di specifici mock di errori impostati nel test su apply_themes, propagali
        if isinstance(mgr.apply_themes.side_effect, Exception):
            raise mgr.apply_themes.side_effect
        if isinstance(mgr.apply_themes.return_value, ApplyResult):
            # Se il test ha modificato il valore di ritorno di apply_themes, adeguiamoci
            val = mgr.apply_themes.return_value
            if val.shell_theme is None and component == ThemeType.SHELL:
                res_kwargs["shell_theme"] = None
                if val.warnings:
                    res_kwargs["warnings"] = val.warnings
            if val.warnings and not res_kwargs["warnings"]:
                res_kwargs["warnings"] = val.warnings
            if val.gtk4_override_applied is not None:
                res_kwargs["gtk4_override_applied"] = val.gtk4_override_applied
        return ApplyResult(**res_kwargs)

    mgr.apply_component.side_effect = mock_apply_component
    return mgr
