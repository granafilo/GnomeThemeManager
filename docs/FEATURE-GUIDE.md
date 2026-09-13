# Feature Guide — What Each Phase and Task Introduces

A plain-language guide to what GnomeThemeManager gains, phase by phase,
task by task. No code, no jargon on purpose.

**How to read this:** a *phase* is a milestone (a release). A *task* is one
small step inside it. ✅ = already shipped.

---

## Phase 0 — Stabilization & UX (v1.0) ✅

The app becomes reliable and pleasant to use.

- **0.1** The app now shows correctly, at startup, whether the GTK4 theme
  override is active.
  
- **0.2** The theme scanner finds *all* installed themes (user and system
  folders, inherited themes). Broken themes are flagged, never crash the app.
  
- **0.3** Small quality-of-life: Ctrl+W closes the window, clicking outside
  removes focus, a filter hides system themes.
  
- **0.4** Selective apply: choose exactly what to change (GTK3, GTK4, Shell,
  icons, cursors) instead of everything at once.
  
-  **0.5** Presets 2.0 **(diventati "Global Themes" nella Fase 1: vedi 1.1)**:

    save named theme combinations explicitly.

- **0.6** Shell themes: the app detects the required "User Themes" extension
  and offers to enable it, instead of failing silently.
  
- **0.7** Docs: how to make the launcher executable and run the app.

---

## Chore — English-first ✅/in progress

Everything public (docs, UI, CLI messages) speaks English by default;
Italian becomes a translation you get automatically with an Italian system.

## Chore — Version single source

The version number lives in exactly one place; everything else reads it.
No more mismatched versions between files, CLI and releases.

---

## Phase 1 — Global Themes & Validation (v1.1) ✅

One-click complete looks, and the app protects you from broken themes.

- **1.1** Global Themes: ONE page for everything — your saved looks on top (newest first), 3 starter looks at the bottom; apply with one click. ✅
- **1.2** Theme validator: the app checks that a theme package is complete
  and standard-compliant before trusting it. ✅
- **1.3** Corruption detection: if a theme is incomplete, you get a clear
  warning *before* applying it, and you can cancel. ✅
- **1.4** Icon pack preview: see real app icons rendered with each icon pack
  before applying it — no more guessing. ✅
- **1.5** Safe in-app preview: try a GTK4 theme on the app's own window
  without touching your system; instant revert. ✅
- **1.6** The app creates `~/.themes` and `~/.icons` for you if missing. ✅
- **1.7** Assisted install: install a theme from a folder or an archive
  (.tar.gz / .zip), validated before installation. ✅

---

## Phase 2 — Theme Editor (v1.2) ✅

Build your own look: mix themes and edit colors, safely.

- **2.1** Theme mixer: combine pieces from different themes (e.g. GTK3 from
  one, icons from another) into your own named Global Theme. ✅
- **2.2** Color extractor: the app reads a theme's colors (foreground,
  background, accent) so you can see and edit them. ✅
- **2.3** Editor UI: pick components, change colors with color pickers,
  preview in-app, save as your own Global Theme. ✅
- **2.4** Color forks: your color edits are saved as a *copy* of the theme;
  the original stays untouched; fully reversible. ✅
- **2.5** Drafts: your work-in-progress is saved automatically and can be
  resumed next time you open the app. ✅
- **2.6** *(stretch)* Adaptive color: suggest a palette extracted from your
  current wallpaper. ✅
- **2.7** Shell editor: change panel, overview and accent colors of your
  GNOME Shell theme; applied with live preview and safety auto-rollback, fully reversible. ✅

---

## Phase 3 — Fallback & Robustness (v1.3) ✅

No more scary alerts: the app heals itself.

- **3.1** Fallback themes: pick a backup per category; unavailable themes
  (e.g. in snap/flatpak) are replaced by your backup — silently, with a
  small info banner. The "missing themes" alert is gone. ✅
- **3.2** User Themes extension: optional silent auto-enable. ✅
- **3.3** Docs: how to make the launcher executable. ✅
- **3.4** The app ships fallback icons: its UI never shows broken placeholders. ✅

---

## Phase 4 — Editors (v1.4) ✅

Full control over your own looks.

- **4.1** Edit your existing Global Themes in place; starters duplicate
  via "save as copy". ✅
