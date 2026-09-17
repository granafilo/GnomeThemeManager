# Agent Instructions — Implementazione Design System
**Destinatario:** Coder Agent  
**Ambito:** Refactoring UI / GTK4 / Libadwaita per "GNOME Theme Manager"  
**Filosofia:** GNOME Native Pure + Adaptive Visual Cards  

---

## 1. Posizione dei File e Risorse

I file di riferimento del Design System sono archiviati in:
* **Token di Design:** `docs/design/design-tokens.json`
* **Linee Guida di Stile:** `docs/design/style-guidelines.md`
* **Istruzioni Operative:** `docs/design/agent-instructions.md`

Tutto il codice CSS applicativo custom deve essere centralizzato in un unico foglio di stile pulito:
* **Percorso target CSS:** `src/gnome_theme_manager/gui_gtk/style.css`
* Il file CSS deve essere caricato durante l'avvio in `src/gnome_theme_manager/gui_gtk/app.py` o `window.py` tramite `Gtk.CssProvider` con priorità `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION`.

---

## 2. Vincolo Fondamentale ed Esplicito (NON NEGOZIABILE)

> **REGOLA "ZERO-HEX":**  
> È SEVERAMENTE VIETATO introdurre colori hardcoded in formato esadecimale (`#rrggbb`, `#rgb`), valori `rgb(...)` o `rgba(...)` con coordinate fisse per gli elementi dell'interfaccia dell'applicazione.  
> Qualsiasi colore utilizzato DEVE fare riferimento alle variabili semantiche native di Libadwaita (es. `@window_bg_color`, `@card_bg_color`, `@borders`, `@window_fg_color`, `@accent_bg_color`, `@accent_color`, `@warning_bg_color`, ecc.) o a sfumature con funzione `alpha(@variabile, valore)`.

---

## 3. Logica Operativa di Applicazione ai Widget GTK

### A. Pulizia delle Forzature Esistenti in `window.py`
1. Rimuovere l'intero blocco `css_data` inline presente nel metodo `_setup_custom_styling()` di `src/gnome_theme_manager/gui_gtk/window.py`.
2. Eliminare qualsiasi override di altezza minima su widget di sistema (`headerbar { min-height: ... }`, `dropdown > button { min-height: ... }`, `row.activatable { min-height: ... }`).
3. Rimuovere l'override tipografico `window.main-window { font-size: 1.04rem; }`.

### B. Normalizzazione della Sidebar in `ui/window.ui`
1. Rimuovere la classe `.heading` applicata su ciascuna `GtkLabel` nelle righe della sidebar di navigazione (`row_status`, `row_themes_shell`, ecc.).
2. Rimuovere le proprietà manuali `margin-start="12"`, `margin-end="12"`, `margin-top="10"`, `margin-bottom="10"` inserite nei container interni delle righe della sidebar; affidare lo spacing e l'allineamento interamente alla classe nativa `.navigation-sidebar`.

### C. Applicazione delle Classi Semantiche
1. **Per le schede visive (Temi, Icone, Categorie Store, Theme Cards):**
   * Nei file `.ui`: aggiungere il tag `<style><class name="gtm-preview-card"/></style>` (o combinato con `.card`).
   * Nel codice Python (es. `pages/store.py` in `StoreThemeCard` o `pages/themes.py`): invocare `widget.add_css_class("gtm-preview-card")` invece di classi custom con stili sparsi.
2. **Per elenchi funzionali e configurazioni (Estensioni, Diagnostica, Sandbox, Fallback):**
   * Mantenere rigorosamente `AdwPreferencesGroup` e `.boxed-list` (`AdwActionRow`, `AdwComboRow`, `AdwSwitchRow`).
   * Non applicare card fluttuanti a questi elenchi.
3. **Per riquadri di anteprima (Terminal & Swatch):**
   * Terminal Preview: applicare la classe `.gtm-preview-frame` al container di anteprima in `pages/terminal.py` con raggio `8px` e bordo `1px solid @borders`.
   * Cerchi Swatch Colore: in `pages/editor_view.py` e `widgets/color_picker.py`, usare raggio circolare `9999px` e bordo semantico `1px solid @borders`.
4. **Per i Banner dello Store:**
   * Sostituire il gradiente esadecimale fisso di `.store-banner-box` con un gradiente semantico reattivo all'accento di sistema, es.:
     `background: linear-gradient(135deg, alpha(@accent_bg_color, 0.20) 0%, alpha(@accent_bg_color, 0.05) 100%);`
   * Sostituire lo sfondo del lightbox `#0b0d13` con `@popover_bg_color` o `alpha(@window_bg_color, 0.95)`.

### D. Clamping e Responsività dei Contenitori
* Unificare i contenitori `AdwClamp` dell'applicazione secondo la scala in `design-tokens.json`:
  * Viste compatte / dialoghi wizard: `maximum-size="540"`
  * Viste standard di navigazione e liste: `maximum-size="800"`
  * Gallerie larghe e Store: `maximum-size="1000"`

---

## 4. Verifica e Criteri di Accettazione

Prima di considerare completata l'integrazione, il Coder Agent deve verificare che:
1. L'interfaccia sia visivamente impeccabile e con contrasto perfetto sia con `gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'` sia con `'prefer-dark'`.
2. Al cambio di Accent Color di GNOME (es. da Blu ad Arancione, Verde, Rosa), tutti i badge, focus e bordi evidenziati riflettano istantaneamente la nuova tonalità.
3. Nessun test automatico risulti compromesso e tutti i test di regressione GUI siano verdi.
