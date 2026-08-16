# Phase 1: Terminal MVP (Minimal Theme Switcher)

## Phase Goals

The first phase focuses on building a functional command-line prototype (CLI) capable of:
1. **Scanning the filesystem** to discover GTK themes, icon packs, and cursor themes installed in user and system directories.
2. **Interacting with GNOME GSettings** to read currently active themes and apply new ones.
3. Providing a clean, usable, and extensible initial text interface.

---

## Architecture and Involved Modules

```text
src/gnome_theme_manager/
├── core/
│   ├── constants.py        # XDG paths and GSettings key definitions
│   ├── models.py           # ThemeType, Theme, ThemeSet
│   ├── scanner.py          # Filesystem discovery logic
│   ├── gsettings.py        # Gio.Settings wrapper
│   └── errors.py           # Specific exceptions
└── cli/
    ├── __main__.py         # python -m gnome_theme_manager.cli
    ├── args.py             # argparse parser
    └── main.py             # Command router and terminal output
```

---

## Technical Details and Specifications

### 1. XDG Scan Paths
- **GTK / Application Themes**:
  - User: `~/.local/share/themes`, `~/.themes` (legacy)
  - System: `/usr/share/themes`
- **Icon Packs and Cursor Themes**:
  - User: `~/.local/share/icons`, `~/.icons` (legacy)
  - System: `/usr/share/icons`

### 2. GSettings Schemas and Keys
Schema: `org.gnome.desktop.interface`
- `gtk-theme` (string): Theme name for GTK3/GTK4 widgets.
- `icon-theme` (string): Icon pack name.
- `cursor-theme` (string): Mouse cursor theme name.
- `color-scheme` (string, optional for GNOME 42+): `'default'` or `'prefer-dark'`.

### 3. Planned CLI Commands

```bash
# Show current state of applied themes
gnome-theme-manager current

# List all available themes in system and home directories
gnome-theme-manager list [--type gtk|icon|cursor|all]

# Apply one or more themes
gnome-theme-manager apply --gtk "Adwaita-dark" --icon "Papirus" --cursor "Yaru"
```

---

## Implementation Checklist

- [x] **Constants & Models**:
  - Implement `Theme` dataclass with attributes: `name`, `theme_type`, `path`, `is_user_level`.
  - Define `ThemeType` enum (`GTK`, `ICON`, `CURSOR`).
- [x] **GSettings Client**:
  - Wrapper around `gi.repository.Gio.Settings("org.gnome.desktop.interface")`.
  - Methods `get_current() -> ThemeSet` and `apply(theme_set: ThemeSet)`.
  - Safe fallback / dedicated exception if schema is missing (e.g. non-GNOME environments).
- [x] **Scanner**:
  - Safe directory iteration with `pathlib.Path`.
  - Duplicate detection (user themes shadow system themes with the same name).
- [x] **CLI Interface**:
  - Argparse with subcommands (`current`, `list`, `apply`).
  - Formatted readable output (ASCII tables or colored lists).
- [x] **Unit Tests**:
  - Tests for `scanner` with temporary directory mocks.
  - Tests for `gsettings` with `Gio.Settings` mocks.
  - CLI integration tests for all commands.
