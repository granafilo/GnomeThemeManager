# Gestione delle Pull Request e strategia di merge

Questo file definisce come gestire le PR e il merge su `main`.

## Quando aprire una PR

- **Fase 1**: non necessario, tutto su `main`.
- **Fase 2** (prodotto stabile):
  - Ogni feature/fix rilevante va su un branch dedicato.
  - Prima del merge su `main`, si apre una PR.

## Struttura minima di una PR

- Titolo: in stile Conventional Commit, es.:
  - `feat: aggiungi login utente`
  - `fix(header): correggi layout su mobile`
- Descrizione:
  - Cosa è stato fatto.
  - Perché è stato fatto (se non ovvio).
  - Come testare la modifica (se rilevante).
- Riferimenti:
  - Issue collegate (`Closes #123`, `Refs #45`).

## Strategia di merge

Strategia adottata: **Squash and merge**.

Motivazione:

- Ogni PR rappresenta una feature/fix singola.
- Su `main` rimane un solo commit per PR.
- La storia di `main` resta pulita e lineare.

Regole:

- Usare sempre “Squash and merge” da GitHub.
- Il messaggio del commit risultante deve seguire `commit-conventions.md`.
- Se la PR ha più commit, questi verranno uniti in uno solo.

## Ruolo dell’agente Git

L’agente deve:

- Suggerire il titolo della PR in stile Conventional Commit.
- Proporre una descrizione chiara e concisa.
- Ricordare di usare “Squash and merge”.
- Suggerire eventuali voci per `CHANGELOG.md` in base alla PR.