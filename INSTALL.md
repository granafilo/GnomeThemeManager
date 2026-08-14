# 📦 Guida all'Installazione ed Esecuzione - GNOME Theme Manager

Questa guida illustra come eseguire, installare ed eventualmente compilare da sorgenti il pacchetto **AppImage** di **GNOME Theme Manager**.

---

## ⚡ 1. Esecuzione Rapida via AppImage (Consigliata)

Un pacchetto **AppImage** è un singolo file eseguibile portabile che contiene l'applicazione e le sue dipendenze Python.

### Passi per l'esecuzione:

1. Scarica l'ultima release del file `.AppImage` dalla sezione [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases).
2. Apri il terminale nella cartella di download e assegna i permessi di esecuzione:

```bash
chmod +x GNOMEThemeManager-0.9.0-beta3-x86_64.AppImage
```

3. Avvia l'applicazione:

```bash
./GNOMEThemeManager-0.9.0-beta3-x86_64.AppImage
```

### AppImage e FUSE

La build dell'AppImage usa `appimagetool` in modalità `extract-and-run`, quindi la CI non richiede un mount FUSE.

Per eseguire l'AppImage finale su Ubuntu 24.04 può essere necessaria la libreria FUSE 2 compatibile:

```bash
sudo apt install libfuse2t64
```

Per versioni Ubuntu precedenti (es. 22.04), utilizzare:

```bash
sudo apt install libfuse2
```

---

## 📋 2. Prerequisiti di Sistema

Poiché GNOME Theme Manager è un'applicazione nativa **GTK4** e **Libadwaita**, il sistema operativo ospitante deve disporre delle librerie di runtime GTK4 / Libadwaita e di PyGObject.

### Ubuntu 22.04 LTS / 24.04 LTS e Debian 12+

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

### Fedora 38+

```bash
sudo dnf install -y python3-gobject gtk4 libadwaita
```

### Arch Linux / Manjaro

```bash
sudo pacman -S --needed python-gobject gtk4 libadwaita
```

---

## 🛠️ 3. Compilazione Locale dell'AppImage

Se desideri pacchietare ed impacchettare autonomamente l'AppImage dal codice sorgente:

### 1. Clona la repository:

```bash
git clone https://github.com/granafilo/GnomeThemeManager.git
cd GnomeThemeManager
```

### 2. Assicurati che `appimagetool` sia presente o esegui lo script di build:

```bash
chmod +x scripts/build-appimage.sh
./scripts/build-appimage.sh
```

Lo script genererà il file `.AppImage` all'interno della cartella `dist/`.

---

## 🔍 4. Troubleshooting (Risoluzione Problemi)

### ⚠️ Errore: `dlopen(): error loading libfuse.so.2`
Sulle distribuzioni recenti come Ubuntu 22.04+ / 24.04+, FUSE 2 potrebbe non essere preinstallato per impostazione predefinita.

**Soluzione (Ubuntu/Debian):**
```bash
sudo apt install -y libfuse2t64 || sudo apt install -y libfuse2
```

In alternativa, puoi estrarre l'AppImage ed eseguirla direttamente senza FUSE:
```bash
./GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

### ⚠️ Errore PyGObject / `Namespace Gtk not available`
Verifica che i pacchetti `gir1.2-gtk-4.0` e `gir1.2-adw-1` siano installati correttamente nel sistema ospitante.
