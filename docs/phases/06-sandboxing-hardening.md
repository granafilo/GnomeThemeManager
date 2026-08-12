# Fase 6: Hardening, Packaging e Distribuzione Sandbox

## Obiettivi della Fase

Rendere l'applicazione robusta, sicura e facilmente distribuibile su distribuzioni Linux moderne:
1. **Packaging Flatpak**: Creazione di manifest Flatpak (`org.gnome.ThemeManager.json` / `.yaml`) e gestione permessi filesystem.
2. **Supporto GNOME 45+ / 46+ e Wayland**: Gestione corretta dei vincoli di theming introdotti con Libadwaita e GTK4.
3. **Funzionalità Avanzate**:
   - Salvataggio e ripristino di preset/profili completi (GTK + Icone + Cursori + Dark mode).
   - Anteprime grafiche dei temi.
   - Esportazione/importazione configurazioni.

---

## Dettagli Sandbox Flatpak

### Permessi Filesystem e D-Bus
Per interagire con il sistema da sandbox:
- `finish-args`:
  - `--filesystem=xdg-data/themes:create` (accesso a `~/.local/share/themes`)
  - `--filesystem=xdg-data/icons:create` (accesso a `~/.local/share/icons`)
  - `--talk-name=ca.desrt.dconf` o accesso GSettings tramite XDG Desktop Portal.
  - `--filesystem=xdg-download:ro` (per selezionare archivi dalla cartella Download).

---

## Architettura e Moduli Coinvolti

```text
packaging/
├── flatpak/
│   ├── org.gnome.ThemeManager.json
│   └── org.gnome.ThemeManager.desktop
└── meson.build             # Sistema di build per Flatpak e installazione di sistema

src/gnome_theme_manager/
└── core/
    └── presets.py          # Gestione import/export profili (JSON/YAML)
```

---

## Checklist di Implementazione

- [ ] Definizione manifest Flatpak compatibile con GNOME Runtime 46/47.
- [ ] Implementazione modulo `presets.py` per snapshot e restore delle impostazioni grafiche.
- [ ] Documentazione per build locale via `flatpak-builder`.
- [ ] Fallback eleganti in caso di limitazioni sandbox o assenza di schemi D-Bus.
