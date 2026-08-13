# GNOME THEME MANAGER

## Panoramica delle fasi

Useremo Python 3 e moduli standard (os, pathlib, shutil, zipfile, tarfile) per file e directory, e PyGObject (gi.repository.Gio/GSettings) per scrivere le chiavi GNOME come `gtk-theme`, `icon-theme`, `cursor-theme` sotto `org.gnome.desktop.interface`. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)

Proposta di fasi:

1. MVP CLI: lettura e scrittura temi via terminale
2. Modulo di gestione archivi e installazione temi
3. Layer “core library” pulito e testabile
4. Prima GUI semplice (Tkinter) per concetti di base
5. GUI GTK (PyGObject) integrata con GNOME
6. Hardening GNOME/GTK4, sandbox (Flatpak/Snap) e rifiniture

Ogni fase è autonoma, incrementale e può essere messa su git come milestone/tag.

***

## Fase 1 – MVP da terminale (Theme Switcher minimale)

### Obiettivi

- Scrivere un piccolo tool CLI che:
  - Scansiona le directory temi e icone dell’utente.
  - Mostra i temi disponibili.
  - Permette di applicare un tema GTK, icone e cursori modificando le chiavi GSettings GNOME. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Acquisire famigliarità con:
  - Struttura basi di un progetto Python (package, moduli).
  - Uso di GSettings da Python con PyGObject (Gio.Settings o GLib/Gio). [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)

### Struttura proposta del codice

