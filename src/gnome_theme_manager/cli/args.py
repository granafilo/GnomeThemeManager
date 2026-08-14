# SPDX-License-Identifier: GPL-3.0-or-later

"""Definizione e configurazione del parser argomenti CLI con argparse."""

import argparse

from gnome_theme_manager import _, __version__


def create_parser() -> argparse.ArgumentParser:
    """Crea e configura l'ArgumentParser principale per l'applicazione."""
    parser = argparse.ArgumentParser(
        prog="gnome-theme-manager",
        description=_("Manager modulare per temi GTK, icone, cursori e GNOME Shell."),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-g",
        "--gui",
        action="store_true",
        help=_("Avvia l'interfaccia grafica nativa GNOME GTK4/Libadwaita"),
    )

    subparsers = parser.add_subparsers(
        title=_("comandi"),
        dest="command",
        help=_("Comando da eseguire"),
    )

    # Subcomando: gui (GTK4/Libadwaita)
    subparsers.add_parser(
        "gui",
        help=_("Avvia l'interfaccia grafica nativa GNOME GTK4/Libadwaita"),
    )

    # Subcomando: current
    subparsers.add_parser(
        "current",
        help=_("Mostra i temi attualmente applicati sul desktop GNOME"),
    )

    # Subcomando: sandbox-status
    subparsers.add_parser(
        "sandbox-status",
        help=_("Mostra lo stato di integrazione con i runtime sandbox (Snap e Flatpak)"),
    )

    # Subcomando: list
    list_parser = subparsers.add_parser(
        "list",
        help=_("Elenca i temi disponibili nel sistema"),
    )
    list_parser.add_argument(
        "-t",
        "--type",
        choices=["all", "gtk", "icon", "cursor", "shell"],
        default="all",
        help=_("Filtra per tipologia di tema (default: all)"),
    )
    list_parser.add_argument(
        "--user-only",
        action="store_true",
        help=_("Mostra solo i temi installati a livello utente (~/.local/share/...)"),
    )

    # Subcomando: apply
    apply_parser = subparsers.add_parser(
        "apply",
        help=_("Applica uno o più temi su GNOME"),
    )
    apply_parser.add_argument(
        "--gtk",
        metavar="NOME",
        help=_("Nome del tema GTK da applicare"),
    )
    apply_parser.add_argument(
        "--theme",
        metavar="NOME",
        help=_(
            "Applica un tema unificato (GTK, Shell e override GTK4/Libadwaita) con lo stesso nome"
        ),
    )
    apply_parser.add_argument(
        "--icon",
        metavar="NOME",
        help=_("Nome del tema di icone da applicare"),
    )
    apply_parser.add_argument(
        "--cursor",
        metavar="NOME",
        help=_("Nome del tema dei cursori da applicare"),
    )
    apply_parser.add_argument(
        "--shell",
        metavar="NOME",
        help=_("Nome del tema per la GNOME Shell da applicare"),
    )
    apply_parser.add_argument(
        "--color-scheme",
        choices=["default", "prefer-dark"],
        help=_("Schema colore (default o prefer-dark per GNOME 42+)"),
    )
    apply_parser.add_argument(
        "--no-gtk4-override",
        action="store_true",
        help=_("Non applicare l'override GTK4 in ~/.config/gtk-4.0 quando si imposta un tema GTK"),
    )
    apply_parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help=_("Non propagare il tema alle app Snap/Flatpak"),
    )

    # Subcomando: install
    install_parser = subparsers.add_parser(
        "install",
        help=_("Installa un tema a partire da un file archivio (.zip, .tar.*)"),
    )
    install_parser.add_argument(
        "-f",
        "--file",
        required=True,
        metavar="PERCORSO",
        help=_("Percorso del file archivio da installare"),
    )
    install_parser.add_argument(
        "-t",
        "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        help=_("Tipo di tema (se non specificato, verrà effettuato il rilevamento automatico)"),
    )
    install_parser.add_argument(
        "-n",
        "--name",
        metavar="NOME",
        help=_("Nome personalizzato per la cartella di destinazione del tema"),
    )
    install_parser.add_argument(
        "-y",
        "--overwrite",
        action="store_true",
        help=_("Sovrascrive il tema se la cartella di destinazione esiste già"),
    )
    install_parser.add_argument(
        "--legacy",
        action="store_true",
        help=_(
            "Installa nel percorso legacy ~/.themes e ~/.icons invece dello standard XDG (~/.local/share/themes)"
        ),
    )

    # Subcomando: uninstall
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help=_("Disinstalla un tema specifico dalle directory utente"),
    )
    uninstall_parser.add_argument(
        "-n",
        "--name",
        required=True,
        metavar="NOME",
        help=_("Nome del tema da disinstallare"),
    )
    uninstall_parser.add_argument(
        "-t",
        "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        required=True,
        help=_("Tipo del tema da disinstallare"),
    )
    uninstall_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("Conferma la disinstallazione senza prompt interattivo"),
    )

    # Subcomando: preset
    preset_parser = subparsers.add_parser(
        "preset",
        help=_("Gestione di preset e profili di configurazione temi"),
    )
    preset_subparsers = preset_parser.add_subparsers(
        title=_("azioni preset"),
        dest="preset_action",
        help=_("Azione da eseguire sul preset"),
    )

    # preset list
    preset_subparsers.add_parser(
        "list",
        help=_("Elenca tutti i preset memorizzati"),
    )

    # preset save <nome> [--overwrite]
    save_parser = preset_subparsers.add_parser(
        "save",
        help=_("Salva la combinazione di temi corrente come nuovo preset"),
    )
    save_parser.add_argument(
        "name",
        metavar="NOME",
        help=_("Nome identificativo del preset da salvare"),
    )
    save_parser.add_argument(
        "-y",
        "--overwrite",
        action="store_true",
        help=_("Sovrascrive il preset se già esistente"),
    )

    # preset apply <nome> [--no-gtk4-override]
    apply_preset_parser = preset_subparsers.add_parser(
        "apply",
        help=_("Applica un preset salvato"),
    )
    apply_preset_parser.add_argument(
        "name",
        metavar="NOME",
        help=_("Nome del preset da applicare"),
    )
    apply_preset_parser.add_argument(
        "--no-gtk4-override",
        action="store_true",
        help=_("Non applicare l'override GTK4 in ~/.config/gtk-4.0"),
    )
    apply_preset_parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help=_("Non propagare il tema alle app Snap/Flatpak"),
    )

    # preset delete <nome> [-y]
    delete_preset_parser = preset_subparsers.add_parser(
        "delete",
        help=_("Elimina un preset memorizzato"),
    )
    delete_preset_parser.add_argument(
        "name",
        metavar="NOME",
        help=_("Nome del preset da eliminare"),
    )
    delete_preset_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("Conferma l'eliminazione senza prompt interattivo"),
    )

    return parser
