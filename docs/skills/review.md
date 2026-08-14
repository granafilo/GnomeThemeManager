# Skill: Review del codice AI

Quando devi farmi rivedere il codice di un task, segui QUESTA checklist
in ordine e presentami il risultato come report strutturato.

## Checklist review

### 1. Scope check
- Il diff tocca SOLO i file previsti dal task?
- Se tocca file fuori scope, elencali con motivazione.

### 2. Test coverage
- Quanti test nuovi sono stati aggiunti?
- Quali behavior verificano? (elenco puntato)
- Coverage di `core/` prima/dopo il task (se disponibile)

### 3. Contract compliance
- Le nuove API in `core/` hanno type hints completi?
- Sono consumate da GUI e CLI nello stesso modo? (regola §0.2 del MASTER_PLAN)

### 4. Edge case
Elenca i 3 edge case più probabili che il codice NON gestisce:
1. ...
2. ...
3. ...
Per ognuno, indica se è accettabile o va fixato.

### 5. Rischi di regressione
Cosa potrebbe rompersi in task successivi o in altre feature?

## Output richiesto
Report in 5 sezioni, massimo 20 righe totali. NO codice inline, solo diff.