- `theme_manager_cli/`
  - `__init__.py`
  - `paths.py` – costanti e funzioni per le directory:
    - `~/.local/share/themes`
    - `~/.local/share/icons`. [samwhelp.github](https://samwhelp.github.io/note-about-ubuntu/read/desktop_environment/gnome-flashback/adjustment/theme.html)
  - `scanner.py` – funzioni per elencare i temi (GTK, icone, cursori).
  - `gsettings_client.py` – wrapper per leggere/scrivere `org.gnome.desktop.interface` (chiavi `gtk-theme`, `icon-theme`, `cursor-theme`). [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
  - `cli.py` – entrypoint con `argparse` o input testuale.
  - `__main__.py` – permette `python -m theme_manager_cli`.

### Moduli Python da usare

- Standard:
  - `os`, `pathlib` – per path, espansione `~`, listare directory.
  - `argparse` – per eventuali subcomandi (`list`, `apply`, ecc.).
- Terze parti:
  - `gi` (PyGObject) + `from gi.repository import Gio`:
    - `settings = Gio.Settings(schema='org.gnome.desktop.interface')`
    - `settings.set_string('gtk-theme', 'NomeTema')`, ecc. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)

### Potenziali ostacoli per un principiante

- Installazione PyGObject:
  - Su Ubuntu: `sudo apt install python3-gi gir1.2-glib-2.0 gir1.2-gtk-3.0` e simili. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
  - Eventuali errori di import (`ImportError: cannot import name Gio`).
- Comprendere GSettings:
  - Differenza tra `gsettings` da terminale e `Gio.Settings` in Python. [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)
  - Capire cosa sono schema e chiavi (`org.gnome.desktop.interface`, `gtk-theme`, ecc.). [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)
- Gestione di errori:
  - Tema inesistente (nome non presente nelle directory).
  - Eccezioni se lo schema non è disponibile (ambienti non GNOME “puri”).

***

## Fase 2 – Gestione archivi e installazione temi

### Obiettivi

- Estendere il tool per:
  - Prendere un archivio `.zip` / `.tar.xz` contenente un tema.
  - Riconoscere tipo di archivio.
  - Estrarre nella directory corretta (temi o icone) seguendo la struttura del tema. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Concettualmente: simulare quello che l’utente farebbe a mano, ma in modo sicuro e ripetibile.

### Struttura file aggiunta

- `installer.py` – funzioni:
  - `detect_archive_type(path)`
  - `extract_theme_archive(path, target_dir)`
  - `validate_theme_structure(path_estratto)` (controlla cartella con `gtk-3.0/`, `index.theme`, `cursors/` per icone/cursori, ecc.). [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Aggiornare `cli.py` con un comando:
  - `install-theme --type gtk|icon|cursor --file /path/to/archive.tar.xz`.

### Moduli Python da usare

- Standard:
  - `zipfile` – gestione `.zip`.
  - `tarfile` – gestione `.tar`, `.tar.gz`, `.tar.xz`.
  - `shutil` – spostare directory/folder estratte.
  - `tempfile` – cartelle temporanee per l’estrazione.
- (Opzionale) `logging` – log leggibili (utile per debugging e per un principiante vedere cosa succede).

### Potenziali ostacoli

- Strutture di archivi non standard:
  - Archivi che contengono direttamente il contenuto (es. `gtk-3.0/`) vs archivi che contengono una cartella root (`MyTheme/gtk-3.0/`).
- Permessi:
  - Alcuni utenti potrebbero voler installare in `/usr/share/themes` o `/usr/share/icons`, che richiede privilegi root; per l’MVP, limitarsi a directory utente. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Riconoscere correttamente il tipo di archivio:
  - Gestire errori se l’estensione non corrisponde al contenuto reale, oppure segnalare all’utente.
- Riconoscere tipo di tema (GTK vs icone vs cursori):
  - All’inizio, chiedere esplicitamente `--type`.
  - Solo più avanti si può tentare di auto-indovinare tramite cartelle o `index.theme`. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)

***

## Fase 3 – “Core library” pulita e modulare

### Obiettivi

- Refactoring per trasformare il codice in una piccola libreria Python riutilizzabile da:
  - CLI
  - GUI Tkinter
  - GUI GTK.
- Obiettivo architetturale: separare rigorosamente:
  - livello “core” (logica di business, filesystem, GSettings)
  - livello “UI” (CLI/GUI).

### Struttura proposta

- `theme_manager_core/`
  - `__init__.py`
  - `models.py` – classi semplici:
    - `Theme` (nome, tipo, percorso).
    - `ThemeSet` (gtk_theme, icon_theme, cursor_theme attivi).
  - `paths.py` – come prima.
  - `scanner.py` – ritorna liste di `Theme`.
  - `gsettings_client.py` – funzioni:
    - `get_current_themes() -> ThemeSet`
    - `apply_themes(ThemeSet)`. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
  - `installer.py` – funzioni per installare e ritornare l’oggetto `Theme`.
  - `errors.py` – eccezioni personalizzate.

- `theme_manager_cli/` ora diventa uno “strato sottilissimo” sopra `theme_manager_core`.

### Moduli Python da usare

- Oltre ai precedenti:
  - `dataclasses` – per definire `Theme`, `ThemeSet` come dataclass, codici leggibili anche per principianti.
  - (Opzionale) `typing` – `List[Theme]`, `Optional[str]` per preparare il terreno a un codice più robusto.

### Potenziali ostacoli

- Concetto di package multipli:
  - Struttura `src/` vs root, import relativi/assoluti.
- Gestione delle eccezioni:
  - Definire delle eccezioni custom (es. `ThemeInstallationError`) e usarle bene.
- Pensiero “a strati”:
  - Non mescolare più `input()` o `print()` dentro le funzioni core; tutta l’I/O rimane nella UI.

***

## Fase 4 – Prima GUI semplice con Tkinter (focus su flusso, non su estetica)

> Anche se non sarà l’interfaccia finale, Tkinter è utile per imparare a strutturare GUI e separare la logica core dal layer grafico.

### Obiettivi

- Creare una piccola GUI che:
  - Mostra le liste dei temi GTK, icone, cursori (es. 3 `Listbox` o `Combobox`).
  - Permette di selezionare e applicare i temi tramite i pulsanti (“Applica”).
  - Mostra l’attuale tema attivo (`get_current_themes()` dal core). [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)
- Imparare concetti base di GUI:
  - Event loop, callback, separazione tra stato GUI e logica.

### Struttura proposta

- `theme_manager_tk/`
  - `__init__.py`
  - `app.py` – classe `ThemeManagerTkApp`:
    - Costruisce finestra root Tk.
    - Inizializza widget.
    - Collega eventi (on_click_apply_gtk, ecc.) alle funzioni del core.
  - `main.py` – `if __name__ == "__main__": ThemeManagerTkApp().run()`.

### Moduli Python da usare

- Standard:
  - `tkinter` – base GUI.
  - `tkinter.ttk` – widget più moderni.
- Dal core:
  - Tutti i moduli di `theme_manager_core`.

### Potenziali ostacoli

- Threading / blocco GUI:
  - Operazioni lente (es. estrazione archivi grossi) possono bloccare la finestra; per l’MVP si può accettare, ma è un buon punto per parlare di “non bloccare l’UI”.
- Aggiornamento dinamico:
  - Dopo l’installazione di un nuovo tema, bisogna aggiornare la lista nella GUI.
- Layout manager:
  - `pack` vs `grid` vs `place` – può creare confusione; suggerisco `grid` con layout semplice.

***

## Fase 5 – GUI nativa GNOME con PyGObject/GTK

Questa è la fase chiave per arrivare a una app “vera” integrata con GNOME.

### Obiettivi

- Implementare una GUI basata su GTK (via PyGObject):
  - Finestra principale con:
    - Sidebar o tab per “Temi GTK”, “Icone”, “Cursori”.
    - Liste/Combo di temi disponibili.
    - Pulsanti per applicare, installare da archivio, rimuovere tema.
  - Integrazione base con theme/color scheme di GNOME (usare `Adwaita`/Libadwaita se possibile).
- Usare il core esistente (scanner, installer, gsettings) come backend.

### Struttura proposta

- `theme_manager_gtk/`
  - `__init__.py`
  - `app.py` – classe `ThemeManagerGtkApp`:
    - Deriva da `Gtk.Application` (se possibile Libadwaita `Adw.Application` in un passo successivo).
  - `windows.py` – finestra principale `MainWindow(Gtk.ApplicationWindow)`.
  - `widgets/` – eventuali widget riutilizzabili.
  - `resources/` – file `.ui` XML (builder), icone, ecc.

### Moduli Python da usare

- Terze parti:
  - `gi` (PyGObject) + `from gi.repository import Gtk, Gio` (e più avanti `Adw` per Libadwaita).
- Dal core:
  - `theme_manager_core.scanner`, `installer`, `gsettings_client`, `models`.

### Potenziali ostacoli

- Installazione e versione di PyGObject/GTK:
  - Differenze tra GTK3 e GTK4, e tra GNOME versioni diverse. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Concetto di “builder”:
  - Caricare UI da file `.ui` invece che creare tutti i widget a mano in Python.
- Track dello stato:
  - Tenere sincronizzato lo stato interno (tema selezionato) con ciò che è mostrato nei widget.
- Libadwaita e GTK4:
  - Libadwaita è lo standard moderno GNOME; usare `Adw.Application` richiede qualche passaggio in più, ma dà un aspetto molto più “nativo”. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)

