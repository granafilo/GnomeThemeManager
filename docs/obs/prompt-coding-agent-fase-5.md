# Prompt per il coding agent — Fase 5

## Contesto comune

Stai lavorando a `GnomeThemeManager`, un'applicazione Linux orientata a GNOME.
La Fase 5 introduce e consolida una GUI nativa moderna basata su:

- Python 3.10+;
- PyGObject;
- GTK 4;
- Libadwaita;
- GtkBuilder con file `.ui` per il layout;
- CLI separata dalla GUI.

Tkinter non deve più essere utilizzato come backend grafico principale e, salvo diversa indicazione esplicita, deve essere rimosso dal progetto.

## Regole obbligatorie

- Prima di modificare il codice, analizza la struttura esistente e produci un piano breve.
- Lavora esclusivamente sul sotto-obiettivo indicato nel prompt corrente.
- Non riscrivere componenti funzionanti senza necessità.
- Non introdurre un nuovo toolkit grafico.
- Non modificare API pubbliche o comportamento della CLI senza dichiararlo.
- Mantieni la logica applicativa fuori dai widget GTK.
- Mantieni tutte le operazioni GTK/UI sul main thread.
- Usa API asincrone GIO quando disponibili.
- Usa `Gio.Task` per operazioni realmente bloccanti.
- Usa `GLib.idle_add` soltanto per riportare piccoli aggiornamenti al main loop, mai per eseguire il lavoro pesante.
- Non usare `sudo` automaticamente.
- Non eseguire cancellazioni o modifiche distruttive senza validazione e conferma coerenti con il comportamento esistente.
- Non aggiungere funzionalità non richieste.
- Aggiorna i test e la documentazione quando il comportamento cambia.
- Al termine esegui i test pertinenti, `ruff check` e, se possibile, un avvio manuale della GUI.
- Se una dipendenza GTK/Libadwaita non è disponibile nell'ambiente, non sostituirla con Tkinter: segnala il problema chiaramente.

## Formato obbligatorio della risposta finale dell'agente

Riporta sempre:

1. riepilogo delle modifiche;
2. file creati, modificati o rimossi;
3. test eseguiti e risultato;
4. comandi di verifica eseguiti;
5. problemi o limitazioni residue;
6. eventuali assunzioni fatte.

---

# Prompt 5.0 — Audit preliminare

## Obiettivo

Analizza lo stato reale del progetto prima di implementare la nuova GUI. Non modificare il codice.

## Attività

- individua l'entry point CLI;
- mappa `gui_tk`, eventuale GUI GTK e backend applicativo;
- individua il modello dati dei temi;
- individua i servizi per rilevamento, applicazione, installazione e rimozione;
- verifica quali funzionalità sono realmente implementate e quali sono stub;
- verifica test e documentazione esistenti;
- individua dipendenze GTK4, Libadwaita e PyGObject;
- evidenzia riferimenti Tkinter nella CLI, nei test e nella documentazione;
- controlla se esistono già file `.ui` o componenti riutilizzabili.

## Output richiesto

Produci un report senza modifiche con:

- stato attuale;
- mappa dei componenti;
- flussi principali;
- problemi e rischi;
- elenco dei file da toccare;
- proposta di ordine dei task della Fase 5;
- test mancanti.

Non implementare nulla finché il report non è completo.

---

# Prompt 5.1 — Rimozione Tkinter e scheletro GTK

## Obiettivo

Rimuovere il layer grafico Tkinter e predisporre uno scheletro GTK4/Libadwaita minimale, senza implementare ancora tutte le pagine.

## Implementa

- rimuovi `src/gnome_theme_manager/gui_tk/` e i relativi test soltanto se non sono più utilizzati;
- rimuovi i riferimenti Tkinter da launcher, CLI, packaging e documentazione;
- crea `gui_gtk/` con entry point, applicazione e finestra principale;
- crea un `Adw.Application` e una `Adw.ApplicationWindow` funzionanti;
- carica il layout principale da `ui/window.ui` tramite `Gtk.Builder`;
- usa `Adw.ToastOverlay`;
- mantieni `gnome-theme-manager gui` e `--gui` compatibili, facendoli avviare la GUI GTK4;
- aggiungi una schermata iniziale minimale con titolo e stato dell'applicazione.

## Criteri di accettazione

