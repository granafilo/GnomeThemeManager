# 🤖 Prompt per AI — Creazione AppImage GNOME Theme Manager

**Copia e incolla questo prompt a un'AI assistente per generare automaticamente tutti i file necessari.**

---

## 📋 Contesto del Progetto

Sto sviluppando **GNOME Theme Manager**, un'applicazione desktop Python 3 per Ubuntu/GNOME che gestisce temi GTK4, Shell, Icone e Cursori.

**Stack tecnico**:
- Python 3.10+
- GTK 4.0 + Libadwaita 1.0
- PyGObject (gi.repository)
- Architettura: Facade Pattern con separazione GUI/CLI/Core

**Struttura repository**:
```
gnome-theme-manager/
├── src/
│   └── gnome_theme_manager/
│       ├── __init__.py
│       ├── __main__.py
│       ├── gui/
│       │   └── main.py
│       ├── core/
│       │   └── manager.py
│       └── cli/
│           └── main.py
├── tests/
├── requirements.txt
└── README.md
```

---

## 🎯 Obiettivo

Voglio creare un **file AppImage** singolo, portabile ed eseguibile su tutte le distribuzioni Linux (Ubuntu 22.04+, Fedora 38+, Debian 11+, Arch).

---

## 📦 Cosa Devi Generare

Crea **tutti i file seguenti** pronti per essere commitati nella repository:

### 1. Directory `appimage/` con 3 File

#### 1.1 `appimage/io.github.username.ThemeManager.desktop`
File desktop entry per integrazione nel menu applicazioni.

**Requisiti**:
- Nome: "GNOME Theme Manager"
- Icona: `io.github.username.ThemeManager`
- Categorie: GTK, Settings, DesktopSettings, AppearanceSettings
- Keywords: theme, gtk, icon, cursor, gnome, settings

#### 1.2 `appimage/io.github.username.ThemeManager.svg`
Icona dell'applicazione in formato SVG.

