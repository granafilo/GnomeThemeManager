# Phase 3: Core Library Architecture and Decoupling

## Phase Goals

Refine and consolidate the `gnome_theme_manager.core` layer so that it operates as a pure library consumable by any interface (CLI, GTK4, external scripts):
1. **Complete separation of I/O and UI**: No calls to `print()`, `input()`, or terminal dependencies inside `core`.
2. **Event / Callback / Logging System**: Standard `logging` module usage across all domain operations.
3. **Strict Type Annotations and Data Validation**: Complete dataclasses with full type hinting (`typing`, `dataclasses`).
4. **Complete Testability**: Headless test execution with complete mocks for filesystem and GSettings.

---

## Architecture and Public Core API

```text
gnome_theme_manager.core
├── ThemeManager        # Main facade class for coordinated access
├── models              # Theme, ThemeSet, ThemeType
├── scanner             # scan_themes(), get_theme_by_name()
├── gsettings           # GSettingsClient (read, write, schema check)
├── installer           # install_from_archive(), remove_theme()
└── errors              # GnomeThemeManagerError and subclasses
```

### Programmatic Usage Example (Facade Pattern)

```python
from gnome_theme_manager.core import ThemeManager, ThemeType

# Facade initialization
manager = ThemeManager()

# Retrieve current state
current_set = manager.get_current_themes()
print(f"Active GTK theme: {current_set.gtk_theme}")

# List available themes
gtk_themes = manager.list_themes(theme_type=ThemeType.GTK)
for theme in gtk_themes:
    print(f"- {theme.name} ({'User' if theme.is_user_level else 'System'})")

# Apply new theme
manager.apply_theme(ThemeType.GTK, "Nordic")
```

---

## Implementation Checklist

- [x] **`ThemeManager` Facade**:
  - Unification of scanning, applying, installing, and removing themes behind a single clean interface.
- [x] **Model Refactoring**:
  - `ThemeSet`: Utility methods (e.g. `as_dict()`, `is_complete()`).
  - `to_dict()`, `from_dict()` methods for JSON serialization and presets.
- [x] **Error Handling**:
  - Formal hierarchy:
    - `GnomeThemeManagerError`
      - `GSettingsUnavailableError`
      - `ThemeNotFoundError`
      - `ThemeValidationError`
      - `ArchiveExtractionError`
- [x] **Test Suite**:
  - Regression tests for all core classes and functions.
  - Ensured code coverage (>80%).
