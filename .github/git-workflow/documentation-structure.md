# Struttura della documentazione del progetto

Questo file definisce come organizzare e mantenere aggiornata la documentazione del repository.

## File principali

### `README.md` (root)

Descrive il progetto a grandi linee ed è il punto di ingresso principale.

Deve contenere almeno:

- Titolo e breve descrizione.
- Stack tecnologico principale.
- Istruzioni di installazione e avvio rapido.
- Link a documentazione più dettagliata (se presente).
- Stato del progetto (Fase 1 / Fase 2, stabile, WIP, ecc.).

Il `README.md` va aggiornato quando:

- Cambiano requisiti o dipendenze principali.
- Cambiano comandi di installazione/avvio.
- Vengono aggiunte/rimosse funzionalità principali.
- Cambia lo stato del progetto (es. da “Fase 1” a “Fase 2 – stabile”).

### `CHANGELOG.md` (root)

Registra le modifiche rilevanti per versione.

Formato consigliato: [Keep a Changelog](https://keepachangelog.com/).

Struttura:

```md
# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

## [1.0.0] - 2026-08-13

### Added
- Login utente con email e password.

### Fixed
- Layout header su mobile.

### Changed
- Aggiornate dipendenze di sicurezza.

## [0.1.0] - 2026-07-01

### Added
- Struttura iniziale del progetto.
```

Il `CHANGELOG.md` va aggiornato per ogni feature/fix rilevante, idealmente:

- Prima del merge di una PR (Fase 2).
- Dopo aver completato un insieme di commit significativi (Fase 1).

### `docs/` (opzionale)

Cartella per documentazione più dettagliata:

- `docs/architecture.md` – panoramica architetturale.
- `docs/features/` – una pagina per feature importante.
- `docs/guides/` – guide operative (es. deploy, configurazione, ecc.).

I file in `docs/` vanno creati/aggiornati quando:

- Una feature è abbastanza complessa da richiedere spiegazioni dedicate.
- Serve documentazione per utenti o sviluppatori oltre al README.

## Regole per l’aggiornamento della documentazione

### Dopo ogni commit/merge significativo

L’agente Git (Copilot) deve:

1. Valutare se la modifica è rilevante per:
   - `README.md`
   - `CHANGELOG.md`
   - `docs/`

2. Se sì:
   - Proporre il testo da aggiungere/modificare.
   - Proporre un messaggio di commit per la documentazione, es.:
     - `docs: aggiorna README per feature login`
     - `docs: aggiorna CHANGELOG per versione 1.0.0`

3. Includere i file di documentazione nei commit, se necessario.

### Chiarezza e coerenza

- Documentazione in italiano (coerente con il resto del progetto).
- Messaggi di commit per la documentazione in stile Conventional Commits (`docs: ...`).
- Evitare duplicazioni: se una cosa è già spiegata in `docs/`, nel README mettere solo un link.

## Automazione (opzionale)

In futuro si può aggiungere:

- Una GitHub Action che:
  - Suggerisce aggiornamenti al `CHANGELOG.md` in base ai commit/PR.
  - Apre una PR di aggiornamento documentazione quando serve.

Per ora, l’aggiornamento è gestito manualmente con l’aiuto dell’agente Git.