- `gnome-theme-manager gui` avvia GTK4/Libadwaita;
- non viene importato Tkinter;
- la finestra si apre senza errori;
- il layout viene caricato da `.ui`;
- i test esistenti non regressiscono;
- il launcher non contiene percorsi morti.

Non implementare ancora installer, preset, sandbox o operazioni asincrone.

---

# Prompt 5.2 — Shell dell'applicazione e navigazione

## Obiettivo

Implementare la struttura visiva principale della GUI, senza collegare ancora tutte le operazioni reali.

## Implementa

- `Adw.NavigationSplitView` con sidebar e contenuto principale;
- navigazione verso le pagine: Stato, Temi, Preset, Installer e Sandbox;
- una pagina GTK/Libadwaita separata per ogni sezione;
- caricamento dei layout da file `.ui` separati;
- selezione iniziale coerente della pagina Stato;
- comportamento adattivo su finestra stretta;
- titoli, icone e descrizioni coerenti con GNOME;
- messaggio esplicito per le pagine ancora non implementate.

## Vincoli

- non duplicare la logica del backend nei controller UI;
- non simulare dati reali fingendo che siano disponibili;
- non implementare ancora installazione o applicazione temi.

## Criteri di accettazione

- tutte le pagine sono raggiungibili;
- la navigazione funziona anche in modalità compatta;
- ogni pagina ha un layout separato e leggibile;
- la GUI non presenta errori GTK in avvio o durante la navigazione.

---

# Prompt 5.3 — Pagina Stato e diagnostica minima

## Obiettivo

Collegare la pagina Stato al backend esistente e visualizzare il tema attivo senza introdurre ancora funzioni avanzate.

## Implementa

- caricamento del tema attivo;
- visualizzazione separata di tema GTK, icone, cursore e Shell se supportati dal backend;
- stato di caricamento;
- stato “non disponibile” quando un dato non può essere rilevato;
- pulsante Refresh;
- gestione degli errori con `Adw.Toast`;
- separazione tra modello dati e widget.

## Criteri di accettazione

- il tema visualizzato corrisponde al backend;
- il refresh aggiorna i dati senza riavviare la GUI;
- un errore non causa il crash dell'applicazione;
- nessun widget viene aggiornato da un worker thread;
- sono presenti test con backend mockato.

---

# Prompt 5.4 — Esplora temi

## Obiettivo

Implementare la pagina principale per l'elenco e la selezione dei temi installati.

## Implementa

- caricamento dei temi dal servizio esistente;
- lista con nome, categoria e percorso quando disponibili;
- indicazione del tema attivo;
- ricerca testuale;
- filtro per categoria soltanto se supportato dal modello dati;
- stato vuoto;
- stato di caricamento;
- stato di errore;
- selezione di un tema;
- aggiornamento della pagina senza ricostruire inutilmente tutta la finestra.

## Vincoli

- non applicare automaticamente un tema quando viene selezionato;
- non inventare anteprime se non esiste un meccanismo reale;
- non aggiungere installazione o rimozione in questo task.

## Criteri di accettazione

- la lista rappresenta i dati reali;
- ricerca e filtro non modificano il backend;
- il tema attivo è riconoscibile;
- directory mancanti e temi non validi sono gestiti;
- sono presenti test per lista vuota, risultati multipli e ricerca.

---

# Prompt 5.5 — Applicazione tema e feedback

## Obiettivo

Collegare l'azione di applicazione alla pagina Temi con gestione corretta degli stati asincroni.

## Implementa

- pulsante `Applica` per il tema selezionato;
- validazione del tema prima dell'operazione;
- operazione asincrona per ogni attività potenzialmente bloccante;
- `Gio.Cancellable` dove supportato;
- disabilitazione dei soli controlli coinvolti durante l'operazione;
- spinner o indicatore di attività;
- toast di successo o errore;
- aggiornamento del tema attivo dopo il completamento;
- nessun aggiornamento GTK dal worker.

## Flusso richiesto

```text
selezione tema
→ validazione
→ avvio task
→ stato busy
→ applicazione backend
→ callback nel main context
→ refresh stato
→ toast
→ stato idle
```

## Criteri di accettazione

- la GUI non si blocca durante l'applicazione;
- un errore ripristina correttamente lo stato dei controlli;
- il successo aggiorna lista e stato attivo;
- l'utente riceve un feedback chiaro;
- i test coprono successo, errore e cancellazione quando applicabile.

---

# Prompt 5.6 — Installer temi

## Obiettivo

