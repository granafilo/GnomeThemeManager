# 🗄️ Deprecated: AppImage Packaging & Workflows

> **Note**: As of version 1.5.0, **AppImage packaging is deprecated and unsupported**.
> The primary, supported distribution and sandbox format for **GNOME Theme Manager** is **Flatpak** (`org.gnome.Platform//46` & Libadwaita).

---

## 📌 Reasons for Deprecation

1. **Native GNOME 46 & Libadwaita Integration**:
   - Modern GTK4 and Libadwaita runtime libraries depend heavily on compatible host GObject Introspection bindings and GLib/dconf subsystems.
   - Bundling complete GTK4 and Adwaita graphic stacks into a portable AppImage caused frequent dynamic linking issues (e.g., FUSE2 deprecation in Ubuntu 24.04, GIO module mismatches, and GSettings schema collisions).

2. **Sandboxed D-Bus & Settings Synchronization**:
   - Flatpak provides built-in fine-grained portal permissions (`ca.desrt.dconf`, `org.gnome.Shell.Extensions`, `xdg-data/themes`, `xdg-data/icons`).
   - Flatpak manifests (`flatpak/io.github.granafilo.ThemeManager.yml`) handle all dependencies (e.g. `dconf` Meson module, Python wheels) deterministically.

3. **Distribution & Packaging**:
   - Flatpak provides both one-click `.flatpakref` files and standalone `.flatpak` single-file bundles via `scripts/build-flatpak.sh` and GitHub Actions CI.

---

## 🗂️ Archived Contents

This directory preserves legacy AppImage assets for reference:
- `build-appimage.sh`: Legacy AppImage build script.
- `build-appimage.yml`: Legacy GitHub Actions workflow.
- `AI_APPIMAGE_PROMPT.md`: Historical prompt notes for AppImage builds.
- `io.github.granafilo.ThemeManager.desktop`: Legacy desktop entry file.
- `io.github.granafilo.ThemeManager.metainfo.xml`: Legacy AppStream metainfo.
- `io.github.granafilo.ThemeManager.{png,svg}`: Legacy icon assets.

Active, maintained desktop entries and AppStream metadata are located in:
- `data/desktop/io.github.granafilo.ThemeManager.desktop`
- `data/metainfo/io.github.granafilo.ThemeManager.metainfo.xml`
- `flatpak/io.github.granafilo.ThemeManager.yml`
