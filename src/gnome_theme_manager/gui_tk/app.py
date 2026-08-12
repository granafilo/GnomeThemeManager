"""Finestra principale e ciclo dell'applicazione GUI Tkinter (GnomeThemeManager).

Questo modulo implementa la classe principale `ThemeManagerWindow` che estende `tk.Tk`,
configurando il layout con `ttk.Notebook`, lo stile moderno (`clam`), la barra di stato
e il coordinamento reattivo tra le diverse schede tramite il Facade `ThemeManager`.
"""

import logging
import tkinter as tk
from tkinter import ttk

from .. import __version__
from ..core.manager import ThemeManager
from .views import (
    AvailableThemesView,
    CurrentStatusView,
    PresetManagerView,
    ThemeInstallerView,
)

logger = logging.getLogger("gnome_theme_manager.gui_tk.app")


class ThemeManagerWindow(tk.Tk):
    """Finestra principale dell'applicazione Gnome Theme Manager in Tkinter."""

    def __init__(self, manager: ThemeManager | None = None) -> None:
        """Inizializza la finestra principale e tutti i componenti visuali.

        Args:
            manager: Istanza opzionale di ThemeManager. Se omessa, ne viene creata una nuova.
        """
        super().__init__()

        # Facade Core: business logic e integrazione GSettings/filesystem
        self.manager = manager or ThemeManager()

        # Configurazione proprietà della finestra
        self.title(f"Gnome Theme Manager v{__version__}")
        self.geometry("860x620")
        self.minsize(750, 500)

        # Variabile per i messaggi nella barra di stato inferiore
        self.var_status_bar = tk.StringVar(value="Pronto.")

        # Configurazione stili ed elementi grafici
        self._setup_styles()
        self._center_window(860, 620)
        self._build_layout()

    def _setup_styles(self) -> None:
        """Configura il tema e gli stili dei widget TTK per un aspetto moderno e pulito."""
        self.style = ttk.Style(self)

        # Prova ad applicare il tema 'clam' o usa quello predefinito
        available_themes = self.style.theme_names()
        if "clam" in available_themes:
            self.style.theme_use("clam")

        # Personalizzazione dei font e padding generali
        self.style.configure(".", font=("Sans", 10))
        self.style.configure("TNotebook", tabposition="n", padding=2)
        self.style.configure("TNotebook.Tab", padding=[14, 8], font=("Sans", 10, "bold"))
        self.style.configure("Header.TLabel", font=("Sans", 14, "bold"))
        self.style.configure("SubHeader.TLabel", font=("Sans", 9), foreground="#555555")
        self.style.configure("Treeview.Heading", font=("Sans", 9, "bold"))
        self.style.configure("Treeview", rowheight=24)

    def _center_window(self, width: int, height: int) -> None:
        """Centra la finestra sullo schermo dell'utente.

        Args:
            width: Larghezza desiderata in pixel.
            height: Altezza desiderata in pixel.
        """
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_layout(self) -> None:
        """Costruisce l'architettura a schede e la barra di stato dell'interfaccia."""
        # 1. Header Superiore (Branding / Titolo)
        header_frame = ttk.Frame(self, padding=(16, 12, 16, 8))
        header_frame.pack(fill=tk.X, expand=False)

        lbl_title = ttk.Label(
            header_frame,
            text="🎨 Gnome Theme Manager",
            style="Header.TLabel",
        )
        lbl_title.pack(side=tk.LEFT, anchor=tk.W)

        lbl_subtitle = ttk.Label(
            header_frame,
            text=f"Gestione avanzata e modulare dei temi per Ubuntu / GNOME • v{__version__}",
            style="SubHeader.TLabel",
        )
        lbl_subtitle.pack(side=tk.LEFT, anchor=tk.W, padx=(12, 0), pady=(4, 0))

        btn_refresh_all = ttk.Button(
            header_frame,
            text="🔄 Aggiorna Tutto",
            command=self.refresh_all_views,
        )
        btn_refresh_all.pack(side=tk.RIGHT)

        # Separatore visivo
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=(0, 4))

        # 2. Contenitore a Schede (ttk.Notebook)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))

        # Creazione e aggiunta delle 4 viste specializzate
        self.status_view = CurrentStatusView(
            self.notebook,
            manager=self.manager,
            on_status_change=self._on_status_updated,
        )
        self.themes_view = AvailableThemesView(
            self.notebook,
            manager=self.manager,
            on_theme_applied=self._on_theme_applied,
        )
        self.preset_view = PresetManagerView(
            self.notebook,
            manager=self.manager,
            on_preset_applied=self._on_preset_applied,
        )
        self.installer_view = ThemeInstallerView(
            self.notebook,
            manager=self.manager,
            on_installation_success=self._on_installation_success,
        )

        self.notebook.add(self.status_view, text="  📊 Stato Attuale  ")
        self.notebook.add(self.themes_view, text="  📂 Temi Disponibili  ")
        self.notebook.add(self.preset_view, text="  ⭐ Gestione Preset  ")
        self.notebook.add(self.installer_view, text="  📦 Installa Archivio  ")

        # 3. Barra di Stato Inferiore (StatusBar)
        status_frame = ttk.Frame(self, padding=(12, 4, 12, 6))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, side=tk.BOTTOM)

        lbl_statusbar = ttk.Label(
            status_frame,
            textvariable=self.var_status_bar,
            font=("Sans", 9),
            anchor=tk.W,
        )
        lbl_statusbar.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def set_status_message(self, message: str) -> None:
        """Aggiorna il messaggio informativo visualizzato nella barra di stato.

        Args:
            message: Testo del messaggio da visualizzare.
        """
        self.var_status_bar.set(message)
        logger.debug("StatusBar: %s", message)

    def refresh_all_views(self) -> None:
        """Ricarica i dati in tutte le schede della finestra."""
        self.set_status_message("Ricaricamento globale dei dati in corso...")
        self.status_view.refresh_status()
        self.themes_view.refresh_themes()
        self.preset_view.refresh_presets()
        self.set_status_message("Dati aggiornati correttamente.")

    # -------------------------------------------------------------------------
    # Callback di coordinamento tra schede
    # -------------------------------------------------------------------------

    def _on_theme_applied(self) -> None:
        """Invocato quando un tema viene applicato dalla scheda Temi."""
        self.status_view.refresh_status()
        self.set_status_message("Nuovo tema applicato al desktop.")

    def _on_preset_applied(self) -> None:
        """Invocato quando un preset viene applicato dalla scheda Preset."""
        self.status_view.refresh_status()
        self.set_status_message("Preset applicato con successo.")

    def _on_installation_success(self) -> None:
        """Invocato dopo un'installazione riuscita da archivio."""
        self.themes_view.refresh_themes()
        self.set_status_message("Archivio installato. Elenco temi aggiornato.")

    def _on_status_updated(self) -> None:
        """Invocato quando lo stato viene aggiornato manualmente."""
        self.set_status_message("Stato desktop aggiornato.")


def launch_gui(manager: ThemeManager | None = None) -> int:
    """Punto di ingresso principale per avviare l'interfaccia grafica Tkinter.

    Args:
        manager: Istanza Facade di ThemeManager (opzionale).

    Returns:
        Codice di uscita dell'applicazione (0 in caso di chiusura normale).
    """
    logger.info("Avvio dell'interfaccia grafica Tkinter...")
    app = ThemeManagerWindow(manager=manager)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera ricevuta, chiusura della GUI.")
    return 0
