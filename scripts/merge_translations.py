#!/usr/bin/env python3
# Script per fondere le traduzioni pot nei file po it ed en.

import os
import re


def parse_po_pot(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    pattern = re.compile(
        r'((?:#[^\n]*\n)*)'
        r'msgid\s+((?:"(?:[^"\\]|\\.)*"\s*)+)\s*'
        r'msgstr\s+((?:"(?:[^"\\]|\\.)*"\s*)+)',
        re.MULTILINE
    )
    
    entries = []
    for match in pattern.finditer(content):
        comments = match.group(1).strip()
        msgid_raw = match.group(2)
        msgstr_raw = match.group(3)
        
        # Concatena le righe tra virgolette
        msgid = "".join(eval(chunk) for chunk in msgid_raw.splitlines() if chunk.strip())
        msgstr = "".join(eval(chunk) for chunk in msgstr_raw.splitlines() if chunk.strip())
        
        entries.append({
            'comments': comments,
            'msgid': msgid,
            'msgstr': msgstr
        })
    return entries

def write_po(filepath, entries, lang):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('# Translation for gnome-theme-manager.\n')
        f.write('# Copyright (C) 2026 GnomeThemeManager Contributors\n')
        f.write('#\n')
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Project-Id-Version: gnome-theme-manager 0.9.0b2\\n"\n')
        f.write('"MIME-Version: 1.0\\n"\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write(f'"Language: {lang}\\n"\n')
        f.write('"Content-Transfer-Encoding: 8bit\\n"\n\n')
        
        for entry in entries:
            if not entry['msgid']:
                continue
            if entry['comments']:
                f.write(entry['comments'] + '\n')
            escaped_msgid = entry['msgid'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            escaped_msgstr = entry['msgstr'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            f.write(f'msgid "{escaped_msgid}"\n')
            f.write(f'msgstr "{escaped_msgstr}"\n\n')

def translate_to_english(text):
    translations = {
        "Stato attuale": "Current status",
        "Tema GTK (Applicazioni)": "GTK Theme (Applications)",
        "Tema Icone": "Icon Theme",
        "Tema Cursori": "Cursor Theme",
        "Tema GNOME Shell": "GNOME Shell Theme",
        "Schema Colori": "Color Scheme",
        "Default di sistema": "System Default",
        "Non impostato": "Not set",
        "Nessun elemento da mostrare.": "No elements to show.",
        "comandi": "commands",
        "Comando da eseguire": "Command to execute",
        "Avvia l'interfaccia grafica nativa GNOME GTK4/Libadwaita": "Launch native GNOME GTK4/Libadwaita graphical interface",
        "Mostra i temi attualmente applicati sul desktop GNOME": "Show currently applied themes on GNOME desktop",
        "Mostra lo stato di integrazione con i runtime sandbox (Snap e Flatpak)": "Show integration status with sandbox runtimes (Snap and Flatpak)",
        "Elenca i temi disponibili nel sistema": "List available themes in the system",
        "Filtra per tipologia di tema (default: all)": "Filter by theme type (default: all)",
        "Mostra solo i temi installati a livello utente (~/.local/share/...)": "Show only user-level installed themes (~/.local/share/...)",
        "Applica uno o più temi su GNOME": "Apply one or more themes on GNOME",
        "Nome del tema GTK da applicare": "Name of the GTK theme to apply",
        "Applica un tema unificato (GTK, Shell e override GTK4/Libadwaita) con lo stesso nome": "Apply unified theme (GTK, Shell and GTK4/Libadwaita override) with the same name",
        "Nome del tema di icone da applicare": "Name of the icon theme to apply",
        "Nome del tema dei cursori da applicare": "Name of the cursor theme to apply",
        "Nome del tema per la GNOME Shell da applicare": "Name of the GNOME Shell theme to apply",
        "Schema colore (default o prefer-dark per GNOME 42+)": "Color scheme (default or prefer-dark for GNOME 42+)",
        "Non applicare l'override GTK4 in ~/.config/gtk-4.0 quando si imposta un tema GTK": "Do not apply GTK4 override in ~/.config/gtk-4.0 when setting a GTK theme",
        "Non propagare il tema alle app Snap/Flatpak": "Do not propagate the theme to Snap/Flatpak apps",
        "Installa un tema a partire da un file archivio (.zip, .tar.*)": "Install a theme from an archive file (.zip, .tar.*)",
        "Percorso del file archivio da installare": "Path to the archive file to install",
        "Tipo di tema (se non specificato, verrà effettuato il rilevamento automatico)": "Theme type (if not specified, auto-detection will run)",
        "Nome personalizzato per la cartella di destinazione del tema": "Custom name for the theme destination folder",
        "Sovrascrive il tema se la cartella di destinazione esiste già": "Overwrite theme if destination folder already exists",
        "Disinstalla un tema specifico dalle directory utente": "Uninstall a specific theme from user directories",
        "Nome del tema da disinstallare": "Name of the theme to uninstall",
        "Tipo del tema da disinstallare": "Type of the theme to uninstall",
        "Conferma la disinstallazione senza prompt interattivo": "Confirm uninstallation without interactive prompt",
        "Gestione di preset e profili di configurazione temi": "Manage presets and theme configuration profiles",
        "azioni preset": "preset actions",
        "Azione da eseguire sul preset": "Action to run on preset",
        "Elenca tutti i preset memorizzati": "List all stored presets",
        "Salva la combinazione di temi corrente come nuovo preset": "Save current theme combination as new preset",
        "Nome identificativo del preset da salvare": "Identifying name of the preset to save",
        "Sovrascrive il preset se già esistente": "Overwrite preset if already existing",
        "Applica un preset salvato": "Apply a saved preset",
        "Nome del preset da applicare": "Name of the preset to apply",
        "Non applicare l'override GTK4 in ~/.config/gtk-4.0": "Do not apply GTK4 override in ~/.config/gtk-4.0",
        "Elimina un preset memorizzato": "Delete a stored preset",
        "Nome del preset da eliminare": "Name of the preset to delete",
        "Conferma l'eliminazione senza prompt interattivo": "Confirm deletion without interactive prompt",
        "Stato sandbox non disponibile.": "Sandbox status not available.",
        "NOME": "NAME",
        "TIPO": "TYPE",
        "ORIGINE": "SOURCE",
        "PERCORSO": "PATH",
        "User": "User",
        "System": "System",
        "NOME TEMA": "THEME NAME",
        "PERCORSO INSTALLATO": "INSTALLED PATH",
        "Nessun preset salvato.": "No presets saved.",
        "Preset salvati disponibili:": "Available saved presets:",
        "NOME PRESET": "PRESET NAME",
        "Operazione annullata dall'utente.": "Operation cancelled by user.",
    }
    
    clean = text.strip()
    if clean in translations:
        return translations[clean]
        
    translated = clean
    replacements = [
        ("Errore", "Error"),
        ("Attivo", "Active"),
        ("Non attivo", "Inactive"),
        ("Disponibile", "Available"),
        ("Non disponibile", "Not available"),
        ("Installato", "Installed"),
        ("Non installato", "Not installed"),
        ("Nessun tema trovato per la tipologia", "No theme found for type"),
        ("Totale temi trovati", "Total themes found"),
        ("Modifiche applicate con successo", "Changes applied successfully"),
        ("Tema GTK impostato su", "GTK Theme set to"),
        ("Override GTK4/Libadwaita applicato in", "GTK4/Libadwaita override applied in"),
        ("Nessun file GTK4 trovato nel tema (applicato solo a GTK2/GTK3)", "No GTK4 file found in theme (applied to GTK2/GTK3 only)"),
        ("Tema Icone impostato su", "Icon Theme set to"),
        ("Tema Cursori impostato su", "Cursor Theme set to"),
        ("Tema GNOME Shell impostato su", "GNOME Shell Theme set to"),
        ("Schema Colori impostato su", "Color Scheme set to"),
        ("Propagazione Flatpak", "Flatpak Propagation"),
        ("Accesso filesystem e variabili impostati", "Filesystem access and variables set"),
        ("Propagazione Snap", "Snap Propagation"),
        ("Compatibilità verificata con", "Compatibility verified with"),
        ("Sei sicuro di voler disinstallare il tema", "Are you sure you want to uninstall the theme"),
        ("disinstallato con successo", "uninstalled successfully"),
        ("salvato con successo in", "saved successfully in"),
        ("applicato con successo", "applied successfully"),
        ("Sei sicuro di voler eliminare il preset", "Are you sure you want to delete the preset"),
        ("eliminato con successo", "deleted successfully"),
    ]
    for it_p, en_p in replacements:
        if it_p in translated:
            translated = translated.replace(it_p, en_p)
            
    return translated

def merge(pot_path, po_path, lang):
    pot_entries = parse_po_pot(pot_path)
    po_entries = {}
    if os.path.exists(po_path):
        for entry in parse_po_pot(po_path):
            po_entries[entry['msgid']] = entry['msgstr']
            
    merged = []
    for entry in pot_entries:
        if not entry['msgid']:
            continue
        msgid = entry['msgid']
        msgstr = po_entries.get(msgid, "")
        
        if not msgstr:
            if lang == "it":
                msgstr = msgid
            else:
                msgstr = translate_to_english(msgid)
                
        merged.append({
            'comments': entry['comments'],
            'msgid': msgid,
            'msgstr': msgstr
        })
        
    write_po(po_path, merged, lang)
    print(f"Fusi {len(merged)} elementi in {po_path}")

def main():
    merge("po/gnomethememanager.pot", "po/it.po", "it")
    merge("po/gnomethememanager.pot", "po/en.po", "en")

if __name__ == "__main__":
    main()
