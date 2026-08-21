# SPDX-License-Identifier: GPL-3.0-or-later

"""Package contenente i controller delle pagine modulari della GUI GTK4/Libadwaita (Fase 5.2)."""

from .editor_view import ThemeEditorPage
from .fonts import FontsPage
from .global_themes import GlobalThemesPage
from .installer import InstallerPage
from .sandbox import SandboxPage
from .status import StatusPage
from .themes import ThemesPage

__all__ = [
    "FontsPage",
    "GlobalThemesPage",
    "InstallerPage",
    "SandboxPage",
    "StatusPage",
    "ThemeEditorPage",
    "ThemesPage",
]
