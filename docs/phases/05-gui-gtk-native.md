# Fase 5: GUI Nativa GNOME con GTK4 e Libadwaita

## Obiettivi della Fase

Costruire l'interfaccia grafica definitiva e nativa per l'ecosistema GNOME:
1. Utilizzare **GTK4** e **Libadwaita** tramite `PyGObject` (`gi.repository.Gtk`, `gi.repository.Adw`).
2. Rispettare le GNOME Human Interface Guidelines (HIG): HeaderBar moderna, `Adw.PreferencesPage`, `Adw.ActionRow`, supporto nativo a Dark Mode e accent colors.
3. Separare la definizione grafica dal codice tramite blueprint / file `.ui` XML generati con Cambalache o scritti a mano.

---

## Struttura della GUI Libadwaita

```text
+-------------------------------------------------------------+
| (O) Gnome Theme Manager                                 _ O X |
+-------------------------------------------------------------+
| [ Cerca temi...                                         🔍 ] |
|                                                             |
| ⚙️ Aspetto Globale                                           |
|   Modalità Scura:             [ Predefinito | Scuro ]        |
|                                                             |
| 🎨 Temi GTK                                                |
|   Tema Attuale:               Nordic-dark            [ ▾ ]  |
|   Posizione:                  ~/.local/share/themes         |
|                                                             |
| 🖼️ Icone & Cursori                                          |
|   Set Icone:                  Papirus-Dark           [ ▾ ]  |
|   Cursori:                    Bibata-Modern-Classic  [ ▾ ]  |
|                                                             |
| 📦 Gestione                                                 |
|   [ + Installa Archivio Tema ]     [ 💾 Salva Preset ]      |
+-------------------------------------------------------------+
```

---

## Architettura e Moduli Coinvolti

```text
src/gnome_theme_manager/
└── gui_gtk/
    ├── __init__.py
    ├── application.py      # Adw.Application / Gtk.Application
    ├── window.py           # Adw.ApplicationWindow
    ├── views/
    │   ├── preferences_view.py
    │   ├── theme_browser_view.py
    │   └── installer_dialog.py
    └── resources/          # Risorse GResource (file .ui, icone svg)
        ├── gresource.xml
        └── ui/
            ├── window.ui
            └── theme_row.ui
```

---

## Checklist di Implementazione

- [ ] Inizializzazione applicazione `Adw.Application(application_id="org.gnome.ThemeManager")`.
- [ ] Definizione finestre e viste con widget moderni Libadwaita (`Adw.ToolbarView`, `Adw.PreferencesGroup`, `Adw.ComboRow`).
- [ ] Integrazione con `GLib.idle_add` e `Gio.Task` per il disaccoppiamento I/O asincrono.
- [ ] Integrazione GResource per embedding dei file UI nell'eseguibile.
