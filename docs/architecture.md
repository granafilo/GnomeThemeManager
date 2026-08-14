# Architecture Quick Reference

## Module Map
- `core/scanner.py` — theme discovery from filesystem
- `core/gsettings.py` — gsettings read/write wrapper
- `core/manager.py` — apply operations orchestrator
- `core/installer.py` — theme installation from archives/dirs
- `core/presets.py` — preset CRUD
- `core/theme_validator.py` — index.theme validation (Phase 1+)
- `core/theme_editor.py` — color editing / mixing (Phase 2+)
- `core/profiles.py` — light/dark profiles (Phase 4+)
- `core/store_client.py` — pling.com API (Phase 3+)
- `core/extensions.py` — gnome-extensions wrapper

## Data Locations
- State: ~/.local/state/gnome-theme-manager/
- Cache: ~/.cache/gnome-theme-manager/
- Logs: ~/.local/state/gnome-theme-manager/logs/

## Entry Points
- GUI: `python -m gnome_theme_manager.gui_gtk`
- CLI: `python -m gnome_theme_manager [command]`