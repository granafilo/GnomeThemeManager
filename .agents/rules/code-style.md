---
trigger: always_on
---

Usa nomi chiari e descrittivi in inglese per funzioni, classi e variabili:

    get_current_themes(), apply_gtk_theme(), Theme, ThemeSet, scan_themes_directory().

Organizza il codice in file piccoli e coerenti:

    Un file per responsabilità principale (es. paths.py, scanner.py, gsettings_client.py, installer.py).

Evita file “monolitici” con centinaia di righe; se un file cresce troppo, proponi una suddivisione logica.

Usa docstring (in italiano o inglese semplice) per funzioni e classi pubbliche, con:

    Breve descrizione.

    Parametri.

    Valore di ritorno.

    Eccezioni sollevate (se rilevanti).