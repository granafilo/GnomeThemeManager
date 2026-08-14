# Skill: Security review pre-commit

Quando stai per chiudere una fase, verifica QUESTI rischi tipici
di un'app Python che gestisce temi da fonti esterne.

## Checklist
- [ ] Nessun eval()/exec() su dati utente
- [ ] Path traversal: tutti i path da archivi sono validati (no ../)
- [ ] Shell injection: nessun os.system() con input utente
- [ ] Deserialization sicura: solo JSON, mai pickle
- [ ] File temporanei ripuliti (tempfile + cleanup)
- [ ] Nessuna credenziale hardcoded o loggata
- [ ] gsettings accessi: nessun schema inventato

Se trovi violazioni: elencale PRIMA di proporre fix.