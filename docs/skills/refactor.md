# Skill: Refactoring sicuro

## Prima di qualsiasi refactor
1. Verifica che TUTTI i test passino → se no, stop
2. Fai un commit WIP pulito come rollback point
3. Identifica la metrica di qualità che vuoi migliorare:
   - **Duplication** → cerca codice simile in 2+ file
   - **Complexity** → funzioni > 50 righe
   - **Coupling** → moduli che si importano a vicenda

## Regole
- Massimo UN obiettivo di refactor per sessione
- Dopo ogni change piccolo, esegui i test
- Se i test falliscono 2 volte di fila, reverta e ripensaci

## Output richiesto
Prima e dopo il refactor, mostra le metriche:
- LOC totali del modulo
- Numero di funzioni
- Coverage prima/dopo