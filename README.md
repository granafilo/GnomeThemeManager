# GNOME Theme Manager

![Build AppImage](https://github.com/granafilo/GnomeThemeManager/actions/workflows/build-appimage.yml/badge.svg)
![AppImage](https://img.shields.io/badge/AppImage-Portable-blue?logo=appimage&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20GNOME-4EAA25?logo=gnome&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-3584E4)
![License](https://img.shields.io/badge/License-MIT-success)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

Manager modulare in Python per gestire temi GTK, icone, cursori e GNOME Shell su desktop GNOME.

## Tag

GNOME, GTK4, Libadwaita, PyGObject, Themes, CLI, Linux Desktop, Snap, Flatpak

## Indice

- [Panoramica](#panoramica)
- [Feature](#feature)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Quick Start](#quick-start)
- [Comandi CLI principali](#comandi-cli-principali)
- [Avvio GUI](#avvio-gui)
- [Sviluppo e test](#sviluppo-e-test)
- [Struttura repository](#struttura-repository)
- [Documentazione](#documentazione)
- [Licenza](#licenza)

## Panoramica

Il progetto include:
- CLI completa per automazione e scripting.
- GUI nativa GNOME con GTK4/Libadwaita.
- GUI Tkinter legacy come fallback temporaneo.

Versione pacchetto attuale: 0.1.0

## Feature

- Lettura stato temi correnti con current
- Elenco temi installati per tipo con list
- Applicazione temi GTK, icone, cursori, shell con apply
- Installazione temi da archivio con install
- Disinstallazione temi utente con uninstall
- Gestione preset con preset list, save, apply, delete
- Stato integrazione sandbox Snap/Flatpak con sandbox-status
- Propagazione tema verso runtime sandbox (opzionale)
- Override GTK4 in ~/.config/gtk-4.0 quando applicabile

## Requisiti

- Python >= 3.10
- Linux con ambiente desktop GNOME
- gsettings disponibile nel sistema

Dipendenze Python:
- PyGObject >= 3.42.0

Pacchetti GUI GTK4/Libadwaita (Ubuntu/Debian):

	sudo apt update
	sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1

Pacchetti GUI Tkinter fallback (opzionale):

	sudo apt update
	sudo apt install -y python3-tk

## Installazione

### Opzione A: AppImage Portabile (Consigliata)

Scarica il file eseguibile `.AppImage` dalle [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases) e avvialo:

```bash
chmod +x GNOMEThemeManager-0.1.0-x86_64.AppImage
./GNOMEThemeManager-0.1.0-x86_64.AppImage
```

Per le istruzioni dettagliate sui prerequisiti e compilazione locale, consulta **[INSTALL.md](INSTALL.md)**.

### Opzione B: Installazione da sorgenti (Venv)

	git clone https://github.com/granafilo/GnomeThemeManager.git
	cd GnomeThemeManager

	python3 -m venv .venv
	source .venv/bin/activate

	pip install --upgrade pip
	pip install -e .

Per strumenti di sviluppo:

	pip install -e .[dev]

## Quick Start

	gnome-theme-manager --help
	gnome-theme-manager current
	gnome-theme-manager list

## Comandi CLI principali

Mostra temi correnti:

	gnome-theme-manager current

Elenca solo temi GTK utente:

	gnome-theme-manager list --type gtk --user-only

Applica tema GTK e icone:

	gnome-theme-manager apply --gtk Nordic-dark --icon Papirus-Dark

Applica tema unificato (stesso nome per GTK/Shell se presenti):

	gnome-theme-manager apply --theme Catppuccin-Mocha

Installa tema da archivio:

	gnome-theme-manager install --file ~/Scaricati/Nordic.tar.xz

Disinstalla tema utente:

	gnome-theme-manager uninstall --name Nordic --type gtk --yes

Preset:

	gnome-theme-manager preset save setup-lavoro
	gnome-theme-manager preset list
	gnome-theme-manager preset apply setup-lavoro

Sandbox status:

	gnome-theme-manager sandbox-status

## Avvio GUI

GUI nativa GTK4/Libadwaita:

	gnome-theme-manager --gui
	gnome-theme-manager gui

GUI Tkinter legacy (fallback):

	gnome-theme-manager --tk-gui
	gnome-theme-manager gui-tk

## Sviluppo e test

Esegui test:

	pytest -v

Lint con Ruff:

	ruff check src tests

Script unico:

	bash scripts/run_all_tests.sh

Script utili:

- scripts/run_cli.sh — esegue la CLI senza installare il pacchetto
- scripts/run_all_tests.sh — suite completa pytest + ruff
- scripts/test_env.sh — bootstrap ambiente di sviluppo (.venv + dipendenze)
- scripts/cleanup-repo.sh — pulizia artefatti di build/cache locali

## Struttura repository

	src/gnome_theme_manager/
	  cli/        parser argomenti e routing comandi
	  core/       logica dominio (scanner, manager, installer, gsettings, sandbox)
	  gui_gtk/    GUI nativa GNOME (GTK4/Libadwaita)
	  gui_tk/     GUI legacy Tkinter
	tests/        test unitari e integrazione
	docs/         roadmap e fasi implementative

## Documentazione

- [Guida Installazione AppImage](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](docs/ROADMAP.md)
- [Fase 1 - CLI MVP](docs/phases/01-cli-mvp.md)
- [Fase 2 - Theme Installer](docs/phases/02-theme-installer.md)
- [Fase 3 - Core Architecture](docs/phases/03-core-architecture.md)
- [Fase 4 - GUI Tkinter](docs/phases/04-gui-tkinter.md)
- [Fase 5 - GUI GTK Native](docs/phases/05-gui-gtk-native.md)
- [Fase 6 - Sandboxing & Hardening](docs/phases/06-sandboxing-hardening.md)

## Licenza

[MIT](LICENSE)