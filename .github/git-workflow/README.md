# Git Workflow del progetto

Questo documento descrive il workflow Git adottato nel repository.

## Fase attuale (Fase 1)

- Tutto il lavoro viene svolto direttamente sul ramo `main`.
- I commit seguono le convenzioni definite in `commit-conventions.md`.
- La documentazione viene aggiornata in modo incrementale (vedi `documentation.md`).

## Fase futura (Fase 2 – prodotto stabile)

A partire dalla prima versione stabile del prodotto:

- `main` diventa il ramo stabile, sempre “releasabile”.
- Ogni nuova funzionalità o modifica significativa viene sviluppata su un branch dedicato.
- Le integrazioni su `main` avvengono esclusivamente tramite Pull Request (PR).

## Regole generali

- Ramo principale: `main`.
- Branch temporanei per feature/fix: vedi `branch-naming.md`.
- Commit: vedi `commit-conventions.md`.
- Documentazione: vedi `documentation.md`.
- Merge delle PR: vedi `pr-merge.md`.