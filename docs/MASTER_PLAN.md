# 📋 Master Implementation Plan — GnomeThemeManager

**Versione documento:** 1.0
**Autore:** Planning Agent
**Destinatario:** Coding Agent
**Repo:** `https://github.com/granafilo/GnomeThemeManager`
**Stato attuale:** `0.9.0-beta3`
**Target finale:** parità funzionale con **Evolve Core v1.7** (free) + feature differenzianti open-source

---

## 0. Meta-informazioni

### 0.1 Scopo del documento
Questo documento è l'unica fonte di verità per il coding agent. Definisce **workflow, convenzioni, fasi, task atomici e acceptance criteria**. Il coding agent NON deve procedere con task non presenti in questo documento né inventare feature non specificate.

### 0.2 Architettura di riferimento (da rispettare sempre)

```
src/gnome_theme_manager/
├── cli/           # parser argomenti + routing comandi
├── core/          # logica dominio (scanner, manager, installer, gsettings, sandbox, theme_editor, profiles, store)
├── gui_gtk/       # GUI nativa GTK4/Libadwaita (window, views, widgets)
└── __init__.py
tests/             # unit + integration tests
docs/              # roadmap, README, guide
po/                # file .po per i18n (IT, EN)
```

**Regola d'oro**: GUI e CLI consumano SEMPRE le stesse API in `core/`. Nessuna logica di business deve mai finire in `gui_gtk/` o `cli/`.

### 0.3 Stack tecnico fisso
- Python ≥ 3.10
- PyGObject ≥ 3.42.0
- GTK4 + Libadwaita
- `gsettings` come unico backend di persistenza tema (no file di config proprietario)
- Target primario: **Ubuntu 24.04 — GNOME 46**
- Packaging Flatpak/.deb (solo Fase 5)

### 0.4 Dipendenze esterne consentite
Oltre a PyGObject, sono consentite **solo**: `requests` (Fase 3), `pyyaml` (Fase 4 per profili JSON/YAML — valutare `json` stdlib). Nessuna altra dipendenza senza approvazione esplicita.

---

## 1. Workflow globale del coding agent

### 1.1 Protocollo di branch
Ogni fase viene implementata su una **branch dedicata** derivata da `main`.

```
git checkout main
git pull
git checkout -b feature/phase-N-nome-fase
```

Nome branch obbligatorio: `feature/phase-{N}-{slug}` (es. `feature/phase-1-global-themes`).

### 1.2 Granularità dei commit (1 task = 1 commit)

Ogni TASK completato e testato produce ESATTAMENTE un commit. Ogni fase produce in aggiunta un commit finale di chiusura.

Regole:
- 1 task = 1 commit. Mai accumulare task multipli nello stesso commit.
- Il commit di task contiene SOLO i file di codice + test del task (mai docs, mai i18n).
- Il commit di chiusura fase contiene SOLO gli esiti degli step A–C (docs, verifiche, i18n).
- Il coding agent NON esegue mai commit: stampa il comando, l'utente lo esegue.
- Il comando di commit per-task usa `git add` ESPLICITO sui soli file del task (mai `git add -A`).

Formato messaggi (Conventional Commits + riferimento task):
- `feat(core): task 1.2 — theme validator per index.theme`
- `fix(gui): task 0.1 — gtk4 override status all'avvio`
- `test(core): task 1.2 — unit test parser index.theme`
- `chore: phase {N} completion — docs, tests integrity, i18n verification`

Protocollo per-task (dopo test verdi e review utente del diff):
1. Il coding agent stampa il comando di commit del task (add esplicito + messaggio).
2. L'utente esegue il commit.
3. Si passa al task successivo.

### 1.3 Protocollo di testing OBBLIGATORIO a fine fase
Prima di dichiarare una fase completata, il coding agent DEVE eseguire:

```bash
# Unit tests
pytest tests/ -v --cov=src/gnome_theme_manager --cov-fail-under=80

# Smoke test CLI
python -m gnome_theme_manager --help
python -m gnome_theme_manager list --all
python -m gnome_theme_manager current

# GUI launch smoke test (manuale + log check)
python -m gnome_theme_manager.gui_gtk &
# verificare nessun traceback in stderr entro 10s dall'avvio
```

**Soglia di coverage minima: 80%** sul modulo `core/`. Se inferiore, scrivere ulteriori test prima di procedere.

### 1.4 Protocollo di chiusura fase (POST-CONFERMA — OBBLIGATORIO, sempre ripetuto)

> ⚠️ Il coding agent **NON procede** alla fase successiva finché l'utente non ha dato conferma esplicita ("ok", "approvato", "confermo", ecc.).

