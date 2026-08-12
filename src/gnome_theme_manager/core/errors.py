"""Gerarchia delle eccezioni personalizzate per GnomeThemeManager."""


class GnomeThemeManagerError(Exception):
    """Eccezione base per tutti gli errori del package GnomeThemeManager.

    Funge da classe genitore per catturare qualsiasi anomalia specifica sollevata
    dai vari sottosistemi core del gestore temi.
    """


class GSettingsUnavailableError(GnomeThemeManagerError):
    """Sollevata quando PyGObject o lo schema GSettings richiesto non è disponibile nel sistema.

    Questo può accadere se l'applicazione viene eseguita al di fuori di un ambiente desktop
    GNOME o se mancano i pacchetti di sistema `python3-gi` / `libglib2.0`.
    """


class ThemeNotFoundError(GnomeThemeManagerError):
    """Sollevata quando un tema specificato per nome o tipologia non viene trovato sul filesystem.

    Verificata dallo scanner prima di procedere con l'applicazione di modifiche ai temi.
    """


class ThemeValidationError(GnomeThemeManagerError):
    """Sollevata quando la struttura di un tema estratto non è valida o non è supportata.

    Viene generata se mancano i file descrittori minimi o se la cartella non rispetta
    alcuno dei layout noti (GTK, icone, cursori, shell).
    """


class ArchiveExtractionError(GnomeThemeManagerError):
    """Sollevata durante errori di estrazione o violazioni di sicurezza negli archivi compressi.

    Include casi di file corrotti, formati non supportati o rilevamenti di attacchi
    di tipo Path Traversal (es. ZipSlip).
    """