Implementare l'installazione da archivio mantenendo la GUI reattiva e senza operazioni distruttive implicite.

## Implementa

- file chooser GTK4 per selezionare un archivio;
- validazione estensione e contenuto;
- rilevamento tipologia del tema;
- conferma prima dell'installazione;
- estrazione tramite task asincrono;
- gestione di archivio non valido, collisioni e permessi insufficienti;
- refresh della lista dopo il successo;
- toast di risultato.

## Vincoli

- non usare `sudo` automaticamente;
- non sovrascrivere dati senza regola esplicita;
- usare directory temporanea e cleanup sicuro;
- impedire path traversal durante l'estrazione;
- non procedere se il backend non supporta il tipo rilevato.

## Criteri di accettazione

- archivio valido installato;
- archivio corrotto rifiutato;
- errori di permesso gestiti;
- GUI reattiva;
- lista temi aggiornata senza riavvio.

---

# Prompt 5.7 — Preset e profili

## Obiettivo

Implementare il salvataggio e il ripristino di configurazioni complete, solo se il backend supporta già questi concetti.

## Implementa

- creazione di un preset dalla configurazione corrente;
- elenco preset;
- rinomina o eliminazione con conferma;
- applicazione di un preset;
- validazione dei componenti mancanti;
- feedback asincrono per applicazione e ripristino;
- persistenza in un formato documentato e versionabile.

## Vincoli

- non introdurre un secondo sistema di configurazione incompatibile;
- non cancellare preset senza conferma;
- gestire preset parziali in modo esplicito.

## Criteri di accettazione

- un preset può essere creato e riapplicato;
- dati mancanti producono un avviso comprensibile;
- il formato persistito è stabile;
- sono presenti test per creazione, applicazione e dati corrotti.

---

# Prompt 5.8 — Sandbox e Flatpak/Snap

## Obiettivo

Implementare la diagnostica sandbox solo dopo che il flusso principale dei temi è stabile.

## Implementa

- rilevamento disponibilità di Flatpak e Snap;
- verifica dei temi accessibili all'ambiente sandbox;
- visualizzazione dello stato e delle motivazioni;
- switch di propagazione soltanto se l'azione è supportata e chiaramente definita;
- conferma prima di modifiche esterne;
- gestione di comando assente, permessi insufficienti e timeout;
- task asincroni per comandi lunghi.

## Vincoli

- non modificare permessi di sistema senza consenso;
- non installare pacchetti automaticamente;
- non assumere che Flatpak e Snap siano presenti;
- separare diagnosi da modifica.

## Criteri di accettazione

- ambiente non sandboxato gestito;
- Flatpak/Snap assenti gestiti;
- errori e timeout mostrati all'utente;
- nessuna modifica esterna senza conferma;
- test con comandi mockati.

---

# Prompt 5.9 — Test, qualità e hardening

## Obiettivo

Rendere la GUI verificabile e pronta per una prima release interna.

## Implementa

- test unitari dei controller senza display quando possibile;
- backend `ThemeManager` mockato;
- test dei percorsi successo/errore/cancellazione;
- test di caricamento `.ui`;
- test di compatibilità launcher;
- lint con `ruff check`;
- formattazione con `ruff format`;
- controllo di import inutilizzati e riferimenti Tkinter residui;
- documentazione di installazione e avvio;
- checklist di test manuale.

## Comandi minimi

```bash
pytest tests/ -v
ruff check src/ tests/
ruff format --check src/ tests/
gnome-theme-manager gui
```

## Criteri di completamento

- test superati;
- nessun riferimento Tkinter non intenzionale;
- GUI avviabile su ambiente GNOME supportato;
- errori principali gestiti senza crash;
- documentazione aggiornata;
- diff limitato al task.

---

# Prompt di chiusura della fase 5

Esegui una revisione finale della Fase 5 senza aggiungere nuove funzionalità.

Verifica:

- coerenza tra CLI e GUI;
- assenza di Tkinter non intenzionale;
- separazione UI/backend;
- uso corretto del main thread GTK;
- operazioni lente non bloccanti;
- gestione errori e cancellazione;
- accessibilità minima dei controlli;
- comportamento responsive della navigazione;
- test, lint e documentazione.

Produci una tabella con colonne:

- area;
- stato;
- evidenza;
- problemi residui;
- priorità del fix.

Non implementare i fix durante questa revisione: elencali e attendi un task separato.