- **4.2** Custom icons for your Global Theme cards with fallback. ✅
- **4.3** Font editor: interface/document/monospace fonts + scaling,
  saved inside presets. ✅
- **4.4** *(stretch)* Terminal editor: full color customization, ANSI 16 palette, profiles, and preferences into GNOME Terminal. ✅

---

## Release v1.4.1 — Snap Integration & Maintenance ✅

The app becomes a first-class citizen of sandboxed environments and takes care of the details:

- **Instant Content Snaps**: Your custom themes are packaged into local Content Snaps in less than a second, so Snap applications (Firefox, Thunderbird, etc.) stop complaining about missing themes.
- **Single-Click Permissions**: Installation and connection of all Content Snaps under a single PolicyKit authorization window.
- **Live Diagnostics**: Dashboard displaying in real time which themes are active, which Content Snaps are installed, and which Snap apps are connected.
- **Smarter Editor**: The editor starts from the settings currently in use, lets you rename themes in-place, and includes a safe "Reset" action.
- **Protected Deletion**: You can no longer accidentally delete an active theme; incomplete or invalid themes are still cleanly removed.
- **No More GTK Warnings**: Fallback overrides apply themes directly to GSettings, eliminating desktop error popups.

---

## Release v1.4.2 — Stabilization & Pre-Store Polish 🛠️

Finishing touches before moving to the online Store:

- **Intelligent Theme Fallbacks**: The app no longer relies on hardcoded theme names in code. It dynamically verifies what is installed and applies settings safely.
- **Proper Flatpak Icon**: The application icon is now correctly displayed inside the Flatpak sandbox.
- **Step-by-Step Sandbox Guide**: Clear documentation with ready-to-use commands to expose themes to Flatpak and Snap apps.
- **Real Desktop State**: The "Current Configuration" panel reads live GSettings in real time — no more stale or mismatched values.
- **Explicit Light/Dark Control**: Directly choose from the UI whether to use Light, Dark, or Default color schemes.

---

## Phase 5 — Online Store (v1.5) ✅

- **5.1 Store Client (pling.com)**: Full API integration with Pling and OpenDesktop OCS catalog for searching and fetching themes across GTK, Shell, Icon packs, and Cursors.
- **5.2 Store UI**: Multi-column responsive card grid, category filters, high-resolution screenshot lightbox preview, download progress feedback, and 1-click automatic install into `~/.themes` and `~/.icons`.
- **5.3 Extensions Browser**: Built-in GNOME Shell extensions browser with live enable/disable toggles, individual settings launch, and extensions.gnome.org links.
- **5.4 Local Caching**: Resilient local caching of search results, catalogs, and metadata ensuring instant browsing.

---

## Phase 1.5.1 — Extensions Stabilization (v1.5.1) ✅

- **Multi-image screenshot carousel**: Browse all available screenshots for an extension directly from the detail view.
- **Unrestricted search**: Search finds all extensions from the official catalog regardless of Shell version, highlighting compatibility clearly.
- **Harmonized catalog alignment**: Consistent column spacing and pixel-perfect first-letter alignment for "Installed" and "Details".
- **Resilient downloads & rollbacks**: Atomic cleanup of corrupted or partial downloads and extracted files upon failure.
- **Incompatibility safety warnings**: Confirmation prompts before installing or updating extensions not verified for your GNOME Shell version.

---

## Phase 6 — Profiles & Automation (v1.6)

- **6.1–6.3** Light+dark profiles with a simple UI.
- **6.2** Auto-switch when the system switches light/dark.
- **6.4** Apply your profile at login.
- **6.5** Export/import profiles as one file.

---

## Phase 7 — Sync & Distribution (v1.7+)

- **7.1** LAN sync between your PCs (free alternative to paid sync).
- **7.2/7.3** Flatpak and .deb packages.
- **7.4–7.6** More languages, structured logs, first-run tour.

---

## Glossary (30 seconds)

- **Global Theme** — a complete look: GTK3 + GTK4 + Shell + icons + cursors.
- **Preset** — a saved named combination of themes.
- **Profile** — a light preset + a dark preset, with optional automation.
- **Fork** — your personal edited copy of a theme; original untouched.
- **In-app preview** — trying a theme on the app window only, not the system.