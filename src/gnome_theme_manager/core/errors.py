# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exception hierarchy for GnomeThemeManager."""


class GnomeThemeManagerError(Exception):
    """Base exception for all errors in GnomeThemeManager.

    Serves as the parent class to catch any domain-specific anomalies raised
    by core subsystems of the theme manager.
    """


class GSettingsUnavailableError(GnomeThemeManagerError):
    """Raised when PyGObject or the required GSettings schema is unavailable on the system.

    This may happen if executed outside a GNOME desktop environment or if
    system packages like python3-gi / libglib2.0 are missing.
    """


class ThemeNotFoundError(GnomeThemeManagerError):
    """Raised when a theme specified by name or type is not found on the filesystem."""


class ThemeValidationError(GnomeThemeManagerError):
    """Raised when the structure of an extracted theme is invalid or unsupported."""


class ArchiveExtractionError(GnomeThemeManagerError):
    """Raised during archive extraction failures or security policy violations (e.g. Zip Slip)."""


class ThemeApplyError(GnomeThemeManagerError):
    """Raised for errors while applying themes."""


class ThemeBackupError(GnomeThemeManagerError):
    """Raised for errors creating theme backups."""


class ThemeRollbackError(GnomeThemeManagerError):
    """Raised when restoring or rolling back a theme fails."""


class SandboxCommandError(GnomeThemeManagerError):
    """Raised for timeouts, unavailable commands, or unexpected exit codes from Flatpak/Snap."""


class StoreError(GnomeThemeManagerError):
    """Base exception for all online store API and communication failures."""


class StoreItemNotFoundError(StoreError):
    """Raised when an item requested from the store is not found."""


class StoreDownloadError(StoreError):
    """Raised when downloading a file or archive from the store fails."""


class StoreNetworkError(StoreError):
    """Raised when network connectivity or API timeout issues occur."""