Dopo aver ricevuto conferma, il coding agent esegue **esattamente in quest'ordine**:

#### Step A — Aggiornamento documentazione
- Aggiornare `docs/ROADMAP.md`: spostare le feature della fase da "📋 Da sviluppare" a "✅ Completato" con data effettiva e link alla PR/branch.
- Aggiornare `README.md`: aggiungere feature nuove nella sezione `## Feature`.
- Se sono state aggiunte API pubbliche in `core/`, aggiornare `docs/` con sezione tecnica dedicata (naming, signature, esempi).
- Aggiornare il changelog (file `CHANGELOG.md` se esistente, altrimenti sezione in `ROADMAP.md`).

#### Step B — Verifica integrità test + pulizia file
- Eseguire `pytest` completo: **nessun test skip-pato senza `@pytest.mark.skip(reason=...)` esplicito**.
- Eseguire `pylint src/gnome_theme_manager/` o `ruff check`: zero warning di tipo "unused import", "dead code".
- Verificare che **non esistano file extra o non necessari** nella working directory:
  ```bash
  git status --short
  ```
  Tutti i file non tracciati devono essere o (a) rimossi (`.pyc`, `__pycache__`, `.cache`, `.pytest_cache`, artefatti di build) oppure (b) aggiunti esplicitamente al `.gitignore` se legittimi.
- Rimuovere branch temporanee locali se non già mergiate.
- Verificare che nessun test dipenda da stato locale (path hardcoded alla home, file temporanei non cleanup-pati, dipendenza da ordine di esecuzione). I test devono essere **deterministici e isolati**.

#### Step C — Verifica traduzioni (i18n)
- Eseguire estrazione stringhe aggiornata (comando `xgettext` o tool equivalente su `src/`).
- Verificare che `po/it.po` e `po/en.po` siano **sincronizzati** (stesso numero di stringhe, nessun `fuzzy` non risolto).
- Compilare i `.mo`: `msgfmt po/it.po -o po/it.mo` — deve andare a buon fine senza warning.
- Verificare che **nessuna stringa UI hardcodata in italiano** sopravviva in `gui_gtk/` o `cli/`: tutte passano da `_()` / `gettext`.
- Controllare che nessun carattere sia corrotto (encoding UTF-8, nessun mojibake, nessuna sostituzione tipo `Ã¨` invece di `è`).

#### Step D — Comando di commit finale
Dopo aver completato A, B, C, il coding agent **stampa** (NON esegue) il seguente comando da far eseguire manualmente all'utente:

```bash
git add -A && git commit -m "chore: phase {N} completion — docs, tests integrity, i18n verification [skip ci]"
```

> Nota: i file di codice/test sono già stati committati per-task durante la fase.
> Questo commit contiene esclusivamente le modifiche prodotte dagli step A–C.

> ⚠️ L'utente si occupa del commit. Il coding agent attende il commit prima di dichiarare chiusa la fase.

### 1.5 Gestione modifiche post-conferma
Se l'utente richiede modifiche **dopo** la chiusura formale di una fase (post-commit), il ciclo riprende **dalla feature oggetto della modifica** e **dopo il completamento della modifica stessa gli step A/B/C/D vanno rieseguiti integralmente**. Non si procede alla fase successiva senza riesecuzione completa del protocollo.

Le modifiche post-conferma seguono la stessa policy: 1 commit dedicato per la fix
(codice + test), poi riesecuzione integrale degli step A–D con commit finale separato.

### 1.6 Blocco su ambiguità
Se durante l'implementazione il coding agent incontra ambiguità non risolvibili dal documento (es. comportamento non specificato, conflitto architetturale), **DEVE fermarsi e chiedere chiarimenti** all'utente. Non deve prendere decisioni unilaterali su feature/specifiche.

---

## 2. Convenzioni di progetto

### 2.1 Nomenclatura
- Moduli Python: `snake_case` (es. `theme_validator.py`).
- Classi: `PascalCase` (es. `ThemeValidator`).
- Costanti: `UPPER_SNAKE_CASE` (es. `THEME_DIRECTORIES`).
- Nomi di branch: `feature/phase-N-slug`.
- Nomi di test: `test_<modulo>_<comportamento>.py` (es. `test_theme_validator_missing_directory.py`).

### 2.2 Tipizzazione
Tutti i moduli in `core/` **devono** avere type hints completi (PEP 484) e passare `mypy --strict src/gnome_theme_manager/core/`.

