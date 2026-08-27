# 📋 Master Implementation Plan — GnomeThemeManager

**Versione documento:** 2.0
**Autore:** Planning Agent
**Destinatario:** Coding Agent
**Repo:** https://github.com/granafilo/GnomeThemeManager
**Stato:** FASE 2 ✅ COMPLETATA (agosto 2026) → prossimo: FASE 3
**Target finale:** parità funzionale con Evolve Core v1.7 (free) + feature differenzianti open-source

---

## 0. Meta-informazioni

### 0.1 Scopo del documento
Unica fonte di verità per il coding agent. Definisce workflow, convenzioni, fasi, task atomici e acceptance criteria. Il coding agent NON deve procedere con task non presenti né inventare feature.

### 0.2 Architettura di riferimento (da rispettare sempre)

```
src/gnome_theme_manager/
├── cli/           # parser argomenti + routing comandi
├── core/          # logica dominio (scanner, manager, installer, gsettings,
│                  # sandbox, presets, extensions, theme_editor, profiles, store)
├── gui_gtk/       # GUI nativa GTK4/Libadwaita (window, views, widgets)
└── __init__.py
tests/             # unit + integration tests
docs/              # roadmap, master plan, guide, skills
po/                # file .po per i18n (EN sorgente, IT traduzione)
```

**Regola d'oro**: GUI e CLI consumano SEMPRE le stesse API in `core/`. Nessuna logica di business in `gui_gtk/` o `cli/`.

### 0.3 Stack tecnico fisso
- Python ≥ 3.10 · PyGObject ≥ 3.42.0 · GTK4 + Libadwaita
- `gsettings` unico backend di persistenza tema
- Target primario: Ubuntu 24.04 — GNOME 46

### 0.4 Dipendenze esterne consentite
Solo PyGObject + `requests` (da Fase 3). Nessuna altra senza approvazione esplicita.

---

## 1. Workflow globale del coding agent

### 1.1 Protocollo di branch
Ogni fase su branch dedicata derivata da `main`: `feature/phase-{N}-{slug}`.
Chore standalone: `chore/{slug}` (es. `chore/english-first`).

### 1.2 Granularità dei commit (1 task = 1 commit completo)

Protocollo per-task:
0. L'agent stampa UNA riga GUI CHECK nel formato esatto:
    `GUI CHECK: [comportamento implementato] -> [come verificarlo tramite GUI]`
    Esempio: `GUI CHECK: preview icon pack -> apri la tab "Icon Packs": ogni
    pack mostra una griglia di icone standard renderizzate col pack, senza
    cambiare il tema di sistema.`
    Per task senza superficie GUI: `GUI CHECK: n/a - [motivo]` + comando
    alternativo di verifica (es. comando CLI).
1. L'agent stampa il comando di commit del task...

Ogni TASK produce ESATTAMENTE un commit, contenente TUTTO il lavoro del task:
implementazione iniziale + tutte le modifiche richieste dall'utente finché il
task non è approvato.

Regole:
- Le iterazioni/modifiche su un task APERTO (non ancora approvato) NON creano
  nuovi commit: aggiornano lo stesso commit.
- Il messaggio deve essere COMPLETO: header conventional + corpo che descrive
  l'INTERA integrazione del task (cosa introduce nel progetto). Mai messaggi
  tipo "update/fix del task precedente".
- Se esiste già un commit locale per il task: `git commit --amend` con
  messaggio completo riscritto.
- Se già pushato sulla branch feature: amend + `git push --force-with-lease`
  (MAI su main).
- Il commit di task contiene SOLO codice + test + po del task.
- Il commit di chiusura fase contiene SOLO gli esiti degli step A–C.
- L'agent NON esegue mai commit: stampa il comando, l'utente lo esegue.
- `git add` esplicito sui soli file del task (mai `git add -A`).

Formato messaggio (header + corpo completo):

```
feat(gui): task 1.1 — unified Global Themes view

Introduce a single Global Themes page replacing the presets sidebar:
- unified data model (origin: bundled/user)
- ordering: user themes on top (newest first), 3 bundled at bottom
- seed bundled themes on first launch
- i18n: new strings added to po/en.po and po/it.po
```

### 1.3 Protocollo di testing (fine fase + durante task)

**Comandi canonici di progetto** (definiti nel PLAYBOOK sez. 8, popolati dopo P20):

| Variabile        | Significato                                                  |
| ---------------- | ------------------------------------------------------------ |
| `TEST_SUITE`     | pytest con coverage ( pytest -v )                            |
| `LINT_CMD`       | ruff (ruff check src tests)                                  |
| `TYPE_CHECK_CMD` | mypy (mypy --strict src)                                     |
| `GUI_LAUNCH_CMD` | comando di avvio GUI (PYTHONPATH=src python3 -m gnome_theme_manager gui) |

