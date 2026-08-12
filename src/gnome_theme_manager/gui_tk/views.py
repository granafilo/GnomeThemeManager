"""Viste e schede modulari per l'interfaccia grafica Tkinter.

Questo modulo implementa i componenti visuali (Frame) ospitati nel Notebook dell'applicazione:
1. `CurrentStatusView`: Visualizza la configurazione attiva su GNOME e la diagnostica.
2. `AvailableThemesView`: Tabella interattiva per visualizzare, filtrare, applicare e rimuovere temi.
3. `PresetManagerView`: Gestione completa dei profili e preset di configurazione.
4. `ThemeInstallerView`: Selezione ed estrazione di archivi compressi di temi.

Ciascuna vista è disaccoppiata e interagisce esclusivamente con l'istanza di `ThemeManager`.
"""

import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Callable

from ..core.errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from ..core.models import SystemStatus, Theme, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ..core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_tk.views")


# =============================================================================
# 1. Scheda: Stato Attuale e Diagnostica
# =============================================================================


class CurrentStatusView(ttk.Frame):
    """Scheda per visualizzare la configurazione attiva del desktop GNOME e la diagnostica."""

    def __init__(
        self,
        parent: ttk.Notebook,
        manager: "ThemeManager",
        on_status_change: Callable[[], None] | None = None,
    ) -> None:
        """Inizializza la vista dello stato attuale.

        Args:
            parent: Widget genitore (il Notebook principale).
            manager: Istanza Facade di ThemeManager.
            on_status_change: Callback opzionale da invocare quando lo stato cambia.
        """
        super().__init__(parent, padding=16)
        self.manager = manager
        self.on_status_change = on_status_change

        # Variabili Tkinter reattive per memorizzare i valori correnti
        self.var_gtk = tk.StringVar(value="Caricamento...")
        self.var_icon = tk.StringVar(value="Caricamento...")
        self.var_cursor = tk.StringVar(value="Caricamento...")
        self.var_shell = tk.StringVar(value="Caricamento...")
        self.var_color_scheme = tk.StringVar(value="Caricamento...")

        # Variabili diagnostiche di sistema
        self.var_gsettings_status = tk.StringVar(value="Verifica...")
        self.var_shell_extension = tk.StringVar(value="Verifica...")
        self.var_user_themes_path = tk.StringVar(value="")
        self.var_user_icons_path = tk.StringVar(value="")

        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        """Costruisce il layout della scheda."""
        # Sezione 1: Temi Attualmente Applicati
        themes_frame = ttk.LabelFrame(self, text=" Temi Attivi sul Desktop GNOME ", padding=14)
        themes_frame.pack(fill=tk.X, expand=False, pady=(0, 14))

        # Creazione di una griglia a 2 colonne (Etichetta | Valore Corrente)
        fields = [
            ("Tema GTK (Applicazioni):", self.var_gtk),
            ("Tema Icone:", self.var_icon),
            ("Tema Cursori:", self.var_cursor),
            ("Tema GNOME Shell:", self.var_shell),
            ("Schema Colori (Chiaro/Scuro):", self.var_color_scheme),
        ]

        for row_idx, (label_text, var) in enumerate(fields):
            lbl_title = ttk.Label(themes_frame, text=label_text, font=("Sans", 10, "bold"))
            lbl_title.grid(row=row_idx, column=0, sticky=tk.W, padx=6, pady=4)

            lbl_value = ttk.Label(themes_frame, textvariable=var, font=("Sans", 10))
            lbl_value.grid(row=row_idx, column=1, sticky=tk.W, padx=6, pady=4)

        # Sezione 2: Diagnostica e Percorsi di Sistema
        diag_frame = ttk.LabelFrame(self, text=" Diagnostica e Compatibilità Sistema ", padding=14)
        diag_frame.pack(fill=tk.X, expand=False, pady=(0, 14))

        diag_fields = [
            ("Stato GSettings / dconf:", self.var_gsettings_status),
            ("Estensione User Themes (Shell):", self.var_shell_extension),
            ("Cartella Temi Utente:", self.var_user_themes_path),
            ("Cartella Icone Utente:", self.var_user_icons_path),
        ]

        for row_idx, (label_text, var) in enumerate(diag_fields):
            lbl_title = ttk.Label(diag_frame, text=label_text, font=("Sans", 9, "bold"))
            lbl_title.grid(row=row_idx, column=0, sticky=tk.W, padx=6, pady=3)

            lbl_value = ttk.Label(diag_frame, textvariable=var, font=("Sans", 9))
            lbl_value.grid(row=row_idx, column=1, sticky=tk.W, padx=6, pady=3)

        # Sezione 3: Barra Azioni
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill=tk.X, expand=False, pady=8)

        btn_refresh = ttk.Button(
            actions_frame,
            text="🔄 Aggiorna Stato",
            command=self.refresh_status,
        )
        btn_refresh.pack(side=tk.LEFT, padx=(0, 8))

    def refresh_status(self) -> None:
        """Ricarica la configurazione corrente dei temi e lo stato diagnostico."""
        try:
            # 1. Recupero temi attivi
            current: ThemeSet = self.manager.get_current_themes()
            self.var_gtk.set(current.gtk_theme or "Non configurato")
            self.var_icon.set(current.icon_theme or "Non configurato")
            self.var_cursor.set(current.cursor_theme or "Non configurato")
            self.var_shell.set(current.shell_theme or "Default di sistema / Non attivo")
            self.var_color_scheme.set(current.color_scheme or "default")
        except GSettingsUnavailableError as err:
            logger.warning("GSettings non disponibile durante il refresh dello stato: %s", err)
            self.var_gtk.set("Non disponibile (GSettings assente)")
            self.var_icon.set("Non disponibile")
            self.var_cursor.set("Non disponibile")
            self.var_shell.set("Non disponibile")
            self.var_color_scheme.set("Non disponibile")
        except Exception as err:  # noqa: BLE001
            logger.error("Errore imprevisto nel recupero dei temi attivi: %s", err)
            self.var_gtk.set(f"Errore: {err}")

        try:
            # 2. Recupero diagnostica di sistema
            status: SystemStatus = self.manager.get_system_status()
            gsettings_text = "✅ Disponibile e funzionante" if status.gsettings_available else "❌ Non disponibile"
            shell_text = "✅ Installata e supportata" if status.shell_theme_supported else "⚠️ Non rilevata (schema assente)"

            self.var_gsettings_status.set(gsettings_text)
            self.var_shell_extension.set(shell_text)
            self.var_user_themes_path.set(str(status.user_themes_path))
            self.var_user_icons_path.set(str(status.user_icons_path))
        except Exception as err:  # noqa: BLE001
            logger.warning("Errore nel recupero dello stato di sistema: %s", err)


