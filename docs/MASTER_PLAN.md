# 📋 Master Implementation Plan — GnomeThemeManager

**Versione documento:** 2.0
**Autore:** Planning Agent
**Destinatario:** Coding Agent
**Repo:** https://github.com/granafilo/GnomeThemeManager
**Stato:** FASE 0 ✅ COMPLETATA (agosto 2026) → prossimo: CHORE English-first, poi FASE 1
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
1. Determinare la nuova versione dal mapping §2.7 (fase → minor; chore → patch).
2. Aggiornare l'unica fonte: `__version__` in `src/gnome_theme_manager/__init__.py`.
3. Propagare dove non derivabile: nuova entry CHANGELOG con versione + data;
   entry release in metainfo/.desktop se presenti.
4. Verifica consistenza:
   - `grep -rIn "<vecchia versione>" . --exclude-dir=.git` → zero hit
   - `python -m gnome_theme_manager --version` → stampa la nuova
5. Il bump rientra nel commit finale di chiusura.

**Step E — Comando di commit finale**: stampare (NON eseguire):

```bash
git add -A && git commit -m "chore: phase {N} completion — v{X.Y.Z} — docs, tests integrity, i18n verification [skip ci]"
```

> Nota: i file di codice/test sono già stati committati per-task durante la fase.
> Questo commit contiene esclusivamente gli esiti degli step A–D.
> Il tag `v{X.Y.Z}` viene creato dall'utente dopo il merge.

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

- La versione si aggiorna SOLO durante la chiusura fase (step D), mai durante i task
- Tag git `v{X.Y.Z}` creato dall'utente dopo il merge, allineato alla versione

### 2.8 i18n follows the feature
Ogni task che introduce stringhe user-visible (GUI, CLI, dialoghi) DEVE,
nello STESSO commit del task:
1. Wrappare le stringhe in gettext (`_()`)
2. Aggiungere i msgid a `po/en.po` (lingua sorgente)
3. Aggiungere le traduzioni IT a `po/it.po` (nessun untranslated/fuzzy)

Lo step C della chiusura fase è SOLO verifica finale di consistenza,
non il momento in cui si traduce.
I test che asseriscono su stringhe usano i msgid, mai le traduzioni.

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

### 🔷 FASE 2 — Theme Editor (v1.2)

**Branch:** `feature/phase-2-theme-editor`

#### Task 2.1 — Theme Mixer
- `core/theme_editor.py`: `ThemeComposition(gtk3, gtk4, shell, icon, cursor, custom_name)` → Global Theme utente con `user_composed: true`

Il Theme Mixer salva le composizioni come Global Theme con `origin: "user"`:
appaiono in cima alla lista della view unica (regola Task 1.1).

#### Task 2.2 — CSS Color Extractor
- `core/css_extractor.py`: parse `gtk-4.0/gtk.css` / `gtk-3.0/gtk-main.css`; estrae `@define-color` (theme_fg_color, theme_bg_color, theme_selected_bg_color, theme_selected_fg_color, wm_* opzionali)

#### Task 2.3 — Theme Editor UI
- `gui_gtk/views/editor_view.py` + `color_picker.py`: 5 dropdown componenti, 4 ColorDialogButton (fg/bg/accent/accent_fg), Anteprima (Task 1.5), "Salva come Global Theme", "Reset colori"

#### Task 2.4 — Override colori persistente (fork tema)
- Copia tema in `~/.themes/{custom_name}-gtk4/`; modifica solo `@define-color`; metadata in `theme_forks.json`; etichetta `(edited)`; fork reversibile

#### Task 2.5 — Bozze persistenti
- `editor_draft.json` salvato ad ogni modifica; prompt "Riprendi bozza?" al riavvio

#### Task 2.6 — Stretch goal: Adaptive Colour dal wallpaper
- Palette dominante (k-means k=5) dal wallpaper corrente → proposte nei picker. Se troppo complesso: saltare e documentare come TODO

**Acceptance Fase 2:** mix 5 temi salvabile · colori modificabili con fork funzionante e reversibile · bozze persistenti · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 3 — Store Online (v1.3)

**Branch:** `feature/phase-3-online-store`

#### Task 3.1 — API client pling.com
- `core/store_client.py`: `search(query, category)`, `get_details(id)`, `download(id, dest_dir)`; retry/backoff, timeout 30s; dipendenza `requests`

#### Task 3.2 — Store UI
- `gui_gtk/views/store_view.py`: ricerca + filtri, griglia card, dettaglio con screenshot, "Installa" (riusa Task 1.7), progress bar

#### Task 3.3 — Extensions browser
- Lista `gnome-extensions list`; toggle enable/disable; "Browse online" → link esterno a extensions.gnome.org

#### Task 3.4 — Cache locale
- `~/.cache/gnome-theme-manager/store_cache.json`, TTL 24h

**Acceptance Fase 3:** ricerca <3s · download+install da pling ok · toggle estensioni ok · TTL rispettato · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 4 — Profili & Automazioni (v1.4)

**Branch:** `feature/phase-4-profiles`

#### Task 4.1 — Profili con variante light/dark
- `core/profiles.py`: `{name, light_preset, dark_preset, auto_switch, autostart}` in `profiles.json`

#### Task 4.2 — Integrazione color-scheme (GNOME 42+)
- Read/write `org.gnome.desktop.interface color-scheme`; segnale `changed::color-scheme`; apply automatico se `auto_switch: true`

#### Task 4.3 — UI profili
- Lista profili, form creazione (nome + preset light/dark + toggle), "Imposta come attivo"

#### Task 4.4 — Autostart via systemd user
- `~/.config/systemd/user/gnome-theme-manager.service`; enable/disable automatico coerente con `autostart`

#### Task 4.5 — Export/import profili
- Singolo file JSON bundle (profilo + preset light + dark)

**Acceptance Fase 4:** switch automatico su cambio color-scheme · apply al reboot · round-trip export/import · coverage ≥80% · protocollo §1.4

---

### 🔷 FASE 5 — Sync & Distribuzione (v1.5+)

**Branch:** `feature/phase-5-sync-packaging`

#### Task 5.1 — Base sync (estensione export bundle 4.5)
#### Task 5.2 — Sync LAN (mDNS/Avahi `_gtm._tcp` + HTTP stdlib; tab Sync con Send/Receive)
#### Task 5.3 — Packaging Flatpak (`io.github.granafilo.GnomeThemeManager.yml`, test Ubuntu 22.04+/Fedora 38+)
#### Task 5.4 — Packaging .deb (dir `debian/`, install su Ubuntu 24.04)
#### Task 5.5 — i18n lingue aggiuntive (infrastruttura gettext già creata dal CHORE English-first; qui: workflow traduzioni + eventuali lingue nuove)
#### Task 5.6 — Logging strutturato (JSON in `~/.local/state/gnome-theme-manager/logs/`, rotazione giornaliera, `--verbose`)
#### Task 5.7 — First-run tour (stretch: 5 slide, flag `first_run_completed`)

**Acceptance Fase 5:** sync LAN tra 2 macchine · Flatpak builda e parte · .deb installabile · traduzioni complete · log rotanti · coverage ≥80% · protocollo §1.4

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