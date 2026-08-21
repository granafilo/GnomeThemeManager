# SPDX-License-Identifier: GPL-3.0-or-later

"""Font configuration data structures and helpers (FASE 4 Task 4.3).

Encapsulates the active desktop font configuration (interface, document,
monospace fonts and text scaling factor) plus parsing utilities that split
a ``"Family Size"`` GSettings font-name string into its components.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Default values mirroring a fresh Ubuntu 24.04 / GNOME 46 installation.
DEFAULT_INTERFACE_FONT = "Cantarell 11"
DEFAULT_DOCUMENT_FONT = "Sans 11"
DEFAULT_MONOSPACE_FONT = "Monospace 11"
DEFAULT_TEXT_SCALING_FACTOR = 1.0

_FONT_NAME_RE = re.compile(r"^(?P<family>.+?)\s+(?P<size>\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class FontConfig:
    """Immutable representation of the active desktop font configuration.

    Each font field is a full GSettings ``font-name`` specification
    (e.g. ``"Cantarell 11"``). ``text_scaling_factor`` is a multiplier
    applied to all text on screen.
    """

    interface_font: str = DEFAULT_INTERFACE_FONT
    document_font: str = DEFAULT_DOCUMENT_FONT
    monospace_font: str = DEFAULT_MONOSPACE_FONT
    text_scaling_factor: float = DEFAULT_TEXT_SCALING_FACTOR

    def to_dict(self) -> dict[str, object]:
        """Serialize the configuration to a JSON-friendly dictionary."""
        return {
            "interface_font": self.interface_font,
            "document_font": self.document_font,
            "monospace_font": self.monospace_font,
            "text_scaling_factor": self.text_scaling_factor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> FontConfig:
        """Build a FontConfig from a dictionary, falling back to defaults.

        Args:
            data: Mapping with optional font configuration keys.

        Returns:
            A fully populated FontConfig instance.
        """
        if not data:
            return cls()

        def _as_str(value: object, default: str) -> str:
            return default if value is None else str(value)

        factor_raw = data.get("text_scaling_factor")
        factor: float = DEFAULT_TEXT_SCALING_FACTOR
        if factor_raw is not None:
            try:
                factor = float(str(factor_raw))
            except (TypeError, ValueError):
                factor = DEFAULT_TEXT_SCALING_FACTOR

        return cls(
            interface_font=_as_str(data.get("interface_font"), DEFAULT_INTERFACE_FONT),
            document_font=_as_str(data.get("document_font"), DEFAULT_DOCUMENT_FONT),
            monospace_font=_as_str(data.get("monospace_font"), DEFAULT_MONOSPACE_FONT),
            text_scaling_factor=factor,
        )

    @property
    def is_default(self) -> bool:
        """Return True if the configuration matches default GNOME values."""
        return (
            self.interface_font == DEFAULT_INTERFACE_FONT
            and self.document_font == DEFAULT_DOCUMENT_FONT
            and self.monospace_font == DEFAULT_MONOSPACE_FONT
            and self.text_scaling_factor == DEFAULT_TEXT_SCALING_FACTOR
        )


def parse_font_spec(font_spec: str) -> tuple[str, float]:
    """Parse a ``"Family Size"`` font-name string into family and size.

    Args:
        font_spec: GSettings font-name value (e.g. ``"Cantarell 11"``).

    Returns:
        A tuple ``(family, size)`` where ``family`` is the font family name
        and ``size`` is the numeric point size.

    Raises:
        ValueError: If the specification cannot be parsed.
    """
    if not font_spec or not font_spec.strip():
        raise ValueError("Font specification cannot be empty.")

    match = _FONT_NAME_RE.match(font_spec.strip())
    if match is None:
        raise ValueError(f"Invalid font specification: '{font_spec}'.")

    family = match.group("family").strip()
    size = float(match.group("size"))
    if not family:
        raise ValueError(f"Font family is empty in specification: '{font_spec}'.")
    return family, size


def format_font_spec(family: str, size: float) -> str:
    """Build a GSettings ``font-name`` string from family and size.

    Args:
        family: Font family name.
        size: Numeric point size.

    Returns:
        A ``"Family Size"`` formatted string.

    Raises:
        ValueError: If family is empty.
    """
    family = (family or "").strip()
    if not family:
        raise ValueError("Font family cannot be empty.")
    return f"{family} {size:g}"


def family_of(font_spec: str) -> str:
    """Return the family component of a font specification."""
    family, _ = parse_font_spec(font_spec)
    return family


def size_of(font_spec: str) -> float:
    """Return the size component of a font specification."""
    _, size = parse_font_spec(font_spec)
    return size
