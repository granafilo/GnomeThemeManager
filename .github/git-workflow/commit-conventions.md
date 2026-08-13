# Convenzioni di commit (Conventional Commits)

Questo progetto adotta la specifica [Conventional Commits](https://www.conventionalcommits.org/).

## Struttura del messaggio

```text
<tipo>[scope opzionale]: <descrizione>

[corpo opzionale]

[footer opzionali]
```

### Tipo

- `feat`: nuova funzionalità
- `fix`: correzione di un bug
- `chore`: manutenzione, tooling, dipendenze
- `docs`: sola documentazione
- `refactor`: refactor senza cambiare comportamento
- `test`: aggiunta/modifica di test
- `style`: cambiamenti di stile (formattazione, ecc.)
- `perf`: miglioramento delle performance
- `ci`: modifiche a CI/CD
- `build`: modifiche al sistema di build
- `revert`: revert di un commit precedente

### Descrizione

- Breve, chiara, in forma imperativa (“aggiungi”, “correggi”, “rimuovi”).
- Prima lettera minuscola.
- Nessun punto finale.

### Corpo (opzionale)

- Spiegazione più dettagliata, se necessaria.
- Motivazione del cambiamento.
- Eventuali note su comportamento, limiti, ecc.

### Footer (opzionali)

- Riferimenti a issue/PR:
  - `Closes #123`
  - `Refs #456`
- Breaking changes:
  - `BREAKING CHANGE: descrizione del cambiamento incompatibile`

## Esempi

```text
feat: aggiungi login utente
```

```text
fix(header): correggi layout su mobile

Il menu non era visibile su schermi < 600px.
```

```text
docs: aggiorna README con istruzioni di installazione

Closes #10
```

```text
chore(deps): aggiorna dipendenze di sicurezza

BREAKING CHANGE: rimossa dipendenza deprecata X
```

## Regole pratiche

- Un commit = un cambiamento logico.
- Messaggi in italiano (coerente con il resto del progetto).
- Non usare prefissi arbitrari (es. `[FEATURE]`, `[FIX]`), usa solo i tipi sopra.