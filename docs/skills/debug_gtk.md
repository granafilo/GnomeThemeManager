# Skill: Debug problemi GTK4/Libadwaita

Quando si verifica un problema GUI (crash, widget non renderizzati, 
temi non applicati, signal non scatenati), NON buttarti a indovinare.
Segui questo processo ordinato.

## Step 1 — Raccolta prove
Esegui e incolla in chat:
  GDK_DEBUG=all python -m gnome_theme_manager.gui_gtk 2>&1 | head -100
  G_MESSAGES_DEBUG=all python -m gnome_theme_manager.gui_gtk 2>&1 | head -100

## Step 2 — Classificazione problema
Il bug rientra in una di queste categorie?
- A. Widget non renderizzato → sospetta Gtk.Box/packing, size request
- B. Tema non applicato → sospetta CssProvider o gtk.css syntax
- C. Signal non scatenato → sospetta connect() o signal name
- D. Crash su startup → sospetta init order o dipendenza GTK non pronta
- E. Lentezza → sospetta blocking su main thread

## Step 3 — Isolamento
Se possibile, riproduci il bug in uno script standalone di ~20 righe
(senza il resto dell'app) e allegami il codice.

## Step 4 — Fix + verifica
Proponi fix MINIMO possibile, con test che falliva prima e passa dopo.