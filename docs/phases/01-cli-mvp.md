# Fase 1: MVP da Terminale (Theme Switcher Minimale)

## Obiettivi della Fase

La prima fase si concentra sulla creazione di un prototipo funzionante a riga di comando (CLI) in grado di:
1. **Scansionare il filesystem** per individuare i temi GTK, i set di icone e i temi dei cursori installati nelle directory utente e di sistema.
2. **Interagire con GNOME GSettings** per leggere i temi attualmente attivi e applicarne di nuovi.
3. Fornire una prima interfaccia utente testuale chiara, usabile ed estensibile.

---

## Architettura e Moduli Coinvolti

```text
src/gnome_theme_manager/
├── core/
│   ├── constants.py        # Percorsi XDG e definizioni chiavi GSettings
│   ├── models.py           # ThemeType, Theme, ThemeSet
│   ├── scanner.py          # Logica di discovery nel filesystem
│   ├── gsettings.py        # Wrapper Gio.Settings
│   └── errors.py           # Eccezioni specifiche
└── cli/
    ├── __main__.py         # python -m gnome_theme_manager.cli
    ├── args.py             # Parser argparse
    └── main.py             # Router comandi e output a terminale
```

---

## Dettagli Tecnici e Specifiche

### 1. Percorsi di Scansione XDG
- **Temi GTK / Applicazioni**:
  - Utente: `~/.local/share/themes`, `~/.themes` (legacy)
  - Sistema: `/usr/share/themes`
- **Icone e Cursori**:
  - Utente: `~/.local/share/icons`, `~/.icons` (legacy)
  - Sistema: `/usr/share/icons`

### 2. Schemi e Chiavi GSettings
Schema: `org.gnome.desktop.interface`
- `gtk-theme` (string): Nome del tema per controlli GTK3/GTK4.
- `icon-theme` (string): Nome del tema delle icone.
- `cursor-theme` (string): Nome del tema per i cursori del mouse.
- `color-scheme` (string, opzionale per GNOME 42+): `'default'` o `'prefer-dark'`.

### 3. Comandi CLI Previsti

```bash
# Mostra lo stato attuale dei temi applicati
gnome-theme-manager current

# Elenca tutti i temi disponibili nel sistema e nella home
gnome-theme-manager list [--type gtk|icon|cursor|all]

# Applica uno o più temi
gnome-theme-manager apply --gtk "Adwaita-dark" --icon "Papirus" --cursor "Yaru"
```

---

## Checklist di Implementazione

- [x] **Costanti & Modelli**:
  - Implementare dataclass `Theme` con attributi: `name`, `theme_type`, `path`, `is_user_level`.
  - Definire enum `ThemeType` (`GTK`, `ICON`, `CURSOR`).
- [x] **GSettings Client**:
  - Wrapper su `gi.repository.Gio.Settings("org.gnome.desktop.interface")`.
  - Metodi `get_current() -> ThemeSet` e `apply(theme_set: ThemeSet)`.
  - Fallback sicuro / eccezione dedicata se lo schema non è presente (es. ambienti non-GNOME).
- [x] **Scanner**:
  - Iterazione sicura delle directory con `pathlib.Path`.
  - Rilevamento duplicati (i temi utente oscurano i temi di sistema con lo stesso nome).
- [x] **Interfaccia CLI**:
  - Argparse con subcomandi (`current`, `list`, `apply`).
  - Output formattato leggibile (tabelle ASCII o elenchi colorati).
- [x] **Test Unitari**:
  - Test per `scanner` con mock di directory temporanee.
  - Test per `gsettings` con mock di `Gio.Settings`.
  - Test di integrazione CLI per tutti i comandi.
