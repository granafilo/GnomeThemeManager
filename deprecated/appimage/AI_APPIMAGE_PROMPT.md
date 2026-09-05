# 🤖 AI Prompt — GNOME Theme Manager AppImage Creation

**Copy and paste this prompt to an AI assistant to generate build resources and configurations.**

---

## 📋 Project Context

Developing **GNOME Theme Manager**, a Python 3 desktop application for Ubuntu/GNOME managing GTK4, Shell, Icon, and Cursor themes.

**Technical Stack**:
- Python 3.10+
- GTK 4.0 + Libadwaita 1.0
- PyGObject (`gi.repository`)
- Architecture: Facade Pattern separating GUI / CLI / Core

---

## 🎯 Goal

Create a single, portable executable **AppImage** file running across Linux distributions (Ubuntu 22.04+, Fedora 38+, Debian 12+, Arch).

---

## 📦 What to Generate

### 1. `appimage/` Directory with 3 Files

#### 1.1 `appimage/io.github.granafilo.ThemeManager.desktop`
Desktop entry for application launcher integration.

#### 1.2 `appimage/io.github.granafilo.ThemeManager.svg`
Application icon in SVG format.

#### 1.3 `appimage/io.github.granafilo.ThemeManager.metainfo.xml`
AppStream metadata for distribution validation.

---

### 2. Build Script `scripts/build-appimage.sh`
Automated bash script for AppImage extraction, dependency setup, and packaging with `appimagetool`.