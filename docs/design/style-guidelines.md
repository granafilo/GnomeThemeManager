# Style Guidelines — GNOME Theme Manager
**Target:** GNOME 46 / Libadwaita 1.5+  
**Design Direction:** GNOME Native Pure + Adaptive Visual Cards  

Questo documento definisce le specifiche visive, semantiche e di accessibilità per l'applicazione, derivate da `design-tokens.json`. Tutte le interfacce GTK4 / Libadwaita devono attenersi rigorosamente a queste regole.

---

## 1. Classi Semantiche e Regole di Utilizzo

### `.gtm-preview-card` (Card per Elementi con Anteprima Visiva)
* **Quando usarla:** Esclusivamente per elementi che richiedono una forte componente grafica: schede temi (GTK, Shell) con swatch cromatici, pacchetti icone con griglie di preview, e card dello Store (categorie e temi Pling).
* **Quando NON usarla:** Non usare mai per elenchi testuali, diagnostica, impostazioni, o liste di estensioni.
* **Geometria:**
  * Background: `@card_bg_color`
  * Bordo: `1px solid @borders`
  * Border-radius: `12px` (`radius.card`)
  * Padding interno: `12px` (`spacing.medium`)
  * Transizione: `box-shadow 150ms ease-in-out, border-color 150ms ease-in-out`

### `.gtm-preview-frame` (Contenitore Anteprima Frameless & Clean)
* **Quando usarla:** Per racchiudere aree di anteprima viva, come il riquadro di output del Terminale o il canvas dell'anteprima tema.
* **Geometria:**
  * Background: `@window_bg_color` (oppure il colore dinamico del tema anteposto)
  * Bordo: `1px solid @borders`
  * Border-radius: `8px` (`radius.medium`)
  * Nessuna ombra o cornice nidificata.

### `.gtm-swatch-circle` (Campioni di Colore Circolari)
* **Quando usarla:** Per i cerchi di selezione o preview dei colori di accento (Accent Color).
* **Geometria:**
  * Dimensione minima: `24px x 24px`
  * Border-radius: `9999px` (`radius.pill`)
  * Bordo: `1px solid @borders` (adattivo sia a sfondi chiari che scuri)

### `.boxed-list` & `AdwPreferencesGroup` (Dati, Opzioni e Liste Funzionali)
* **Quando usarla:** Per tutte le liste prive di anteprima visiva primaria: elenco estensioni GNOME Shell, impostazioni di diagnostica, percorsi cartelle utente, switch di comportamento, e selezione temi di fallback.
* **Regola aurea:** Preservare la spaziatura e l'altezza naturale calcolata da Libadwaita senza imporre `min-height` artificiali o override CSS sui singoli elementi della riga.

### `.gtm-status-badge` (Badge Informativo / Stato)
* **Quando usarla:** Per indicare stati come "In use", "Installed", "Flatpak", "System".
* **Geometria:**
  * Border-radius: `9999px` (`radius.pill`)
  * Padding: `2px 8px`
  * Stile tipografico: `.caption`, peso semi-bold/bold.
  * Colore attivo ("In use"): background `alpha(@accent_bg_color, 0.15)`, testo `@accent_color`.

---

## 2. Regole di Stato (Interaction States)

Tutti gli stati interattivi devono derivare unicamente dalle variabili Libadwaita per reagire in tempo reale alle modalità Chiara/Scura e all'Accent Color dell'utente.

### Hover (`:hover`)
* **Sulle Card (`.gtm-preview-card:hover`):**
  * Box-shadow: `0 2px 8px alpha(@borders, 0.35)`
  * Bordo: `1px solid alpha(@accent_color, 0.50)`
* **Sulle Liste (`list.boxed-list > row.activatable:hover`):**
  * Ereditare il comportamento nativo di Libadwaita. Nessuna sovrascrittura di colore testo o forzatura di padding.
* **Sui Bottoni Flat (`button.flat:hover`):**
  * Sfruttare lo sfondo nativo `alpha(@window_fg_color, 0.08)`.

### Active / Pressed (`:active`)
* Leggera pressione tattile: `box-shadow: none` su card e bottoni.
* Sulle card interattive: background `alpha(@accent_bg_color, 0.10)`.

### Focus Visibile (`:focus-visible`)
* Tutti i controlli interattivi (card cliccabili, bottoni, campi di testo) devono evidenziare il focus con un anello chiaro e visibile:
  * `outline: 2px solid @accent_color;`
  * `outline-offset: 2px;`

### Disabilitato (`:disabled`)
* Opacità ridotta: `opacity: 0.50;`
* Sfondo trasparente per elementi di riga: divieto assoluto di applicare box scuri o grigi rigidi sugli elementi disabilitati.

---

## 3. Regole di Accessibilità & Ergonomia (WCAG & HIG)

1. **Rapporto di Contrasto (WCAG 2.1 AA):**
   * Testo normale su sfondo: contrasto minimo di 4.5:1.
   * Testo grande (titoli ≥ 18pt o bold ≥ 14pt) e componenti UI essenziali: contrasto minimo di 3:1.
   * L'accoppiamento vincolante `@window_fg_color` su `@window_bg_color` e `@card_fg_color` su `@card_bg_color` assicura matematicamente la conformità in qualsiasi tema di sistema.

2. **Dimensioni Minime dei Target Interattivi:**
   * Tutti gli elementi cliccabili (bottoni, righe interattive, card, swatch) devono avere un'area target di almeno `36px x 36px` per garantire ergonomia con mouse e schermi touch.

3. **Invarianza Tipografica e Accessibilità di Sistema:**
   * È severamente vietato impostare `font-size` con valori assoluti (`px` o `pt`) o scalature arbitrarie (`rem` sulla finestra principale).
   * L'applicazione deve sempre ereditare il font di sistema (`@system-font`) e rispettare le impostazioni di "Testo Grande" (Large Text) configurate nel sistema operativo.

4. **Sidebar di Navigazione:**
   * Le voci della sidebar devono utilizzare testo standard (`default`). È vietato l'uso della classe `.heading` sulle singole righe di navigazione per preservare l'equilibrio visivo raccomandato da GNOME HIG.
