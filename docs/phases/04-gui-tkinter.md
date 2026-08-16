# Phase 4: Simple GUI Prototype with Tkinter

## Phase Goals

Develop an initial lightweight graphical prototype using `tkinter` and `tkinter.ttk` (Python standard library):
1. Validate UI ergonomics and user workflows (theme selection -> info -> apply / install / manage presets).
2. Test integration of the `core` layer (`ThemeManager` Facade) with a GUI event loop.
3. Provide an intuitive tabbed desktop experience (`ttk.Notebook`).

---

## Window Layout and Structure

```text
+--------------------------------------------------------------------------+
| 🎨 Gnome Theme Manager v0.1.0                              [🔄 Refresh All]|
| Modular theme management for Ubuntu / GNOME                              |
+--------------------------------------------------------------------------+
| [ 📊 Current Status | 📂 Available Themes | ⭐ Preset Manager | 📦 Install ] |
|                                                                          |
| (Selected tab content)                                                   |
|                                                                          |
+--------------------------------------------------------------------------+
| Ready.                                                                   |
+--------------------------------------------------------------------------+
```

---

## Architecture and Implemented Modules

```text
src/gnome_theme_manager/
└── gui_tk/
    ├── __init__.py         # Exports ThemeManagerWindow and launch_gui
    ├── app.py              # Main window, TTK configuration, and coordinator
    └── views.py            # Dedicated views:
                            #  - CurrentStatusView
                            #  - AvailableThemesView
                            #  - PresetManagerView
                            #  - ThemeInstallerView
```

---

## Implementation Checklist

- [x] Main `ThemeManagerWindow` class with `ttk.Notebook` and `clam` theme styling.
- [x] "Current Status" tab with active configuration and diagnostics.
- [x] "Available Themes" tab with `ttk.Treeview`, filters by type/search, apply/uninstall actions.
- [x] "Preset Manager" tab for saving, previewing, applying, and deleting profiles.
- [x] "Installer" tab with file dialogs, overwrite options, and visual feedback.
- [x] CLI integration (`--gui` / `-g` and `gui` subcommand).
- [x] Automated test suite (`tests/test_gui_tk.py`).

> [!NOTE]
> The legacy Tkinter GUI has been replaced by the native GTK4/Libadwaita interface in Phase 5.
