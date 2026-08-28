# Changelog

All notable changes to this project are documented in this file.

## [1.5.0] - 2026-08-28

### Added
- **Online Theme Store (5.1 & 5.2)**: Integrated OpenDesktop and Pling OCS v1 API client with category filtering (GTK3/4, Shell, Icons, Cursors), search, dynamic multi-column responsive grid card view, sort options, and 1-click automatic download and installation into `~/.themes` and `~/.icons`.
- **Theme Detail View & Screenshot Inspection**: Rich detail page with author, downloads, rating, tags, changelog descriptions, and full-screen lightbox modal for high-definition screenshot viewing.
- **GNOME Shell Extensions Manager (5.3)**: Built-in Extensions view listing system and user-installed extensions with one-click enable/disable toggles, individual extension settings button launch, system Extension Manager opener, and official GNOME Extensions web catalog link.
- **High-Resolution Master Image Rendering**: Automatic bypass of CDN downscaling proxies to fetch original uncompressed 2K/4K screenshots and gallery previews.
- **Solid Opaque Page Transitions**: Opaque window background CSS and transition stabilization across all main pages eliminating crossfade alpha-ghosting.

## [1.4.8] - 2026-08-28

### Added
- **Color Scheme Preference Selector (4.8.5)**: Added interactive `AdwComboRow` widgets across Current Status, GTK Themes, and Theme Editor views to toggle between *Default (Light)*, *Dark*, and *Light* desktop appearance in 1 click, dynamically synchronized with `org.gnome.desktop.interface color-scheme`.
- **In-App Sandbox Integration Guide (4.8.3)**: Integrated modal documentation window inside Sandbox Tools with formatted step-by-step instructions, CLI commands, and Pango-safe markup for manual Flatpak filesystem overrides and Snap connections.
- **Dynamic Current Setup Sync (4.8.4)**: Real-time `Gio.Settings` change listener (`connect_changed`) updating all open pages instantly; added "Update Current Setup" 1-click sync button and active badge indicators on Global Theme presets.
- **Flatpak Runtime Icon Resolution (4.8.2)**: Embedded `/app/share/icons` and bundled fallback SVGs (`flatpak-symbolic`, app icons) ensuring crystal-clear icon rendering across native, Flatpak, and AppImage runtimes.

### Changed & Optimized
- **Dynamic Fallback Scanning (4.8.1)**: Removed hardcoded system fallback names; `ThemeAvailabilityChecker` and `FallbackManager` now dynamically scan system and sandbox directories to determine valid alternatives and apply GSettings directly without blocking alerts.
- **Asynchronous Sandbox Diagnostics**: Moved all sandbox runtime and Snap inspections to background threads, making page switching instantaneous and UI rendering non-blocking.
- **Single-Shot Snap Queries**: Optimized Snap connector diagnostics to query connections in a single batch command instead of per-package sequential loops.

## [1.4.1] - 2026-08-22

### Fixed
- **AppImage Sidebar Icons**: Fixed bundled fallback icon resolution in AppImage bundle packaging by properly embedding `data/icons/` into `usr/share/icons/` and extending `Gtk.IconTheme` search path discovery.
- **Unified Theme Directories**: Custom-composed themes with both GTK and GNOME Shell overrides now save directly to a single unified theme folder (`~/.themes/<name>`), bundling `gtk-4.0/`, `gtk-3.0/`, `gnome-shell/`, and `index.theme` together.
- **Theme Editor State & Reset**: Cleaned up Editor initialization to always start with the currently active desktop configuration; added an "Open Global Theme" selection dialog to modify existing themes and a "Reset" action.
- **Theme Deletion & Active Protections**: Added direct deletion support for user-installed GTK, GNOME Shell, Icon, and Cursor themes with confirmation dialogs; deletion is strictly prevented on currently active themes, and combined GTK+Shell themes warn about complete removal across both categories.

## [1.4.0] - 2026-08-21

### Added
- **Global Theme In-Place Editing (4.1)**: Direct in-place editing of user-created Global Themes (name, description, components, icon, fonts); non-destructive "Save as copy" workflow for bundled starter themes.
- **Custom Theme Icons & Pickers (4.2)**: User-customizable icon metadata for Global Themes with visual icon picker and graceful fallback to theme category icons.
- **Desktop Typography & Font Editor (4.3)**: Complete font management for Interface, Document, and Monospace font categories via native `Gtk.FontDialog`; text scaling factor control (0.50x – 3.00x) and embedding font settings inside Global Themes.
- **GNOME Terminal Palette & Preferences Editor (4.4)**: Full color customization, ANSI 16-color palette derivation from GTK styles, background transparency (0-100%), cursor and bell settings, and complete GNOME Terminal profile management (list, create, delete, and set default).

## [1.3.0] - 2026-08-21

### Added
- **Fallback Themes & Resilient Apply (3.1)**: User-configurable fallback themes for GTK3, GTK4, GNOME Shell, Icons, and Cursors; graceful auto-fallback when requested themes are missing in Host, Flatpak, or Snap sandboxes with non-blocking info banners instead of disruptive errors.
- **Optional User Themes Auto-Enable (3.2)**: User configuration toggle to silently auto-enable the GNOME Shell User Themes extension during theme apply.
- **Launcher Permissions Documentation (3.3)**: Added clear guidance in README for making AppImage and desktop launchers executable.
- **Bundled Fallback Icons (3.4)**: Integrated standard fallback icons search path chain and dynamic symbolic assets in `data/icons/` ensuring UI elements never render missing icon placeholders.

## [1.2.0] - 2026-08-20

### Added
- **Theme Mixer (2.1)**: Combine GTK3, GTK4, GNOME Shell, Icons, Cursors, and Color Scheme into custom user-composed Global Themes.
- **CSS Color Extractor (2.2)**: Automated extraction of GTK3/GTK4 color variables and theme tokens from stylesheets.
- **Theme Editor UI (2.3)**: Native GTK4/Libadwaita editor page with component dropdowns, persistent draft banner, and color controls.
- **Persistent GTK Color Forks (2.4)**: Non-destructive theme duplication in `~/.themes/{name}-gtk4` with `@define-color` style overrides.
- **Persistent Drafts & Auto-save (2.5)**: Session draft persistence with restart prompt, draft discard controls, and configurable auto-save settings.
- **Adaptive Wallpaper Palette (2.6)**: K-means color extraction (k=5) from active desktop wallpaper with global GTK and Shell accent application.
- **GNOME Shell Theme Editor (2.7)**: Color customization and fork generator for GNOME Shell (panel background, text, overview, and accent).

## [1.1.0] - 2026-08-20

### Added
- **Global Themes (1.1)**: Unified view replacing presets, ordering user themes on top (newest first) and 3 bundled starter themes on bottom.
- **Theme Validator (1.2)**: Structural and compliance validator for GTK, GNOME Shell, Icons, and Cursor themes.
- **Corruption Detection & Warning (1.3)**: Warning modal dialog and confirmation before applying incomplete or broken themes.
- **Icon Pack Preview (1.4)**: Real visual grid preview of standard GNOME app icons using temporary GtkIconTheme without altering system settings.
- **System Theme Preview with Safe Rollback (1.5)**: Instant in-app live style hot-reload and desktop preview with auto-rollback on cancel or exit.
- **Automatic User Directory Creation (1.6)**: Guaranteed automatic creation of `~/.themes`, `~/.local/share/themes`, `~/.icons`, and `~/.local/share/icons`.
- **Assisted Theme Installer (1.7)**: Modern `Gtk.FileDialog` file and folder picker with pre-install validation feedback and conflict overwrite management.

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