### 2.3 Logging
Usare modulo `logging` stdlib. Logger per modulo:
```python
logger = logging.getLogger(__name__)
```
Nessun `print()` in `core/` o `gui_gtk/`. In `cli/` è consentito `click.echo` / `print` solo per output user-facing.

### 2.4 Gestione errori
- `core/` **non** deve mai crashare su temi non validi; deve restituire oggetti di errore (`ThemeValidationResult`, `OperationResult`) con stato esplicito.
- `gui_gtk/` mostra dialoghi Libadwaita (`Adw.MessageDialog`) per errori rilevanti.
- `cli/` usa exit codes: `0` successo, `1` errore generico, `2` uso errato, `3` permessi insufficienti.

### 2.5 Persistenza stato utente
Stato applicativo (preferenze GUI, profili, preset) **solo** in `~/.local/state/gnome-theme-manager/` (XDG_STATE_HOME) con struttura JSON. **MAI** in `~/.config/` (che è riservato a gsettings).

---

## 3. Fasi di implementazione

> Ogni fase è **sequenziale**. La fase N+1 non inizia finché la fase N non è chiusa formalmente (protocollo 1.4 completato + commit utente effettuato).

---

### 🔷 FASE 0 — Setup & Stabilizzazione (v1.0)

**Branch:** `feature/phase-0-stabilization`
**Obiettivo:** Risolvere bug critici segnalati nelle ISSUE interne, stabilizzare la GUI, abilitare apply selettivo per componente, rifondare i preset come snapshot espliciti (base per i Global Themes).

#### Task 0.1 — Fix `gtk4 override status` all'avvio
- **Modulo:** `core/gsettings.py` + `gui_gtk/views/current_view.py`
- **Descrizione:** Attualmente la GUI non legge correttamente se l'override `~/.config/gtk-4.0/gtk.css` è attivo. Implementare `GSettingsReader.detect_gtk4_override()` che:
  1. Verifica l'esistenza di `~/.config/gtk-4.0/gtk.css`.
  2. Restituisce un enum `Gtk4OverrideStatus { ACTIVE, INACTIVE }` (o valore booleano coerente) basato sulla presenza del file.
- **Acceptance criteria:**
  - Al lancio della GUI, il toggle "GTK4 override" riflette lo stato reale del filesystem entro 200 ms.

#### Task 0.2 — Fix `missing themes` nello scanner
- **Modulo:** `core/scanner.py`
- **Descrizione:** Estendere `ThemeScanner` per includere TUTTE le directory standard in ordine:
  1. `~/.themes/`
  2. `~/.local/share/themes/`
  3. `/usr/share/themes/`
  4. `/usr/local/share/themes/`
- Per ogni tema trovato, parsare `index.theme` (sezione `[Desktop Entry]`, chiave `Directories`/`Inherits`). Gestire temi che **ereditano** da altri (inheritance chain risolta ricorsivamente con max depth 5).
- **Acceptance criteria:**
  - `list --all` restituisce ≥ 95% dei temi effettivamente installati su Ubuntu 24.04.
  - Temi con `index.theme` corrotto/assente appaiono con flag `invalid: true` ma non crashano lo scanner.

#### Task 0.3 — UX: shortcut e focus behavior
- **Modulo:** `gui_gtk/window.py`
- **Descrizione:**
  - Bind `Ctrl+W` (e `Ctrl+Q`) per chiudere la finestra.
  - Click su area vuota della finestra rimuove il focus da qualsiasi widget input.
  - Aggiungere toggle "Nascondi temi di sistema" nel filtro lista (persistito in `~/.local/state/gnome-theme-manager/ui_prefs.json`).

#### Task 0.4 — Apply selettivo per componente (GUI)
- **Modulo:** `gui_gtk/views/apply_view.py` + `core/manager.py`
- **Descrizione:** La GUI attuale applica TUTTO in blocco. Sostituire con UI a 4 righe indipendenti con toggle:
  - [ ] GTK3 theme
  - [ ] GTK4 theme
  - [ ] GNOME Shell theme
  - [ ] Icon theme
  - [ ] Cursor theme
- Pulsante "Apply Selected" applica solo i componenti flaggati.
- **Acceptance criteria:**
  - Ogni toggle chiama `ThemeManager.apply_component(component: Component, theme_name: str)`.
  - I toggle ricordano l'ultima selezione (persistenza `ui_prefs.json`).
  - Se l'utente flagga solo "Icon theme", solo le icone vengono cambiate (verifica con `gsettings get org.gnome.desktop.interface icon-theme`).

