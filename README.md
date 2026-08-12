# GNOME Theme Manager

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Un'applicazione modulare in Python per la scansione, gestione, installazione e applicazione di temi GTK, set di icone e cursori su ambiente desktop **GNOME**.

Il progetto è strutturato a strati incrementali: parte da un core riutilizzabile e una CLI minimale, fino ad arrivare a una GUI nativa GTK4/Libadwaita e al packaging Flatpak.

---

## 📑 Indice

- [Caratteristiche Principali](#-caratteristiche-principali)
- [Architettura del Repository](#-architettura-del-repository)
- [Prerequisiti di Sistema](#-prerequisiti-di-sistema)
- [Installazione e Setup Sviluppo](#-installazione-e-setup-sviluppo)
- [Guida all'Uso Rapido (CLI)](#-guida-alluso-rapido-cli)
- [Roadmap di Sviluppo](#-roadmap-di-sviluppo)
- [Testing e Qualità del Codice](#-testing-e-qualit-del-codice)
- [Licenza](#-licenza)

---

## ✨ Caratteristiche Principali

- 🔍 **Scansione Intelligente**: Individua automaticamente i temi installati a livello utente (`~/.local/share/themes`, `~/.local/share/icons`) e di sistema (`/usr/share/...`).
- ⚙️ **Integrazione Nativa GSettings**: Gestione diretta dello schema `org.gnome.desktop.interface` tramite `PyGObject` (`Gio.Settings`).
- 📦 **Gestione & Installazione Archivi**: Estrazione e validazione automatica di file `.zip`, `.tar.gz`, `.tar.xz` con protezione da path traversal.
- 🧩 **Architettura Modulare Disaccoppiata**: Layer `core` puro, privo di I/O UI, facilmente integrabile con CLI, script esterni o interfacce grafiche (Tkinter, GTK4/Libadwaita).

---

## 📂 Architettura del Repository

```text
GnomeThemeManager/
├── .gitignore                      # Esclusioni Python, virtualenv, build e IDE
├── README.md                       # Questa documentazione
├── pyproject.toml                  # Configurazione package PEP 517/621 & entrypoints
├── requirements.txt                # Dipendenze runtime
├── requirements-dev.txt            # Dipendenze sviluppo e test
├── docs/                           # Documentazione e specifiche
│   ├── roadMap.md                  # Roadmap generale
│   └── phases/                     # Documenti dettagliati per ciascuna fase
│       ├── 01-cli-mvp.md
│       ├── 02-theme-installer.md
│       ├── 03-core-architecture.md
│       ├── 04-gui-tkinter.md
│       ├── 05-gui-gtk-native.md
│       └── 06-sandboxing-hardening.md
├── src/
│   └── gnome_theme_manager/        # Package principale
│       ├── core/                   # Logica di dominio, scansione e GSettings
│       ├── cli/                    # Interfaccia da riga di comando
│       ├── gui_tk/                 # Prototipo grafico Tkinter
│       └── gui_gtk/                # GUI Nativa GTK4 / Libadwaita
└── tests/                          # Suite di test unitari e fixture
```

---

## 🛠️ Prerequisiti di Sistema

`GnomeThemeManager` interagisce con le librerie di sistema GNOME tramite **PyGObject** (`gi.repository`).

### Ubuntu / Debian / Pop!_OS
```bash
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-glib-2.0 gir1.2-gtk-3.0
```

### Fedora / RHEL
```bash
sudo dnf install python3 python3-gobject gtk3
```

### Arch Linux / Manjaro
```bash
sudo pacman -S python python-gobject gtk3
```

---

## 🚀 Installazione e Setup Sviluppo

Poiché `PyGObject` si interfaccia con i binding C del sistema, si consiglia di creare il virtual environment abilitando l'accesso ai package di sistema (`--system-site-packages`):

```bash
# 1. Clona la repository
git clone https://github.com/tuo-username/GnomeThemeManager.git
cd GnomeThemeManager

# 2. Crea e attiva l'ambiente virtuale
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# 3. Installa il progetto in modalità modificabile (editable) con dipendenze dev
pip install -e ".[dev]"
```

---

## 💻 Guida all'Uso Rapido (CLI)

Una volta installato, il comando `gnome-theme-manager` sarà disponibile nel tuo path (oppure invocabile con `python3 -m gnome_theme_manager.cli`):

```bash
# Mostra i temi attualmente applicati
gnome-theme-manager current

# Elenca tutti i temi GTK disponibili
gnome-theme-manager list --type gtk

# Applica un nuovo tema GTK e set di icone
gnome-theme-manager apply --gtk "Adwaita-dark" --icon "Papirus"
```

---

## 🗺️ Roadmap di Sviluppo

| Fase | Descrizione | Documentazione | Stato |
| :--- | :--- | :--- | :--- |
| **Fase 1** | MVP CLI (Scanner + Switcher GSettings) | [docs/phases/01-cli-mvp.md](docs/phases/01-cli-mvp.md) | 🟡 *In pianificazione* |
| **Fase 2** | Installer temi da archivi (.zip / .tar.*) | [docs/phases/02-theme-installer.md](docs/phases/02-theme-installer.md) | ⚪ *Pianificato* |
| **Fase 3** | Core Library & Facade API | [docs/phases/03-core-architecture.md](docs/phases/03-core-architecture.md) | ⚪ *Pianificato* |
| **Fase 4** | Prototipo GUI semplice (Tkinter) | [docs/phases/04-gui-tkinter.md](docs/phases/04-gui-tkinter.md) | ⚪ *Pianificato* |
| **Fase 5** | GUI Nativa GNOME (GTK4 / Libadwaita) | [docs/phases/05-gui-gtk-native.md](docs/phases/05-gui-gtk-native.md) | ⚪ *Pianificato* |
| **Fase 6** | Packaging Flatpak & Hardening | [docs/phases/06-sandboxing-hardening.md](docs/phases/06-sandboxing-hardening.md) | ⚪ *Pianificato* |

Consulta [docs/roadMap.md](docs/roadMap.md) per la visione d'insieme.

---

## 🧪 Testing e Qualità del Codice

```bash
# Esecuzione dei test unitari
pytest

# Verifica del codice con Ruff linter
ruff check .
```

---

## 📄 Licenza

Rilasciato sotto licenza MIT. Consulta il file `LICENSE` per maggiori dettagli.