# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/).

## [0.9.0-beta3] - 2026-08-13

### Changed
- Changed the project license from MIT to GPL-3.0-or-later.
- Updated source headers and SPDX identifiers.
- Updated project metadata and documentation.
- Documented third-party dependency and asset licensing.

## [0.9.0-beta2] - 2026-08-13

### Fixed
- Added working `--version` support to the CLI and AppImage.
- Fixed argument forwarding from the AppImage launcher wrapper script.
- Prevented unnecessary GUI or configuration initialization for version checks.

### Removed
- Removed the legacy Tkinter GUI.
- Removed the `gui-tk` command and `--tk-gui` option.
- GNOME Theme Manager now uses GTK4/Libadwaita as its only graphical interface.

## [0.9.0-beta1] - 2026-08-13

### Added
- Integrazione di backup e rollback sicuri in `GTK4ThemeLinker` per la directory `~/.config/gtk-4.0/`.
- Manifest persistente ed atomico `gtk4_manifest.json` per tenere traccia delle preferenze applicate e dei backup.
- Rilevamento delle modifiche manuali esterne apportate dall'utente (conflict resolution).
- Validazione rigida sintattica dei nomi dei temi per Flatpak/Snap in `SandboxBridge`.
- Costruzione dei comandi esterni Flatpak e Snap come liste di argomenti, escludendo l'uso di `shell=True`.
- Eccezioni personalizzate: `ThemeApplyError`, `ThemeBackupError`, `ThemeRollbackError`, `SandboxCommandError`.
- Test di integrazione reali del filesystem sul rollback e conflict resolution.
- Automatizzazione e integrazione del linter/formatter `ruff` nel workflow di CI.

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