# Phase 2: Archive Management and Theme Installation

## Phase Goals

Automate and secure the installation of downloaded themes (e.g. from GNOME-Look or GitHub/GitLab repositories):
1. Support popular archive formats: `.zip`, `.tar.gz`, `.tar.xz`, `.tar.bz2`.
2. Validate internal theme structure prior to installation.
3. Install themes into appropriate user directories (`~/.local/share/themes` or `~/.local/share/icons`).
4. Prevent archive extraction vulnerabilities (e.g. Zip Slip / directory traversal).

---

## Architecture and Involved Modules

```text
src/gnome_theme_manager/
├── core/
│   ├── installer.py        # Extraction, validation, and copy logic
│   └── errors.py           # ThemeValidationError, ArchiveExtractionError
└── cli/
    └── args.py             # `install` subcommand
```

---

## Technical Details and Specifications

### 1. Archive Recognition and Formats
- Identification via extension and/or magic bytes.
- Standard library usage: `zipfile`, `tarfile`, `tempfile`, `shutil`.

### 2. Structural Theme Validation
A theme archive typically has one of two directory layouts:
- **Single root layout**: `MyTheme/gtk-3.0/gtk.css`
- **Flat layout**: `gtk-3.0/gtk.css` (requires creating a directory named after the theme).

Validation rules:
- **GTK Theme**: Presence of at least one of `gtk-3.0/`, `gtk-4.0/`, `gnome-shell/` directories or an `index.theme` file containing a `[Desktop Entry]` section.
- **Icon / Cursor Theme**: Presence of `index.theme` with `[Icon Theme]` section and/or a `cursors/` directory.

### 3. Security (Safe Extraction)
- Path Traversal prevention: ensure no archive member specifies absolute paths or `..` sequences escaping the destination directory.
- Use `tarfile.data_filter` (Python 3.12+) or explicit validation on each `member.name`.

### 4. Extended CLI Commands

```bash
# Install specifying theme type
gnome-theme-manager install --file ~/Downloads/Nordic.tar.xz --type gtk

# Automatic type detection
gnome-theme-manager install --file ~/Downloads/Tela-circle-blue.zip

# Uninstall a user theme
gnome-theme-manager uninstall --name "Nordic" --type gtk
```

---

## Implementation Checklist

- [x] **Installer Module**:
  - `safe_extract(archive_path, dest_dir)` function.
  - `detect_theme_type(extracted_dir) -> ThemeType` function.
  - `install_theme(archive_path, theme_type=None, custom_name=None) -> Theme` function.
  - `uninstall_theme(theme_name, theme_type) -> bool` function.
- [x] **CLI Subcommands**:
  - Added `install` and `uninstall` to `cli/args.py`.
- [x] **Unit Tests**:
  - Tests with mocked zip and tar archives covering valid and invalid layouts.
  - Security tests verifying path traversal protection.
