# 🗺️ Development Roadmap — GNOME Theme Manager

**Last updated**: August 22, 2026  
**Current version**: v1.4.1 (Phase 4 + Release v1.4.1 completed)  
**Status**: Active development (Release v1.4.1 Snap Integration & Diagnostics completed)

---

## 📊 Priority Overview

| Priority | Feature | Complexity | User Impact | Status |
| :--- | :--- | :---: | :---: | :---: |
| **P0** | 1-Click Backup and Restore | Medium | 🔴 Critical | 📋 Planned |
| **P1** | `color-scheme` integration (GNOME 42+) | Low | 🟠 High | 📋 Planned |
| **P1** | Flatpak Packaging | Medium | 🟠 High | 📋 Planned |
| **P2** | Flatpak GTK3 Runtime Detection | Medium | 🟡 Medium | 📋 Planned |
| **P2** | .deb Packaging (Ubuntu/Debian) | Medium | 🟡 Medium | 📋 Planned |
| **P3** | Advanced Environment Diagnostics | Low | 🟡 Medium | 💡 Idea |
| **P3** | Structured Logging | Low | 🟢 Low | 💡 Idea |
| **P3** | Internationalization (i18n) | Medium | 🟢 Low | 💡 Idea |

---

## 🎯 Phase 6 — Security and Resilience (v1.1.0)

### 6.1 1-Click Backup and Restore
**Priority**: P0 (Critical)  
**Estimate**: 3-4 days  
**Status**: 📋 To develop

#### Goals
- [ ] Create automatic "system-default" preset on first launch
- [ ] Implement emergency button "Restore Default Themes"
- [ ] Validate restore behavior in test environments

#### Implementation Details

**6.1.1 System Preset Data Structure**
```json
// ~/.config/gnome-theme-manager/presets/system-default.json
{
  "name": "System Default",
  "created_at": "2026-08-12T22:00:00Z",
  "is_system_preset": true,
  "settings": {
    "org.gnome.desktop.interface": {
      "gtk-theme": "Yaru",
      "icon-theme": "Yaru",
      "cursor-theme": "Yaru",
      "color-scheme": "default"
    }
  },
  "symlinks": {
    "gtk-4.0": null,
    "gtk-3.0": null
  },
  "notes": "Automatically created on first launch"
}
```

**6.1.2 Core Changes**
- [ ] `core/manager.py`: Add `create_system_backup_preset()` method
- [ ] `core/manager.py`: Add `restore_system_defaults()` method
- [ ] `core/presets.py`: Extend `PresetManager` to handle `is_system_preset` flag
- [ ] `core/presets.py`: Prevent deletion of system preset via UI

**6.1.3 GUI Changes**
- [ ] `pages/status_page.py`: Add "Danger Zone" section with red button
- [ ] `pages/status_page.py`: Confirmation dialog with explicit warning
- [ ] `pages/status_page.py`: Success/error banner post-restore

**6.1.4 Tests**
- [ ] Unit test: first launch preset creation
- [ ] Unit test: GSettings settings restore
- [ ] Unit test: GTK4 symlinks removal
- [ ] Manual test: apply corrupted theme -> restore -> verify UI

**6.1.5 Acceptance Criteria**
- ✅ On first launch, preset "System Default" exists in `~/.config/gnome-theme-manager/presets/`
- ✅ The "Restore Default Themes" button is visible only if overrides are active
- ✅ Confirmation dialog clearly states what will be restored
- ✅ After restore, `gtk-theme`, `icon-theme`, `cursor-theme` revert to Ubuntu defaults
- ✅ Symlinks in `~/.config/gtk-4.0/` are cleanly removed if present

---

### 6.2 `color-scheme` Integration (GNOME 42+)
**Priority**: P1 (High)  
**Estimate**: 2-3 days  
**Status**: 📋 To develop

#### Goals
- [ ] Read/write `org.gnome.desktop.interface.color-scheme`
- [ ] UI selector for light/dark preference
- [ ] Accent color support (when available)

#### Implementation Details

