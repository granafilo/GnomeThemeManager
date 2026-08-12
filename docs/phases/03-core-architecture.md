# Fase 3: Architettura Core Library e Disaccoppiamento

## Obiettivi della Fase

Rifinire e consolidare il layer `gnome_theme_manager.core` affinché operi come una libreria pura e riutilizzabile da qualsiasi interfaccia (CLI, Tkinter, GTK4, script esterni):
1. **Separazione totale I/O e UI**: Nessuna chiamata a `print()`, `input()` o dipendenza da terminale all'interno del `core`.
2. **Sistema di Eventi / Callback / Logging**: Utilizzo del modulo standard `logging` per tracciare le operazioni.
3. **Type Hinting Completo e Validazione Dati**: Dataclass con type hint completi (`typing`, `dataclasses`).
4. **Testabilità Totale**: Supporto per test headless con mock completi del filesystem e di GSettings.

---

## Architettura e API Pubblica del Core

```text
gnome_theme_manager.core
├── ThemeManager        # Classe facade principale per l'accesso coordinato
├── models              # Theme, ThemeSet, ThemeType
├── scanner             # scan_themes(), get_theme_by_name()
├── gsettings           # GSettingsClient (read, write, schema check)
├── installer           # install_from_archive(), remove_theme()
└── errors              # GnomeThemeManagerError e derivate
```

### Esempio di Utilizzo Programmatico (Facade Pattern)

```python
from gnome_theme_manager.core import ThemeManager, ThemeType

# Inizializzazione facade
manager = ThemeManager()

# Recupero stato attuale
current_set = manager.get_current_themes()
print(f"Tema GTK attivo: {current_set.gtk_theme}")

# Elenco temi disponibili
gtk_themes = manager.list_themes(theme_type=ThemeType.GTK)
for theme in gtk_themes:
    print(f"- {theme.name} ({'User' if theme.is_user_level else 'System'})")

# Applicazione nuovo tema
manager.apply_theme(ThemeType.GTK, "Nordic")
```

---

## Checklist di Implementazione

- [ ] **Facade `ThemeManager`**:
  - Unificazione dei metodi di scansione, applicazione, installazione e rimozione in un'unica interfaccia pulita.
- [ ] **Refactoring Modelli**:
  - `ThemeSet`: Metodi di utilità (es. `as_dict()`, `is_complete()`).
  - Metodi `to_dict()`, `from_dict()` per serializzazione/backup (preparazione per preset).
- [ ] **Gestione Errori**:
  - Gerarchia formale:
    - `GnomeThemeManagerError`
      - `GSettingsUnavailableError`
      - `ThemeNotFoundError`
      - `ThemeInstallationError`
      - `InvalidThemeArchiveError`
- [ ] **Suite di Test**:
  - Test di regressione per tutte le classi e funzioni core.
  - Copertura test minima garantita (>80%).
