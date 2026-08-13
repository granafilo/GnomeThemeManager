# Gestione della documentazione

Questo file definisce come e dove aggiornare la documentazione nel progetto.

## File principali

- `README.md`
  - Descrizione del progetto.
  - Istruzioni di installazione e uso base.
  - Aggiornare ogni volta che cambiano:
    - requisiti
    - comandi di installazione/avvio
    - funzionalità principali visibili all’utente

- `CHANGELOG.md`
  - Elenco delle modifiche per versione.
  - Aggiornare per ogni feature/fix rilevante.
  - Formato consigliato:
    ```md
    ## [1.0.0] - 2026-08-13

    ### Added
    - Login utente con email e password.

    ### Fixed
    - Layout header su mobile.
    ```

- `docs/` (opzionale, se presente o da creare)
  - Documentazione più dettagliata (architettura, API, guide, ecc.).
  - Creare file come:
    - `docs/architecture.md`
    - `docs/features/nome-feature.md`

## Regole per l’agente Git

Quando si lavora su una feature/fix:

1. Valutare se aggiornare:
   - `README.md` (se cambia qualcosa di visibile o di installazione).
   - `CHANGELOG.md` (se la modifica è rilevante per l’utente).
   - `docs/` (se serve documentazione più approfondita).

2. Proporre:
   - il testo da aggiungere/modificare,
   - il messaggio di commit per la documentazione (es. `docs: aggiorna README per login`).

3. Includere i file di documentazione nei commit, se necessario.