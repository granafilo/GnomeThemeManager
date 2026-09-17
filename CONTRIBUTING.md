# Contributing to GNOME Theme Manager

Thank you for your interest in contributing to **GNOME Theme Manager**! We welcome bug reports, feature proposals, documentation improvements, translations, and code contributions.

---

## 🛠️ Development Setup

Before opening a pull request, please review our comprehensive guide:

👉 **[Development & Testing Guide](docs/DEVELOPMENT.md)**

It covers system dependencies, virtual environment setup, running tests with coverage, linting with Ruff, static typing with Mypy, and local Flatpak builds.

---

## 📋 Pull Request Guidelines

To ensure smooth review and integration, please follow these conventions:

1. **Architecture Isolation**: All domain logic must live in `src/gnome_theme_manager/core/`. The Libadwaita GUI and CLI must consume identical APIs.
2. **Type Hints**: All new modules and functions must include PEP 484 type annotations and pass `mypy --strict src`.
3. **Code Style**: Code must adhere to PEP 8 and pass `ruff check` and `ruff format`.
4. **Test Coverage**: Maintain ≥ 80% coverage on new core logic. Tests must be isolated and deterministic using `tmp_path`.
5. **Internationalization (i18n)**: Wrap all UI strings in `_()`. Update translation catalogs (`po/en.po`, `po/it.po`) in the same commit.
6. **Commit Standards**: Use clear, descriptive commit messages following [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat: add accent color picker`, `fix: handle missing cursor index`).

---

## ⚖️ Licensing

GNOME Theme Manager is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.

By submitting code, translations, or assets to this repository, you agree that your contributions will be licensed under the terms of the GPL-3.0-or-later. Every new Python source file must include the SPDX license identifier header:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
```