# =============================================================================
# 2. Scheda: Temi Disponibili (Esplora e Applica)
# =============================================================================


class AvailableThemesView(ttk.Frame):
    """Scheda per visualizzare, filtrare, applicare e rimuovere i temi installati."""

    def __init__(
        self,
        parent: ttk.Notebook,
        manager: "ThemeManager",
        on_theme_applied: Callable[[], None] | None = None,
    ) -> None:
        """Inizializza la vista dei temi disponibili.

        Args:
            parent: Widget genitore.
            manager: Istanza di ThemeManager.
            on_theme_applied: Callback da eseguire dopo l'applicazione di un tema.
        """
        super().__init__(parent, padding=12)
        self.manager = manager
        self.on_theme_applied = on_theme_applied

        # Mappa per convertire le opzioni del combobox in ThemeType
        self.type_filter_options = {
            "Tutti i tipi": None,
            "GTK (Applicazioni)": ThemeType.GTK,
            "Icone": ThemeType.ICON,
            "Cursori": ThemeType.CURSOR,
            "GNOME Shell": ThemeType.SHELL,
        }

        # Variabili di filtro
        self.var_type_filter = tk.StringVar(value="Tutti i tipi")
        self.var_user_only = tk.BooleanVar(value=False)
        self.var_search_query = tk.StringVar(value="")
        self.var_apply_gtk4_override = tk.BooleanVar(value=True)

        # Cache locale dei temi scansionati per facilitare il filtraggio rapido
        self._cached_themes: list[Theme] = []

        self._build_ui()
        self.refresh_themes()

    def _build_ui(self) -> None:
        """Costruisce i componenti dell'interfaccia utente."""
        # 1. Barra Filtri Superiore
        filter_frame = ttk.LabelFrame(self, text=" Filtri di Ricerca ", padding=8)
        filter_frame.pack(fill=tk.X, expand=False, pady=(0, 8))

        # Filtro Tipologia (Combobox)
        ttk.Label(filter_frame, text="Tipologia:").pack(side=tk.LEFT, padx=(4, 4))
        cb_type = ttk.Combobox(
            filter_frame,
            textvariable=self.var_type_filter,
            values=list(self.type_filter_options.keys()),
            state="readonly",
            width=18,
        )
        cb_type.pack(side=tk.LEFT, padx=(0, 10))
        cb_type.bind("<<ComboboxSelected>>", lambda _: self._apply_ui_filter())

        # Filtro Checkbox Solo Utente
        chk_user = ttk.Checkbutton(
            filter_frame,
            text="Solo Utente (~/.local)",
            variable=self.var_user_only,
            command=self.refresh_themes,
        )
        chk_user.pack(side=tk.LEFT, padx=(0, 10))

        # Campo di Ricerca per Nome
        ttk.Label(filter_frame, text="Cerca per nome:").pack(side=tk.LEFT, padx=(10, 4))
        entry_search = ttk.Entry(filter_frame, textvariable=self.var_search_query, width=18)
        entry_search.pack(side=tk.LEFT, padx=(0, 8))
        self.var_search_query.trace_add("write", lambda *_: self._apply_ui_filter())

        # Pulsante Ricarica Scansione
        btn_reload = ttk.Button(
            filter_frame,
            text="🔄 Ricarica",
            command=self.refresh_themes,
        )
        btn_reload.pack(side=tk.RIGHT, padx=4)

        # 2. Tabella Centrale (ttk.Treeview) con Scrollbar
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        columns = ("name", "type", "origin", "path")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        # Configurazione colonne e intestazioni
        self.tree.heading("name", text="Nome Tema", command=lambda: self._sort_by_column("name", False))
        self.tree.heading("type", text="Tipologia", command=lambda: self._sort_by_column("type", False))
        self.tree.heading("origin", text="Origine", command=lambda: self._sort_by_column("origin", False))
        self.tree.heading("path", text="Percorso nel Filesystem", command=lambda: self._sort_by_column("path", False))

        self.tree.column("name", width=180, anchor=tk.W)
        self.tree.column("type", width=110, anchor=tk.CENTER)
        self.tree.column("origin", width=90, anchor=tk.CENTER)
        self.tree.column("path", width=380, anchor=tk.W)

        # Scrollbar verticale
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Evento selezione riga e doppio clic
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click_row)

        # 3. Barra Azioni Inferiore
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill=tk.X, expand=False, pady=4)

        # Override GTK4
        chk_gtk4 = ttk.Checkbutton(
            actions_frame,
            text="Applica override GTK4 / Libadwaita",
            variable=self.var_apply_gtk4_override,
        )
        chk_gtk4.pack(side=tk.LEFT, padx=(0, 12))

        # Pulsante Applica Tema Unificato (GTK + GNOME Shell contemporaneamente con 1 clic)
        self.btn_apply_unified = ttk.Button(
            actions_frame,
            text="🌐 Applica a Tutto il Sistema (GTK + Shell)",
            command=self._on_apply_unified,
            state=tk.DISABLED,
        )
        self.btn_apply_unified.pack(side=tk.RIGHT, padx=(4, 0))

        # Pulsante Applica Singolo Componente
        self.btn_apply = ttk.Button(
            actions_frame,
            text="▶ Applica Solo Questo",
            command=self._on_apply_selected,
            state=tk.DISABLED,
        )
        self.btn_apply.pack(side=tk.RIGHT, padx=(4, 0))

        # Pulsante Disinstalla Tema (solo per temi utente)
        self.btn_uninstall = ttk.Button(
            actions_frame,
            text="🗑️ Disinstalla Tema",
            command=self._on_uninstall_selected,
            state=tk.DISABLED,
        )
        self.btn_uninstall.pack(side=tk.RIGHT, padx=(4, 4))

    def refresh_themes(self) -> None:
        """Esegue una scansione completa dei temi sul filesystem."""
        try:
            user_only = self.var_user_only.get()
            self._cached_themes = self.manager.list_themes(theme_type=None, user_only=user_only)
            self._apply_ui_filter()
        except Exception as err:  # noqa: BLE001
            logger.error("Errore durante la scansione dei temi: %s", err)
            messagebox.showerror("Errore Scansione Temi", f"Impossibile scansionare i temi: {err}")

    def _apply_ui_filter(self) -> None:
        """Filtra la lista dei temi in base alla tipologia selezionata e alla stringa di ricerca."""
        # Svuota la tabella
        for row in self.tree.get_children():
            self.tree.delete(row)

        target_type = self.type_filter_options.get(self.var_type_filter.get())
        search_query = self.var_search_query.get().strip().lower()

        for theme in self._cached_themes:
            # Controllo filtro tipo
            if target_type is not None and theme.theme_type != target_type:
                continue

            # Controllo filtro ricerca testuale per nome o percorso
            if search_query and (search_query not in theme.name.lower() and search_query not in str(theme.path).lower()):
                continue

            origin_text = "Utente" if theme.is_user_level else "Sistema"
            self.tree.insert(
                "",
                tk.END,
                values=(theme.name, theme.theme_type.value.upper(), origin_text, str(theme.path)),
            )

        # Disabilita pulsanti azione poiché la selezione è azzerata
        self._update_action_buttons(None)

    def _on_tree_select(self, _event: tk.Event) -> None:
        """Gestisce il cambio di selezione nella tabella."""
        selected_items = self.tree.selection()
        if not selected_items:
            self._update_action_buttons(None)
            return

        item = self.tree.item(selected_items[0])
        values = item["values"]
        if values and len(values) >= 4:
            self._update_action_buttons(values)

    def _update_action_buttons(self, values: list | None) -> None:
        """Aggiorna lo stato abilitato/disabilitato dei pulsanti di azione."""
        if not values:
            self.btn_apply.configure(state=tk.DISABLED)
            self.btn_apply_unified.configure(state=tk.DISABLED)
            self.btn_uninstall.configure(state=tk.DISABLED)
            return

        self.btn_apply.configure(state=tk.NORMAL)

        # Il pulsante di tema globale (GTK + Shell con 1 click) è attivo per temi GTK o Shell
        type_str = str(values[1]).strip().lower()
        if type_str in ("gtk", "shell"):
            self.btn_apply_unified.configure(state=tk.NORMAL)
        else:
            self.btn_apply_unified.configure(state=tk.DISABLED)

        origin = str(values[2]).strip().lower()
        if origin == "utente":
            self.btn_uninstall.configure(state=tk.NORMAL)
        else:
            self.btn_uninstall.configure(state=tk.DISABLED)

    def _get_selected_theme_data(self) -> tuple[str, ThemeType, str] | None:
        """Estrae (nome, ThemeType, origine) dalla riga attualmente selezionata."""
        selected_items = self.tree.selection()
        if not selected_items:
            return None

        item = self.tree.item(selected_items[0])
        values = item["values"]
        if not values or len(values) < 3:
            return None

        name = str(values[0])
        type_str = str(values[1]).strip().lower()
        origin = str(values[2]).strip().lower()

        try:
            theme_type = ThemeType(type_str)
        except ValueError:
            return None

        return name, theme_type, origin

    def _on_double_click_row(self, _event: tk.Event) -> None:
        """Al doppio clic applica il tema a tutto il sistema se GTK/Shell, oppure singolarmente."""
        data = self._get_selected_theme_data()
        if not data:
            return
        _, theme_type, _ = data
        if theme_type in (ThemeType.GTK, ThemeType.SHELL):
            self._on_apply_unified()
        else:
            self._on_apply_selected()

    def _on_apply_selected(self) -> None:
        """Applica il tema selezionato al desktop GNOME."""
        data = self._get_selected_theme_data()
        if not data:
            return

        name, theme_type, _ = data
        apply_gtk4 = self.var_apply_gtk4_override.get()

        try:
            # Costruisce il ThemeSet in base al tipo selezionato
            if theme_type == ThemeType.GTK:
                theme_set = ThemeSet(gtk_theme=name)
            elif theme_type == ThemeType.ICON:
                theme_set = ThemeSet(icon_theme=name)
            elif theme_type == ThemeType.CURSOR:
                theme_set = ThemeSet(cursor_theme=name)
            elif theme_type == ThemeType.SHELL:
                theme_set = ThemeSet(shell_theme=name)
            else:
                theme_set = ThemeSet()

            result = self.manager.apply_themes(theme_set, apply_gtk4_override=apply_gtk4)

            # Notifica di successo
            msg_parts = [f"Tema {theme_type.value.upper()} '{name}' applicato con successo."]
            if result.gtk4_override_applied:
                msg_parts.append("Override GTK4 / Libadwaita applicato in ~/.config/gtk-4.0.")
            if result.warnings:
                msg_parts.append("\nAvvisi:\n" + "\n".join(f"- {w}" for w in result.warnings))

            messagebox.showinfo("Tema Applicato", "\n\n".join(msg_parts))

            # Notifica il cambio di stato alla finestra principale
            if self.on_theme_applied:
                self.on_theme_applied()

        except (GSettingsUnavailableError, ThemeNotFoundError, ValueError) as err:
            logger.warning("Impossibile applicare il tema '%s': %s", name, err)
            messagebox.showerror("Errore Applicazione Tema", str(err))
        except Exception as err:  # noqa: BLE001
            logger.error("Errore imprevisto nell'applicazione del tema: %s", err)
            messagebox.showerror("Errore Imprevisto", f"Si è verificato un errore: {err}")

    def _on_apply_unified(self) -> None:
        """Applica il tema selezionato a tutto il sistema in un solo clic (GTK e Shell contemporaneamente)."""
        data = self._get_selected_theme_data()
        if not data:
            return

        name, _, _ = data
        apply_gtk4 = self.var_apply_gtk4_override.get()

        try:
            # Invoca il metodo Facade apply_unified_theme per impostare GTK, Shell e override GTK4
            result = self.manager.apply_unified_theme(
                theme_name=name,
                apply_gtk4_override=apply_gtk4,
            )

            msg_parts = [f"🎨 Tema globale '{name}' applicato con successo a tutto il sistema!"]
            if result.gtk_theme:
                msg_parts.append(f" • Tema GTK (Applicazioni): {result.gtk_theme}")
            if result.shell_theme:
                msg_parts.append(f" • Tema GNOME Shell: {result.shell_theme}")
            if result.gtk4_override_applied:
                msg_parts.append(" • Override GTK4 / Libadwaita: ~/.config/gtk-4.0")
            if result.warnings:
                msg_parts.append("\nAvvisi:\n" + "\n".join(f"- {w}" for w in result.warnings))

            messagebox.showinfo("Tema Globale Applicato", "\n".join(msg_parts))

            # Notifica il cambio di stato per aggiornare le altre schede
            if self.on_theme_applied:
                self.on_theme_applied()

        except (GSettingsUnavailableError, ThemeNotFoundError, ValueError) as err:
            logger.warning("Impossibile applicare il tema unificato '%s': %s", name, err)
            messagebox.showerror("Errore Tema Globale", str(err))
        except Exception as err:  # noqa: BLE001
            logger.error("Errore imprevisto nell'applicazione unificata: %s", err)
            messagebox.showerror("Errore Imprevisto", f"Si è verificato un errore: {err}")

    def _on_uninstall_selected(self) -> None:
        """Disinstalla il tema selezionato a livello utente."""
        data = self._get_selected_theme_data()
        if not data:
            return

        name, theme_type, origin = data
        if origin != "utente":
            messagebox.showwarning(
                "Operazione Non Consentita",
                "Non è possibile disinstallare i temi di sistema protetti in /usr/share.",
            )
            return

        confirm = messagebox.askyesno(
            "Conferma Disinstallazione",
            f"Sei sicuro di voler eliminare definitivamente il tema {theme_type.value.upper()} '{name}'?",
        )
        if not confirm:
            return

        try:
            self.manager.uninstall_theme(name=name, theme_type=theme_type)
            messagebox.showinfo(
                "Tema Rimosso",
                f"Il tema '{name}' è stato rimosso correttamente dalle directory utente.",
            )
            self.refresh_themes()
            if self.on_theme_applied:
                self.on_theme_applied()
        except ThemeNotFoundError as err:
            messagebox.showerror("Tema Non Trovato", str(err))
        except Exception as err:  # noqa: BLE001
            messagebox.showerror("Errore Disinstallazione", f"Impossibile disinstallare il tema: {err}")

    def _sort_by_column(self, col: str, reverse: bool) -> None:
        """Ordina la tabella cliccando sull'intestazione della colonna."""
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rows.sort(reverse=reverse)

        for index, (_, k) in enumerate(rows):
            self.tree.move(k, "", index)

        # Inverte la direzione per il prossimo clic
        self.tree.heading(col, command=lambda: self._sort_by_column(col, not reverse))


