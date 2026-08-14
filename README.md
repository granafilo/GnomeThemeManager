# GNOME Theme Manager

![Build AppImage](https://github.com/granafilo/GnomeThemeManager/actions/workflows/build-appimage.yml/badge.svg)
![Tests](https://github.com/granafilo/GnomeThemeManager/actions/workflows/tests.yml/badge.svg)
![AppImage](https://img.shields.io/badge/AppImage-Portable-blue?logo=appimage&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20GNOME-4EAA25?logo=gnome&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-3584E4)
![License](https://img.shields.io/badge/License-GPL--3.0-blue)
![Status](https://img.shields.io/badge/Status-Beta-orange)

## Stato del progetto

La versione 0.9.0-beta3 è una release destinata ai test pubblici.
Non viene ancora garantita la compatibilità con tutte le distribuzioni,
versioni di GNOME o temi non conformi agli standard attesi.

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
- [Traduzioni (i18n)](#traduzioni-i18n)
- [Struttura repository](#struttura-repository)
- [Documentazione](#documentazione)
- [Licenza](#licenza)

## Panoramica

Il progetto include:
- CLI completa per automazione e scripting.
- GUI nativa GNOME con GTK4/Libadwaita.
- GUI Tkinter legacy come fallback temporaneo.

Versione pacchetto attuale: 0.9.0-beta3 (PEP 440: 0.9.0b3)

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

## Installazione

### Opzione A: AppImage Portabile (Consigliata)

Scarica il file eseguibile `.AppImage` dalle [GitHub Releases](https://github.com/granafilo/GnomeThemeManager/releases) e avvialo:

```bash
chmod +x GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage
./GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage
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

## Interfaccia grafica

GNOME Theme Manager utilizza GTK4 e Libadwaita per l’interfaccia grafica.

Tkinter non è più supportato.

Avvio della GUI:

	gnome-theme-manager --gui
	gnome-theme-manager gui


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

## Configurazione, Backup e Ripristino

Theme Manager memorizza i suoi dati e i backup in percorsi XDG standard:
- **Manifest GTK4**: `$XDG_CONFIG_HOME/gnome-theme-manager/gtk4_manifest.json` (di default `~/.config/gnome-theme-manager/gtk4_manifest.json`).
- **File di backup**: `$XDG_DATA_HOME/gnome-theme-manager/backups/` (di default `~/.local/share/gnome-theme-manager/backups/`).
- **Preset**: `$XDG_CONFIG_HOME/gnome-theme-manager/presets/` (di default `~/.config/gnome-theme-manager/presets/`).

### Procedura di Rollback manuale
Se per qualsiasi motivo si desidera rimuovere l'override di Theme Manager e ripristinare i file originali manualmente:
1. Rimuovere i collegamenti simbolici correnti:
   `rm -f ~/.config/gtk-4.0/gtk.css ~/.config/gtk-4.0/gtk-dark.css`
   `rm -rf ~/.config/gtk-4.0/assets`
2. Copiare i file di backup dalla directory `backups` (se presenti) ripristinandoli con il nome originale in `~/.config/gtk-4.0/`.

## Matrice di Compatibilità
Gli ambienti testati e convalidati per questa release beta sono:

| Distribuzione | Versione | GNOME | GTK | Installazione | GUI | CLI | GTK4 override | Esito |
|---|---|---|---|---|---|---|---|---|
| Ubuntu | 24.04 LTS | GNOME 46 | GTK4 / GTK3 | Convalidato | Convalidato | Convalidato | Convalidato | ✓ Supportato |
| Ubuntu | 22.04 LTS | GNOME 42 | GTK4 / GTK3 | Convalidato | Convalidato | Convalidato | Convalidato | ✓ Supportato |
| Fedora | 40 | GNOME 46 | GTK4 | Convalidato | Convalidato | Convalidato | Convalidato | ✓ Supportato |
| Arch Linux | Rolling | GNOME 46 | GTK4 | Convalidato | Convalidato | Convalidato | Convalidato | ✓ Supportato |
| Debian | 12 | GNOME 43 | GTK4 / GTK3 | Non testato | Non testato | Non testato | Non testato | Parzialmente testato |

### Limitazioni Sandbox (Snap & Flatpak)
Le applicazioni all'interno di sandbox isolate (come Firefox in formato Snap o Flatpak) potrebbero non riflettere immediatamente i temi GTK installati nella cartella utente. Theme Manager include la propagazione automatica (tramite comandi `flatpak override` ed il controllo di `gtk-common-themes` per Snap), ma temi non standard richiedono pacchetti specifici della distribuzione.

### Dipendenze residue dell'AppImage
L'eseguibile AppImage di GNOME Theme Manager non include le librerie di runtime GTK4/Libadwaita o GObject Introspection host. Pertanto, l'ambiente host deve disporre di `python3-gi`, `gir1.2-gtk-4.0` e `gir1.2-adw-1` installati per garantire l'avvio della GUI nativa.

## Traduzioni (i18n)

GNOME Theme Manager supporta la localizzazione (i18n) tramite `gettext`.

### Come avviare l'applicazione in una lingua specifica
Per avviare l'applicazione forzando una lingua (ad esempio l'inglese o l'italiano), imposta le variabili d'ambiente `LANG` e `LC_ALL`:

```bash
# Avvio in inglese
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 python3 -m gnome_theme_manager

# Avvio in italiano
LC_ALL=it_IT.UTF-8 LANG=it_IT.UTF-8 python3 -m gnome_theme_manager
```

### AppImage e file di traduzione
L'AppImage include i file `.mo` nell'installazione Python del package, sotto `gnome_theme_manager/locale/`. Durante la build viene effettuata una copia esplicita della directory locale e viene impostata la variabile `TEXTDOMAINDIR` per garantire che `gettext` trovi le traduzioni anche all'interno del filesystem montato dell'AppImage.

```bash
./scripts/build-appimage.sh
./dist/GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage --appimage-extract
find squashfs-root -name "*.mo"

LANG=it_IT.UTF-8 ./dist/GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage
LANG=en_US.UTF-8 ./dist/GNOMEThemeManager-0.9.0-beta2-x86_64.AppImage
```

### Come aggiungere o aggiornare le traduzioni
Il progetto include script dedicati nella cartella `po/` per automatizzare l'estrazione e la compilazione delle stringhe senza dipendenze esterne:

1. **Aggiungere una nuova lingua**: Aggiungi il codice locale a `po/LINGUAS` (es. `es` per lo spagnolo).
2. **Estrarre le stringhe e aggiornare i file `.po`**:
   Esegui lo script di aggiornamento:
   ```bash
   ./po/update-po.sh
   ```
   Questo genererà/aggiornerà i file `.po` (es. `po/it.po` o `po/es.po`).
3. **Tradurre**: Apri il file `.po` appena aggiornato con un editor di testo o un tool come Poedit e traduci le coppie `msgid` -> `msgstr`.
4. **Compilare**: Rielabora `./po/update-po.sh` per compilare i file `.mo` pronti all'uso dell'applicazione in `src/gnome_theme_manager/locale/`.

### Come testare le traduzioni
Per convalidare e testare il funzionamento delle traduzioni, sono disponibili due strumenti:

1. **Test automatici**:
   Esegui la suite di test unitari dedicati con pytest:
   ```bash
   pytest tests/test_i18n.py
   ```
2. **Script di convalida manuale**:
   Esegui lo script che mostra l'output del comando `current` in italiano e in inglese per verificarne la traduzione a runtime:
   ```bash
   ./scripts/test-translation.sh
   ```

## Struttura repository

	src/gnome_theme_manager/
	  cli/        parser argomenti e routing comandi
	  core/       logica dominio (scanner, manager, installer, gsettings, sandbox)
	  gui_gtk/    GUI nativa GNOME (GTK4/Libadwaita)
	tests/        test unitari e integrazione
	docs/         roadmap e fasi implementative

## Documentazione

- [Guida Installazione AppImage](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](docs/ROADMAP.md)
- [Fase 1 - CLI MVP](docs/phases/01-cli-mvp.md)
- [Fase 2 - Theme Installer](docs/phases/02-theme-installer.md)
- [Fase 3 - Core Architecture](docs/phases/03-core-architecture.md)
- [Fase 5 - GUI GTK Native](docs/phases/05-gui-gtk-native.md)
- [Fase 6 - Sandboxing & Hardening](docs/phases/06-sandboxing-hardening.md)

## Licenza

GNOME Theme Manager è distribuito sotto licenza
[GNU General Public License v3.0 or later](LICENSE).

Il codice può essere utilizzato, studiato, modificato e redistribuito
nel rispetto dei termini della GPL-3.0-or-later.