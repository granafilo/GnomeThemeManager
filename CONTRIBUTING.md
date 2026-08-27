# Contributing to GNOME Theme Manager

Thank you for your interest in contributing to **GNOME Theme Manager**!

---

## 🛠️ Development Setup & Workflow

We have streamlined the development experience. For step-by-step instructions on setting up your environment, running the test suite, code quality checks, and translation tools, please see:

👉 **[Development & Testing Guide](docs/DEVELOPMENT.md)**

---

## 📋 Core Guidelines

1. **Architecture Rule**: All business logic belongs in `src/gnome_theme_manager/core/`. The GUI (`gui_gtk/`) and CLI (`cli/`) must consume the exact same public APIs.
2. **Type Safety**: All modules must include PEP 484 type hints and pass `mypy --strict src`.
3. **Clean Code & Formatting**: Follow PEP 8 and verify code formatting with `ruff check src tests` and `ruff format --check src tests`.
4. **Testing**: Maintain high test coverage (≥ 80% on `core/`). All tests must be deterministic and isolated. Run `./scripts/run_tests.sh` before submitting changes.
5. **Internationalization (i18n)**: All new user-visible strings must use `_()` and be added to `po/en.po` and `po/it.po`.
6. **Commit Messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/) standards.

---

## ⚖️ Contribution Licensing

By submitting code, documentation, assets, or translations to this project, you agree to license your contributions under the terms of the **GNU General Public License version 3 or later (GPL-3.0-or-later)**.

Every new source file must include the appropriate SPDX identifier:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
```
