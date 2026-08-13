# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-07-01

### Added
- Struttura iniziale del progetto: CLI, core library, GUI GTK4/Libadwaita, GUI Tkinter legacy.
- Gestione temi GTK, icone, cursori e GNOME Shell (current, list, apply, install, uninstall).
- Sistema di preset (save, apply, delete, list).
- Integrazione sandbox Snap/Flatpak (sandbox-status).
- Packaging AppImage con build automatizzata via GitHub Actions.

### Changed
- Ripulita la struttura del repository: rimossi script ridondanti, documentazione duplicata e configurazioni interne non necessarie al pubblico.
- Corretto `scripts/test_env.sh` per usare gli extra `[dev]` di `pyproject.toml` invece di un `requirements-dev.txt` inesistente.