# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.9.0-beta3] - 2026-08-14

### Added
- Added support for installing themes to legacy paths `~/.themes` and `~/.icons` via CLI (`--legacy` flag) and GUI (dedicated switch).
- Full internationalization support with English (`en`) and Italian (`it`) translations, along with self-contained extraction/compilation scripts.

### Changed
- Changed project license from MIT to GPL-3.0-or-later.
- Updated source headers and SPDX identifiers.
- Updated project metadata and documentation.
- Documented third-party dependency and asset licensing.

### Fixed
- **Sandbox Propagation**: Limited automatic propagation strictly to GTK themes and icon packs, avoiding unnecessary flatpak/snap calls for cursor or shell themes.
- **Sandbox Error Handling**: Bridge execution issues in Flatpak/Snap no longer fail the entire operation and are logged as non-fatal warnings.
- **Atomic Installation**: Implemented a two-pass (*check-then-write*) check to prevent partial or inconsistent installation states on conflict in multi-theme archives.
- **GTK4/Libadwaita Override**: Fixed stale override states by cleaning up previous files in `~/.config/gtk-4.0` when switching to a theme without GTK4 support.
- **GUI Installer**: Fixed the "Select folder" action by correctly triggering `select_folder` on `Gtk.FileDialog`.

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
- Safe backup and rollback integration in `GTK4ThemeLinker` for the `~/.config/gtk-4.0/` directory.
- Persistent and atomic `gtk4_manifest.json` to track active preferences and backups.
- External manual modification detection and conflict resolution.
- Strict syntax validation for theme names in Flatpak/Snap inside `SandboxBridge`.
- External Flatpak and Snap command generation as argument lists, eliminating `shell=True`.
- Custom exceptions: `ThemeApplyError`, `ThemeBackupError`, `ThemeRollbackError`, `SandboxCommandError`.
- Integration tests on real filesystem rollback and conflict resolution.
- Automated linting and formatting with `ruff` in CI workflow.

## [0.1.0] - 2026-07-01

### Added
- Initial project structure: CLI, core library, GTK4/Libadwaita GUI, legacy Tkinter GUI.
- Management of GTK themes, icon packs, cursor themes, and GNOME Shell themes (`current`, `list`, `apply`, `install`, `uninstall`).
- Preset system (`save`, `apply`, `delete`, `list`).
- Snap and Flatpak sandbox status inspection (`sandbox-status`).
- AppImage packaging and automated build via GitHub Actions.

### Changed
- Cleaned up repository structure: removed redundant scripts and duplicate internal documentation.
- Fixed `scripts/test_env.sh` to use `[dev]` extras from `pyproject.toml`.