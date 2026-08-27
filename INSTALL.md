# 📦 Installation and Execution Guide - GNOME Theme Manager

This guide explains how to run, install, and optionally build the **GNOME Theme Manager** **AppImage** package from source.

---

## ⚡ 1. Quick Start via AppImage (Recommended)

An **AppImage** package is a single portable executable containing the application and its Python dependencies.

### Steps to run:

1. Download the latest `.AppImage` release from [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases).
2. Open your terminal in the download folder and grant execution permissions:

```bash
chmod +x GNOMEThemeManager-1.0.0-x86_64.AppImage
```

3. Launch the application:

```bash
./GNOMEThemeManager-1.0.0-x86_64.AppImage
```

### AppImage and FUSE

The AppImage build uses `appimagetool` in `extract-and-run` mode, so CI runners do not require a FUSE mount.

To run the AppImage on Ubuntu 24.04, the compatible FUSE 2 library may be required:

```bash
sudo apt install libfuse2t64
```

For older Ubuntu releases (e.g. 22.04), use:

```bash
sudo apt install libfuse2
```

---

## 📋 2. System Prerequisites

Because GNOME Theme Manager is a native **GTK4** and **Libadwaita** application, the host system must provide the GTK4 / Libadwaita runtime libraries and PyGObject.

### Ubuntu 22.04 LTS / 24.04 LTS and Debian 12+

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

### Fedora 38+

```bash
sudo dnf install -y python3-gobject gtk4 libadwaita
```
---

## 🛠️ 3. Building the AppImage Locally

If you want to package the AppImage locally from source:

### 1. Clone the repository:

```bash
git clone https://github.com/granafilo/GnomeThemeManager.git
cd GnomeThemeManager
```

### 2. Run the build script:

```bash
chmod +x scripts/build-appimage.sh
./scripts/build-appimage.sh
```

The script will generate the `.AppImage` bundle inside the `dist/` directory.

---

## 🔍 4. Troubleshooting

### ⚠️ Error: `dlopen(): error loading libfuse.so.2`
On newer Linux distributions like Ubuntu 22.04+ / 24.04+, FUSE 2 might not be installed by default.

**Solution (Ubuntu/Debian):**
```bash
sudo apt install -y libfuse2t64 || sudo apt install -y libfuse2
```

---

## ⚙️ 5. Development Mode (venv)

To run in development mode without packaging:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]

# Run CLI
gnome-theme-manager --help

# Run GTK4 GUI
gnome-theme-manager --gui
```