**6.2.1 GSettings Keys**
```bash
# Schema: org.gnome.desktop.interface
gsettings get org.gnome.desktop.interface.color-scheme
# Values: 'default', 'prefer-dark', 'prefer-light'

# (Optional, distro dependent)
gsettings get org.gnome.desktop.interface.accent-color
# Values: 'blue', 'green', 'orange', 'red', 'purple', 'brown', 'slate'
```

**6.2.2 Core Changes**
- [ ] `core/manager.py`: Extend `GSettingsClient` to manage `color-scheme`
- [ ] `core/manager.py`: Method `get_color_scheme()` -> returns `Literal['default', 'prefer-dark', 'prefer-light']`
- [ ] `core/manager.py`: Method `set_color_scheme(scheme: str)`
- [ ] `core/manager.py`: Method `get_accent_color()` (optional, with fallback)
- [ ] `core/manager.py`: Method `set_accent_color(color: str)` (optional)

**6.2.3 GUI Changes**
- [ ] `pages/themes_page.py`: Add `AdwComboRow` for "Color Preference"
- [ ] `pages/themes_page.py`: Populate with ['Default', 'Dark', 'Light']
- [ ] `pages/themes_page.py`: (Optional) `AdwComboRow` for "Accent Color"
- [ ] `controllers/themes_controller.py`: Connect selection to `ThemeManager.set_color_scheme()`

**6.2.4 Tests**
- [ ] Unit test: `color-scheme` read/write
- [ ] Manual test: switch preference -> verify with `gsettings get`
- [ ] Manual test: apply dark theme + light preference -> verify behavior

**6.2.5 Acceptance Criteria**
- ✅ User can select light/dark preference from the UI
- ✅ Selection persists after application restart
- ✅ Preference switch is reflected immediately in GTK4 apps
- ✅ (Optional) Accent color selection works on GNOME 45+

---

## 📦 Phase 7 — Packaging and Distribution (v1.2.0)

### 7.1 Flatpak Packaging
**Priority**: P1 (High)  
**Estimate**: 4-5 days  
**Status**: 📋 To develop

#### Goals
- [ ] Create manifest `io.github.<username>.ThemeManager.yml`
- [ ] Configure build with `flatpak-builder`
- [ ] Test on Ubuntu 22.04+, Fedora 38+
- [ ] Publish on Flathub (optional)

#### Implementation Details

**7.1.1 Flatpak Manifest**
```yaml
# io.github.<username>.ThemeManager.yml
app-id: io.github.<username>.ThemeManager
runtime: org.gnome.Platform
runtime-version: '45'
sdk: org.gnome.Sdk
command: gnome-theme-manager

build-options:
  env:
    - PYTHONPATH=/app/lib/python3.11/site-packages

finish-args:
  # GSettings/dconf access
  - --talk-name=org.gnome.Settings
  - --filesystem=~/.local/share/themes:ro
  - --filesystem=~/.local/share/icons:ro
  - --filesystem=~/.config/gnome-theme-manager:create
  - --filesystem=~/.config/gtk-4.0:create
  - --filesystem=host-os:ro
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri

modules:
  - name: gnome-theme-manager
    buildsystem: simple
    build-commands:
      - install -D gnome-theme-manager /app/bin/gnome-theme-manager
      - install -D main.py /app/lib/python3.11/site-packages/gnome_theme_manager/__main__.py
      - cp -r src/gnome_theme_manager /app/lib/python3.11/site-packages/
    sources:
      - type: dir
        path: .
      - type: script
        dest-filename: gnome-theme-manager
        commands:
          - python3 -m gnome_theme_manager.gui
    modules:
      - name: python3-gi
        buildsystem: simple
        build-commands:
          - pip3 install --prefix=/app PyGObject
```

**7.1.2 Build and Test**
```bash
# Build
flatpak-builder build --force-clean --install io.github.<username>.ThemeManager.yml

# Test
flatpak run io.github.<username>.ThemeManager

# Inspect permissions
flatpak info --show-permissions io.github.<username>.ThemeManager
```

**7.1.3 Flathub Publishing**
- [ ] Create repository `flathub/io.github.<username>.ThemeManager`
- [ ] Submit PR to https://github.com/flathub/flathub
- [ ] Pass review (license, metadata, security)

