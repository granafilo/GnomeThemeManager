# 🛠️ Developer & Contributor Guide

Welcome to the **GNOME Theme Manager** development guide. This document outlines local environment setup, testing standards, static analysis, translation workflows, and Flatpak packaging.

---

## 1. System Requirements & Dependencies

GNOME Theme Manager requires **Python 3.10+**, **GTK 4**, **Libadwaita**, and GObject Introspection.

### Debian / Ubuntu 22.04 LTS / 24.04 LTS & Zorin OS
```bash
sudo apt update
sudo apt install -y \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  python3-venv \
  python3-pip \
  gettext
```

### Fedora 38+
```bash
sudo dnf install -y \
  python3-gobject \
  gtk4 \
  libadwaita \
  python3-pip \
  gettext
```

### Arch Linux / CachyOS
```bash
sudo pacman -S --needed \
  python-gobject \
  gtk4 \
  libadwaita \
  python-pip \
  gettext
```

---

## 2. Setting Up the Local Environment

We recommend developing within a virtual environment configured with `--system-site-packages` so Python can access the system GObject bindings (`gi`).

### Automated Setup (Recommended)
We provide an automated bootstrap script in `scripts/`:
```bash
# Creates .venv, installs dev requirements, and compiles translation catalogs
./scripts/install_dependencies.sh
```

### Manual Setup
```bash
# 1. Create virtual environment with access to system GTK4 bindings
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# 2. Upgrade pip and install editable package with dev dependencies
pip install --upgrade pip
pip install -e ".[dev]"

# 3. Compile translation catalogs
python3 scripts/compile_translations.py
```

---

## 3. Running from Source

You can execute both the GTK4/Libadwaita GUI and the CLI directly from source:

### Using Helper Scripts
```bash
# Launch the Libadwaita GUI
./scripts/run_app.sh

# Run CLI subcommands
./scripts/run_cli.sh current
./scripts/run_cli.sh list --type gtk
```

### Using Python Directly
```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/src"

# Launch GUI
python3 -m gnome_theme_manager gui

# Launch CLI
python3 -m gnome_theme_manager.cli.main --help
```

---

## 4. Code Quality & Testing Standards

All pull requests must pass the complete automated test suite, linting, and type verification.

### Run All Checks in One Step
```bash
./scripts/run_tests.sh
```

### Individual Quality Commands

#### 1. Unit & Integration Tests (pytest)
We enforce a minimum test coverage of **80%** on `src/gnome_theme_manager/core/`. All tests must be isolated and deterministic (using `tmp_path` fixtures).
```bash
pytest -v --cov=gnome_theme_manager
```

#### 2. Linter & Code Formatter (Ruff)
```bash
# Check code style and formatting
ruff check src tests
ruff format --check src tests

# Auto-fix lint and format issues
ruff check --fix src tests
ruff format src tests
```

#### 3. Strict Static Type Checking (Mypy)
All code must comply with PEP 484 and pass strict type checks:
```bash
mypy --strict src
```

#### 4. Version Consistency Check
Verifies single source of truth across `__init__.py`, `README.md`, `CHANGELOG.md`, and AppStream metadata:
```bash
python3 scripts/check_version_coherence.py
```

---

## 5. Internationalization (i18n)

GNOME Theme Manager uses standard GNU `gettext`.

### Guidelines
- Every user-visible string must be wrapped with `_("...")`.
- Whenever a string is added or updated, update both `po/en.po` and `po/it.po`.
- `.mo` files are compiled build artifacts (gitignored).

### Compiling and Testing Translations
```bash
# Compile all .po catalogs to .mo
python3 scripts/compile_translations.py

# Test UI under Italian locale
LANG=it_IT.UTF-8 ./scripts/run_app.sh

# Test UI under default English locale
LANG=en_US.UTF-8 ./scripts/run_app.sh

# Run translation test suite
pytest tests/test_i18n.py
```

---

## 6. Building Flatpak Locally

The primary distribution target is Flatpak using the GNOME 46 runtime.

### Build and Package
```bash
chmod +x scripts/build-flatpak.sh
./scripts/build-flatpak.sh
```

The script builds the local OSTree repository and exports bundles to `dist/`:
- `dist/GNOMEThemeManager-1.5.3-x86_64.flatpak` (Offline standalone bundle)
- `dist/GNOMEThemeManager.flatpakref` (Single-click installer)

---

## 7. Architecture Rules for Contributors

1. **Strict Core Separation**: All business logic, theme scanning, file operations, and D-Bus calls reside exclusively in `src/gnome_theme_manager/core/`. Both the GUI (`gui_gtk/`) and CLI (`cli/`) must consume the same public Core APIs.
2. **No `print()` in Production**: Never use `print()` in `core/` or `gui_gtk/`. Use Python's standard `logging` module.
3. **State Storage**: Never store application state in `~/.config/`. Use `~/.local/state/gnome-theme-manager/` (or `~/.cache/gnome-theme-manager/` for transient caches).
