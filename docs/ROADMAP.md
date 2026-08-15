# 🗺️ Roadmap di Sviluppo — GNOME Theme Manager

**Ultimo aggiornamento**: 15 Agosto 2026  
**Versione corrente**: v1.0.0(Fase 0 completata)  
**Stato**: In sviluppo attivo (Fase 0 stabilizzazione e test eseguiti con successo)

---

## 📊 Panoramica delle Priorità²²

| Priorità²² | Feature | Complessità²² | Impatto Utente | Stato |
| :--- | :--- | :---: | :---: | :---: |
| **P0** | Backup e Ripristino con 1 Click | Media | 🔴 Critico | 📋 Pianificato |
| **P1** | Integrazione `color-scheme` (GNOME 42+) | Bassa | 🟠 Alto | 📋 Pianificato |
| **P1** | Packaging Flatpak | Media | 🟠 Alto | 📋 Pianificato |
| **P2** | Rilevamento Runtime Flatpak GTK3 | Media | 🟡 Medio | 📋 Pianificato |
| **P2** | Packaging .deb (Ubuntu/Debian) | Media | 🟡 Medio | 📋 Pianificato |
| **P3** | Diagnostica Ambiente Avanzata | Bassa | 🟡 Medio | 💡 Idea |
| **P3** | Logging Strutturato | Bassa | 🟢 Basso | 💡 Idea |
| **P3** | Internazionalizzazione (i18n) | Media | 🟢 Basso | 💡 Idea |

---

## 🎯 Fase 6 — Sicurezza e Resilienza (v1.1.0)

### 6.1 Backup e Ripristino con 1 Click
**Priorità²²**: P0 (Critico)  
**Stima**: 3-4 giorni  
**Stato**: 📋 Da sviluppare

#### Obiettivi
- [ ] Creare preset automatico "system-default" al primo avvio
- [ ] Implementare pulsante di emergenza "Ripristina Temi Predefiniti"
- [ ] Validare ripristino su ambiente di test

#### Dettaglio Implementazione

**6.1.1 Struttura Dati Preset di Sistema**
```json
// ~/.config/gnome-theme-manager/presets/system-default.json
{
  "name": "Default di Sistema",
  "created_at": "2026-08-12T22:00:00Z",
  "is_system_preset": true,
  "settings": {
    "org.gnome.desktop.interface": {
      "gtk-theme": "Yaru",
      "icon-theme": "Yaru",
      "cursor-theme": "Yaru",
      "color-scheme": "default"
    }
  },
  "symlinks": {
    "gtk-4.0": null,
    "gtk-3.0": null
  },
  "notes": "Creato automaticamente al primo avvio"
}
```

**6.1.2 Modifiche al Core**
- [ ] `core/manager.py`: Aggiungere metodo `create_system_backup_preset()`
- [ ] `core/manager.py`: Aggiungere metodo `restore_system_defaults()`
- [ ] `core/presets.py`: Estendere `PresetManager` per gestire flag `is_system_preset`
- [ ] `core/presets.py`: Impedire eliminazione preset di sistema via UI

**6.1.3 Modifiche alla GUI**
- [ ] `pages/status_page.py`: Aggiungere sezione "Zona Pericolosa" con bottone rosso
- [ ] `pages/status_page.py`: Dialogo di conferma con warning esplicito
- [ ] `pages/status_page.py`: Banner di successo/errore post-ripristino

**6.1.4 Test**
- [ ] Test unitario: creazione preset al primo avvio
- [ ] Test unitario: ripristino settings GSettings
- [ ] Test unitario: rimozione symlink GTK4
- [ ] Test manuale: applicare tema corrotto → ripristinare → verificare UI

**6.1.5 Criteri di Accettazione**
- ✅ Al primo avvio, preset "Default di Sistema" esiste in `~/.config/gnome-theme-manager/presets/`
- ✅ Il pulsante "Ripristina Temi Predefiniti" è visibile solo se ci sono override attivi
- ✅ Il dialogo di conferma mostra esattamente cosa verrà ripristinato
- ✅ Dopo il ripristino, `gtk-theme`, `icon-theme`, `cursor-theme` tornano ai valori Ubuntu default
- ✅ I symlink in `~/.config/gtk-4.0/` vengono rimossi se presenti

---

### 6.2 Integrazione `color-scheme` (GNOME 42+)
**Priorità²²**: P1 (Alto)  
**Stima**: 2-3 giorni  
**Stato**: 📋 Da sviluppare

#### Obiettivi
- [ ] Leggere/scrivere `org.gnome.desktop.interface.color-scheme`
- [ ] UI per selezionare preferenza chiara/scura
- [ ] Supporto colori di accento (se disponibile)

#### Dettaglio Implementazione

