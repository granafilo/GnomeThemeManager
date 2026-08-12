---
trigger: always_on
---

# Git/GitHub Workflow – Linux Theme Manager

Questo documento definisce il flusso di lavoro Git/GitHub per lo sviluppo del progetto **Linux Theme Manager**.

---

## 1. Principi generali

- Il repository principale è ospitato su GitHub.
- Il ramo principale si chiama `main` ed è sempre in uno stato **stabile e potenzialmente rilasciabile**.
- Ogni nuova funzionalità, bugfix o modifica significativa viene sviluppata in un **branch dedicato** (feature branch).
- Non si fanno commit direttamente su `main` (tranne casi eccezionali e consapevoli).
- Ogni integrazione in `main` avviene tramite **pull request (PR)**, con una breve revisione del codice (anche se lavori da solo).

---

## 2. Struttura dei branch

### 2.1. Branch principali

- `main`
  - Contiene il codice stabile e rilasciabile.
  - Ogni commit su `main` dovrebbe essere testato e funzionante.

*(Opzionale, per il futuro)*

- `develop`
  - Può essere introdotto in futuro come ramo di integrazione continua.
  - Per ora, si lavora direttamente con branch che puntano a `main`.

### 2.2. Branch temporanei

I branch temporanei sono usati per sviluppare funzionalità, fix o documentazione:

- `feature/<nome-breve>` – per nuove funzionalità.
  - Esempi:
    - `feature/cli-mvp`
    - `feature/theme-installer`
    - `feature/gsettings-client`
    - `feature/gtk-gui`
- `fix/<nome-breve>` – per correzioni di bug.
  - Esempi:
    - `fix/gsettings-schema-not-found`
    - `fix/extract-zip-path-error`
- `docs/<nome-breve>` – per modifiche sostanziali alla documentazione.
  - Esempi:
    - `docs/architecture-overview`
    - `docs/ai-coding-rules`

**Regole di naming:**

- Usa solo minuscole, numeri e trattini (`-`).
- Nomi brevi ma descrittivi (massimo 3–4 parole).
- Evita spazi, underscore e caratteri speciali.

---

## 3. Ciclo di vita di una feature

### 3.1. Creazione del branch

Prima di iniziare una nuova funzionalità o fix:

```bash
# 1. Vai su main e aggiornalo
git checkout main
git pull origin main

# 2. Crea un nuovo branch dalla versione più recente di main
git checkout -b feature/<nome-breve>
```

Esempio:

```bash
git checkout -b feature/cli-mvp
```

Ogni task significativo (es. “MVP CLI”, “installer da archivio”, “GUI GTK”) deve avere il suo branch dedicato.

---

### 3.2. Sviluppo sul branch

Durante lo sviluppo sul branch:

- Fai commit piccoli e coerenti, ognuno con uno scopo chiaro.
- Pusha regolarmente il branch remoto per backup e per eventuali review:

```bash
git push -u origin feature/<nome-breve>   # prima volta
# poi basta
git push
```

Regola pratica: meglio commit e push frequenti che un singolo mega-commit a fine lavoro.

---

### 3.3. Allineamento con main prima della PR

Quando la feature è pronta (o in uno stato decente per review):

```bash
# 1. Aggiorna main locale
git fetch origin
git checkout main
git pull origin main

# 2. Torna sul branch di feature e ribasalo su main aggiornato
git checkout feature/<nome-breve>
git rebase origin/main
```

Se compaiono conflitti:

```bash
# risolvi i conflitti nei file indicati
git add <file-risolti>
git rebase --continue
```

Poi pusha il branch aggiornato:

```bash
# se non hai riscritto la storia
git push

# se hai effettuato rebase
git push --force-with-lease origin feature/<nome-breve>
```

---

### 3.4. Creazione della pull request (PR)

Su GitHub:

1. Vai alla pagina del repository.
2. Clicca su **Pull requests** → **New pull request**.
3. Imposta:
   - **Base**: `main`
   - **Compare**: `feature/<nome-breve>`
4. Compila:
   - **Titolo**: chiaro e sintetico (es. `Implement MVP CLI for theme listing and applying`).
   - **Descrizione**:
     - Cosa fa la PR (feature/fix).
     - Come testarla (comandi, passi).
     - Eventuali note (limitazioni, TODO, decisioni di design).

Ogni PR deve riguardare **una singola feature/fix ben definita**, non un miscuglio di modifiche.

