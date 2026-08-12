# Fase 4: Prototipo GUI Semplice con Tkinter

## Obiettivi della Fase

Sviluppare un prototipo grafico completo e leggero utilizzando `tkinter` e `tkinter.ttk` (libreria standard Python):
1. Verificare l'ergonomia dell'interfaccia utente e il flusso operativo (selezione tema -> info -> applica / installa / gestisci preset).
2. Collaudare l'integrazione del layer `core` (`ThemeManager` Facade) con un ciclo degli eventi (Event Loop GUI).
3. Fornire un'esperienza desktop ricca e intuitiva strutturata a schede (`ttk.Notebook`).

---

## Layout e Struttura della Finestra

```text
+--------------------------------------------------------------------------+
| 🎨 Gnome Theme Manager v0.1.0                          [🔄 Aggiorna Tutto]|
| Gestione avanzata e modulare dei temi per Ubuntu / GNOME                 |
+--------------------------------------------------------------------------+
| [ 📊 Stato Attuale | 📂 Temi Disponibili | ⭐ Gestione Preset | 📦 Installa ] |
|                                                                          |
| (Contenuto della scheda selezionata)                                      |
|                                                                          |
+--------------------------------------------------------------------------+
| Pronto.                                                                  |
+--------------------------------------------------------------------------+
```

---

## Architettura e Moduli Implementati

```text
src/gnome_theme_manager/
└── gui_tk/
    ├── __init__.py         # Esportazione di ThemeManagerWindow e launch_gui
    ├── app.py              # Finestra principale, configurazione TTK e coordinamento
    └── views.py            # Viste dedicate:
                            #  - CurrentStatusView
                            #  - AvailableThemesView
                            #  - PresetManagerView
                            #  - ThemeInstallerView
```

---

## Checklist di Implementazione

- [x] Creazione classe principale `ThemeManagerWindow` con `ttk.Notebook` e styling `clam`.
- [x] Scheda "Stato Attuale" con visualizzazione diagnostica e impostazioni attive.
- [x] Scheda "Temi Disponibili" con `ttk.Treeview`, filtri per tipologia/ricerca e applicazione/disinstallazione.
- [x] Scheda "Gestione Preset" con salvataggio, anteprima, applicazione ed eliminazione profili.
- [x] Scheda "Installer" con file dialog, opzioni di sovrascrittura e feedback visivo.
- [x] Integrazione CLI (`--gui` / `-g` e subcomando `gui`).
- [x] Suite di test automatizzati (`tests/test_gui_tk.py`).
