# Istruzioni per GitHub Copilot in questo progetto

Questo file definisce le istruzioni globali per GitHub Copilot (VS Code) nel repository.

## Contesto del progetto

- Stack tecnologico: (da completare in base al repo reale)
- Struttura: (frontend/backend/monorepo, ecc.)
- Convenzioni di stile: (da allineare a linter/formatter già presenti)

## Git / GitHub workflow

Quando ti chiedo di gestire git (branch, commit, PR, release, documentazione correlata), devi seguire le regole definite in:

- `.github/git-workflow/README.md`
- `.github/git-workflow/branch-naming.md`
- `.github/git-workflow/commit-conventions.md`
- `.github/git-workflow/documentation.md`
- `.github/git-workflow/pr-merge.md`

In particolare:

1. **Branch**
   - In Fase 1: tutto su `main`, nessun branch feature.
   - In Fase 2: usa i nomi branch secondo `branch-naming.md`.

2. **Commit**
   - Usa sempre Conventional Commits come in `commit-conventions.md`.
   - Proponi messaggi di commit chiari, in italiano, coerenti con lo storico.

3. **Documentazione**
   - Per ogni feature/fix rilevante, valuta se aggiornare:
     - `README.md`
     - `CHANGELOG.md`
     - `docs/` (se presente)
   - Proponi il testo da inserire e il messaggio di commit per la documentazione.

4. **Pull Request e merge**
   - In Fase 2, per ogni feature/fix rilevante:
     - Proponi titolo e descrizione della PR.
     - Ricorda di usare “Squash and merge”.
   - Allinea il messaggio di merge alle convenzioni di commit.

5. **Comportamento generale**
   - Non modificare codice applicativo se non esplicitamente richiesto.
   - Concentrati su:
     - comandi git,
     - messaggi di commit,
     - documentazione,
     - PR e merge.
   - Chiedi conferma prima di operazioni potenzialmente distruttive (es. rebase, force push, eliminazione branch).

## Altre istruzioni

- Rispetta le convenzioni di stile e architettura già presenti nel repo.
- Se qualcosa non è chiaro o ambiguo, chiedimi prima di procedere.