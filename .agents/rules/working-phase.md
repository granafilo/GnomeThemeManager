---
trigger: always_on
---

Progetta il codice pensando alle fasi del progetto:

    MVP CLI.

    Installazione da archivi.

    Core library pulita.

    GUI Tkinter.

    GUI GTK/PyGObject.

    Hardening e sandbox (Flatpak/Snap).

Quando proponi modifiche:

    Specifica a quale fase appartengono.

    Evita di introdurre funzionalità “da fase avanzata” nel codice della fase corrente, a meno che non siano facilmente ignorabili/disattivabili.

Se vedi un’opportunità di refactoring che migliora le fasi future, segnalala esplicitamente e spiega il trade-off.