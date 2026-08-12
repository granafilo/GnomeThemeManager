"""Modelli di dati del dominio per temi e configurazioni."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


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
    gtk_theme: str | None = None
    icon_theme: str | None = None
    cursor_theme: str | None = None
    color_scheme: str | None = None
    shell_theme: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Converte il set di temi in un dizionario serializzabile in JSON.

        Returns:
            Dizionario con le chiavi dei componenti del tema e i relativi valori.
        """
        return {
            "gtk_theme": self.gtk_theme,
            "icon_theme": self.icon_theme,
            "cursor_theme": self.cursor_theme,
            "color_scheme": self.color_scheme,
            "shell_theme": self.shell_theme,
        }

    def as_dict(self) -> dict[str, str | None]:
        """Alias retrocompatibile per to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThemeSet":
        """Ricostruisce un'istanza di ThemeSet a partire da un dizionario.

        Args:
            data: Dizionario contenente le configurazioni dei temi.

        Returns:
            Nuova istanza di ThemeSet popolata con i valori del dizionario.
        """
        return cls(
            gtk_theme=data.get("gtk_theme"),
            icon_theme=data.get("icon_theme"),
            cursor_theme=data.get("cursor_theme"),
            color_scheme=data.get("color_scheme"),
            shell_theme=data.get("shell_theme"),
        )

    def is_empty(self) -> bool:
        """Verifica se nessuna proprietà del tema è valorizzata.

        Returns:
            True se tutte le proprietà sono None o stringhe vuote, False altrimenti.
        """
        return not any([
            self.gtk_theme,
            self.icon_theme,
            self.cursor_theme,
            self.color_scheme,
            self.shell_theme,
        ])

    def merge(self, other: "ThemeSet") -> "ThemeSet":
        """Fonde l'istanza corrente con un'altra, dando precedenza ai valori non nulli di other.

        Args:
            other: L'altro ThemeSet da cui prendere i valori aggiornati.

        Returns:
            Nuova istanza di ThemeSet con i valori uniti.
        """
        return ThemeSet(
            gtk_theme=other.gtk_theme if other.gtk_theme is not None else self.gtk_theme,
            icon_theme=other.icon_theme if other.icon_theme is not None else self.icon_theme,
            cursor_theme=other.cursor_theme if other.cursor_theme is not None else self.cursor_theme,
            color_scheme=other.color_scheme if other.color_scheme is not None else self.color_scheme,
            shell_theme=other.shell_theme if other.shell_theme is not None else self.shell_theme,
        )


@dataclass
class SandboxStatus:
    """Stato dei runtime sandbox (Snap/Flatpak) rilevati sul sistema."""
    snap_available: bool = False
    flatpak_available: bool = False
    snap_gtk_common_themes_installed: bool = False
    flatpak_filesystem_override_active: bool = False


@dataclass
class PropagationResult:
    """Risultato della propagazione tema ai sistemi sandbox."""
    flatpak_success: bool = False
    snap_success: bool = False
    flatpak_messages: list[str] = field(default_factory=list)
    snap_messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    """Risultato dettagliato dell'applicazione di un set o preset di temi."""
    gtk_theme: str | None = None
    gtk4_override_applied: bool = False
    icon_theme: str | None = None
    cursor_theme: str | None = None
    shell_theme: str | None = None
    color_scheme: str | None = None
    warnings: list[str] = field(default_factory=list)
    sandbox_propagation: PropagationResult | None = None


@dataclass
class SystemStatus:
    """Stato di diagnostica, compatibilità e percorsi attivi del sistema GNOME."""
    gsettings_available: bool
    shell_theme_supported: bool
    color_scheme_supported: bool
    user_themes_path: Path
    user_icons_path: Path
    sandbox_status: SandboxStatus | None = None
