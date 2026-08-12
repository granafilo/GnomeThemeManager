---
trigger: always_on
---

Usa Python 3 moderno (3.10+), ma evita feature troppo avanzate se non necessarie.

Preferisci:

    Funzioni pure e dataclass per modelli semplici.

    Package separati per core e UI (es. theme_manager_core, theme_manager_cli, theme_manager_gtk).

Mantieni una separazione netta:

    Core: logica di business, filesystem, GSettings.

    UI: CLI, Tkinter, GTK.

Non introdurre pattern complessi (es. microservizi, dependency injection pesanti, ORM, ecc.) se non strettamente necessari.

Quando proponi un’architettura, spiega brevemente perché è utile e come si evolve nel tempo.