#### Task 0.5 — Preset 2.0: snapshot espliciti
- **Modulo:** `core/presets.py` (nuovo) + `core/manager.py`
- **Descrizione:** Un preset ora è una **combinazione esplicita nominata** `{gtk3, gtk4, shell, icons, cursors}`. Formato JSON in `~/.local/state/gnome-theme-manager/presets.json`:
  ```json
  {
    "presets": [
      {
        "name": "My Nord",
        "components": {
          "gtk3": "Nordic",
          "gtk4": "Nordic-gtk4",
          "shell": "Nordic",
          "icons": "Nordic-folders",
          "cursors": "Nordzy"
        },
        "created_at": "2026-08-14T10:00:00Z"
      }
    ]
  }
  ```
- CLI: `preset save NAME`, `preset list`, `preset apply NAME`, `preset delete NAME`.
- GUI: sidebar preset con button salva/applica/elimina.
- **Acceptance criteria:**
  - I preset sono **deterministici**: applicare lo stesso preset due volte produce stato identico.
  - Se un tema referenziato nel preset non è installato, l'apply fallisce con errore esplicito per quel componente (non rollback parziale: skip componente mancante + warning).

#### Task 0.6 — Shell theme: gestione estensione `user-theme`
- **Modulo:** `core/manager.py` + `core/extensions.py` (nuovo)
- **Descrizione:** L'applicazione del tema GNOME Shell richiede l'estensione `user-theme@gnome-shell-extensions.gcampax.github.com`. Implementare:
  1. `ExtensionsManager.is_user_theme_enabled() -> bool`
  2. `ExtensionsManager.enable_user_theme() -> bool` (via `gnome-extensions enable`)
  3. All'apply di shell theme, se estensione disabilitata: dialog Libadwaita con proposta "Abilita e continua" / "Annulla".

#### Task 0.7 — Documentazione permessi esecuzione
- **File:** `README.md`
- **Descrizione:** Aggiungere sezione "## Prerequisiti" con istruzioni per rendere eseguibile il launcher e note su permessi Flatpak/Snap host.

#### Acceptance Criteria globali Fase 0
- [ ] Tutti i task 0.1–0.7 completati e testati.
- [ ] Coverage `core/` ≥ 80%.
- [ ] `pytest tests/` passa al 100%.
- [ ] GUI lanciabile su Ubuntu 24.04 senza crash entro 30s dall'avvio.
- [ ] Protocollo 1.4 (chiusura fase) eseguito integralmente dopo conferma utente.

---

### 🔷 FASE 1 — Global Themes & Validazione (v1.1)

**Branch:** `feature/phase-1-global-themes`
**Obiettivo:** Introdurre i "Global Themes" (1-click = gtk3+gtk4+shell+icons+cursors), validazione robusta dei pacchetti tema (corruption detection), preview visuale dei pack di icone, preview in-app sicura, installazione assistita da cartella.

#### Task 1.1 — Global Themes (composizione preset + UI)
- **Modulo:** `core/global_themes.py` (nuovo), `gui_gtk/views/global_themes_view.py` (nuova)
- **Descrizione:** Un Global Theme è un preset **bundled o utente** visualizzato come singola card nella UI con thumbnail rappresentativa.
- Bundling iniziale: 3–5 global theme predefiniti in `data/global_themes/` (es. "Adwaita Classic", "Yaru Mix", "Nord Bundle") referenziati dai preset.
- UI: griglia di card (nome + thumbnail + pulsante "Apply").

#### Task 1.2 — `ThemeValidator` — parsing e validazione `index.theme`
- **Modulo:** `core/theme_validator.py` (nuovo)
- **Descrizione:** Classe `ThemeValidator` che per ogni tema installato:
  1. Legge `index.theme` con `configparser`.
  2. Verifica sezione `[Desktop Entry]` presente con chiavi minime (`Name`, `Type=X-GNOME-Metatheme`).
  3. Verifica esistenza directory `gtk-3.0/` o `gtk-4.0/` (per GTK themes).
  4. Verifica esistenza directory `cursors/` per cursor themes.
  5. Verifica presenza file `index.theme` per icon themes + almeno 5 icone standard (`preferences-system`, `home`, `folder`, `user-trash`, `application-x-executable`).
- Restituisce `ThemeValidationResult { valid: bool, warnings: list[str], missing_files: list[str] }`.

#### Task 1.3 — Corruption detection + warning pre-apply
- **Modulo:** `core/manager.py` (estensione `apply*` methods)
- **Descrizione:** Prima di ogni `apply_component`, chiamare `ThemeValidator.validate()`. Se `warnings` non vuoto:
  - CLI: print warning + chiede conferma interattiva (`-y` per saltare).
  - GUI: `Adw.MessageDialog` con titolo "Tema potenzialmente incompleto" + lista warning + pulsanti "Applica comunque" / "Annulla".

