# GNOME Theme Manager

![Build AppImage](https://github.com/granafilo/GnomeThemeManager/actions/workflows/build-appimage.yml/badge.svg)
![Tests](https://github.com/granafilo/GnomeThemeManager/actions/workflows/tests.yml/badge.svg)
![AppImage](https://img.shields.io/badge/AppImage-Portable-blue?logo=appimage&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20GNOME-4EAA25?logo=gnome&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-3584E4)
![License](https://img.shields.io/badge/License-GPL--3.0-blue)
![Status](https://img.shields.io/badge/Status-Beta-orange)

## Project Status

Version 1.0.0 is a public testing release.
Full compatibility across all distributions, GNOME versions, or non-standard theme packages is not yet guaranteed.

Modular Python manager for managing GTK themes, icon packs, cursor themes, and GNOME Shell themes on GNOME desktops.

## Tags

GNOME, GTK4, Libadwaita, PyGObject, Themes, CLI, Linux Desktop, Snap, Flatpak

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
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

Current package version: 1.0.0 (PEP 440: 1.0.0)

## Features

- Read active theme status via `current`
- List installed themes by type via `list`
- Apply GTK, icon, cursor, and shell themes via `apply`
- Install themes from archives via `install`
- Uninstall user-installed themes via `uninstall`
- Manage theme presets via `preset list`, `save`, `apply`, `delete`
- Check Snap/Flatpak sandbox integration via `sandbox-status`
- Propagate themes to sandbox runtimes (optional)
- GTK4 / Libadwaita theme override in `~/.config/gtk-4.0` when applicable

## Prerequisites

To ensure proper execution of the application and desktop launcher:

1. **Execution Permissions**: Ensure execution permissions are set on the binary or launcher:
   ```bash
   chmod +x /path/to/gnome-theme-manager
   ```
2. **Flatpak & Snap Integration**:
   - For Flatpak: user themes installed in `~/.themes` or `~/.icons` are not visible to sandboxes by default. The application uses `flatpak override` to grant filesystem access to Flatpak sandboxes.
   - For Snap: ensure standard runtime theme snaps (such as `gtk-common-themes`) are installed and connected to your GNOME host.

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
chmod +x GNOMEThemeManager-1.0.0-x86_64.AppImage
./GNOMEThemeManager-1.0.0-x86_64.AppImage
```

> [!NOTE]
> **FUSE Requirement for AppImage**: Like most AppImage packages on Linux, running the AppImage requires `libfuse` to mount the executable.
> - **Ubuntu 24.04 LTS / Debian 13+**: `sudo apt install -y libfuse2t64`
> - **Ubuntu 22.04 LTS / Debian 12**: `sudo apt install -y libfuse2`
> - **Fedora**: `sudo dnf install -y fuse-libs`
> - **Arch Linux**: `sudo pacman -S fuse2`
>
> Alternatively, you can run the AppImage without FUSE using: `./GNOMEThemeManager-1.0.0-x86_64.AppImage --appimage-extract-and-run`

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