***

## Fase 6 – GNOME/GTK4 refinement e sandbox (Flatpak/Snap)

### Obiettivi

- Migliorare compatibilità e robustezza:
  - Verificare comportamento con GTK4 (temi limitati, influenza di Libadwaita). [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
  - Gestire limitazioni sandbox (Flatpak/Snap):
    - Accesso a `~/.local/share/themes` e `~/.local/share/icons` richiede permessi specifici (filesystem overrides, ports di `xdg-desktop-portal`, ecc.). [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Aggiungere funzionalità opzionali:
  - Preview del tema (es. screenshot, icona di esempio).
  - “Preset” di temi (set GTK+icone+cursori salvati).
  - Integrazione con estensione Shell (eventualmente in futuro).

### Moduli / tecnologie da toccare

- Documentazione Flatpak:
  - Permesso `--filesystem=~/.local/share/themes:ro` ecc., manifest `flatpak-builder`.
- Documentazione Snap:
  - `plugs: home`, ecc., e test in container.
- Potenzialmente:
  - `subprocess` per controllare se i cambiamenti GSettings hanno effetto su Wayland, Sway, ecc., se vuoi supporti più ampi. [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)

### Potenziali ostacoli

- Temi e GTK4:
  - GTK4/Libadwaita non supportano i temi custom nello stesso modo di GTK3; molte app restano “Adwaita-like” anche cambiando `gtk-theme`. [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Sandbox:
  - Se l’app gira come Flatpak con permessi limitati, potrebbe non vedere le directory dei temi; l’utente dovrà concedere permessi esplicitamente.
- Coerenza comportamento:
  - Differenze tra GNOME Shell “full”, GNOME Flashback, ambienti Wayland come Sway/Hyprland che usano GSettings solo parzialmente. [github](https://github.com/swaywm/sway/wiki/GTK-3-settings-on-Wayland)

***

## Suggerimenti pratici per la tua situazione

- Vista la tua esperienza con GNOME e shell extensions, ti conviene:
  - Concentrarti per bene sulle Fasi 1–3 prima di entrare nelle GUI.
  - Mappare con attenzione le chiavi GSettings e come influiscono realmente sulle applicazioni in GNOME 45+ / 46+ (gtk-theme/icon-theme/cursor-theme). [wiki.archlinux](https://wiki.archlinux.org/title/GTK)
- Per un principiante Python:
  - Scrivi tutto il core con dataclass e tante funzioni pure, e usa CLI e tests come harness didattico.
  - Chiedi all’AI di generare moduli molto commentati, ma mantieni tu il controllo del design modulare (come sopra), per evitare il “mega-script” difficile da gestire.