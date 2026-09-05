# 📦 Installation and Execution Guide - GNOME Theme Manager

This guide explains how to install, run, and build the **GNOME Theme Manager** **Flatpak** package.

---

## ⚡ 1. Flatpak Installation (Recommended)

GNOME Theme Manager is distributed via Flatpak with sandboxed security and native desktop theming capabilities.

### Method A: One-Click `.flatpakref` (Recommended)

1. Download `GNOMEThemeManager.flatpakref` from the latest [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases).
2. Double-click the file in Files (Nautilus) or open it with GNOME Software / App Center.
3. Or install via CLI:
   ```bash
   flatpak install GNOMEThemeManager.flatpakref
   ```

### Method B: Offline Standalone Single-File Bundle (`.flatpak`)

1. Download `GNOMEThemeManager-1.5.0-x86_64.flatpak` from [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases).
2. Install the bundle:
   ```bash
   flatpak install --bundle GNOMEThemeManager-1.5.0-x86_64.flatpak
   ```

### Running the Application

Launch from your desktop application grid or via terminal:
```bash
flatpak run io.github.granafilo.ThemeManager
```

---

## 🛠️ 2. Building Flatpak Locally

To build the Flatpak repository, standalone `.flatpak` bundle, and `.flatpakref` from source:

```bash
git clone https://github.com/granafilo/GnomeThemeManager.git
cd GnomeThemeManager
chmod +x build-flatpak.sh
./build-flatpak.sh
```

The script will automatically build using the GNOME 46 runtime, generate a local repository, and export the packages into `dist/`:
- `dist/GNOMEThemeManager-1.5.0-x86_64.flatpak` (Standalone offline bundle)
- `dist/GNOMEThemeManager.flatpakref` (One-click installer)

---

## 📋 3. System Prerequisites (For Source Development)

If running the Python code directly from source outside of Flatpak:

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

The script will generate the `.AppImage` bundle inside the `dist/` directory, complete with bundled `.DirIcon`, multi-resolution PNG icons (128x128, 256x256, 512x512), and hicolor app/mimetypes integration.

### 🎨 Application Icon Sources

The application icons bundled into the AppImage and desktop integrations are located in the following repository paths:

- **Multi-size PNG Icons**: `data/icons/hicolor/{128x128,256x256,512x512}/apps/io.github.granafilo.ThemeManager.png`
- **Scalable SVG Master**: `data/icons/hicolor/scalable/apps/io.github.granafilo.ThemeManager.svg`
- **AppImage Root Bundle Icons**: `appimage/io.github.granafilo.ThemeManager.png` and `appimage/io.github.granafilo.ThemeManager.svg`
- **Desktop Entry (`Icon=io.github.granafilo.ThemeManager`)**: `data/desktop/io.github.granafilo.ThemeManager.desktop` and `appimage/io.github.granafilo.ThemeManager.desktop`

To update the application icon in the future, replace the PNG and SVG files in `data/icons/hicolor/` and re-run `./scripts/build-appimage.sh`.

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
