# 📐 Architecture Overview

GNOME Theme Manager is engineered with strict separation between core business logic and presentation layers.

```text
                    ┌─────────────────────────┐
                    │       Entry Points       │
                    │   (CLI & GTK4 / Adw GUI) │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  gnome_theme_manager    │
                    │         .core           │
                    │   (Single Source of     │
                    │    Domain Logic)        │
                    └───────┬─────────┬───────┘
                            │         │
             ┌──────────────▼───┐   ┌─▼──────────────────┐
             │ System GSettings │   │ Filesystem & Paths │
             │     & D-Bus      │   │ (~/.themes, icons) │
             └──────────────────┘   └────────────────────┘
```

---

## 1. Core Modules (`src/gnome_theme_manager/core/`)

- **`scanner.py`**: Theme discovery from system (`/usr/share/...`) and user directories (`~/.local/share/...`, `~/.themes`, `~/.icons`).
- **`gsettings.py`**: Robust GSettings client with live schema change observation.
- **`manager.py`**: Main orchestrator facade handling atomic theme switching and rollback.
- **`installer.py`**: Archive decompression (`.tar.*`, `.zip`), GTK4 CSS symlink creation, and theme removal.
- **`presets.py` & `global_themes.py`**: Global Theme snapshots, registry, and composite component management.
- **`theme_validator.py`**: Integrity verification of `index.theme` and standard directory structures.
- **`theme_editor.py` & `theme_forks.py`**: Palette color extraction, non-destructive theme forking, and live preview.
- **`fonts.py`**: System typography, desktop scaling factor, and font dialog bindings.
- **`terminal_palette.py` & `terminal_profile.py`**: GNOME Terminal ANSI-16 palettes and profile customization.
- **`sandbox_bridge.py`**: Flatpak filesystem overrides and Snap Content Snap lifecycle integration.
- **`store_client.py`**: OpenDesktop / Pling OCS API client for theme discovery and downloads.
- **`extensions.py` & `extension_backend.py`**: GNOME Shell extension discovery, status toggles, and metadata caching.
- **`fallback.py` & `icon_fallback.py`**: Resilient fallbacks ensuring broken themes never crash the application.

---

## 2. Presentation Layer (`src/gnome_theme_manager/gui_gtk/`)

Built natively using **GTK4** and **Libadwaita**:
- **`window.py`**: Main window featuring Libadwaita `Adw.NavigationSplitView` and responsive layouts.
- **`pages/`**: Modular view controllers:
  - `global_themes.py`: One-click Global Theme cards.
  - `themes.py`: Tabbed browser for GTK, Shell, Icons, and Cursors.
  - `store.py`: Online OCS theme catalog with screenshot modal.
  - `extensions.py`: GNOME Shell extensions browser and manager.
  - `editor_view.py`: Theme mixing and color customization.
  - `fonts.py` & `terminal.py`: Typography and terminal preferences.
  - `installer.py`: Drag-and-drop theme archive installer.
  - `sandbox.py`: Sandbox diagnostics and permission wizard.
  - `status.py`: Real-time desktop appearance overview.

---

## 3. Data & State Storage

The application adheres strictly to the **XDG Base Directory Specification**:
- **State**: `~/.local/state/gnome-theme-manager/` (user presets, custom forks, active configuration)
- **Cache**: `~/.cache/gnome-theme-manager/` (downloaded store thumbnails, extension cache)
- **Logs**: `~/.local/state/gnome-theme-manager/logs/`

> **Architectural Rule**: The application never stores or modifies runtime state in `~/.config/`.

---

## 4. Packaging & Distribution

- **Primary Format**: **Flatpak** (`io.github.granafilo.ThemeManager`)
- **Manifest**: `flatpak/io.github.granafilo.ThemeManager.yml`
- **Permissions**: `xdg-data/themes:create`, `xdg-data/icons:create`, `org.gnome.Settings` D-Bus talk.

---

## 5. Entry Points

- **GUI**: `python3 -m gnome_theme_manager gui` (or `./scripts/run_app.sh`)
- **CLI**: `python3 -m gnome_theme_manager.cli.main` (or `./scripts/run_cli.sh`)