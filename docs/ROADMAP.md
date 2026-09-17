# 🗺️ Development Roadmap — GNOME Theme Manager

Last updated: September 17, 2026
Current version: v1.5.3 (Phase 1.5.3 — Multi-Distro Terminal & Debian 13 Support — completed)
Status: Active development — next: Phase 6 (Profiles & Automations, v1.6)

## 📊 Completed Phases

| Phase | Version | Name | Status |
|-------|---------|------|--------|
| 0 | v1.0.0 | Setup & Stabilization | ✅ Completed (August 2026) |
| 1 | v1.1.0 | Global Themes & Validation | ✅ Completed (August 2026) |
| 2 | v1.2.0 | Theme Editor | ✅ Completed (August 2026) |
| 3 | v1.3.0 | Fallback & Robustness | ✅ Completed |
| 4 | v1.4.0 | Editors (Global Themes, Icons, Fonts) | ✅ Completed |
| 4.5 | v1.4.1 | Snap Integration & Maintenance | ✅ Completed |
| 4.8 | v1.4.8 | Pre-Store Stabilization | ✅ Completed |
| 5 | v1.5.0 → v1.5.3 | Online Store, Extensions & Multi-Distro Terminal Support | ✅ Completed (September 2026) |

## 🎯 Phase 6 — Profiles & Automations (v1.6)

**Branch:** `feature/phase-6-profiles`
**Status:** 📋 Planned
**Priority:** P2

### Goals
- [ ] Profiles with light/dark variants (`profiles.json`)
- [ ] Auto-switch on `color-scheme` change (GNOME 42+)
- [ ] Profiles UI (list, create, activate)
- [ ] Autostart via systemd user service
- [ ] Export/import profiles (JSON bundle)

### Tasks
- 6.1 Profiles with light/dark variant [P2]
- 6.2 `color-scheme` integration (GNOME 42+) [P2]
- 6.3 Profiles UI [P2]
- 6.4 Autostart via systemd user [P2]
- 6.5 Export/import profiles [P2]

**Acceptance:** Auto-switch on color-scheme; apply at reboot; export round-trip; i18n §2.8; coverage ≥80%.

## 🎯 Phase 7 — Sync & Distribution (v1.7+)

**Branch:** `feature/phase-7-sync-packaging`
**Status:** 💡 Planned
**Priority:** P2–P3

### Goals
- [ ] LAN sync (mDNS/Avahi)
- [ ] Flatpak packaging (official manifest)
- [ ] .deb packaging (Ubuntu/Debian)
- [ ] Additional i18n languages
- [ ] Structured logging
- [ ] First-run tour (stretch)

### Tasks
- 7.1 LAN sync [P2]
- 7.2 Flatpak packaging [P2] — **NOTE:** Flatpak already adopted as primary format; this task is for official Flathub-ready manifest
- 7.3 .deb packaging [P2]
- 7.4 Additional i18n languages [P3]
- 7.5 Structured logging [P3]
- 7.6 First-run tour (stretch) [P3]

**Acceptance:** LAN sync between 2 machines; Flatpak and .deb installable; rotating logs; i18n §2.8; coverage ≥80%.

## 📦 Packaging

**Current:** Flatpak
**Planned:** .deb (Ubuntu/Debian) — Phase 7.3

### Flatpak
- Manifest: `io.github.granafilo.GnomeThemeManager.yml`
- Runtime: `org.gnome.Platform` 45+
- Permissions: `--filesystem=~/.local/share/themes:create`, `--filesystem=~/.local/share/icons:create`, `--talk-name=org.gnome.Settings`

## 📅 Estimated Timeline

| Milestone | Version | Target Date | Main Features |
|-----------|---------|-------------|---------------|
| Phase 6 | v1.6.0 | October 2026 | Profiles, auto-switch, export/import |
| Phase 7 | v1.7.0 | November 2026 | LAN sync, .deb packaging, logging |

## 🔗 Useful Resources

- [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/)
- [Libadwaita Documentation](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/)
- [Flatpak Documentation](https://docs.flatpak.org/)
- [Pling API](https://www.pling.com/api/)