# 🛠️ Development & Testing Guide

This guide covers setting up your local environment, running the automated test suite, code quality checks, and internationalization workflows for **GNOME Theme Manager**.

---

## ⚡ 1. Automated Environment Setup (Recommended)

We provide automated helper scripts located in the `scripts/` directory to bootstrap your environment effortlessly:

```bash
# 1. Standard setup: installs system packages via APT, creates .venv, and installs dev dependencies
./scripts/install_dependencies.sh

# Or global setup: also installs pytest, mypy, and ruff globally on the host system
./scripts/install_dependencies.sh --global
```

### What `install_dependencies.sh` does:
- Verifies system libraries: `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `python3-venv`.
- Creates a virtual environment with `--system-site-packages` in `.venv`.
- Installs Python dependencies in editable mode: `pip install -e ".[dev]"`.
- Installs `mypy` and `ruff`.
- Compiles gettext `.mo` translation catalogs.

---

## 🧪 2. Running Tests & Quality Checks

### Run All Checks at Once
```bash
./scripts/run_tests.sh
```
This script runs:
1. **Pytest** with code coverage on `src/gnome_theme_manager/`.
2. **Ruff** linter (`ruff check src tests`) and code format check (`ruff format --check src tests`).
3. **Mypy** strict static type checking (`mypy --strict src`).

### Running Tools Individually

Inside `.venv` (or globally if installed with `--global`):

```bash
# Run unit & integration tests
pytest -v

# Run tests with coverage report
pytest -v --cov=gnome_theme_manager

# Linting
ruff check src tests

# Code formatting
ruff format src tests

# Strict type checking
mypy --strict src
```

---

## 🚀 3. Running from Source

You can run the application directly from source without installing it globally:

### Using the launcher script
```bash
# Launch the GTK4 / Libadwaita Graphical Interface:
./scripts/run_app.sh

# Run CLI commands:
./scripts/run_app.sh current
./scripts/run_app.sh list
./scripts/run_app.sh apply --gtk "Adwaita-dark" --icon "Papirus"
```

### Running directly with Python
```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/src"

# GUI:
python3 -m gnome_theme_manager gui

# CLI:
python3 -m gnome_theme_manager.cli.main --help
```

---

## 🌐 4. Translations & Localization (i18n)

GNOME Theme Manager uses `gettext` for multi-language support.

### Compiling translations
```bash
python3 scripts/compile_translations.py
```

### Testing translations in different locales
```bash
# Italian
LC_ALL=it_IT.UTF-8 LANG=it_IT.UTF-8 ./scripts/run_app.sh

# English (Default)
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 ./scripts/run_app.sh

# Automated translation tests
pytest tests/test_i18n.py
```

---

## 📦 5. Building the AppImage Bundle

To package the standalone AppImage executable:
```bash
chmod +x scripts/build-appimage.sh
./scripts/build-appimage.sh
```
The output `.AppImage` bundle will be generated in `dist/`.
