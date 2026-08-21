# GNOME Theme Manager

![Build AppImage](https://github.com/granafilo/GnomeThemeManager/actions/workflows/build-appimage.yml/badge.svg)
![Tests](https://github.com/granafilo/GnomeThemeManager/actions/workflows/tests.yml/badge.svg)
![AppImage](https://img.shields.io/badge/AppImage-Portable-blue?logo=appimage&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20GNOME-4EAA25?logo=gnome&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-3584E4)
![License](https://img.shields.io/badge/License-GPL--3.0-blue)
![Status](https://img.shields.io/badge/Status-Beta-orange)

## Project Status

**Current release:** v1.4.0

Version 1.4.0 introduces in-place Global Themes editing, custom icon pickers with robust fallback handling, comprehensive Desktop Typography and Font Scaling management, and full GNOME Terminal color/profile customization.
Full compatibility across all distributions, GNOME versions, or non-standard theme packages is not yet guaranteed.

Modular Python manager for managing GTK themes, icon packs, cursor themes, and GNOME Shell themes on GNOME desktops.

## Tags

GNOME, GTK4, Libadwaita, PyGObject, Themes, CLI, Linux Desktop, Snap, Flatpak

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
  - [Make the launcher executable](#make-the-launcher-executable)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Main CLI Commands](#main-cli-commands)
- [Graphical Interface (GUI)](#graphical-interface-gui)
- [Development and Testing](#development-and-testing)
- [Translations (i18n)](#translations-i18n)
- [Repository Structure](#repository-structure)
- [Documentation](#documentation)
- [License](#license)

## Overview

The project includes:
- A full-featured CLI for automation and scripting.
- A native GNOME GUI built with GTK4 and Libadwaita.
- Robust rollback, override management, and sandbox propagation features.

Current package version: 1.4.0 (PEP 440: 1.4.0)

## Features

- **Status & Discovery**: Read active theme status via `current` and list installed themes by category (`list`).
- **Selective & Global Apply**: Apply individual components (GTK, icon, cursor, shell) or unified **Global Themes** in 1 click.
- **Global Theme & Preset Editors**:
  - Edit existing user Global Themes in-place with instant UI updates; duplicate bundled starter themes via "Save as copy".
  - Assign custom icons or symbolic icons to Global Theme cards with resilient fallback chains.
  - Mix and match GTK, Shell, Icons, Cursors, and Color Scheme into custom user-composed Global Themes.
  - Fine-tune GTK and GNOME Shell colors (panel, overview, text, accents) with reversible theme forking.
  - Extract adaptive dominant palettes from the desktop wallpaper with 1-click global accent application.
  - Persistent editor drafts with auto-save toggle and resume prompt.
- **Typography & Font Management**:
  - Manage Interface, Document, and Monospace fonts with native `Gtk.FontDialog` pickers.
  - Control global display text scaling factor with live application and reversible reset.
  - Embed font preferences directly inside saved Global Themes and presets.
- **GNOME Terminal Palette & Preferences**:
  - Manage, create, and delete GNOME Terminal profiles and configure the default profile.
  - Derive 16-color ANSI palettes automatically from active GTK themes or custom stylesheets.
  - Customize text/background colors, background transparency (0-100%), cursor style/blink, and audio bells.
  - Export terminal palettes to JSON or apply them directly to GNOME Terminal profiles.
- **Theme Previews**:
  - Live system theme preview with instant in-app hot-reload and safe auto-rollback on exit/cancel.
  - Icon pack visual preview grid rendering real GNOME app icons without altering system configuration.
- **Theme Validation & Corruption Detection**: Automatic structural integrity checks against `index.theme` and stylesheets with pre-apply warning dialogs.
- **Assisted Installation & Management**:
  - Assisted installer with native `Gtk.FileDialog` supporting directories and `.tar.gz`/`.tar.xz`/`.zip` archives with pre-install validation.
  - Automatic user directory creation (`~/.themes`, `~/.icons`, `~/.local/share/themes`, `~/.local/share/icons`).
  - Safe uninstallation of user themes via CLI and GUI.
- **System Integration**:
  - GTK4 / Libadwaita theme override management in `~/.config/gtk-4.0` with atomic backups and rollback.
  - Snap and Flatpak sandbox propagation and environment diagnostics (`sandbox-status`).

## Prerequisites

### Make the launcher executable

To run the standalone AppImage bundle, local helper scripts, or launch the app from a custom `.desktop` launcher, ensure that execution permissions are explicitly granted:

1. **AppImage Bundle**:
   ```bash
   chmod +x GNOMEThemeManager-*.AppImage
   ```

2. **Repository Helper Scripts** (for local development or direct script execution):
   ```bash
   chmod +x scripts/run_cli.sh scripts/run_all_tests.sh scripts/test-translation.sh
   ```

3. **Desktop Launcher (`.desktop`) File**:
   If creating a custom launcher in `~/.local/share/applications/`:
   ```bash
   chmod +x ~/.local/share/applications/gnome-theme-manager.desktop
   ```
   Ensure the `Exec=` key specifies the absolute path to the executable or AppImage with valid permissions.

### Sandbox Integration (Flatpak & Snap)

- **Flatpak**: User themes installed in `~/.themes` or `~/.icons` are isolated from sandboxes by default. The application automatically propagates access via `flatpak override --filesystem=xdg-data/themes:ro` and `flatpak override --filesystem=xdg-data/icons:ro`.
- **Snap**: Standard desktop integration relies on theme snaps (such as `gtk-common-themes`). Ensure theme snaps are installed and connected to your GNOME desktop interface slots.

## Requirements

### Runtime Requirements

- **Operating System**: Linux with GNOME Desktop environment (Target: GNOME 42+, tested and verified on GNOME 46 / Ubuntu 24.04 LTS)
- **Python**: `>= 3.10`
- **System Utilities**:
  - `gsettings` (provided by `libglib2.0-bin` / GLib)
  - `gettext` (`gettext` / `libglib2.0-bin` for locale translations)
- **GNOME GObject Introspection Libraries**:
  - `PyGObject` (`python3-gi` >= 3.42.0)
  - `PyGObject Cairo` (`python3-gi-cairo`)
  - `GTK 4` GObject Introspection (`gir1.2-gtk-4.0`)
  - `Libadwaita 1` GObject Introspection (`gir1.2-adw-1`)

#### Ubuntu 24.04 LTS / Debian One-Liner (Runtime)

```bash
sudo apt update && sudo apt install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libglib2.0-bin gettext
```

### Development & Testing Dependencies (Dev-only)

For running the test suite, linting, and static type checking:
- `pytest` (`>= 7.0`)
- `ruff` (`>= 0.3.0`)
- `mypy` (`>= 1.8.0`)

Install dev dependencies:
```bash
pip install -e ".[dev]"
```


## Installation

### Option A: Portable AppImage (Recommended)

Download the latest `.AppImage` executable from [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases) and launch it:

```bash
chmod +x GNOMEThemeManager-1.2.0-x86_64.AppImage
./GNOMEThemeManager-1.2.0-x86_64.AppImage
```

> [!TIP]
> If you encounter AppImage FUSE issues on modern distributions (e.g. Ubuntu 24.04), install `libfuse2` via:
> ```bash
> sudo apt install -y libfuse2
> ```
> Alternatively, you can run the AppImage without FUSE using: `./GNOMEThemeManager-1.2.0-x86_64.AppImage --appimage-extract-and-run`

For detailed instructions and prerequisites, see **[INSTALL.md](INSTALL.md)**.

### Option B: From Source (Virtualenv)

```bash
git clone https://github.com/granafilo/GnomeThemeManager.git
cd GnomeThemeManager

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e .
```

For development dependencies:

```bash
pip install -e .[dev]
```

## Quick Start

```bash
gnome-theme-manager --help
gnome-theme-manager current
gnome-theme-manager list
```

## Main CLI Commands

Show current themes:

```bash
gnome-theme-manager current
```

List only user GTK themes:

```bash
gnome-theme-manager list --type gtk --user-only
```

Apply GTK theme and icon pack:

```bash
gnome-theme-manager apply --gtk Nordic-dark --icon Papirus-Dark
```

Apply unified theme (same name across GTK/Shell when available):

```bash
gnome-theme-manager apply --theme Catppuccin-Mocha
```

Install theme from archive:

```bash
gnome-theme-manager install --file ~/Downloads/Nordic.tar.xz
```

Uninstall user theme:

```bash
gnome-theme-manager uninstall --name Nordic --type gtk --yes
```

Manage presets:

```bash
gnome-theme-manager preset save work-setup
gnome-theme-manager preset list
gnome-theme-manager preset apply work-setup
```

Inspect sandbox status:

```bash
gnome-theme-manager sandbox-status
```

## Graphical Interface (GUI)

GNOME Theme Manager uses GTK4 and Libadwaita for its native graphical interface.

Launch the GUI:

```bash
gnome-theme-manager --gui
# or
gnome-theme-manager gui
```

## Development and Testing

Run tests:

```bash
pytest -v
```

Lint with Ruff:

```bash
ruff check src tests
```

Single test runner script:

```bash
bash scripts/run_all_tests.sh
```

Useful scripts:

- `scripts/run_cli.sh` — run CLI without installing the package
- `scripts/run_all_tests.sh` — full pytest + ruff test suite
- `scripts/test_env.sh` — bootstrap development environment (.venv + dependencies)
- `scripts/cleanup-repo.sh` — clean local build artifacts and caches

## Configuration, Backup, and Recovery

Theme Manager stores configuration and backups in standard XDG paths:
- **GTK4 Manifest**: `$XDG_CONFIG_HOME/gnome-theme-manager/gtk4_manifest.json` (defaults to `~/.config/gnome-theme-manager/gtk4_manifest.json`).
- **Backup files**: `$XDG_DATA_HOME/gnome-theme-manager/backups/` (defaults to `~/.local/share/gnome-theme-manager/backups/`).
- **Presets**: `$XDG_CONFIG_HOME/gnome-theme-manager/presets/` (defaults to `~/.config/gnome-theme-manager/presets/`).

### Manual Rollback Procedure
If you want to manually remove the GTK4 override and restore original files:
1. Remove current symlinks:
   ```bash
   rm -f ~/.config/gtk-4.0/gtk.css ~/.config/gtk-4.0/gtk-dark.css
   rm -rf ~/.config/gtk-4.0/assets
   ```
2. Restore original backup files from the `backups` folder back to `~/.config/gtk-4.0/`.

## Compatibility Matrix

Tested and verified environments for this release:

| Distribution | Version | GNOME | GTK | Installation | GUI | CLI | GTK4 override | Result |
|---|---|---|---|---|---|---|---|---|
| Ubuntu | 24.04 LTS | GNOME 46 | GTK4 / GTK3 | Verified | Verified | Verified | Verified | ✓ Supported |
| Ubuntu | 22.04 LTS | GNOME 42 | GTK4 / GTK3 | Verified | Verified | Verified | Verified | ✓ Supported |
| Fedora | 40 | GNOME 46 | GTK4 | Verified | Verified | Verified | Verified | ✓ Supported |
| Arch Linux | Rolling | GNOME 46 | GTK4 | Verified | Verified | Verified | Verified | ✓ Supported |
| Debian | 12 | GNOME 43 | GTK4 / GTK3 | Untested | Untested | Untested | Untested | Partially tested |

### Sandbox Limitations (Snap & Flatpak)
Applications running inside isolated sandboxes (such as Flatpak or Snap browsers) might not immediately reflect user-installed GTK themes. Theme Manager includes automatic propagation (via `flatpak override` and `gtk-common-themes` checking for Snap), but custom themes may require specific distribution runtime packages.

### AppImage Host Dependencies
The AppImage bundle does not bundle host GTK4/Libadwaita system C libraries. Therefore, the host system must have `python3-gi`, `gir1.2-gtk-4.0`, and `gir1.2-adw-1` installed to run the native GUI.

## Translations (i18n)

GNOME Theme Manager supports internationalization (i18n) via `gettext`.

### Running in a specific language
To run the application with a specific language override, set `LANG` and `LC_ALL`:

```bash
# Launch in English (default)
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 python3 -m gnome_theme_manager

# Launch in Italian
LC_ALL=it_IT.UTF-8 LANG=it_IT.UTF-8 python3 -m gnome_theme_manager
```

### AppImage localization
The AppImage bundles compiled `.mo` files under `gnome_theme_manager/locale/`. The build script sets `TEXTDOMAINDIR` so `gettext` accurately resolves translations inside the mounted filesystem.

### Adding or Updating Translations
The project provides helper scripts in `po/` to automate template extraction and compilation:

1. **Add new language**: Add the locale code to `po/LINGUAS` (e.g. `es`).
2. **Extract strings and update `.po` files**:
   ```bash
   ./po/update-po.sh
   ```
3. **Translate**: Edit `po/<lang>.po` with a text editor or Poedit (`msgid` -> `msgstr`).
4. **Compile**: Run `./po/update-po.sh` to compile `.mo` catalogs into `src/gnome_theme_manager/locale/`.

### Testing Translations
1. **Automated tests**:
   ```bash
   pytest tests/test_i18n.py
   ```
2. **Manual validation script**:
   ```bash
   ./scripts/test-translation.sh
   ```

## Repository Structure

```text
src/gnome_theme_manager/
  cli/        argument parser and command routing
  core/       domain logic (scanner, manager, installer, gsettings, sandbox)
  gui_gtk/    native GNOME GUI (GTK4/Libadwaita)
tests/        unit and integration test suite
docs/         roadmap and phase documentation
```

## Documentation

- [AppImage Installation Guide](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](docs/ROADMAP.md)
- [Phase 1 - CLI MVP](docs/phases/01-cli-mvp.md)
- [Phase 2 - Theme Installer](docs/phases/02-theme-installer.md)
- [Phase 3 - Core Architecture](docs/phases/03-core-architecture.md)
- [Phase 5 - GUI GTK Native](docs/phases/05-gui-gtk-native.md)
- [Phase 6 - Sandboxing & Hardening](docs/phases/06-sandboxing-hardening.md)

## License

GNOME Theme Manager is released under the
[GNU General Public License v3.0 or later](LICENSE).