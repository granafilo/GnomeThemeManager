# Phase 6: Hardening, Packaging, and Sandbox Distribution

## Phase Goals

Make the application resilient, secure, and easily distributable across modern Linux distributions:
1. **Flatpak Packaging**: Creation of Flatpak manifests (`io.github.granafilo.ThemeManager.json` / `.yaml`) and proper filesystem permission configuration.
2. **GNOME 45+ / 46+ and Wayland Support**: Proper handling of theming constraints and GTK4/Libadwaita override symlinks.
3. **Advanced Features**:
   - Save and restore complete desktop presets (GTK + Icons + Cursors + Shell + Dark style).
   - Theme previews and inspection.
   - Configuration export and import.

---

## Flatpak Sandbox Details

### Filesystem and D-Bus Permissions
For sandbox interaction with the host system:
- `finish-args`:
  - `--filesystem=xdg-data/themes:create` (access to `~/.local/share/themes`)
  - `--filesystem=xdg-data/icons:create` (access to `~/.local/share/icons`)
  - `--talk-name=org.gnome.Settings` or GSettings access via portal.
  - `--filesystem=xdg-download:ro` (to select archives from the Downloads folder).

---

## Architecture and Involved Modules

```text
packaging/
├── appimage/
│   ├── io.github.granafilo.ThemeManager.desktop
│   ├── io.github.granafilo.ThemeManager.svg
│   └── io.github.granafilo.ThemeManager.metainfo.xml
src/gnome_theme_manager/
└── core/
    ├── presets.py          # Preset management (JSON)
    └── sandbox_bridge.py   # Flatpak/Snap propagation and detection
```

---

## Implementation Checklist

- [x] Flatpak and Snap propagation bridge logic in `SandboxBridge`.
- [x] Preset management in `PresetManager` with schema validation.
- [x] AppImage packaging scripts in `scripts/build-appimage.sh`.
- [x] Graceful fallbacks when running without sandbox runtimes.