# =============================================================================
# 3. Scheda: Gestione Preset e Profili
# =============================================================================


class PresetManagerView(ttk.Frame):
    """Scheda per visualizzare, applicare, salvare ed eliminare preset di configurazione."""

    def __init__(
        self,
        parent: ttk.Notebook,
        manager: "ThemeManager",
        on_preset_applied: Callable[[], None] | None = None,
    ) -> None:
        """Inizializza la vista dei preset.

        Args:
            parent: Widget genitore.
            manager: Istanza di ThemeManager.
            on_preset_applied: Callback da invocare quando un preset viene applicato o salvato.
        """
        super().__init__(parent, padding=12)
        self.manager = manager
        self.on_preset_applied = on_preset_applied

        # Variabili per la gestione del form di salvataggio
        self.var_new_preset_name = tk.StringVar(value="")

        # Variabili per l'anteprima del preset selezionato
        self.var_preview_gtk = tk.StringVar(value="-")
        self.var_preview_icon = tk.StringVar(value="-")
        self.var_preview_cursor = tk.StringVar(value="-")
        self.var_preview_shell = tk.StringVar(value="-")
        self.var_preview_color = tk.StringVar(value="-")

        self._build_ui()
        self.refresh_presets()

    def _build_ui(self) -> None:
        """Costruisce i componenti dell'interfaccia utente."""
        # 1. Sezione Superiore: Salvataggio Preset Corrente
        save_frame = ttk.LabelFrame(self, text=" Salva Configurazione Attuale come Preset ", padding=10)
        save_frame.pack(fill=tk.X, expand=False, pady=(0, 10))

        ttk.Label(save_frame, text="Nome Nuovo Preset:").pack(side=tk.LEFT, padx=(4, 6))
        entry_name = ttk.Entry(save_frame, textvariable=self.var_new_preset_name, width=24)
        entry_name.pack(side=tk.LEFT, padx=(0, 10))

        btn_save = ttk.Button(
            save_frame,
            text="💾 Salva Preset",
            command=self._on_save_preset,
        )
        btn_save.pack(side=tk.LEFT, padx=4)

        # 2. Sezione Centrale: Split Pane (Lista Preset a sinistra, Dettagli a destra)
        content_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        content_pane.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Pannello Sinistro: Lista Preset
        left_frame = ttk.LabelFrame(content_pane, text=" Preset Salvati ", padding=8)
        content_pane.add(left_frame, weight=1)

        self.tree_presets = ttk.Treeview(left_frame, columns=("name",), show="headings", selectmode="browse")
        self.tree_presets.heading("name", text="Nome Preset")
        self.tree_presets.column("name", width=220, anchor=tk.W)

        scroll_presets = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree_presets.yview)
        self.tree_presets.configure(yscrollcommand=scroll_presets.set)

        self.tree_presets.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_presets.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_presets.bind("<<TreeviewSelect>>", self._on_preset_select)
        self.tree_presets.bind("<Double-1>", lambda _: self._on_apply_preset())

        # Pannello Destro: Dettagli / Anteprima Preset
        right_frame = ttk.LabelFrame(content_pane, text=" Dettagli Preset Selezionato ", padding=12)
        content_pane.add(right_frame, weight=2)

        details = [
            ("Tema GTK:", self.var_preview_gtk),
            ("Tema Icone:", self.var_preview_icon),
            ("Tema Cursori:", self.var_preview_cursor),
            ("Tema Shell:", self.var_preview_shell),
            ("Schema Colori:", self.var_preview_color),
        ]

        for row_idx, (label_text, var) in enumerate(details):
            lbl_title = ttk.Label(right_frame, text=label_text, font=("Sans", 10, "bold"))
            lbl_title.grid(row=row_idx, column=0, sticky=tk.W, padx=6, pady=6)

            lbl_val = ttk.Label(right_frame, textvariable=var, font=("Sans", 10))
            lbl_val.grid(row=row_idx, column=1, sticky=tk.W, padx=6, pady=6)

        # 3. Barra Azioni Inferiore
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill=tk.X, expand=False, pady=4)

        self.btn_apply_preset = ttk.Button(
            actions_frame,
            text="▶ Applica Preset",
            command=self._on_apply_preset,
            state=tk.DISABLED,
        )
        self.btn_apply_preset.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_delete_preset = ttk.Button(
            actions_frame,
            text="🗑️ Elimina Preset",
            command=self._on_delete_preset,
            state=tk.DISABLED,
        )
        self.btn_delete_preset.pack(side=tk.RIGHT, padx=(4, 4))

        btn_refresh = ttk.Button(
            actions_frame,
            text="🔄 Ricarica Elenco",
            command=self.refresh_presets,
        )
        btn_refresh.pack(side=tk.LEFT, padx=(0, 4))

    def refresh_presets(self) -> None:
        """Ricarica l'elenco dei preset disponibili."""
        try:
            for row in self.tree_presets.get_children():
                self.tree_presets.delete(row)

            presets = self.manager.list_presets()
            for p_name in presets:
                self.tree_presets.insert("", tk.END, values=(p_name,))

            # Reset preview e pulsanti
            self._clear_preview()
        except Exception as err:  # noqa: BLE001
            logger.error("Errore nel recupero dei preset: %s", err)
            messagebox.showerror("Errore Preset", f"Impossibile leggere i preset: {err}")

    def _clear_preview(self) -> None:
        """Azzera l'anteprima dei dettagli."""
        self.var_preview_gtk.set("-")
        self.var_preview_icon.set("-")
        self.var_preview_cursor.set("-")
        self.var_preview_shell.set("-")
        self.var_preview_color.set("-")
        self.btn_apply_preset.configure(state=tk.DISABLED)
        self.btn_delete_preset.configure(state=tk.DISABLED)

    def _get_selected_preset_name(self) -> str | None:
        """Restituisce il nome del preset selezionato."""
        selected = self.tree_presets.selection()
        if not selected:
            return None
        values = self.tree_presets.item(selected[0])["values"]
        if not values:
            return None
        return str(values[0])

    def _on_preset_select(self, _event: tk.Event) -> None:
        """Aggiorna il riquadro di anteprima quando l'utente seleziona un preset."""
        name = self._get_selected_preset_name()
        if not name:
            self._clear_preview()
            return

        try:
            theme_set = self.manager.presets.load_preset(name)
            self.var_preview_gtk.set(theme_set.gtk_theme or "Non specificato")
            self.var_preview_icon.set(theme_set.icon_theme or "Non specificato")
            self.var_preview_cursor.set(theme_set.cursor_theme or "Non specificato")
            self.var_preview_shell.set(theme_set.shell_theme or "Non specificato")
            self.var_preview_color.set(theme_set.color_scheme or "default")

            self.btn_apply_preset.configure(state=tk.NORMAL)
            self.btn_delete_preset.configure(state=tk.NORMAL)
        except Exception as err:  # noqa: BLE001
            logger.warning("Impossibile caricare l'anteprima del preset '%s': %s", name, err)
            self._clear_preview()

    def _on_save_preset(self) -> None:
        """Salva lo stato corrente come nuovo preset."""
        name = self.var_new_preset_name.get().strip()
        if not name:
            messagebox.showwarning("Nome Mancante", "Inserisci un nome valido per il preset.")
            return

        try:
            self.manager.save_current_as_preset(name, overwrite=False)
            messagebox.showinfo("Preset Salvato", f"Preset '{name}' salvato con successo!")
            self.var_new_preset_name.set("")
            self.refresh_presets()
        except FileExistsError:
            # Richiesta di conferma sovrascrittura
            confirm = messagebox.askyesno(
                "Preset Esistente",
                f"Il preset '{name}' esiste già. Desideri sovrascriverlo con la configurazione attuale?",
            )
            if confirm:
                try:
                    self.manager.save_current_as_preset(name, overwrite=True)
                    messagebox.showinfo("Preset Aggiornato", f"Preset '{name}' sovrascritto con successo!")
                    self.var_new_preset_name.set("")
                    self.refresh_presets()
                except Exception as err:  # noqa: BLE001
                    messagebox.showerror("Errore Salvataggio", str(err))
        except Exception as err:  # noqa: BLE001
            messagebox.showerror("Errore Salvataggio Preset", str(err))

    def _on_apply_preset(self) -> None:
        """Applica il preset selezionato."""
        name = self._get_selected_preset_name()
        if not name:
            return

        try:
            result = self.manager.apply_preset(name, apply_gtk4_override=True)
            msg = f"Preset '{name}' applicato con successo!"
            if result.warnings:
                msg += "\n\nAvvisi:\n" + "\n".join(f"- {w}" for w in result.warnings)

            messagebox.showinfo("Preset Applicato", msg)
            if self.on_preset_applied:
                self.on_preset_applied()
        except (FileNotFoundError, ThemeNotFoundError, ValueError, GSettingsUnavailableError) as err:
            messagebox.showerror("Errore Applicazione Preset", str(err))
        except Exception as err:  # noqa: BLE001
            messagebox.showerror("Errore Imprevisto", f"Impossibile applicare il preset: {err}")

    def _on_delete_preset(self) -> None:
        """Elimina il preset selezionato."""
        name = self._get_selected_preset_name()
        if not name:
            return

        confirm = messagebox.askyesno(
            "Conferma Eliminazione",
            f"Sei sicuro di voler eliminare definitivamente il preset '{name}'?",
        )
        if not confirm:
            return

        try:
            self.manager.delete_preset(name)
            messagebox.showinfo("Preset Eliminato", f"Preset '{name}' eliminato.")
            self.refresh_presets()
        except Exception as err:  # noqa: BLE001
            messagebox.showerror("Errore Eliminazione Preset", str(err))


