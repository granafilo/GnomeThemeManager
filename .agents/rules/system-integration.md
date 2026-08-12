---
trigger: always_on
---

Per il filesystem:

    Usa pathlib.Path invece di os.path dove possibile.

    Espandi sempre ~ con Path.home() o Path.expanduser().

    Lavora di default su directory utente:

        ~/.local/share/themes

        ~/.local/share/icons

        (eventualmente ~/.icons per compatibilità).

Per GNOME/GSettings:

    Usa gi.repository.Gio (PyGObject) per leggere/scrivere org.gnome.desktop.interface.

    Chiavi principali da gestire:

        gtk-theme

        icon-theme

        cursor-theme

    Incapsula tutta l’interazione con GSettings in un modulo dedicato (gsettings_client.py).

    Prevedi fallback o messaggi chiari se lo schema non è disponibile (es. ambiente non GNOME).