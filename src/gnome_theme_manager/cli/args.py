"""Definizione e configurazione del parser argomenti CLI con argparse."""

import argparse
from gnome_theme_manager import __version__


def create_parser() -> argparse.ArgumentParser:
    """Crea e configura l'ArgumentParser principale per l'applicazione."""
    parser = argparse.ArgumentParser(
        prog="gnome-theme-manager",
        description="Manager modulare per temi GTK, icone, cursori e GNOME Shell.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        title="comandi",
        dest="command",
        help="Comando da eseguire",
    )

    # Subcomando: current
    subparsers.add_parser(
        "current",
        help="Mostra i temi attualmente applicati sul desktop GNOME",
    )

    # Subcomando: list
    list_parser = subparsers.add_parser(
        "list",
        help="Elenca i temi disponibili nel sistema",
    )
    list_parser.add_argument(
        "-t", "--type",
        choices=["all", "gtk", "icon", "cursor", "shell"],
        default="all",
        help="Filtra per tipologia di tema (default: all)",
    )
    list_parser.add_argument(
        "--user-only",
        action="store_true",
        help="Mostra solo i temi installati a livello utente (~/.local/share/...)",
    )

    # Subcomando: apply
    apply_parser = subparsers.add_parser(
        "apply",
        help="Applica uno o più temi su GNOME",
    )
    apply_parser.add_argument(
        "--gtk",
        metavar="NOME",
        help="Nome del tema GTK da applicare",
    )
    apply_parser.add_argument(
        "--icon",
        metavar="NOME",
        help="Nome del tema di icone da applicare",
    )
    apply_parser.add_argument(
        "--cursor",
        metavar="NOME",
        help="Nome del tema dei cursori da applicare",
    )
    apply_parser.add_argument(
        "--shell",
        metavar="NOME",
        help="Nome del tema per la GNOME Shell da applicare",
    )
    apply_parser.add_argument(
        "--color-scheme",
        choices=["default", "prefer-dark"],
        help="Schema colore (default o prefer-dark per GNOME 42+)",
    )
    apply_parser.add_argument(
        "--no-gtk4-override",
        action="store_true",
        help="Non applicare l'override GTK4 in ~/.config/gtk-4.0 quando si imposta un tema GTK",
    )

    # Subcomando: install
    install_parser = subparsers.add_parser(
        "install",
        help="Installa un tema a partire da un file archivio (.zip, .tar.*)",
    )
    install_parser.add_argument(
        "-f", "--file",
        required=True,
        metavar="PERCORSO",
        help="Percorso del file archivio da installare",
    )
    install_parser.add_argument(
        "-t", "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        help="Tipo di tema (se non specificato, verrà effettuato il rilevamento automatico)",
    )
    install_parser.add_argument(
        "-n", "--name",
        metavar="NOME",
        help="Nome personalizzato per la cartella di destinazione del tema",
    )
    install_parser.add_argument(
        "-y", "--overwrite",
        action="store_true",
        help="Sovrascrive il tema se la cartella di destinazione esiste già",
    )

    # Subcomando: uninstall
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Disinstalla un tema specifico dalle directory utente",
    )
    uninstall_parser.add_argument(
        "-n", "--name",
        required=True,
        metavar="NOME",
        help="Nome del tema da disinstallare",
    )
    uninstall_parser.add_argument(
        "-t", "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        required=True,
        help="Tipo del tema da disinstallare",
    )
    uninstall_parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Conferma la disinstallazione senza prompt interattivo",
    )

    return parser

