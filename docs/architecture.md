# Architecture Quick Reference

## Core Modules (`src/gnome_theme_manager/core/`)
- `scanner.py` — theme discovery from filesystem
- `gsettings.py` — gsettings read/write wrapper & live notifications
- `manager.py` — apply operations orchestrator & facade
- `installer.py` — theme installation from archives/dirs & GTK4 symlinks
- `presets.py` — preset CRUD & snapshot management
- `global_themes.py` — unified Global Themes models & registry
- `theme_validator.py` — `index.theme` structure validation
- `theme_editor.py` — color editing & theme mixing
- `theme_forks.py` — non-destructive user theme forks
- `fonts.py` — desktop typography and text scaling
- `terminal_palette.py` — ANSI 16-palette generator from themes
- `terminal_profile.py` — GNOME Terminal profile configuration
- `sandbox_bridge.py` — Flatpak and Snap permissions & runtime diagnostics
- `store_client.py` — OpenDesktop / Pling OCS v1 API client (Phase 5)
- `extensions.py` — GNOME Shell extensions CLI/REST wrapper (Phase 5)
- `extension_backend.py` — catalog search, details, and caching for extensions (Phase 5)
- `fallback.py` — resilient fallback resolution when themes are missing
- `icon_fallback.py` — multi-tier cascading icon lookup

## GUI Pages (`src/gnome_theme_manager/gui_gtk/pages/`)
- `global_themes.py` — Global Themes page with card previews
- `themes.py` — GTK, Shell, Icon, and Cursor browsing
- `editor_view.py` — Theme Editor and mixer
- `fonts.py` — Typography configuration
- `terminal.py` — Terminal palette and profiles
- `store.py` — Online Store catalog and 1-click theme install (Phase 5)
- `extensions.py` — GNOME Shell extensions manager & catalog browser (Phase 5)
- `installer.py` — Archive drop-zone and theme uninstaller
- `sandbox.py` — Sandbox status, diagnostic checks, and guided repair wizard
- `status.py` — Current desktop setup overview

## Data Locations
- State: `~/.local/state/gnome-theme-manager/`
- Cache: `~/.cache/gnome-theme-manager/`
- Logs: `~/.local/state/gnome-theme-manager/logs/`

## Packaging
- Primary distribution format: **Flatpak** (`io.github.granafilo.ThemeManager`)
- Manifest: `flatpak/io.github.granafilo.ThemeManager.yml`

## Entry Points
- GUI: `python3 -m gnome_theme_manager gui` (or `gnome-theme-manager gui`)
- CLI: `python3 -m gnome_theme_manager [command]` (or `gnome-theme-manager [command]`)