**7.1.4 Acceptance Criteria**
- ✅ Application launches with `flatpak run io.github.<username>.ThemeManager`
- ✅ Themes in `~/.local/share/themes` are visible
- ✅ Presets are saved in `~/.config/gnome-theme-manager`
- ✅ Permissions are minimal and documented

---

### 7.2 .deb Packaging (Ubuntu/Debian)
**Priority**: P2 (Medium)  
**Estimate**: 3-4 days  
**Status**: 📋 To develop

#### Goals
- [ ] Create `debian/` structure
- [ ] Configure `debian/control` with dependencies
- [ ] Build `.deb` package
- [ ] Test installation on Ubuntu 22.04+, 24.04+

#### Implementation Details

**7.2.1 debian/ Structure**
```text
debian/
├── changelog
├── compat
├── control
├── copyright
├── gnome-theme-manager.install
├── gnome-theme-manager.links
├── rules
└── source/
    └── format
```

**7.2.2 `debian/control` File**
```control
Source: gnome-theme-manager
Section: utils
Priority: optional
Maintainer: Your Name <your.email@example.com>
Build-Depends: debhelper (>= 13), python3-all, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1

Package: gnome-theme-manager
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, dconf-gsettings-backend
Description: Native theme manager for GNOME 42+
 GNOME Theme Manager is a modular, clean, and resilient desktop application for Ubuntu/GNOME.
Homepage: https://github.com/<username>/gnome-theme-manager
```

**7.2.3 Build**
```bash
# Install dependencies
sudo apt install debhelper python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Build
debuild -us -uc

# Install
sudo apt install ../gnome-theme-manager_1.2.0_all.deb
```

**7.2.4 Acceptance Criteria**
- ✅ Package installs cleanly with `apt install ./gnome-theme-manager_*.deb`
- ✅ The command `gnome-theme-manager` is available in PATH
- ✅ Dependencies are resolved automatically by apt

---

## 🔍 Phase 8 — Diagnostics and Compatibility (v1.3.0)

### 8.1 Flatpak GTK3 Runtime Detection
**Priority**: P2 (Medium)  
**Estimate**: 2-3 days  
**Status**: 📋 To develop

#### Goals
- [ ] Check if active theme is installed as a Flatpak runtime
- [ ] Display informative feedback to the user
- [ ] Suggest runtime installation when missing

#### Implementation Details

**8.1.1 Core Changes**
- [ ] `core/sandbox.py`: Add `check_gtk3_flatpak_runtime(theme_name: str) -> bool` method
- [ ] `core/sandbox.py`: Implement `flatpak list --runtime` output parser
- [ ] `core/sandbox.py`: Add `get_flatpak_gtk3_themes() -> list[str]` method

**8.1.2 Flatpak Commands**
```bash
# List installed runtimes
flatpak list --runtime | grep org.gtk.Gtk3theme

# Check specific theme
flatpak list --runtime | grep "org.gtk.Gtk3theme.Nordic"

# Install runtime (if needed)
flatpak install flathub org.gtk.Gtk3theme.Nordic
```

**8.1.3 GUI Changes**
- [ ] `pages/sandbox_page.py`: Add "GTK3 Themes for Flatpak" section
- [ ] `pages/sandbox_page.py`: Display ✅/❌ badges for each detected theme
- [ ] `pages/sandbox_page.py`: (Optional) "Install missing runtime" button

**8.1.4 Acceptance Criteria**
- ✅ The sandbox page indicates whether the GTK3 theme is available as a Flatpak runtime
- ✅ Clear messaging: "Theme X is installed for Flatpak applications"
- ✅ (Optional) User can trigger runtime installation with one click

---

### 8.2 Advanced Environment Diagnostics
**Priority**: P3 (Medium)  
**Estimate**: 1-2 days  
**Status**: 💡 Idea

#### Goals
- [ ] Display GNOME version
- [ ] Detect session type (X11/Wayland)
- [ ] Check critical extensions (e.g. "User Themes")

#### Implementation Details

**8.2.1 Information to Collect**
```bash
# GNOME version
gnome-shell --version

# Session type
echo $XDG_SESSION_TYPE

# Enabled extensions
gsettings get org.gnome.shell enabled-extensions

# User Themes extension
gsettings get org.gnome.shell enabled-extensions | grep user-theme
```

