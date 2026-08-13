# Convenzioni nomi branch

Questo file definisce le convenzioni per i nomi dei branch.

## Formato generale

```text
<tipo>/<descrizione-breve>
```

- Tutto lowercase.
- Parole separate da `-` (kebab-case).
- Niente spazi o caratteri speciali.

## Tipi supportati

- `feat` – nuova funzionalità
- `fix` – correzione di un bug
- `chore` – task di manutenzione (dipendenze, config, script, ecc.)
- `docs` – modifiche solo alla documentazione
- `refactor` – refactor senza cambiare comportamento esterno
- `release` – preparazione di una release
- `hotfix` – correzione urgente su produzione

## Esempi

- `feat/login-utente`
- `fix/header-mobile`
- `chore/aggiorna-dipendenze`
- `docs/aggiorna-readme`
- `refactor/semplifica-auth`
- `release/1.0.0`
- `hotfix/correggi-crash-login`

## Quando usare i branch

- **Fase 1**: tutto su `main`, nessun branch feature.
- **Fase 2** (prodotto stabile):
  - Ogni feature/fix rilevante va su un branch dedicato.
  - Il merge su `main` avviene solo tramite PR.