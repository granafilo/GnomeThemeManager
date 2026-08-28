# SPDX-License-Identifier: GPL-3.0-or-later

"""Package contenente i controller delle pagine modulari della GUI GTK4/Libadwaita (Fase 5.2)."""

from .editor_view import ThemeEditorPage
from .extensions import ExtensionsPage
from .fonts import FontsPage
from .global_themes import GlobalThemesPage
from .installer import InstallerPage
from .sandbox import SandboxPage
from .status import StatusPage
from .store import StorePage
from .terminal import TerminalPage
from .themes import ThemesPage

__all__ = [
    "ExtensionsPage",
    "FontsPage",
    "GlobalThemesPage",
    "InstallerPage",
    "SandboxPage",
    "StatusPage",
    "StorePage",
    "TerminalPage",
    "ThemeEditorPage",
    "ThemesPage",
]