**Durante ogni task** (al cambio verde):

```bash
$TEST_SUITE
$LINT_CMD
$TYPE_CHECK_CMD
```

**A fine fase** (prima del protocollo §1.4):

- Eseguire i 3 comandi canonici
- Lanciare la GUI con `$GUI_LAUNCH_CMD` e verificare assenza di traceback entro 10s
- Coverage minima `core/`: 80%

**Regola anti-overhead**: l'agent NON esegue comandi esplorativi prima di quelli canonici.
Se un comando canonico fallisce, l'agent chiede:

1. Output completo dell'errore
2. (Opzionale) comandi più specifici suggeriti dal framework (es. `pytest tests/test_x.py::test_y`)

Non indaga mai in autonomia su test/lint prima di chiedere.

### 1.4 Protocollo di chiusura fase (POST-CONFERMA — OBBLIGATORIO)

L'agent NON procede alla fase successiva senza conferma esplicita dell'utente.
Dopo la conferma, eseguire in ordine:

**Step A — Documentazione**: 

- aggiornare `docs/ROADMAP.md` (feature → ✅ con data)
-  `README.md` (sezione Feature)
-  docs tecniche API nuove
-  changelog.

- Aggiornare `docs/FEATURE_GUIDE.md`: una riga per ogni nuovo task shipped (✅ quando mergiato)

**Step B — Integrità test + pulizia**: pytest completo senza skip ingiustificati; pylint/ruff zero warning unused; `git status --short` pulito (artefatti rimossi o in .gitignore); nessun test dipendente da stato locale.

**Step C — Traduzioni**: estrazione stringhe aggiornata; `po/en.po` e `po/it.po` sincronizzati, nessun fuzzy; `msgfmt` senza warning; nessuna stringa UI hardcodata; encoding UTF-8 verificato.

**Step D — Version bump**

1. Nuova versione dal mapping §2.7.
2. Aggiornare l'unica fonte: `__version__` in `src/gnome_theme_manager/__init__.py`.
3. Aggiornare la **version surface** (tutti i marker "versione corrente"):
   - `CHANGELOG.md`: entry in cima `## [X.Y.Z] - YYYY-MM-DD`
   - `README.md`: riga standard `**Current release:** vX.Y.Z` + tutte le reference alla versione corrente
   - metainfo `.xml` / `.desktop` (se presenti): ultima `<release version="X.Y.Z"/>`
   - `docs/ROADMAP.md`: riga "current version" se presente
   - (`docs/FEATURE_GUIDE.md` NON va toccata: contiene versioni storiche)
4. Eseguire in locale: `python3 scripts/check_version_coherence.py` → deve passare.
5. Regola grep: nessun marker "corrente" con la vecchia versione.
6. Il bump rientra nel commit finale di chiusura.

**Step E — Comando di commit finale**: stampare (NON eseguire):

```bash
git add -A && git commit -m "chore: phase {N} completion — v{X.Y.Z} — docs, tests integrity, i18n verification [skip ci]"
```

> Nota: i file di codice/test sono già stati committati per-task durante la fase.
> Questo commit contiene esclusivamente gli esiti degli step A–D.
> Il tag `v{X.Y.Z}` viene creato dall'utente dopo il merge.

**Step F — PR summary**
Dopo lo step E, stampare un PR summary pronto da incollare (titolo + body),
costruito dal `git log` della branch e dalle righe GUI CHECK della fase:

```
## Summary — Phase {N}: <nome> (v{X.Y.Z})

<2-3 righe: cosa introduce la fase nel complesso>

## Tasks
- [x] {N}.1 <nome> — una riga su cosa introduce
- [x] {N}.2 <nome> — ...
- [x] <eventuali commit chore della fase (i18n backfill, docs deps...)>

## Manual verification (GUI CHECK)
- <comportamento> -> <verifica GUI>
- ...

## Tests & quality
- pytest verde, coverage core >= 80% · ruff/mypy puliti
- i18n en/it sincronizzati, msgfmt ok · versione allineata a v{X.Y.Z}

## Breaking changes / note
- <se presenti, altrimenti "none">

## Post-merge
- tag v{X.Y.Z}
```

L'utente lo incolla in `gh pr create --body`. Non eseguire la PR: spetta all'utente.

### 1.5 Gestione modifiche post-conferma
Se l'utente richiede modifiche dopo la chiusura, il ciclo riprende dalla feature modificata e gli step A–D vanno rieseguiti integralmente.
Le modifiche post-conferma seguono la stessa policy: 1 commit dedicato per la fix (codice + test), poi riesecuzione A–D con commit finale separato.