#### Task 1.4 — Preview visuale icon pack
- **Modulo:** `gui_gtk/widgets/icon_pack_preview.py` (nuovo)
- **Descrizione:** Widget che per ogni icon theme installato renderizza una griglia 5×2 con icone delle app GNOME standard (Files, Settings, Terminal, Text Editor, Software, Web, Calculator, Clock). Le icone sono caricate tramite `Gtk.IconTheme` caricato **temporaneamente** col pack selezionato (senza cambiare il tema di sistema).
- UI: tab dedicata "Icon Packs" con lista + preview laterale.

#### Task 1.5 — Preview in-app sicura (sandbox tema GTK4)
- **Modulo:** `core/sandbox_theme.py` (nuovo), `gui_gtk/window.py`
- **Descrizione:** Permettere all'utente di "provare" un tema GTK4 sulla finestra dell'app senza applicarlo a livello di sistema.
- Implementazione: caricare il CSS del tema target in un `Gtk.CssProvider` locale e applicarlo solo al widget root della finestra principale. Pulsante "Revert" ripristina il provider originale.
- **Acceptance criteria:**
  - Il tema di sistema NON cambia durante la preview.
  - Il CSS applicato è reversibile in < 100 ms.

#### Task 1.6 — Creazione cartelle `~/.themes` e `~/.icons`
- **Modulo:** `core/installer.py`
- **Descrizione:** Aggiungere metodo `Installer.ensure_user_directories()` che crea (se mancanti) `~/.themes`, `~/.local/share/themes`, `~/.icons`, `~/.local/share/icons`. Chiamato automaticamente all'avvio della GUI e prima di ogni `install`.

#### Task 1.7 — Installazione assistita da cartella (GUI)
- **Modulo:** `core/installer.py` + `gui_gtk/views/install_view.py`
- **Descrizione:** Bottone "Installa da cartella…" apre `Gtk.FileDialog` (GTK4 native) che accetta:
  - Directory (già decompressa) contenente un tema valido.
  - Archivi `.tar.gz`, `.tar.xz`, `.zip` (decompressione in tmp + validazione + spostamento in `~/.themes`).
- Validazione tramite `ThemeValidator` prima dell'installazione.

#### Acceptance Criteria globali Fase 1
- [ ] Un global theme si applica in un click e tutte le 5 componenti cambiano effettivamente.
- [ ] `ThemeValidator` rileva correttamente un tema privo di `gtk-3.0/` o di `index.theme`.
- [ ] Preview icone pack funziona senza cambiare tema di sistema.
- [ ] Preview in-app sicura funziona e revert è istantaneo.
- [ ] Installazione da archivio `.tar.gz` va a buon fine.
- [ ] Coverage `core/` ≥ 80%, `pytest` verde.
- [ ] Protocollo 1.4 eseguito dopo conferma utente.

---

### 🔷 FASE 2 — Theme Editor (v1.2)

**Branch:** `feature/phase-2-theme-editor`
**Obiettivo:** Implementare l'editor di temi che permette di mixare componenti da temi diversi, modificare colori fg/bg/accent, con preview sicura e rollback. **Core feature differenziante vs Evolve.**

#### Task 2.1 — Theme Mixer
- **Modulo:** `core/theme_editor.py` (nuovo)
- **Descrizione:** Classe `ThemeMixer` che prende in input:
  ```python
  ThemeComposition(
      gtk3_theme: str | None,
      gtk4_theme: str | None,
      shell_theme: str | None,
      icon_theme: str | None,
      cursor_theme: str | None,
      custom_name: str
  )
  ```
  e produce un Global Theme nominato salvabile in `presets.json` con flag `user_composed: true`.

#### Task 2.2 — CSS Color Extractor
- **Modulo:** `core/css_extractor.py` (nuovo)
- **Descrizione:** Classe `CssColorExtractor` che:
  1. Parsa `gtk-4.0/gtk.css` di un tema (o `gtk-3.0/gtk-main.css`).
  2. Estrae variabili CSS `@define-color`:
     - `theme_fg_color`, `theme_bg_color`
     - `theme_selected_bg_color` (accent)
     - `theme_selected_fg_color`
     - `wm_bg_color`, `wm_title_color` (opzionale)
  3. Restituisce dizionario `{name: rgba_string}`.

