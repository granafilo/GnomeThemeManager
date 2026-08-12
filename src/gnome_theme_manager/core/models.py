"""Modelli di dati del dominio per temi e configurazioni."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ThemeType(str, Enum):
    """Tipologia di tema gestito."""
    GTK = "gtk"
    ICON = "icon"
    CURSOR = "cursor"
    SHELL = "shell"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Theme:
    """Rappresentazione di un singolo tema installato sul filesystem."""
    name: str
    theme_type: ThemeType
    path: Path
    is_user_level: bool

    @property
    def exists(self) -> bool:
        """Verifica se il percorso del tema esiste realmente."""
        return self.path.exists() and self.path.is_dir()


@dataclass
class ThemeSet:
    """Insieme di temi configurati/attivi sul desktop GNOME."""
    gtk_theme: Optional[str] = None
    icon_theme: Optional[str] = None
    cursor_theme: Optional[str] = None
    color_scheme: Optional[str] = None
    shell_theme: Optional[str] = None

    def as_dict(self) -> dict[str, Optional[str]]:
        """Converte il set di temi in un dizionario serializzabile."""
        return {
            "gtk_theme": self.gtk_theme,
            "icon_theme": self.icon_theme,
            "cursor_theme": self.cursor_theme,
            "color_scheme": self.color_scheme,
            "shell_theme": self.shell_theme,
        }