**Requisiti**:
- Dimensione: 256x256 (scalabile)
- Stile: Moderno, coerente con GNOME 42+
- Colori: Blu GNOME (#3584e4, #1a5fb4)
- Soggetto: Icona astratta che rappresenta "temi" o "personalizzazione"

#### 1.3 `appimage/io.github.username.ThemeManager.metainfo.xml`
Metadati AppStream per validazione e informazioni.

**Requisiti**:
- ID: `io.github.username.ThemeManager`
- Licenza: GPL-3.0
- Descrizione: 2-3 frasi in inglese
- Features: lista puntata (5-6 punti)
- Screenshot: URL placeholder (da sostituire dopo)
- URL homepage e bugtracker: GitHub

---

### 2. Script di Build `scripts/build-appimage.sh`

Script Bash automatizzato che:

**Funzionalità²²**:
1. Pulisce directory `AppDir/` precedente
2. Crea struttura directory completa:
   - `AppDir/usr/bin/`
   - `AppDir/usr/lib/python3.11/site-packages/`
   - `AppDir/usr/share/applications/`
   - `AppDir/usr/share/icons/hicolor/scalable/apps/`
   - `AppDir/usr/share/metainfo/`
3. Copia sorgenti Python da `src/gnome_theme_manager/`
4. Crea script wrapper eseguibile `AppDir/usr/bin/gnome-theme-manager`
5. Crea file `AppRun` (entry point AppImage)
6. Copia file `.desktop` e icona dalla directory `appimage/`
7. Copia metadati AppStream
8. Installa dipendenze Python da `requirements.txt`
9. Crea AppImage finale con `appimagetool`

**Output**:
- File: `GNOMEThemeManager-<VERSION>-x86_64.AppImage`
- Messaggi colorati per ogni step
- Validazione finale del file creato

**Gestione Errori**:
- Controlla che `appimagetool` sia installato
- Fallisce con messaggio chiaro se qualcosa va storto

---

### 3. Workflow GitHub Actions `.github/workflows/build-appimage.yml`

Workflow CI/CD che:

**Trigger**:
- Pubblicazione release su GitHub (`release: types: [published]`)
- Esecuzione manuale (`workflow_dispatch`)

**Job**:
1. Setup Python 3.11
2. Installa dipendenze di sistema (GTK4, Libadwaita, PyGObject)
3. Installa `appimagetool`
4. Esegue script `scripts/build-appimage.sh`
5. Upload artifact dell'AppImage
6. Upload automatico alla release GitHub (se trigger è tag)

**Requisiti**:
- Usa `ubuntu-22.04` come runner
- Include gestione errori
- Mostra dimensione finale AppImage nei log

---

### 4. File `INSTALL.md` (Sezione AppImage)

Aggiungi o crea file `INSTALL.md` con sezione dedicata ad AppImage:

**Contenuto**:
1. Prerequisiti di sistema (pacchetti da installare su Ubuntu/Debian/Fedora/Arch)
2. Istruzioni build locale (comando `./scripts/build-appimage.sh`)
3. Istruzioni esecuzione (chmod +x, ./file.AppImage)
4. Istruzioni download da GitHub Releases
5. Troubleshooting comune (dipendenze mancanti, permessi, ecc.)

---

### 5. File `README.md` (Badge e Istruzioni Rapide)

Aggiorna `README.md` con:

**Badge**:
- Build status GitHub Actions
- Licenza (GPL-3.0)
- Versione ultima release

**Sezione Installazione**:
- Breve istruzioni per AppImage (3-4 righe)
- Link a `INSTALL.md` per dettagli

---

## 📝 Istruzioni Specifiche per Ogni File

### Per i File Desktop e Metadati

- Sostituisci `<username>` con placeholder testuale (lo sostituirò²²² dopo con il mio username GitHub reale)
- Usa ID app: `io.github.username.ThemeManager`
- Mantieni coerenza tra nome icona, file .desktop e metadati

### Per lo Script di Build

- Usa variabili per VERSION e ARCH in cima allo script
- Includi controlli per dipendenze mancanti (appimagetool)
- Aggiungi commenti in italiano o inglese per ogni sezione
- Usa colori per output (verde per successo, giallo per warning, rosso per errori)

### Per il Workflow GitHub Actions

- Usa azioni ufficiali GitHub (`actions/checkout@v4`, `actions/setup-python@v5`)
- Includi step per validazione desktop file e metadati (opzionale)
- Configura upload artifact e release

---

## ✅ Criteri di Accettazione

Tutti i file generati devono:

1. **Essere pronti all'uso**: Posso copiarli nella repo e eseguire subito
2. **Avere nomi coerenti**: Tutti usano lo stesso ID app (`io.github.username.ThemeManager`)
3. **Includere commenti**: Script e workflow devono essere commentati
4. **Gestire errori**: Script deve fallire con messaggi chiari se qualcosa va storto
5. **Seguire best practice**: Desktop entry valida, metadati AppStream corretti, workflow GitHub Actions funzionante

---

## 🚀 Output Atteso

Genera **esattamente questi file**:

```
appimage/
├── io.github.username.ThemeManager.desktop
├── io.github.username.ThemeManager.svg
└── io.github.username.ThemeManager.metainfo.xml

scripts/
└── build-appimage.sh

.github/
└── workflows/
    └── build-appimage.yml

INSTALL.md (nuovo file o aggiornamento)
README.md (aggiornamento con badge e istruzioni)
```

Per ogni file, fornisci:
- **Percorso completo** (es. `appimage/io.github.username.ThemeManager.desktop`)
- **Contenuto completo** (pronto per copia-incolla)
- **Breve descrizione** (1-2 righe su cosa fa)

---

## 📚 Note Aggiuntive

- **Non includere dipendenze Python pesanti** nell'AppImage (solo PyGObject e strette dipendenze)
- **Documenta chiaramente** che GTK4 e Libadwaita devono essere presenti sul sistema target
- **Ottimizza per dimensione**: AppImage ideale < 50MB, massimo < 100MB
- **Testabilità²²**: Includi istruzioni per test su Docker o VM pulita

---

## 🎯 Esempio di Output Atteso

Per ogni file, formatta così:

```markdown
### File: `appimage/io.github.username.ThemeManager.desktop`

**Descrizione**: File desktop entry per integrazione nel menu applicazioni.

**Contenuto**:
```ini
[Desktop Entry]
Type=Application
Name=GNOME Theme Manager
...
```
```

---

**Genera tutti i file elencati sopra.**