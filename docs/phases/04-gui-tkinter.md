# Fase 4: Prototipo GUI Semplice con Tkinter

## Obiettivi della Fase

Sviluppare un primo prototipo grafico leggero utilizzando `tkinter` e `tkinter.ttk` (libreria standard Python):
1. Verificare l'ergonomia dell'interfaccia utente e il flusso operativo (selezione tema -> anteprima/info -> applica).
2. Collaudare l'integrazione del layer `core` con un ciclo degli eventi (Event Loop GUI).
3. Gestire lo stato asincrono (es. estrazione archivi) senza bloccare l'interfaccia grafica.

---

## Layout e Struttura della Finestra

```text
+-------------------------------------------------------------+
| Gnome Theme Manager (Tkinter Prototype)                     |
+-------------------------------------------------------------+
| [ Schede: Temi GTK | Icone | Cursori | Gestione/Installa ]  |
|                                                             |
| +-------------------------+  +----------------------------+ |
| | Temi Disponibili:       |  | Dettagli Tema:             | |
| | > Adwaita               |  | Nome: Nordic               | |
| |   Adwaita-dark          |  | Percorso: ~/.local/share...| |
| |   Nordic                |  | Tipo: GTK 3.0 / GTK 4.0    | |
| |   Yaru                  |  | Livello: Utente            | |
| |                         |  +----------------------------+ |
| |                         |  | Stato: [ Inattivo ]        | |
| +-------------------------+  | [ Applica Tema ]           | |
|                              +----------------------------+ |
|                                                             |
| [ Barra di stato: Tema GTK attivo: Adwaita-dark           ] |
+-------------------------------------------------------------+
```

---

## Architettura e Moduli Coinvolti

```text
src/gnome_theme_manager/
└── gui_tk/
    ├── __init__.py
    ├── app.py              # Classe principale Tkinter Application
    ├── tabs/
    │   ├── theme_list_tab.py
    │   └── installer_tab.py
    └── dialogs.py          # Messaggi di conferma ed errori
```

---

## Checklist di Implementazione

- [ ] Creazione classe `ThemeManagerTkApp`.
- [ ] Binding delle azioni di selezione e clic con `ThemeManager` del core.
- [ ] Gestione threading con `concurrent.futures.ThreadPoolExecutor` per le operazioni di I/O pesanti.
- [ ] Aggiornamento dinamico delle liste post-installazione.
