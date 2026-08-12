---
trigger: always_on
---

Usa eccezioni Python standard (ValueError, FileNotFoundError, ecc.) e, se utile, crea eccezioni custom nel modulo errors.py del core:

    ThemeNotFoundError, ThemeInstallationError, GSettingsError.

Non nascondere gli errori con try/except generici; cattura solo ciò che sai gestire e lascia propagare il resto.

Quando scrivi funzioni che possono fallire (es. installazione da archivio, scrittura GSettings):

    Documenta chiaramente quali eccezioni possono essere sollevate.

    Suggerisci come gestirle a livello UI (es. mostrare messaggio all’utente).