- Modifiche su task APERTO (non approvato) = stesso commit (amend), messaggio
  completo riscritto.
- Modifiche su task GIÀ approvato/committato = commit di fix separato +
  riesecuzione step A–D.

### 1.6 Blocco su ambiguità
In caso di ambiguità non risolvibile dal documento: fermarsi e chiedere. Mai decisioni unilaterali su feature/specifiche.

### 1.7 Skills on-demand
In `docs/skills/` esistono playbook specialistici invocati dall'utente: `review.md`, `debug_gtk.md`, `test_strategy.md`, `refactor.md`, `security_review.md`, `error_triage.md`. Quando l'utente li invoca, seguirli alla lettera.

### 1.8 Condizioni di STOP (non negoziabili)

Il coding agent DEVE fermarsi immediatamente se:
- `$TEST_SUITE` fallisce (anche un solo test rosso)
- `$LINT_CMD` fallisce
- `$TYPE_CHECK_CMD` fallisce
- `$GUI_LAUNCH_CMD` crasha o produce traceback

In caso di STOP:

1. NON aprire branch, NON creare commit, NON toccare task successivi
2. Diagnosticare il fallimento (skill `error_triage` se utile)
3. Proporre fix minimo e applicarlo
4. Riportare $TEST_SUITE e $LINT_CMD al verde PRIMA di riprendere
5. Un task è completato (e committibile) SOLO con test verdi

"Fixa senza attendere conferma" significa: fixa in autonomia il fallimento,
NON: salta il fallimento e procedi.

---

## 2. Convenzioni di progetto

### 2.1 Nomenclatura
Moduli snake_case · Classi PascalCase · Costanti UPPER_SNAKE · Branch `feature/phase-N-slug` · Test `test_<modulo>_<comportamento>.py`

### 2.2 Tipizzazione
Type hints completi (PEP 484) in `core/`; `mypy --strict src/gnome_theme_manager/core/` deve passare.

### 2.3 Logging
`logging` stdlib, logger per modulo. Nessun `print()` in `core/` o `gui_gtk/`.

### 2.4 Gestione errori
`core/` non crasha su temi non validi: restituisce oggetti risultato (`ThemeValidationResult`, `OperationResult`). GUI: `Adw.MessageDialog`. CLI exit codes: 0 ok, 1 generico, 2 uso errato, 3 permessi.

### 2.5 Persistenza stato utente
Solo `~/.local/state/gnome-theme-manager/` (JSON). Mai `~/.config/`.

### 2.6 Lingua (English-first)
- Contenuti pubblici (README, docs pubbliche, CHANGELOG, metainfo/.desktop, stringhe UI, output CLI, commenti, docstring, log) = **inglese**
- i18n: msgid gettext in EN (lingua sorgente); `po/it.po` = traduzione italiana; default locale = en
- File agent e personali (MASTER_PLAN, ARCHITECTURE, PLAYBOOK, .cursorrules, skills) = italiano
- Comunicazione in chat con l'utente = italiano

### 2.7 Versioning (single source of truth)
- Unica fonte scrivibile: `src/gnome_theme_manager/__init__.py` → `__version__`
- `pyproject.toml` la legge dinamicamente (setuptools `dynamic = ["version"]`): mai duplicare il valore
- CLI `--version` e GUI About leggono `__version__` a runtime
- Schema SemVer: fase = minor (1.1.0, 1.2.0…), chore/fix = patch (1.0.1), major solo per release breaking
- Mapping fase → versione:

| Milestone | Versione |
| --------- | -------- |
| Fase 0    | 1.0.0    |
| Fase 1    | 1.1.0    |
| Fase 2    | 1.2.0    |
| Fase 3    | 1.3.0    |
| Fase 4    | 1.4.0    |
| Fase 5    | 1.5.0    |
| Fase 6    | 1.6.0    |
| Fase 7    | 1.7.0    |

- La versione si aggiorna SOLO durante la chiusura fase (step D), mai durante i task
- Tag git `v{X.Y.Z}` creato dall'utente dopo il merge, allineato alla versione

