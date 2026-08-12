"""Definizione e configurazione del parser argomenti CLI con argparse."""

import argparse
from gnome_theme_manager import __version__


def create_parser() -> argparse.ArgumentParser:
    """Crea e configura l'ArgumentParser principale per l'applicazione."""
    parser = argparse.ArgumentParser(
        prog="gnome-theme-manager",
        description="Manager modulare per temi GTK, icone e cursori su GNOME.",
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
        choices=["all", "gtk", "icon", "cursor"],
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
        choices=["gtk", "icon", "cursor"],
        help="Tipo di tema (se non specificato, verrà effettuato il rilevamento automatico)",
    )

    return parser