**8.2.2 GUI Changes**
- [ ] `pages/status_page.py`: Add "System Information" section
- [ ] `pages/status_page.py`: Display GNOME version, session type, and critical extension statuses

---

## 🛠️ Phase 9 — Maintenance and Quality (v1.4.0)

### 9.1 Structured Logging
**Priority**: P3 (Low)  
**Estimate**: 1-2 days  
**Status**: 💡 Idea

#### Goals
- [ ] Implement JSON file logger in `~/.local/state/gnome-theme-manager/`
- [ ] Log critical operations (theme applications, errors)
- [ ] Add CLI `--verbose` flag for debugging

#### Implementation Details

**9.1.1 Logger Configuration**
```python
# core/logger.py
import json
import logging
from pathlib import Path

LOG_DIR = Path.home() / ".local/state/gnome-theme-manager"
LOG_FILE = LOG_DIR / "app.log"


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("gnome_theme_manager")
    logger.setLevel(logging.DEBUG)

    # File handler (JSON)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        )
    )

    logger.addHandler(file_handler)
    return logger
```

---

### 9.2 Internationalization (i18n)
**Priority**: P3 (Low)  
**Estimate**: 2-3 days  
**Status**: 💡 Idea

#### Goals
- [ ] Integrate `gettext` for IT/EN translations
- [ ] Create `.po` files for Italian and English
- [ ] Translate all UI strings

#### Implementation Details

**9.2.1 Structure**
```text
locales/
├── it/
│   └── LC_MESSAGES/
│       └── gnome_theme_manager.po
└── en/
    └── LC_MESSAGES/
        └── gnome_theme_manager.po
```

**9.2.2 gettext Setup**
```python
# core/i18n.py
import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).parent.parent / "locales"


def setup_i18n(lang_code: str = "it"):
    translation = gettext.translation("gnome_theme_manager", LOCALE_DIR, languages=[lang_code])
    translation.install()
    return translation.gettext


_ = setup_i18n("it")
```

---

## 📅 Estimated Timeline

| Milestone | Version | Target Date | Main Features |
| :--- | :---: | :---: | :--- |
| **M0 (Phase 0)** | v1.0.0 | August 15, 2026 | Stabilization, Presets 2.0, Extensions, Unified Modals (Completed) |
| **M6** | v1.1.0 | September 2026 | Backup/Restore, color-scheme |
| **M7** | v1.2.0 | October 2026 | Flatpak & .deb Packaging |
| **M8** | v1.3.0 | November 2026 | Flatpak GTK3 Detection, Diagnostics |
| **M9** | v1.4.0 | December 2026 | Logging, i18n, Maintenance |

---

## 🎯 Priority Criteria

### P0 — Critical
- Essential features for safety and usability
- Blocker for production adoption
- **Example**: Backup and Restore

### P1 — High
- Highly requested features
- Significantly improves user experience
- **Example**: `color-scheme`, Flatpak Packaging

### P2 — Medium
- Useful but non-blocking features
- Can be delivered in subsequent updates
- **Example**: Flatpak GTK3 Runtime Detection, .deb Packaging

### P3 — Low
- Nice-to-have features
- Long-term maintenance value
- **Example**: Structured logging, Advanced diagnostics

---

## 📝 Developer Notes

1. **Before starting each phase**:
   - Create dedicated Git branch (e.g. `feature/backup-restore`)
   - Update `CHANGELOG.md` with planned features
   - Run `pytest tests/ -v` to ensure baseline passes

2. **After each completed feature**:
   - Update test suite
   - Run `ruff check src tests`
   - Commit with conventional commit message format

3. **Before release**:
   - Tag version: `git tag -a v1.1.0 -m "Release v1.1.0"`
   - Update `README.md` and release notes
   - Push tag to GitHub

---

## 🔗 Useful Resources

- [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/)
- [Libadwaita Documentation](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/)
- [Flatpak Documentation](https://docs.flatpak.org/)
- [Debian New Maintainers' Guide](https://www.debian.org/doc/manuals/maint-guide/)
- [Python gettext](https://docs.python.org/3/library/gettext.html)