---

### 3.5. Code review

Anche in solo-dev, tratta la PR come se ci fosse un reviewer:

- Usa la vista “Files changed” per rileggere il codice a mente fredda.
- Controlla:
  - Chiarezza dei commenti.
  - Coerenza con la struttura del progetto.
  - Assenza di funzioni troppo lunghe o codice duplicato.
- Se in futuro ci saranno altri collaboratori, useranno la PR per commenti e approvazioni.

È consigliabile non fare “merge immediato” appena creata la PR; concediti il tempo per una breve auto-review.

---

### 3.6. Merge in `main` e pulizia branch

Dopo la review:

1. Esegui il merge della PR su GitHub.
   - Preferisci **“Squash and merge”**:
     - Tutti i commit della feature vengono compressi in un unico commit pulito su `main`.

2. Aggiorna `main` in locale:

```bash
git checkout main
git pull origin main
```

3. Elimina il branch locale:

```bash
git branch -d feature/<nome-breve>
```

4. (Consigliato) Elimina anche il branch remoto:

```bash
git push origin --delete feature/<nome-breve>
```

Obiettivo: mantenere `main` pulito, con un commit significativo per ogni feature/fix.

---

## 4. Convenzioni per i messaggi di commit

Si usa uno stile ispirato a **Conventional Commits**, in forma semplificata.

### 4.1. Formato base

```text
<tipo>(<scope>): <descrizione breve>

<corpo opzionale>

<footer opzionale>
```

Tipi principali:

- `feat` – nuova funzionalità.
- `fix` – correzione di bug.
- `docs` – documentazione.
- `refactor` – refactoring senza cambiare il comportamento esterno.
- `style` – formattazione, spazi, naming (senza logica).
- `test` – aggiunta o modifica dei test.
- `chore` – attività di supporto (deps, CI, ecc.).

Esempi:

- `feat(cli): add list-themes command`
- `feat(core): implement GSettings client for gtk-theme`
- `fix(installer): handle nested folder in zip archives`
- `docs(readme): add setup instructions for PyGObject`
- `refactor(scanner): extract theme validation logic`
- `style(core): format imports and remove unused variables`
- `test(cli): add basic tests for theme listing`
- `chore(deps): update requirements.txt`

### 4.2. Regole pratiche

- Prima riga:
  - Max ~50 caratteri.
  - Imperativo, presente, senza punto finale.
- Corpo (se presente):
  - Spiega **cosa** e **perché**, non solo **come**.
  - Righe spezzate a ~72 caratteri.
- Footer (opzionale):
  - Usa `BREAKING CHANGE:` se il commit introduce cambiamenti non retrocompatibili.

---

## 5. Sincronizzazione e gestione conflitti

Quando un branch resta aperto per più giorni:

```bash
git fetch origin
git checkout main
git pull origin main
git checkout feature/<nome-breve>
git rebase origin/main
```

In caso di conflitti:

```bash
# risolvi manualmente i conflitti nei file
git add <file-risolti>
git rebase --continue
```

Regola: mantieni il branch di feature il più possibile allineato a `main` per ridurre conflitti grandi alla fine.

---

## 6. Tag e release (opzionale, per il futuro)

Quando il progetto sarà più maturo, potrai:

```bash
git tag -a v0.1.0 -m "Release v0.1.0 - MVP CLI"
git push origin v0.1.0
```

Formato consigliato:

- `v<major>.<minor>.<patch>` (es. `v0.1.0`, `v0.2.0`, `v1.0.0`).

---

## 7. Riepilogo operativo rapido

Per una nuova feature:

```bash
# 1. Allinea main
git checkout main
git pull origin main

# 2. Crea branch
git checkout -b feature/<nome-breve>

# 3. Lavora, commit e push
git add .
git commit -m "feat(<scope>): <descrizione>"
git push -u origin feature/<nome-breve>

# (ripeti add/commit/push durante lo sviluppo)

# 4. Allinea con main prima della PR
git fetch origin
git checkout main
git pull origin main
git checkout feature/<nome-breve>
git rebase origin/main
git push --force-with-lease origin feature/<nome-breve>

# 5. Crea PR su GitHub, fai review, poi merge (squash) in main

# 6. Pulisci branch
git checkout main
git pull origin main
git branch -d feature/<nome-breve>
git push origin --delete feature/<nome-breve>
```