#### Task 2.3 — Theme Editor UI
- **Modulo:** `gui_gtk/views/editor_view.py` (nuova), `gui_gtk/widgets/color_picker.py` (nuovo)
- **Descrizione:** View dedicata con:
  - 5 dropdown per scegliere tema base per ogni componente.
  - Sezione "Colori personalizzati" con 4 `Gtk.ColorDialogButton` (fg, bg, accent, accent_fg) precaricati dal tema GTK4 selezionato.
  - Pulsante "Anteprima" → attiva preview in-app (Task 1.5).
  - Pulsante "Salva come Global Theme" → salva la composizione in `presets.json` come preset utente con `user_composed: true`.
  - Pulsante "Reset colori" → ripristina i colori originali del tema base.

#### Task 2.4 — Override colori persistente (fork tema)
- **Modulo:** `core/theme_editor.py` (estensione)
- **Descrizione:** Quando l'utente modifica i colori:
  1. Copiare il tema GTK4 originale in `~/.themes/{custom_name}-gtk4/`.
  2. Modificare solo le variabili `@define-color` nel `gtk.css` copiato (preservando il resto del file).
  3. Salvare metadata del fork in `~/.local/state/gnome-theme-manager/theme_forks.json`.
  4. Il tema fork appare nella lista "GTK4 themes" con etichetta `(edited)`.

#### Task 2.5 — Bozze persistenti
- **Modulo:** `gui_gtk/views/editor_view.py`
- **Descrizione:** Salvare automaticamente lo stato corrente dell'editor (composizione + colori modificati) in `~/.local/state/gnome-theme-manager/editor_draft.json` ad ogni modifica. Al riavvio, se draft presente, prompt "Riprendi bozza o inizia da nuovo?".

#### Task 2.6 — Stretch goal (opzionale — solo se tempo): Adaptive Colour dal wallpaper
- **Modulo:** `core/wallpaper_palette.py` (nuovo)
- **Descrizione:** Leggere il wallpaper corrente (`org.gnome.desktop.background picture-uri`), scaricare/analizzare l'immagine, estrarre palette dominante (k-means con k=5), proporre 5 palette pre-caricate nei picker dell'editor. **Se troppo complesso, saltare e documentare come TODO futuro.**

#### Acceptance Criteria globali Fase 2
- [ ] Utente può creare un Global Theme combinando 5 temi diversi e salvarlo.
- [ ] I colori fg/bg/accent di un tema GTK4 sono modificabili e la modifica produce un fork funzionante in `~/.themes/`.
- [ ] Il fork è reversibile (cancella cartella + rimuovi metadata).
- [ ] Bozze persistono tra sessioni.
- [ ] Coverage `core/` ≥ 80%, `pytest` verde.
- [ ] Protocollo 1.4 eseguito dopo conferma utente.

---

### 🔷 FASE 3 — Store Online (v1.3)

**Branch:** `feature/phase-3-online-store`
**Obiettivo:** Catalogo online di temi, icone e estensioni GNOME con ricerca, download e installazione.

#### Task 3.1 — API client per gnome-look.org / pling.com
- **Modulo:** `core/store_client.py` (nuovo)
- **Descrizione:** Classe `StoreClient` che:
  - Wrappa l'API pubblica di **pling.com** (OpenDesktop REST API) per sezioni "GTK3/4 Themes", "Icon Themes", "Cursor Themes", "Gnome Shell Themes".
  - Metodi: `search(query, category)`, `get_details(id)`, `download(id, dest_dir)`.
  - Gestione rate-limiting, retry con backoff, timeout 30s.
- Dipendenza consentita: `requests`.

#### Task 3.2 — Store UI
- **Modulo:** `gui_gtk/views/store_view.py` (nuova)
- **Descrizione:** View con:
  - Barra di ricerca + filtri per categoria.
  - Griglia di card (thumbnail + nome + autore + rating + pulsanti "Download" / "Anteprima").
  - View dettaglio con screenshot, descrizione, pulsante "Installa" (che scarica + usa `Installer.install_from_archive` del Task 1.7).
  - Stato download con progress bar (GTK4 `Gtk.ProgressBar`).

#### Task 3.3 — Extensions browser (read-only)
- **Modulo:** `core/extensions.py` (estensione), `gui_gtk/views/extensions_view.py` (nuova)
- **Descrizione:**
  - Lista estensioni installate via `gnome-extensions list`.
  - Toggle enable/disable via `gnome-extensions enable UUID` / `disable UUID`.
  - Pulsante "Browse online" apre `https://extensions.gnome.org` in browser di sistema (link esterno, NO embedded browser).

#### Task 3.4 — Cache locale
- **Modulo:** `core/store_client.py`
- **Descrizione:** Cache dei risultati di ricerca in `~/.cache/gnome-theme-manager/store_cache.json` con TTL 24h.

