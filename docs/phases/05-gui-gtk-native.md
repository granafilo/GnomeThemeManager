# Phase 5: Native GNOME GUI with GTK4 and Libadwaita

## Phase Goals

Build the definitive native graphical interface for the GNOME desktop:
1. Utilize **GTK4** and **Libadwaita** via `PyGObject` (`gi.repository.Gtk`, `gi.repository.Adw`).
2. Adhere to GNOME Human Interface Guidelines (HIG): modern HeaderBar, `Adw.PreferencesPage`, `Adw.ActionRow`, native Dark Mode, and accent color support.
3. Separate UI definitions from code using declarative XML `.ui` blueprint files.

---

## Libadwaita GUI Layout

```text
+-------------------------------------------------------------+
| (O) Gnome Theme Manager                               _ O X |
+-------------------------------------------------------------+
| [ Search themes...                                      🔍 ] |
|                                                             |
| ⚙️ Global Appearance                                        |
|   Dark Style Preference:      [ Default | Dark ]            |
|                                                             |
| 🎨 GTK Themes                                               |
|   Current Theme:              Nordic-dark            [ ▾ ]  |
|   Location:                   ~/.local/share/themes         |
|                                                             |
| 🖼️ Icons & Cursors                                          |
|   Icon Pack:                  Papirus-Dark           [ ▾ ]  |
|   Cursor Theme:               Bibata-Modern-Classic  [ ▾ ]  |
|                                                             |
| 📦 Management                                               |
|   [ + Install Theme Archive ]      [ 💾 Save Preset ]       |
+-------------------------------------------------------------+
```

---

## Architecture and Involved Modules

```text
src/gnome_theme_manager/
└── gui_gtk/
    ├── __init__.py
    ├── app.py              # Adw.Application / Gtk.Application
    ├── window.py           # Adw.ApplicationWindow
    ├── pages/
    │   ├── status.py
    │   ├── themes.py
    │   ├── presets.py
    │   ├── installer.py
    │   └── sandbox.py
    └── ui/                 # Declarative GTK Builder UI XML files
        ├── window.ui
        ├── status_page.ui
        ├── themes_page.ui
        ├── presets_page.ui
        ├── installer_page.ui
        └── sandbox_page.ui
```

---

## Implementation Checklist

- [x] Application initialization with `Adw.Application(application_id="org.gnome.ThemeManager")`.
- [x] Window and page declarations using modern Libadwaita widgets (`Adw.ToolbarView`, `Adw.PreferencesGroup`, `Adw.ActionRow`).
- [x] Integration with `GLib.idle_add` for non-blocking UI updates.
- [x] Internationalization integration via `gettext` across UI files and Python code.
