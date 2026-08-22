# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exceptions for the Snap Theme Manager subsystem."""

from __future__ import annotations


class ThemeSnapError(Exception):
    """Base exception for all snap theme manager errors."""


class BuildError(ThemeSnapError):
    """Raised when building or compiling a content snap fails."""


class ConnectionError(ThemeSnapError):
    """Raised when connecting or disconnecting a snap slot/plug fails."""


class ValidationError(ThemeSnapError):
    """Raised when verifying a theme mount inside a snap environment fails."""


class SnapPermissionError(ThemeSnapError):
    """Raised when required sudo or snap administration permissions are missing."""