#### Acceptance Criteria globali Fase 3
- [ ] Ricerca online restituisce risultati entro 3s.
- [ ] Download + installazione automatica funzionano per ≥ 1 tema da pling.com.
- [ ] Lista estensioni installate è corretta, toggle enable/disable funziona.
- [ ] Cache rispetta TTL.
- [ ] Coverage `core/` ≥ 80%, `pytest` verde.
- [ ] Protocollo 1.4 eseguito dopo conferma utente.

---

### 🔷 FASE 4 — Profili & Automazioni (v1.4)

**Branch:** `feature/phase-4-profiles`
**Obiettivo:** Profili con coppia light/dark, switch automatico basato su `color-scheme` del sistema, autostart all'avvio.

#### Task 4.1 — Profili come preset con variante light/dark
- **Modulo:** `core/profiles.py` (nuovo, evoluzione di `presets.py`)
- **Descrizione:** Un profilo è un oggetto:
  ```json
  {
    "name": "My Profile",
    "light_preset": "preset_id_light",
    "dark_preset": "preset_id_dark",
    "auto_switch": true,
    "autostart": true
  }
  ```
  Salvato in `~/.local/state/gnome-theme-manager/profiles.json`.

#### Task 4.2 — Integrazione `color-scheme` (GNOME 42+)
- **Modulo:** `core/gsettings.py`
- **Descrizione:**
  - Leggere `org.gnome.desktop.interface color-scheme` (`prefer-light` / `prefer-dark`).
  - Esporre segnale `color-scheme-changed` usando `Gio.Settings.connect("changed::color-scheme", callback)`.
  - Quando il profilo attivo ha `auto_switch: true`, applicare il preset corrispondente al cambio di segnale.

#### Task 4.3 — UI profili
- **Modulo:** `gui_gtk/views/profiles_view.py` (nuova)
- **Descrizione:** View con:
  - Lista profili salvati.
  - Form creazione: nome + dropdown "preset light" + dropdown "preset dark" + toggle "Auto-switch con sistema" + toggle "Attiva all'avvio".
  - Pulsante "Imposta come attivo".

#### Task 4.4 — Autostart via systemd user
- **Modulo:** `core/autostart.py` (nuovo)
- **Descrizione:** Quando un profilo con `autostart: true` viene impostato come attivo:
  1. Installare file `~/.config/systemd/user/gnome-theme-manager.service` che al boot applica il preset corrispondente al `color-scheme` corrente.
  2. Eseguire `systemctl --user enable gnome-theme-manager.service`.
  3. Al disattivamento del profilo, rimuovere il file e `systemctl --user disable`.

#### Task 4.5 — Export/import profili
- **Modulo:** `core/profiles.py`
- **Descrizione:** `export(profile_name, path)` salva profilo + preset light + preset dark in un singolo file JSON. `import(path)` ricrea tutto.

#### Acceptance Criteria globali Fase 4
- [ ] Cambio manuale di `color-scheme` via `gsettings` fa cambiare automaticamente tema se profilo attivo con `auto_switch: true`.
- [ ] Reboot + login applica il profilo corretto.
- [ ] Export/import round-trip preserva tutto.
- [ ] Coverage `core/` ≥ 80%, `pytest` verde.
- [ ] Protocollo 1.4 eseguito dopo conferma utente.

---

### 🔷 FASE 5 — Sync & Distribuzione (v1.5+)

**Branch:** `feature/phase-5-sync-packaging`
**Obiettivo:** Sync tra PC, packaging Flatpak/.deb, i18n completa, logging strutturato, first-run tour.

