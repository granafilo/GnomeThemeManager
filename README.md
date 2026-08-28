# GNOME Theme Manager

![Platform](https://img.shields.io/badge/Platform-Linux%20GNOME-4EAA25?logo=gnome&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-3584E4)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-blue)
[![Tests](https://github.com/granafilo/GnomeThemeManager/actions/workflows/tests.yml/badge.svg)](https://github.com/granafilo/GnomeThemeManager/actions)
[![AppImage](https://img.shields.io/badge/AppImage-Portable-blue?logo=appimage&logoColor=white)](https://github.com/granafilo/GnomeThemeManager/releases)

A modern, native theme manager and customization suite for the **GNOME Desktop environment** (GTK4 & Libadwaita).

**Current release:** v1.5.0

---

## ✨ Features

- **🌐 Online Theme Store**:
  - Browse, search, and filter thousands of themes from **Pling** and **OpenDesktop** across GTK, Shell, Icons, and Cursors.
  - High-resolution screenshot inspection, author ratings, download counts, and 1-click automatic installation into `~/.themes` and `~/.icons`.
- **🧩 GNOME Shell Extensions Manager**:
  - Live list of user and system extensions with instant enable/disable toggles.
  - Direct access to individual extension settings dialogs, system Extensions app, and extensions.gnome.org catalog.
- **🎨 Unified Theme Management**:
  - Browse, preview, and apply **GTK 3/4**, **GNOME Shell**, **Icon Packs**, and **Cursors**.
  - **Global Themes**: Save, switch, and share complete desktop setups in 1 click with live GSettings synchronization.
  - **🌗 Color Scheme Preferences**: 1-click toggling between Default (Light), Dark, and Light appearance across all views.
- **🖌️ Interactive Theme Editor & Mixer**:
  - Mix installed components into custom Global Themes with localized option bindings.
  - Customize extracted GTK and Shell palette colors with live preview and safe auto-rollback.
  - Extract adaptive accent color palettes from your desktop wallpaper.
- **🔤 Typography & Font Control**:
  - Configure Interface, Document, and Monospace fonts with native font dialogs.
  - Live adjustment of global display text scaling factor.
- **💻 GNOME Terminal Palette Customizer**:
  - Manage profiles, derive 16-color ANSI palettes from themes, adjust background transparency, and configure terminal fonts.
- **📦 Smart Installer & Theme Validation**:
  - Drag-and-drop or select `.zip` / `.tar.*` archives and folders with pre-install integrity checks.
  - Safe theme uninstallation with active-theme protections.
- **🛡️ Sandbox Integration & In-App Guide**:
  - Automatic theme sync for **Flatpak** overrides and **Snap** custom content connectors.
  - In-app interactive guide modal and conditional runtime diagnostics.

---

## Prerequisites

### Make the launcher executable

To run the standalone AppImage bundle, local helper scripts, or launch the app from a custom desktop launcher, ensure execution permissions are granted:

```bash
# AppImage bundle:
chmod +x GNOMEThemeManager-*.AppImage

# Local development helper scripts:
chmod +x scripts/run_app.sh scripts/run_tests.sh scripts/run_cli.sh
```

### Sandbox Integration (Flatpak & Snap)

- **Flatpak**: Automatic theme propagation via filesystem overrides (`xdg-data/themes:ro`, `xdg-data/icons:ro`).
- **Snap**: Native integration via `gtk-common-themes` and local dynamic Content Snaps.

For deep-dive details on sandbox integration and snap configuration, see **[docs/SANDBOX.md](docs/SANDBOX.md)**.

---

## ⚡ Quick Start

### 1. Portable AppImage (Recommended for Users)

Download the latest `.AppImage` from [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases) and launch:

```bash
chmod +x GNOMEThemeManager-1.4.1-x86_64.AppImage
./GNOMEThemeManager-1.4.1-x86_64.AppImage
```

*(See [INSTALL.md](INSTALL.md) for distribution packages and FUSE troubleshooting).*

---

### 2. Run from Source (GUI & CLI)

Clone the repository and run using the automated launcher scripts:

```bash
# 1. Setup environment and install dependencies
./scripts/install_dependencies.sh

# 2. Launch the GTK4 / Libadwaita GUI
./scripts/run_app.sh
```

---

## 💻 CLI Usage Examples

GNOME Theme Manager includes a full-featured CLI for terminal lovers and scripting:

```bash
# Show currently applied themes
gnome-theme-manager current

# List available themes
gnome-theme-manager list --type gtk

# Apply a combination of themes
gnome-theme-manager apply --gtk "Adwaita-dark" --icon "Papirus" --color-scheme prefer-dark

# Manage Global Theme presets
gnome-theme-manager preset list
gnome-theme-manager preset save my-custom-preset
gnome-theme-manager preset apply my-custom-preset

# Install a theme archive
gnome-theme-manager install -f ~/Downloads/Nordic.tar.xz
```

---

## 🛠️ Development & Testing

We provide full automation for development, testing, and formatting:

```bash
# Run entire test suite (Pytest + Coverage + Ruff + Mypy)
./scripts/run_tests.sh
```

For complete instructions on development workflows, virtualenv setup, translation tools, and contributing guidelines, check out:
👉 **[Development Guide](docs/DEVELOPMENT.md)** | **[Contributing Guidelines](CONTRIBUTING.md)**

---

## 📚 Documentation

- 📦 **[Installation & System Requirements](INSTALL.md)**: Distro-specific dependencies and AppImage setup.
- 🛠️ **[Development & Quality Guide](docs/DEVELOPMENT.md)**: Testing, linting, type-checking, and i18n workflows.
- 📦 **[Sandbox Integration (Snap & Flatpak)](docs/SANDBOX.md)**: Details on sandbox permissions and theme propagation.
- 🗺️ **[Roadmap](docs/ROADMAP.md)**: Project milestones and upcoming features.
- 📝 **[Changelog](CHANGELOG.md)**: Version history and release notes.

---

## ⚖️ License

GNOME Theme Manager is open-source software licensed under the [GNU General Public License v3.0 or later (GPL-3.0-or-later)](LICENSE).
