"""Package contenente i controller delle pagine modulari della GUI GTK4/Libadwaita (Fase 5.2)."""

from .installer import InstallerPage
from .presets import PresetsPage
from .sandbox import SandboxPage
from .status import StatusPage
from .themes import ThemesPage

__all__ = [
    "InstallerPage",
    "PresetsPage",
    "SandboxPage",
    "StatusPage",
    "ThemesPage",
]