**6.2.1 Chiavi GSettings**
```bash
# Schema: org.gnome.desktop.interface
gsettings get org.gnome.desktop.interface.color-scheme
# Valori: 'default', 'prefer-dark', 'prefer-light'

# (Opzionale, dipende dalla distro)
gsettings get org.gnome.desktop.interface.accent-color
# Valori: 'blue', 'green', 'orange', 'red', 'purple', 'brown', 'slate'
```

**6.2.2 Modifiche al Core**
- [ ] `core/manager.py`: Estendere `GSettingsClient` per gestire `color-scheme`
- [ ] `core/manager.py`: Metodo `get_color_scheme()` → restituisce `Literal['default', 'prefer-dark', 'prefer-light']`
- [ ] `core/manager.py`: Metodo `set_color_scheme(scheme: str)`
- [ ] `core/manager.py`: Metodo `get_accent_color()` (opzionale, con fallback)
- [ ] `core/manager.py`: Metodo `set_accent_color(color: str)` (opzionale)

**6.2.3 Modifiche alla GUI**
- [ ] `pages/themes_page.py`: Aggiungere `AdwComboRow` per "Preferenza Colore"
- [ ] `pages/themes_page.py`: Popolare con ['Predefinito', 'Scuro', 'Chiaro']
- [ ] `pages/themes_page.py`: (Opzionale) `AdwComboRow` per "Colore di Accento"
- [ ] `controllers/themes_controller.py`: Collegare selezione a `ThemeManager.set_color_scheme()`

**6.2.4 Test**
- [ ] Test unitario: lettura/scrittura `color-scheme`
- [ ] Test manuale: cambiare preferenza → verificare con `gsettings get`
- [ ] Test manuale: applicare tema scuro + preferenza chiara → verificare comportamento

**6.2.5 Criteri di Accettazione**
- ✅ L'utente può selezionare preferenza chiara/scura dalla UI
- ✅ La selezione persiste dopo il riavvio dell'app
- ✅ Il cambio di preferenza si riflette immediatamente nelle app GTK4
- ✅ (Opzionale) La selezione del colore di accento funziona su GNOME 45+

---

## 📦 Fase 7 — Packaging e Distribuzione (v1.2.0)

### 7.1 Packaging Flatpak
**Priorità²²**: P1 (Alto)  
**Stima**: 4-5 giorni  
**Stato**: 📋 Da sviluppare

#### Obiettivi
- [ ] Creare manifest `io.github.<username>.ThemeManager.yml`
- [ ] Configurare build con `flatpak-builder`
- [ ] Testare su Ubuntu 22.04+, Fedora 38+
- [ ] Pubblicare su Flathub (opzionale)

#### Dettaglio Implementazione

**7.1.1 Manifest Flatpak**
```yaml
# io.github.<username>.ThemeManager.yml
app-id: io.github.<username>.ThemeManager
runtime: org.gnome.Platform
runtime-version: '45'
sdk: org.gnome.Sdk
command: gnome-theme-manager

build-options:
  env:
    - PYTHONPATH=/app/lib/python3.11/site-packages

finish-args:
  # Accesso a GSettings/dconf
  - --talk-name=org.gnome.Settings
  - --filesystem=~/.local/share/themes:ro
  - --filesystem=~/.local/share/icons:ro
  - --filesystem=~/.config/gnome-theme-manager:create
  - --filesystem=~/.config/gtk-4.0:create
  - --filesystem=host-os:ro
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri

modules:
  - name: gnome-theme-manager
    buildsystem: simple
    build-commands:
      - install -D gnome-theme-manager /app/bin/gnome-theme-manager
      - install -D main.py /app/lib/python3.11/site-packages/gnome_theme_manager/__main__.py
      - cp -r src/gnome_theme_manager /app/lib/python3.11/site-packages/
    sources:
      - type: dir
        path: .
      - type: script
        dest-filename: gnome-theme-manager
        commands:
          - python3 -m gnome_theme_manager.gui
    modules:
      - name: python3-gi
        buildsystem: simple
        build-commands:
          - pip3 install --prefix=/app PyGObject
```

**7.1.2 Build e Test**
```bash
# Build
flatpak-builder build --force-clean --install io.github.<username>.ThemeManager.yml

# Test
flatpak run io.github.<username>.ThemeManager

# Verifica permessi
flatpak info --show-permissions io.github.<username>.ThemeManager
```

**7.1.3 Pubblicazione Flathub**
- [ ] Creare repo `flathub/io.github.<username>.ThemeManager`
- [ ] Submit PR a https://github.com/flathub/flathub
- [ ] Superare review (licenza, metadata, sicurezza)

