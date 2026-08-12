# Fase 2: Gestione Archivi e Installazione Temi

## Obiettivi della Fase

Automatizzare e rendere sicura l'installazione di nuovi temi scaricati (es. da GNOME-Look o repository GitHub/GitLab):
1. Supportare formati di archivio diffusi: `.zip`, `.tar.gz`, `.tar.xz`, `.tar.bz2`.
2. Validare la struttura interna del tema prima dell'installazione.
3. Installare il tema nella directory utente appropriata (`~/.local/share/themes` o `~/.local/share/icons`).
4. Prevenire vulnerabilità di estrazione archivi (es. Zip Slip / directory traversal).

---

## Architettura e Moduli Coinvolti

```text
src/gnome_theme_manager/
├── core/
│   ├── installer.py        # Logica di estrazione, validazione e copia
│   └── errors.py           # ThemeValidationError, ArchiveExtractionError
└── cli/
    └── args.py             # Subcomando `install`
```

---

## Dettagli Tecnici e Specifiche

### 1. Riconoscimento e Tipologie di Archivio
- Identificazione tramite estensione e/o magic bytes.
- Utilizzo della libreria standard: `zipfile`, `tarfile`, `tempfile`, `shutil`.

### 2. Validazione Strutturale del Tema
Un archivio di tema può presentarsi in due layout tipici:
- **Layout a radice singola**: `MyTheme/gtk-3.0/gtk.css`
- **Layout flat**: `gtk-3.0/gtk.css` (richiede la creazione di una directory con il nome del tema).

Regole di validazione:
- **GTK Theme**: Presenza di almeno una tra le cartelle `gtk-3.0/`, `gtk-4.0/`, `gnome-shell/` o un file `index.theme` contenente la sezione `[Desktop Entry]`.
- **Icon / Cursor Theme**: Presenza di `index.theme` con sezione `[Icon Theme]` e/o cartella `cursors/`.

### 3. Sicurezza (Safe Extraction)
- Prevenzione Path Traversal: verificare che nessun membro dell'archivio abbia percorsi assoluti o sequenze `..` che escano dalla directory temporanea di lavoro.
- Utilizzo di `tarfile.data_filter` (Python 3.12+) o validazione esplicita su ogni `member.name`.

### 4. Comandi CLI Estesi

```bash
# Installa specificando il tipo
gnome-theme-manager install --file ~/Downloads/Nordic.tar.xz --type gtk

# Riconoscimento automatico (auto-detect) del tipo
gnome-theme-manager install --file ~/Downloads/Tela-circle-blue.zip

# Disinstallazione di un tema utente
gnome-theme-manager uninstall --name "Nordic" --type gtk
```

---

## Checklist di Implementazione

- [ ] **Modulo Installer**:
  - Funzione `safe_extract(archive_path, dest_dir)`.
  - Funzione `detect_theme_type(extracted_dir) -> ThemeType`.
  - Funzione `install_theme(archive_path, theme_type=None, custom_name=None) -> Theme`.
  - Funzione `uninstall_theme(theme_name, theme_type) -> bool`.
- [ ] **CLI Subcommands**:
  - Aggiunta di `install` e `uninstall` in `cli/args.py`.
- [ ] **Test Unitari**:
  - Test con archivi zip e tar mockati con layout validi e non validi.
  - Test di protezione da archivio malevolo (tentativo di path traversal).