### 2.8 i18n follows the feature
Ogni task che introduce stringhe user-visible DEVE, nello STESSO commit:
1. Wrappare le stringhe in gettext (`_()`)
2. Aggiungere i msgid a `po/en.po`
3. Aggiungere le traduzioni IT a `po/it.po` (niente untranslated/fuzzy)
4. Ricompilare le traduzioni: `python3 scripts/compile_translations.py`
   (i `.po` sono sorgenti; l'app legge i `.mo` binari). I `.mo` NON sono
   committati (`*.mo` in `.gitignore`): generati a fine task e in packaging.
5. Se il task aggiunge/cambia stringhe, il GUI CHECK include la verifica con
   `LANG=it_IT.UTF-8` (italiano) e senza (inglese).

Lo step C della chiusura fase è SOLO verifica finale di consistenza.

### 3.0 Scala di priorità
Ogni task ha un tag [P0–P3]. I tag guidano l'ordine interno alla fase e le
decisioni di taglio se una fase rischia di esplodere.

- **P0 — Critico**: blocca fiducia/correttezza (alert bloccanti, apply su temi
  non disponibili, integrità dello stato). Va fatto sempre, per primo.
- **P1 — Alto**: completa il core di theming o blocca l'onboarding
  (editor sui propri temi, docs essenziali, robustezza UI).
- **P2 — Medio**: valore visibile / differenzianti (store, font, icone,
  profili, packaging).
- **P3 — Basso / stretch**: nice-to-have, tagliabile senza danni
  (terminal editor, tour, lingue extra). Regola: se stretch salta,
  diventa TODO documentato, non debito silenzioso.



---

## 3. Fasi di implementazione

### 🔷 FASE 0 — Setup & Stabilizzazione (v1.0) — ✅ COMPLETATA (agosto 2026)

Branch `feature/phase-0-stabilization` mergiata. Task 0.1–0.7 completati:
- [x] 0.1 Fix gtk4 override status all'avvio (`Gtk4OverrideStatus {ACTIVE, INACTIVE, FOREIGN}`)
- [x] 0.2 Fix missing themes (scanner 4 directory + inheritance)
- [x] 0.3 UX shortcut e focus (Ctrl+W, click-outside, filtro temi sistema)
- [x] 0.4 Apply selettivo per componente (GUI)
- [x] 0.5 Preset 2.0 snapshot espliciti (`presets.json`)
- [x] 0.6 Shell theme + gestione estensione user-theme
- [x] 0.7 Docs permessi esecuzione

---

### 🔧 CHORE — English-first (standalone, eseguibile prima della Fase 1)

**Branch:** `chore/english-first`
**Commit:** singolo commit chore (policy §1.2)

- [x] C.1 Tradurre README.md, docs/ROADMAP.md, docs pubbliche, CHANGELOG
- [x] C.2 Codice: commenti, docstring, log, output CLI, stringhe errore → EN; stringhe hardcoded → gettext con msgid EN
- [x] C.3 i18n: setup gettext se mancante (source EN); `po/en.po` allineato; `po/it.po` completo e non fuzzy
- [x] C.4 .desktop / metainfo / AppStream → EN

**EXCLUDE (restano IT):** PLAYBOOK.md, MASTER_PLAN.md, ARCHITECTURE.md, .agents/rules/*, docs/skills/*

**Acceptance:** pytest/ruff/mypy verdi · msgfmt ok · `grep -rIn "[àèéìòù]" README.md docs/ src/` zero hit fuori da EXCLUDE e po/it.po · GUI default EN, IT con `LANG=it_IT.UTF-8`

---

### 🔧 CHORE — Version single source (standalone)

**Branch:** `chore/version-single-source`
**Commit:** singolo commit `chore: version single source of truth`

- [x] V.1 `__version__` in `__init__.py` unica fonte; `pyproject.toml` dynamic version
- [x] V.2 CLI `--version` e GUI About leggono `__version__` a runtime
- [x] V.3 Metainfo/.desktop: entry release aggiornabile dallo step D (manuale o script)
- [x] V.4 Test: `test_version_consistency` (pyproject risolve == `__version__`; CLI --version coerente)

**Acceptance:** la versione esiste in un solo punto scrivibile; tutto il resto deriva.

---

### 🔷 FASE 1 — Global Themes & Validazione (v1.1) — ✅ COMPLETATA (agosto 2026)

**Branch:** `feature/phase-1-global-themes`

- [x] 1.1 Global Themes: view unica unificata (sostituisce i preset)
- [x] 1.2 ThemeValidator
- [x] 1.3 Corruption detection + warning pre-apply
- [x] 1.4 Preview visuale icon pack
- [x] 1.5 Preview in-app sicura (sandbox GTK4) + rollback automatico
- [x] 1.6 Creazione cartelle utente
- [x] 1.7 Installazione assistita da cartella/archivio con validazione pre-install

**Acceptance Fase 1:** ✅ global theme 1-click su 5 componenti · validator rileva temi incompleti · preview icone senza cambio sistema · preview in-app reversibile · install da archivio ok · coverage ≥80% · protocollo §1.4 post-conferma. 

- [x] Esiste UNA sola pagina Global Themes; nessuna pagina/sidebar preset residua
- [x] Ordinamento corretto: user in cima (recenti prima), 3 bundled in fondo
- [x] Ogni stringa nuova della view è in po/en.po e po/it.po nello stesso commit

---

### 🔷 FASE 2 — Theme Editor (v1.2) — ✅ COMPLETATA (agosto 2026)

**Branch:** `feature/phase-2-theme-editor`

- [x] 2.1 Theme Mixer (`core/theme_editor.py`: `ThemeComposition` → Global Theme utente)
- [x] 2.2 CSS Color Extractor (`core/css_extractor.py`: estrazione token colore e `@define-color`)
- [x] 2.3 Theme Editor UI (`gui_gtk/pages/editor_view.py` + `color_picker.py`: Mixer + selettori colore + preview)
- [x] 2.4 Override colori persistente (`core/theme_forks.py`: fork GTK4 in `~/.themes/{name}-gtk4`)
- [x] 2.5 Bozze persistenti (`core/editor_draft.py`: auto-save configurabile e resume draft)
- [x] 2.6 Adaptive Color dal wallpaper (`core/wallpaper_color.py`: k-means palette e applicazione globale GTK+Shell)
- [x] 2.7 Shell Theme Editor (`core/shell_editor.py`: fork Shell con override CSS marker engine)

**Acceptance Fase 2:** ✅ mixer 5 componenti funzionante · estrazione colori GTK/Shell accurata · anteprima live con auto-revert · fork GTK4 e Shell persistenti senza corrompere i temi base · recupero bozze affidabile · palette wallpaper sincronizzata · coverage ≥80% · protocollo §1.4 post-conferma.

#### Task 2.7 — Shell Theme Editor (editing anche per GNOME Shell)
- Moduli: `core/shell_editor.py` (nuovo); UI: sezione "Shell" in
  `gui_gtk/views/editor_view.py`
- **Fork shell**: copia della porzione shell del tema base in
  `~/.themes/{custom_name}-shell/`; metadata in `theme_forks.json`
  (componente "shell"); fork reversibile (elimina dir + ripristina setting)
- **Estrazione colori chiave** (`ShellColorExtractor`):
  1. Se `gnome-shell.css` contiene `@define-color` → usa quelli
  2. Altrimenti euristiche su selettori stabili: `#panel` (background),
     `.panel-button` (color), `.overview` (background), selezione/accent
- **Colori editabili** (ColorDialogButton): accent/selezione, background
  panel, testo panel, background overview
- **Override generato**: blocco CSS appended al `gnome-shell.css` forkato,
  delimitato da marker `/* GTM-OVERRIDE-START */` / `/* GTM-OVERRIDE-END */`;
  il re-editing SOSTITUISCE il blocco tra i marker (idempotente)
- **Apply**: `org.gnome.shell.extensions.user-theme` (riusa
  `core/extensions.py`, Task 0.6). Preview in-app NON possibile per la shell:
  apply con **auto-revert di sicurezza**: `Adw.MessageDialog` con countdown
  15s; senza conferma → ripristino automatico del tema shell precedente
  (pattern tipo impostazioni display di GNOME)
- **Integrazione**: il tema shell forkato è selezionabile come componente
  shell nel Theme Mixer (Task 2.1) e nei Global Themes (origin "user")
- **Limitazione documentata** (UI + docs): su Wayland può servire logout o
  `Alt+F2 r` per il reload completo del tema shell
- i18n §2.8 per le nuove stringhe; GUI CHECK con e senza `LANG=it_IT.UTF-8`
- Test: estrattore su fixture css (tmp_path) + idempotenza override +
  auto-revert con gsettings mockato

**Acceptance Fase 2:**

- [x] mix 5 temi salvabile 
- [x] colori modificabili con fork funzionante e reversibile
- [x] bozze persistenti
- [x] coverage ≥80% 
- [x] protocollo §1.4
- [x] Tema shell editabile (4 colori chiave)
- [x] fork reversibile; 
- [x] override idempotente su edit ripetuti
- [x] apply con auto-revert 15s funzionante

---

### 🔷 FASE 3 — Fallback & Robustness (v1.3)

**Branch:** `feature/phase-3-fallback-robustness`
**Obiettivo:** eliminare gli alert bloccanti e rendere l'apply robusto su
host/snap/flatpak con fallback theme scegliibili dall'utente.

#### Task 3.1 — Fallback themes + rimozione alert "missing themes" [P0]
- Moduli: `core/fallback.py` (nuovo), `core/sandbox.py` + `core/manager.py`
  (estensioni), `gui_gtk/views/settings_view.py` (sezione "Fallback")
- Config `fallbacks.json` nella state dir: `{gtk3, gtk4, shell, icons,
  cursors}` selezionabili; default = temi di sistema rilevati al primo avvio
- `ThemeAvailabilityChecker.check(theme, target)` con target
  `{host, snap, flatpak}`: verifica presenza nelle directory del target
- Flusso apply: tema non disponibile su un target → NON applicato lì;
  applicato il fallback dell'utente per quel target; info banner
  "fallback in use", mai alert bloccanti
- UI: 5 dropdown che listano SOLO temi disponibili su tutti i target
- RIMOZIONE definitiva dell'alert "missing themes": lo scanner flagga i
  non disponibili, la UI mostra badge "fallback"
- La propagazione sandbox usa la stessa logica
- Test: checker su tmp_path; apply con tema mancante → fallback applicato;
  nessun percorso GUI solleva alert bloccanti

#### Task 3.2 — Estensione User Themes: auto-enable opzionale [P0]
- Moduli: `core/extensions.py` (estensione), `gui_gtk/views/settings_view.py`
- Pref `auto_enable_user_theme` in `ui_prefs.json` + toggle in settings
- ON: apply shell theme abilita l'estensione silenziosamente
- OFF: resta il dialog Adw del Task 0.6
- L'alert permanente diventa toast informativo una-tantum
- Test: entrambi i percorsi con gsettings mockato

#### Task 3.3 — Docs: permessi esecuzione [P1]
- File: `README.md`
- Sezione "Make the launcher executable": chmod +x, note permessi e
  launchers (completa il pending della Fase 0)

#### Task 3.4 — Icone fallback bundled per la UI [P1]
- Moduli: `data/icons/` (asset nuovi), `gui_gtk/window.py` (init chain)
- L'app bundle icone standard usate come fallback nella chain del tema
  icone: la UI non mostra mai placeholder "icona mancante"
- Test: lookup Gtk.IconTheme con tema privo dell'icona → fallback risolto

**Acceptance Criteria globali Fase 3:**
- [x] Alert "missing themes" assente dal codice e dalla UI
- [x] Apply su tema non disponibile → fallback applicato + info banner
- [x] Fallback selezionabili, dropdown filtrati per disponibilità
- [x] Toggle auto-enable user-theme: ON silenzioso / OFF dialog
- [x] README con sezione permessi; UI senza placeholder icone
- [x] i18n §2.8 · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 4 — Editors (v1.4)

**Branch:** `feature/phase-4-editors`
**Obiettivo:** completare il controllo dell'utente sui propri temi
(modifica, icone, font) prima di aprire allo store.

#### Task 4.1 — Editor Global Themes esistenti [P1]
- Moduli: `core/global_themes.py` (estensione),
  `gui_gtk/views/global_themes_view.py`
- Modifica in-place di Global Themes `origin: user`: componenti, nome, icona
- Bundled non modificabili → "Save as copy" (crea origin user in cima)
- Bottone "Edit" sulla card apre il Theme Mixer (Task 2.1) precompilato
- Test: edit in-place preserva origin/created_at e ordinamento;
  save-as-copy crea preset user

#### Task 4.2 — Icone custom per Global Themes [P2]
- Moduli: `core/global_themes.py`, `gui_gtk/widgets/icon_picker.py` (nuovo)
- Campo `icon` nel preset; picker da tema icone corrente o asset bundled
- Le card renderizzano l'icona custom con fallback (Task 3.4) se assente
- Test: round-trip preset con icon; icon mancante → fallback

#### Task 4.3 — Font editor [P2]
- Moduli: `core/fonts.py` (nuovo), `gui_gtk/views/fonts_view.py` (nuova)
- gsettings `org.gnome.desktop.interface`: `font-name`,
  `document-font-name`, `monospace-font-name`, `text-scaling-factor`
- UI: Gtk.FontDialog + spin size + scaling factor + preview live; Apply/Reset
- Campo opzionale `fonts` nel preset: i Global Themes che lo contengono lo
  applicano insieme al resto
- Test: gsettings mockato; round-trip preset con fonts

#### Task 4.4 — Terminal editor (stretch) [P3]
- Moduli: `core/terminal_palette.py` (nuovo)
- Palette derivata dal tema corrente (riusa `CssColorExtractor`)
- Apply a GNOME Terminal via profilo gsettings relocatable; fallback:
  export palette JSON per import manuale
- Se troppo complesso: saltare → TODO documentato (regola §3.0 P3)

**Acceptance Criteria globali Fase 4:**
- [x] Edit Global Theme user in-place; bundled → save as copy
- [x] Icone custom sulle card con fallback
- [x] Font editor applica le 4 chiavi; `fonts` nei preset funzionante
- [x] (Stretch) terminal applicato o TODO documentato
- [x] i18n §2.8 · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 4.5 — Snap Integration & Maintenance (v1.4.1) ✅
**Branch:** `fix/v1.4.1` (già mergiato su `main`)
**Obiettivo:** Integrazione sandbox avanzata (Snap/Flatpak), diagnostica live e fix di stabilità post-Fase 4.

- **Task 4.5.1 — Instant Custom Content Snap Packaging [P1]**: Sottosistema `core/theme_snap_manager` per compilare Content Snap locali (<1s via `snap pack` + `mksquashfs`) per temi GTK e icone personalizzati, eliminando i warning "Missing themes" nelle app Snap confinate.
- **Task 4.5.2 — PolicyKit Integration [P1]**: Installazione batch e connessione slot Snap sotto un singolo prompt grafico `pkexec`.
- **Task 4.5.3 — Live Sandbox Diagnostics [P2]**: Vista real-time dei temi desktop attivi, Content Snap installati e app Snap connesse.
- **Task 4.5.4 — Theme Editor Improvements [P2]**: Avvio editor sulle impostazioni desktop attive, dialog "Open Global Theme", azione "Reset", aggiornamento in-place del nome e fix dei selettori CSS Shell Quick Settings.
- **Task 4.5.5 — Theme Deletion Protections [P1]**: Azione delete su temi utente con protezioni attive per tema in uso, fix `NameError` logger nell'installer e cancellazione di temi incompleti/invalidi.
- **Task 4.5.6 — Core GTK Fallback Override Fix [P1]**: Fix della logica di fallback per applicare direttamente il tema selezionato alle GSettings.
- **Task 4.5.7 — AppImage & Asset Fixes [P2]**: Unificazione risoluzione cartelle temi, launcher icon resolution resiliente.
- **Task 4.5.8 — i18n & Packaging [P2]**: Aggiornamento cataloghi PO/MO en/it, `metainfo.xml`, README e CHANGELOG.

---

### 🔷 FASE 4.8 — Stabilizzazione e Rifinitura Pre-Store (v1.4.8) ✅
**Branch:** `feature/phase-4.8-stabilization`
**Obiettivo:** Risolvere le ultime incongruenze di stato, documentazione e UX prima di aprire la Fase 5 (Online Store).

- [x] **Task 4.8.1 — Fallback Temi Dinamici [P1]**: Rimosso riferimenti hardcodati ai temi di fallback. Esteso `ThemeAvailabilityChecker` per validare dinamicamente i temi di sistema e applicare l'override direttamente alle GSettings.
- [x] **Task 4.8.2 — Risoluzione Icona Flatpak [P1]**: Corretto il percorso di risoluzione e bundle dell'icona di avvio per visualizzazione corretta in Flatpak (runtime `/app/share/icons`, `.desktop`, `metainfo.xml`, `data/icons/`).
- [x] **Task 4.8.3 — Documentazione Override Sandbox & Guida In-App [P2]**: Espanso `docs/SANDBOX.md` e aggiunto dialog modale interattivo in-app con guida e comandi passo-passo per Flatpak e Snap.
- [x] **Task 4.8.4 — Sincronizzazione Live GSettings e Configurazione Attuale [P1]**: Binding in tempo reale con notifiche `changed` Gio.Settings (`org.gnome.desktop.interface`), risoluzione dinamica dell'entry `auto-current` e pulsante di sincronizzazione rapida nella scheda Temi Globali.
- [x] **Task 4.8.5 — Editor Preferenza Chiaro/Scuro (`color-scheme`) [P2]**: `AdwComboRow` interattivo per `color-scheme` in Stato Attuale, scheda Temi GTK e Theme Editor con binding live GSettings e localizzazione.
- [x] **Ottimizzazioni Prestazionali & CI Hardening**: Diagnostica Sandbox asincrona su worker thread, query Snap `gtk-common-themes` single-shot, isolamento scanner mock deterministico per test CI headless.

---

### 🔷 FASE 5 — Online Store (v1.5)

**Branch:** `feature/phase-5-online-store`

#### Task 5.1 — API client pling.com [P2]
- Modulo: `core/store_client.py` (nuovo); dipendenza `requests`
- `search(query, category)`, `get_details(id)`, `download(id, dest_dir)`;
  retry/backoff, timeout 30s

#### Task 5.2 — Store UI [P2]
- Modulo: `gui_gtk/views/store_view.py` (nuova)
- Ricerca + filtri, griglia card, dettaglio con screenshot, "Installa"
  (riusa installer Task 1.7), progress bar

#### Task 5.3 — Extensions browser [P2]
- Moduli: `core/extensions.py`, `gui_gtk/views/extensions_view.py`
- Lista `gnome-extensions list`, toggle enable/disable, link esterno a
  extensions.gnome.org

#### Task 5.4 — Cache locale [P3]
- `~/.cache/gnome-theme-manager/store_cache.json`, TTL 24h

**Acceptance Criteria globali Fase 5:**
- [ ] Ricerca <3s; download+install da pling ok; toggle estensioni ok; TTL ok
- [ ] i18n §2.8 · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 6 — Profili & Automazioni (v1.6)

**Branch:** `feature/phase-6-profiles`

#### Task 6.1 — Profili con variante light/dark [P2]
- Modulo: `core/profiles.py` (nuovo)
- `{name, light_preset, dark_preset, auto_switch, autostart}` in
  `profiles.json`

#### Task 6.2 — Integrazione color-scheme (GNOME 42+) [P2]
- Modulo: `core/gsettings.py`
- Segnale `changed::color-scheme`; apply automatico se `auto_switch: true`

#### Task 6.3 — UI profili [P2]
- Modulo: `gui_gtk/views/profiles_view.py` (nuova)
- Lista, form creazione, "Imposta come attivo"

#### Task 6.4 — Autostart via systemd user [P2]
- Modulo: `core/autostart.py` (nuovo)
- Service user enable/disable coerente con `autostart`

#### Task 6.5 — Export/import profili [P2]
- Bundle JSON singolo (profilo + preset light + dark)

**Acceptance Criteria globali Fase 6:**
- [ ] Switch automatico su color-scheme; apply al reboot; round-trip export
- [ ] i18n §2.8 · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 7 — Sync & Distribuzione (v1.7+)

**Branch:** `feature/phase-7-sync-packaging`

#### Task 7.1 — Sync LAN [P2]
- Modulo: `core/sync_lan.py` (nuovo); mDNS/Avahi `_gtm._tcp` + HTTP stdlib
- Tab Sync con Send/Receive profile

#### Task 7.2 — Packaging Flatpak [P2]
- `io.github.granafilo.GnomeThemeManager.yml`; test Ubuntu 22.04+/Fedora 38+

#### Task 7.3 — Packaging .deb [P2]
- Dir `debian/`; install su Ubuntu 24.04

#### Task 7.4 — i18n lingue aggiuntive [P3]
- Workflow traduzioni + eventuali nuove lingue (infrastruttura già EN-source)

#### Task 7.5 — Logging strutturato [P3]
- `core/logger.py`; JSON rotanti in state dir; `--verbose`

#### Task 7.6 — First-run tour (stretch) [P3]
- `gui_gtk/tour.py`; 5 slide; flag `first_run_completed`

**Acceptance Criteria globali Fase 7:**
- [ ] Sync LAN tra 2 macchine; Flatpak e .deb installabili; log rotanti
- [ ] i18n §2.8 · coverage ≥80% · protocollo §1.4

---

## 4. Appendici

### 4.1 Checklist di chiusura fase (OGNI VOLTA)

```
□ A. Documentazione aggiornata (ROADMAP, README, changelog, doc API)
□ B. Integrità test + pulizia
    □ pytest completo · coverage ≥80% core/
    □ ruff/pylint puliti · git status pulito · test deterministici
    □ Commit per-task: 1 commit per task, verificato con git log --oneline
□ C. Traduzioni (en.po/it.po sincronizzati, msgfmt ok, niente hardcode, UTF-8)
□ D. Version bump: fonte unica aggiornata · grep vecchia versione = zero hit · CLI --version corretta
□ E. Commit finale stampato con versione nel messaggio · tag creato dall'utente post-merge
```

### 4.2 Riferimenti esterni
- Evolve Core (Apache-2.0): https://github.com/arcnations-united/evolve-core
- Pling API: https://www.pling.com/api/
- GNOME HIG: https://developer.gnome.org/hig/

### 4.3 Glossario
| Termine | Significato |
|---|---|
| Global Theme | Combinazione 5 componenti (gtk3, gtk4, shell, icons, cursors) nominata |
| Preset | Snapshot di una combinazione tema |
| Profilo | Coppia preset light+dark con automazione |
| Fork | Copia modificata di un tema in ~/.themes/ |
| Preview in-app | Tema applicato solo alla finestra GnomeThemeManager |

### 4.4 Note finali per il coding agent
- Non inventare feature: domande prima di implementare (§1.6)
- Priorità alla stabilità
- Testability first: `core/` testabile senza GUI e senza filesystem reale
- Report di fine fase: task completati, saltati (motivo), problemi aperti, domande
- Lingua: chat in italiano, contenuti pubblici in inglese (§2.6)

**Fine del documento.** Prossimo passo: CHORE English-first, poi FASE 1.