# SPDX-License-Identifier: GPL-3.0-or-later

"""Domain data models for themes and configurations."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .gsettings import Gtk4OverrideStatus


class ThemeType(str, Enum):
    """Managed theme type."""

    GTK = "gtk"
    ICON = "icon"
    CURSOR = "cursor"
    SHELL = "shell"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Theme:
    """Representation of an individual theme installed on the filesystem."""

    name: str
    theme_type: ThemeType
    path: Path
    is_user_level: bool
    invalid: bool = False
    inheritance_chain: list[str] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        """Check if the theme path exists on the filesystem."""
        return self.path.exists() and self.path.is_dir()


@dataclass
class ThemeSet:
    """Configured or active theme set on the GNOME desktop."""

    gtk_theme: str | None = None
    icon_theme: str | None = None
    cursor_theme: str | None = None
    color_scheme: str | None = None
    shell_theme: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert theme set into a JSON-serializable dictionary.

        Returns:
            Dictionary with theme component keys and values.
        """
        return {
            "gtk_theme": self.gtk_theme,
            "icon_theme": self.icon_theme,
            "cursor_theme": self.cursor_theme,
            "color_scheme": self.color_scheme,
            "shell_theme": self.shell_theme,
        }

    def as_dict(self) -> dict[str, str | None]:
        """Backward-compatible alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThemeSet":
        """Construct a ThemeSet instance from a dictionary.

        Args:
            data: Dictionary containing theme configurations.

        Returns:
            Populated ThemeSet instance.
        """
        return cls(
            gtk_theme=data.get("gtk_theme"),
            icon_theme=data.get("icon_theme"),
            cursor_theme=data.get("cursor_theme"),
            color_scheme=data.get("color_scheme"),
            shell_theme=data.get("shell_theme"),
        )

    def is_empty(self) -> bool:
        """Check if no theme properties are defined.

        Returns:
            True if all properties are None or empty strings, False otherwise.
        """
        return not any(
            [
                self.gtk_theme,
                self.icon_theme,
                self.cursor_theme,
                self.color_scheme,
                self.shell_theme,
            ]
        )

    def merge(self, other: "ThemeSet") -> "ThemeSet":
        """Merge current instance with another, preferring non-null values from other.

        Args:
            other: Another ThemeSet to take updated values from.

        Returns:
            New merged ThemeSet instance.
        """
        return ThemeSet(
            gtk_theme=other.gtk_theme if other.gtk_theme is not None else self.gtk_theme,
            icon_theme=other.icon_theme if other.icon_theme is not None else self.icon_theme,
            cursor_theme=other.cursor_theme
            if other.cursor_theme is not None
            else self.cursor_theme,
            color_scheme=other.color_scheme
            if other.color_scheme is not None
            else self.color_scheme,
            shell_theme=other.shell_theme if other.shell_theme is not None else self.shell_theme,
        )


@dataclass
class SandboxStatus:
    """Status of sandbox runtimes (Snap/Flatpak) detected on the system."""

    snap_available: bool = False
    flatpak_available: bool = False
    snap_gtk_common_themes_installed: bool = False
    flatpak_filesystem_override_active: bool = False


@dataclass
class PropagationResult:
    """Result of theme propagation to sandbox environments."""

    flatpak_success: bool = False
    snap_success: bool = False
    flatpak_messages: list[str] = field(default_factory=list)
    snap_messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    """Detailed result of applying a theme set or preset."""

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
    """Diagnostic status, compatibility, and active paths for the GNOME system."""

    gsettings_available: bool
    shell_theme_supported: bool
    color_scheme_supported: bool
    user_themes_path: Path
    user_icons_path: Path
    sandbox_status: SandboxStatus | None = None
    gtk4_override_active: bool = False
    gtk4_override_status: "Gtk4OverrideStatus | None" = None