#### Task 5.1 — Export/import profili (base sync)
- Già incluso in Task 4.5 (estendere per supportare cartella "profiles/" in root dell'export bundle).

#### Task 5.2 — Sync LAN (alternativa gratuita a Evolve wireless)
- **Modulo:** `core/sync_lan.py` (nuovo)
- **Descrizione:**
  - Discovery via **mDNS/Avahi** (pubblicazione servizio `_gtm._tcp`).
  - Trasferimento profili via HTTP server stdlib (`http.server`) su porta effimera.
  - UI: tab "Sync" mostra altri PC nella LAN + pulsante "Send profile" / "Receive profile".
- Dipendenza opzionale: `python3-avahi` / `zeroconf`.

#### Task 5.3 — Packaging Flatpak
- **File:** `io.github.granafilo.GnomeThemeManager.yml` (nuovo in repo root)
- **Descrizione:** Manifest Flatpak funzionante per Ubuntu 22.04+ e Fedora 38+. Build locale verificata con `flatpak-builder`.

#### Task 5.4 — Packaging .deb
- **File:** `debian/` directory (nuova) con `control`, `rules`, `changelog`.
- **Descrizione:** Build di un `.deb` installabile su Ubuntu 24.04.

#### Task 5.5 — i18n completa (IT + EN)
- **File:** `po/it.po`, `po/en.po`, `po/POTFILES.in`
- **Descrizione:**
  - Estrazione completa stringhe da `src/`.
  - Traduzione completa IT/EN.
  - Setup `gettext` in `__init__.py` per caricamento traduzione a runtime.
  - Wrapper `_()` esposto globalmente.

#### Task 5.6 — Logging strutturato
- **Modulo:** `core/logger.py` (nuovo)
- **Descrizione:** Logger JSON in `~/.local/state/gnome-theme-manager/logs/` con rotazione giornaliera. Flag `--verbose` in CLI.

#### Task 5.7 — First-run tour (stretch)
- **Modulo:** `gui_gtk/tour.py` (nuovo)
- **Descrizione:** Tour guidato (5 slide) alla prima esecuzione con highlight delle feature principali. Flag `first_run_completed: true` in `ui_prefs.json`.

#### Acceptance Criteria globali Fase 5
- [ ] Sync LAN funziona tra due macchine (test su rete locale).
- [ ] Flatpak builda e si lancia senza errori.
- [ ] `.deb` si installa su Ubuntu 24.04 e l'app è lanciabile.
- [ ] 100% stringhe UI tradotte, `msgfmt` senza errori.
- [ ] Log JSON rotanti vengono generati correttamente.
- [ ] Coverage `core/` ≥ 80%, `pytest` verde.
- [ ] Protocollo 1.4 eseguito dopo conferma utente.

---

## 4. Appendici

### 4.1 Checklist di chiusura fase (da spuntare OGNI VOLTA)

```
□ A. Documentazione aggiornata
    □ ROADMAP.md
    □ README.md
    □ Changelog
    □ Eventuale doc tecnica API

□ B. Integrità test + pulizia
    □ pytest completo passa
    □ coverage ≥ 80% su core/
    □ pylint/ruff senza warning di unused
    □ git status --short pulito (solo file legittimi)
    □ Test deterministici e isolati
    □ Nessun file temporaneo residuo
    □ Commit per-task effettuati: verificare con `git log --oneline` che ci sia esattamente 1 commit per ogni task della fase (nessun task accumulato)

□ C. Traduzioni
    □ Stringhe estratte
    □ it.po e en.po sincronizzati
    □ Nessun fuzzy non risolto
    □ msgfmt compila senza errori
    □ Nessuna stringa hardcodata in GUI/CLI
    □ Encoding UTF-8 verificato

□ D. Comando commit fornito all'utente
    □ Output: git add -A && git commit -m "chore: phase N completion..."
```

### 4.2 Riferimenti esterni utili
- Evolve Core (Apache-2.0, v1.7): `https://github.com/arcnations-united/evolve-core` — riferimento per pattern UI/UX.
- Pling API docs: `https://www.pling.com/api/` — riferimento per store.
- GNOME HIG: `https://developer.gnome.org/hig/` — linee guida UI Libadwaita.

### 4.3 Glossario
| Termine | Significato |
|---|---|
| **Global Theme** | Combinazione di 5 componenti (gtk3, gtk4, shell, icons, cursors) in un'unica entità nominata |
| **Preset** | Snapshot di una combinazione tema, base dei Global Themes |
| **Profilo** | Coppia di preset (light + dark) con automazione di switch |
| **Fork** | Copia modificata di un tema in `~/.themes/` per editing colori |
| **Preview in-app** | Applicazione di un tema solo alla finestra GnomeThemeManager (sandbox) |

### 4.4 Note finali per il coding agent
- **Non inventare feature.** Se ritieni che una feature sia utile ma non è qui, apri una domanda all'utente PRIMA di implementare.
- **Priorità alla stabilità.** Meglio una fase meno feature-rich ma stabile che il contrario.
- **Testability first.** Ogni modulo in `core/` deve essere testabile senza GUI e senza filesystem reale (mock di `gsettings`, filesystem in `tmp_path`).
- **Comunica.** Alla fine di ogni fase, fornisci un report conciso: task completati, task saltati (con motivo), problemi aperti, domande per l'utente.

---

**Fine del documento.** Il coding agent può ora iniziare con la **FASE 0** aprendo la branch `feature/phase-0-stabilization`.