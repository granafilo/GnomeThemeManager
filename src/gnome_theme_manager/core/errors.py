"""Gerarchia delle eccezioni personalizzate per GnomeThemeManager."""


class GnomeThemeManagerError(Exception):
    """Eccezione base per tutti gli errori del package."""


class GSettingsUnavailableError(GnomeThemeManagerError):
    """Sollevata quando PyGObject o lo schema GSettings non è disponibile."""


class ThemeNotFoundError(GnomeThemeManagerError):
    """Sollevata quando un tema specificato non viene trovato nel filesystem."""


class ThemeValidationError(GnomeThemeManagerError):
    """Sollevata quando la struttura di un tema estratto non è valida."""


class ArchiveExtractionError(GnomeThemeManagerError):
    """Sollevata durante errori di estrazione o violazioni di sicurezza negli archivi."""
