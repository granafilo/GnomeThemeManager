# Skill: Error Triage & Resolution

Sei il diagnostician di prima linea per gli errori di GnomeThemeManager.
L'utente fornisce un errore tramite template INTAKE con categoria C1–C6.
NON chiedere informazioni aggiuntive se il template è compilato.
Applica il playbook della categoria e rispetta le Output Rules finali.

## Step 0 — Classificazione
- C1 = pytest locale
- C2 = ruff locale
- C3 = pytest su CI (GitHub workflow)
- C4 = ruff su CI
- C5 = build AppImage su CI
- C6 = funzionale (l'app non si comporta come dovrebbe, nessun errore statico)

---

## C1 — pytest locale
1. Riproduci: riesegui SOLO il test fallito con `pytest <file>::<test> -x -vv`
2. Leggi il traceback DAL BASSO: l'ultima riga è la root cause
3. Classifica:
   - AssertionError → logica sbagliata nel codice o nel test
   - Exception (TypeError, KeyError…) → crash, guarda input reali
   - FileNotFoundError / path → fixture o path hardcoded
4. Fix minimo → riesegui test fallito → riesegui suite completa
5. Se a essere sbagliato è il TEST (non il codice): correggi il test e spiega in 1 riga perché il test era errato

## C2 — ruff locale
1. `ruff check src/ --output-format=concise` e raggruppa per codice
2. Fix standard:
   - F401 / F841 (unused) → rimuovi, verificando effetti collaterali
   - E501 (line length) → spezza senza cambiare logica
   - I001 (import order) → `ruff check --select I --fix`
   - UP / PERF / SIM → applica suggerimento ruff se non cambia behavior
3. Dopo: `ruff check` pulito + `pytest` verde (no regressioni)

## C3 — pytest su CI (locale ok)
Analisi DELTA ambiente, in ordine di probabilità:
1. Display: test GUI girano headless? → servono `xvfb-run -a` nel workflow
2. dbus/gsettings: test che toccano gsettings su runner → servono `dbus-run-session`
3. Versione Python runner vs locale
4. Path/locale/home diversi (mai hardcodare `~` o path assoluti nei test)
Azione: rendi il test environment-independent (mock, tmp_path, skip con reason)
OPPURE allinea il workflow. Preferisci sempre la prima.

## C4 — ruff su CI (locale ok)
1. Confronta versioni: `ruff --version` locale vs versione pin-nata nel workflow
2. Allinea: stessa versione in `requirements-dev.txt` E nel workflow
3. Riproduci con la versione CI e `ruff check --fix`
Root cause tipica: drift di versione, non codice.

## C5 — build AppImage su CI
1. Recupera step fallito + ultime 50 righe di log (`gh run view --log-failed`)
2. Cause comuni, in ordine:
   - FUSE mancante sul runner (appimagetool) → `libfuse2` o flag `--appimage-extract-and-run`
   - dipendenza di sistema mancante nel container di build
   - path relativi / permessi exec persi (AppRun, .desktop)
   - drift tra build locale e CI (versioni tool)
3. Se non riproducibile locale: aggiungi verbose logging allo step e itera su CI

## C6 — funzionale
1. Se INTAKE-F incompleto (steps/atteso/effettivo mancanti) → chiedili, una volta sola
2. Riproduci con gli step esatti; se non riproducibile, chiedi di riprodurre con log attivo
3. Attiva diagnostica: `G_MESSAGES_DEBUG=all` + logger app `--verbose`
4. Isola il layer con la CLI come sonda:
   - CLI funziona e GUI no → layer GUI
   - CLI sbaglia → layer core (scanner / manager / gsettings / installer)
5. Se è regressione: `git bisect` tra ultimo commit noto buono e HEAD
6. Fix mirato + TEST DI REGRESSIONE che riproduce esattamente il bug

---

## Output Rules (sempre, tutte le categorie)
- PRIMA del fix: root cause in 1 riga ("Causa: …")
- Fix minimo possibile, niente refactor opportunistici durante il fix
- C1/C3/C6: obbligatorio test di regressione
- MAI silenziare: niente `noqa`, niente `skip`, niente try/except vuoti senza reason esplicita approvata dall'utente
- Chiudi con: comando esatto per verificare che l'errore è risolto