# =============================================================================
# 4. Scheda: Installazione Temi da Archivio
# =============================================================================


class ThemeInstallerView(ttk.Frame):
    """Scheda per l'installazione guidata di temi a partire da file compressi (.zip, .tar.*)."""

    def __init__(
        self,
        parent: ttk.Notebook,
        manager: "ThemeManager",
        on_installation_success: Callable[[], None] | None = None,
    ) -> None:
        """Inizializza la vista dell'installer.

        Args:
            parent: Widget genitore.
            manager: Istanza di ThemeManager.
            on_installation_success: Callback da invocare dopo un'installazione riuscita.
        """
        super().__init__(parent, padding=16)
        self.manager = manager
        self.on_installation_success = on_installation_success

        self.type_options = {
            "Rilevamento automatico": None,
            "GTK (Applicazioni)": ThemeType.GTK,
            "Icone": ThemeType.ICON,
            "Cursori": ThemeType.CURSOR,
            "GNOME Shell": ThemeType.SHELL,
        }

        # Variabili di input
        self.var_archive_path = tk.StringVar(value="")
        self.var_selected_type = tk.StringVar(value="Rilevamento automatico")
        self.var_custom_name = tk.StringVar(value="")
        self.var_overwrite = tk.BooleanVar(value=False)
        self.var_status_msg = tk.StringVar(value="Seleziona un file archivio da installare.")

        self._build_ui()

    def _build_ui(self) -> None:
        """Costruisce il layout della scheda installer."""
        # Sezione Selezione Archivio
        file_frame = ttk.LabelFrame(self, text=" 1. File Archivio Compresso ", padding=12)
        file_frame.pack(fill=tk.X, expand=False, pady=(0, 12))

        ttk.Label(file_frame, text="Percorso file (.zip, .tar.gz, .tar.xz, ...):").pack(anchor=tk.W, pady=(0, 4))

        input_row = ttk.Frame(file_frame)
        input_row.pack(fill=tk.X, expand=True)

        entry_file = ttk.Entry(input_row, textvariable=self.var_archive_path)
        entry_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_browse = ttk.Button(
            input_row,
            text="📁 Sfoglia...",
            command=self._on_browse_file,
        )
        btn_browse.pack(side=tk.RIGHT)

        # Sezione Opzioni di Installazione
        options_frame = ttk.LabelFrame(self, text=" 2. Opzioni di Installazione ", padding=12)
        options_frame.pack(fill=tk.X, expand=False, pady=(0, 12))

        # Tipologia forzata o automatica
        row_type = ttk.Frame(options_frame)
        row_type.pack(fill=tk.X, pady=4)
        ttk.Label(row_type, text="Tipo di tema:", width=22).pack(side=tk.LEFT)
        cb_type = ttk.Combobox(
            row_type,
            textvariable=self.var_selected_type,
            values=list(self.type_options.keys()),
            state="readonly",
            width=24,
        )
        cb_type.pack(side=tk.LEFT)

        # Nome cartella personalizzato
        row_name = ttk.Frame(options_frame)
        row_name.pack(fill=tk.X, pady=4)
        ttk.Label(row_name, text="Nome cartella personalizzato:", width=22).pack(side=tk.LEFT)
        entry_custom_name = ttk.Entry(row_name, textvariable=self.var_custom_name, width=26)
        entry_custom_name.pack(side=tk.LEFT)
        ttk.Label(row_name, text="(Opzionale, lascia vuoto per rilevamento automatico)", font=("Sans", 8)).pack(
            side=tk.LEFT, padx=6
        )

        # Checkbox Sovrascrittura
        row_ow = ttk.Frame(options_frame)
        row_ow.pack(fill=tk.X, pady=4)
        chk_overwrite = ttk.Checkbutton(
            row_ow,
            text="Sovrascrivi cartelle esistenti con lo stesso nome",
            variable=self.var_overwrite,
        )
        chk_overwrite.pack(side=tk.LEFT)

        # Sezione Esecuzione e Feedback
        exec_frame = ttk.Frame(self)
        exec_frame.pack(fill=tk.X, expand=False, pady=8)

        btn_install = ttk.Button(
            exec_frame,
            text="🚀 Installa Tema",
            command=self._on_install_click,
        )
        btn_install.pack(side=tk.LEFT, padx=(0, 10))

        lbl_status = ttk.Label(exec_frame, textvariable=self.var_status_msg, font=("Sans", 9, "italic"))
        lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _on_browse_file(self) -> None:
        """Apre la finestra di dialogo di selezione file per scegliere l'archivio."""
        filetypes = [
            ("Archivi supportati", "*.zip *.tar.gz *.tar.xz *.tar.bz2 *.tar *.tgz"),
            ("Archivi ZIP", "*.zip"),
            ("Archivi TAR", "*.tar *.tar.gz *.tar.xz *.tar.bz2 *.tgz"),
            ("Tutti i file", "*.*"),
        ]
        chosen = filedialog.askopenfilename(
            title="Seleziona Archivio Tema",
            filetypes=filetypes,
        )
        if chosen:
            self.var_archive_path.set(chosen)
            self.var_status_msg.set(f"File selezionato: {Path(chosen).name}")

    def _on_install_click(self) -> None:
        """Esegue l'installazione del tema richiamando il Facade ThemeManager."""
        path_str = self.var_archive_path.get().strip()
        if not path_str:
            messagebox.showwarning("File Mancante", "Seleziona un file archivio compresso prima di installare.")
            return

        archive_path = Path(path_str)
        if not archive_path.is_file():
            messagebox.showerror("File Non Trovato", f"Il percorso specificato non esiste o non è un file valido:\n{archive_path}")
            return

        theme_type = self.type_options.get(self.var_selected_type.get())
        custom_name = self.var_custom_name.get().strip() or None
        overwrite = self.var_overwrite.get()

        self._execute_install(
            archive_path=archive_path,
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
        )

    def _execute_install(
        self,
        archive_path: Path,
        theme_type: ThemeType | None,
        custom_name: str | None,
        overwrite: bool,
    ) -> None:
        """Esegue l'installazione gestendo le eccezioni e i dialoghi di conferma."""
        self.var_status_msg.set("Installazione in corso...")
        self.update_idletasks()

        try:
            installed_themes = self.manager.install_theme_archive(
                archive_path=archive_path,
                theme_type=theme_type,
                custom_name=custom_name,
                overwrite=overwrite,
            )

            lines = [f"✅ Installati con successo {len(installed_themes)} tema/i:\n"]
            for th in installed_themes:
                lines.append(f" • {th.name} ({th.theme_type.value.upper()}) -> {th.path}")

            msg_text = "\n".join(lines)
            self.var_status_msg.set(f"Installazione completata: {len(installed_themes)} tema/i installati.")
            messagebox.showinfo("Installazione Riuscita", msg_text)

            # Reset campi
            self.var_archive_path.set("")
            self.var_custom_name.set("")

            # Notifica le altre schede
            if self.on_installation_success:
                self.on_installation_success()

        except FileExistsError as err:
            self.var_status_msg.set("Conflitto: la cartella di destinazione esiste già.")
            confirm = messagebox.askyesno(
                "Cartella Tema Già Esistente",
                f"{err}\n\nDesideri sovrascrivere la cartella esistente?",
            )
            if confirm:
                # Riesegue con sovrascrittura abilitata
                self._execute_install(
                    archive_path=archive_path,
                    theme_type=theme_type,
                    custom_name=custom_name,
                    overwrite=True,
                )
        except (ArchiveExtractionError, ThemeValidationError, GnomeThemeManagerError) as err:
            self.var_status_msg.set("Errore durante l'installazione.")
            messagebox.showerror("Errore Installazione", str(err))
        except Exception as err:  # noqa: BLE001
            self.var_status_msg.set("Errore imprevisto.")
            messagebox.showerror("Errore Imprevisto", f"Si è verificato un errore durante l'installazione:\n{err}")