**7.1.4 Criteri di Accettazione**
- ✅ L'app si avvia con `flatpak run io.github.<username>.ThemeManager`
- ✅ I temi in `~/.local/share/themes` sono visibili
- ✅ I preset vengono salvati in `~/.config/gnome-theme-manager`
- ✅ I permessi sono minimi e documentati

---

### 7.2 Packaging .deb (Ubuntu/Debian)
**Priorità²²**: P2 (Medio)  
**Stima**: 3-4 giorni  
**Stato**: 📋 Da sviluppare

#### Obiettivi
- [ ] Creare struttura `debian/`
- [ ] Configurare `debian/control` con dipendenze
- [ ] Build pacchetto `.deb`
- [ ] Testare installazione su Ubuntu 22.04+, 24.04+

#### Dettaglio Implementazione

**7.2.1 Struttura debian/**
```
debian/
├── changelog
├── compat
├── control
├── copyright
├── gnome-theme-manager.install
├── gnome-theme-manager.links
├── rules
└── source/
    └── format
```

**7.2.2 File `debian/control`**
```control
Source: gnome-theme-manager
Section: utils
Priority: optional
Maintainer: Your Name <your.email@example.com>
Build-Depends: debhelper (>= 13), python3-all, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1

Package: gnome-theme-manager
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, dconf-gsettings-backend
Description: Gestore temi nativo per GNOME 42+
 GNOME Theme Manager è un'applicazione desktop Python 3 nativa per Ubuntu/GNOME
 progettata con un'architettura modulare, pulita e resiliente.
Homepage: https://github.com/<username>/gnome-theme-manager
```

**7.2.3 Build**
```bash
# Installa dipendenze
sudo apt install debhelper python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Build
debuild -us -uc

# Installa
sudo apt install ../gnome-theme-manager_1.2.0_all.deb
```

**7.2.4 Criteri di Accettazione**
- ✅ Il pacchetto si installa con `apt install ./gnome-theme-manager_*.deb`
- ✅ Il comando `gnome-theme-manager` è disponibile nel PATH
- ✅ Le dipendenze sono risolte automaticamente da apt

---

## 🔍 Fase 8 — Diagnostica e Compatibilità²² (v1.3.0)

### 8.1 Rilevamento Runtime Flatpak GTK3
**Priorità²²**: P2 (Medio)  
**Stima**: 2-3 giorni  
**Stato**: 📋 Da sviluppare

#### Obiettivi
- [ ] Verificare se il tema attivo è installato come runtime Flatpak
- [ ] Mostrare feedback informativo all'utente
- [ ] Suggerire installazione se mancante

#### Dettaglio Implementazione

**8.1.1 Modifiche al Core**
- [ ] `core/sandbox.py`: Aggiungere metodo `check_gtk3_flatpak_runtime(theme_name: str) -> bool`
- [ ] `core/sandbox.py`: Implementare parsing output `flatpak list --runtime`
- [ ] `core/sandbox.py`: Metodo `get_flatpak_gtk3_themes() -> List[str]`

**8.1.2 Comandi Flatpak**
```bash
# Lista runtime installati
flatpak list --runtime | grep org.gtk.Gtk3theme

# Verifica tema specifico
flatpak list --runtime | grep "org.gtk.Gtk3theme.Nordic"

# Installa runtime (se necessario)
flatpak install flathub org.gtk.Gtk3theme.Nordic
```

**8.1.3 Modifiche alla GUI**
- [ ] `pages/sandbox_page.py`: Aggiungere sezione "Temi GTK3 per Flatpak"
- [ ] `pages/sandbox_page.py`: Mostrare badge ✅/❌ per ogni tema rilevato
- [ ] `pages/sandbox_page.py`: (Opzionale) Bottone "Installa runtime mancante"

**8.1.4 Criteri di Accettazione**
- ✅ La sandbox page mostra se il tema GTK3 è disponibile come runtime Flatpak
- ✅ Il messaggio è chiaro: "Il tema X è già installato per le app Flatpak"
- ✅ (Opzionale) L'utente può installare il runtime con un click

---

### 8.2 Diagnostica Ambiente Avanzata
**Priorità²²**: P3 (Medio)  
**Stima**: 1-2 giorni  
**Stato**: 💡 Idea

#### Obiettivi
- [ ] Mostrare versione GNOME
- [ ] Rilevare session type (X11/Wayland)
- [ ] Verificare estensioni critiche (es. "User Themes")

#### Dettaglio Implementazione

**8.2.1 Informazioni da Raccogliere**
```bash
# Versione GNOME
gnome-shell --version

# Session type
echo $XDG_SESSION_TYPE

# Estensioni abilitate
gsettings get org.gnome.shell enabled-extensions

# Estensione User Themes
gsettings get org.gnome.shell enabled-extensions | grep user-theme
```

**8.2.2 Modifiche alla GUI**
- [ ] `pages/status_page.py`: Aggiungere sezione "Informazioni Sistema"
- [ ] `pages/status_page.py`: Mostrare GNOME version, session type, estensioni critiche

---

## 🛠️ Fase 9 — Manutenzione e Qualità²² (v1.4.0)

### 9.1 Logging Strutturato
**Priorità²²**: P3 (Basso)  
**Stima**: 1-2 giorni  
**Stato**: 💡 Idea

#### Obiettivi
- [ ] Implementare logger JSON in `~/.local/state/gnome-theme-manager/`
- [ ] Loggare operazioni critiche (applicazioni temi, errori)
- [ ] Aggiungere comando CLI `--verbose` per debug

#### Dettaglio Implementazione

**9.1.1 Configurazione Logger**
```python
# core/logger.py
import logging
import json
from pathlib import Path

LOG_DIR = Path.home() / ".local/state/gnome-theme-manager"
LOG_FILE = LOG_DIR / "app.log"


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("gnome_theme_manager")
    logger.setLevel(logging.DEBUG)

    # File handler (JSON)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        )
    )

    logger.addHandler(file_handler)
    return logger
```

---

### 9.2 Internazionalizzazione (i18n)
**Priorità²²**: P3 (Basso)  
**Stima**: 2-3 giorni  
**Stato**: 💡 Idea

#### Obiettivi
- [ ] Integrare `gettext` per traduzioni IT/EN
- [ ] Creare file `.po` per italiano e inglese
- [ ] Tradurre tutte le stringhe UI

#### Dettaglio Implementazione

**9.2.1 Struttura**
```
locales/
├── it/
│   └── LC_MESSAGES/
│       └── gnome_theme_manager.po
└── en/
    └── LC_MESSAGES/
        └── gnome_theme_manager.po
```

**9.2.2 Setup gettext**
```python
# core/i18n.py
import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).parent.parent / "locales"


def setup_i18n(lang_code: str = "it"):
    translation = gettext.translation("gnome_theme_manager", LOCALE_DIR, languages=[lang_code])
    translation.install()
    return translation.gettext


_ = setup_i18n("it")
```

---

## 📅 Timeline Stimata

| Milestone | Versione | Data Target | Feature Principali |
| :--- | :---: | :---: | :--- |
| **M0 (Fase 0)** | v1.0.0-beta3 | 15 Agosto 2026 | Stabilizzazione, Preset 2.0, Estensioni, modali unificati (Completato) |
| **M6** | v1.1.0 | Settembre 2026 | Backup/Ripristino, color-scheme |
| **M7** | v1.2.0 | Ottobre 2026 | Packaging Flatpak, .deb |
| **M8** | v1.3.0 | Novembre 2026 | Rilevamento Flatpak GTK3, Diagnostica |
| **M9** | v1.4.0 | Dicembre 2026 | Logging, i18n, manutenzione |

---

## 🎯 Criteri di Priorità²²

### P0 — Critico
- Feature essenziali per sicurezza e usabilità²²
- Bloccano adozione in produzione
- **Esempio**: Backup e Ripristino

### P1 — Alto
- Feature fortemente richieste dagli utenti target
- Migliorano significativamente l'esperienza
- **Esempio**: color-scheme, Packaging Flatpak

### P2 — Medio
- Feature utili ma non bloccanti
- Possono aspettare release successive
- **Esempio**: Rilevamento Flatpak GTK3, Packaging .deb

### P3 — Basso
- Feature "nice to have"
- Utili per manutenzione a lungo termine
- **Esempio**: Logging, i18n, Diagnostica avanzata

---

## 📝 Note per lo Sviluppatore

1. **Prima di iniziare ogni fase**:
   - Creare branch Git dedicato (es. `feature/backup-restore`)
   - Aggiornare `CHANGELOG.md` con le feature pianificate
   - Eseguire `pytest tests/ -v` per verificare baseline

2. **Dopo ogni feature completata**:
   - Aggiornare test suite
   - Eseguire `ruff check src tests`
   - Commit con messaggio descrittivo (Conventional Commits)

3. **Prima del release**:
   - Taggare versione con `git tag -a v1.1.0 -m "Release v1.1.0"`
   - Aggiornare `README.md` con changelog
   - Push tag su GitHub

---

## 🔗 Risorse Utili

- [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/)
- [Libadwaita Documentation](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/)
- [Flatpak Documentation](https://docs.flatpak.org/)
- [Debian New Maintainers' Guide](https://www.debian.org/doc/manuals/maint-guide/)
- [Python gettext](https://docs.python.org/3/library/gettext.html)

---

**Buono sviluppo! 🚀**