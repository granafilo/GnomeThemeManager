"""Entry point logico per l'interfaccia a riga di comando (CLI).

Questo modulo gestisce il routing dei comandi dell'utente (`current`, `list`, `apply`),
interfacciandosi con il core (`ThemeScanner`, `GSettingsClient` e `GTK4ThemeLinker`) e gestendo
la formattazione dell'output e le eccezioni in modo elegante e pulito.
"""

from pathlib import Path
import sys
from typing import Optional, Sequence

from ..core.errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from ..core.gsettings import GSettingsClient
from ..core.gtk4_linker import GTK4ThemeLinker
from ..core.installer import ThemeInstaller
from ..core.models import Theme, ThemeSet, ThemeType
from ..core.scanner import ThemeScanner
from .args import create_parser



def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Formatta una lista di righe in una tabella ASCII pulita e allineata.

    Args:
        headers: Lista delle intestazioni delle colonne.
        rows: Lista di righe (ciascuna è una lista di stringhe corrispondenti alle colonne).

    Returns:
        Stringa formattata con bordi ASCII e spaziatura calcolata dinamicamente.
    """
    if not rows:
        return "Nessun elemento da mostrare."

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(cell)))

    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    data_lines = [
        "| " + " | ".join(f"{str(cell):<{w}}" for cell, w in zip(row, col_widths)) + " |"
        for row in rows
    ]

    return "\n".join([separator, header_line, separator] + data_lines + [separator])


# -----------------------------------------------------------------------------
# Handlers per i singoli comandi CLI
# -----------------------------------------------------------------------------


def handle_current_command() -> int:
    """Gestisce il comando `current` mostrando i temi attivi sul desktop."""
    client = GSettingsClient()
    current = client.get_current()

    print("\nTemi attualmente attivi su GNOME:")
    print(f"  Tema GTK (Applicazioni):  {current.gtk_theme or 'Non impostato'}")
    print(f"  Tema Icone:               {current.icon_theme or 'Non impostato'}")
    print(f"  Tema Cursori:             {current.cursor_theme or 'Non impostato'}")

    if client.is_shell_theme_supported:
        shell_val = current.shell_theme if current.shell_theme else "Default di sistema"
        print(f"  Tema GNOME Shell:         {shell_val}")
    else:
        print("  Tema GNOME Shell:         Non gestito (richiede estensione 'User Themes')")

    if current.color_scheme:
        print(f"  Schema Colori:            {current.color_scheme}")
    print()
    return 0


def handle_list_command(theme_type: str, user_only: bool) -> int:
    """Gestisce il comando `list` scansionando e mostrando i temi disponibili.

    Args:
        theme_type: Tipologia di tema da elencare ('all', 'gtk', 'icon', 'cursor', 'shell').
        user_only: Se True, mostra esclusivamente i temi a livello utente.
    """
    scanner = ThemeScanner()
    themes: list[Theme] = []

    if theme_type == "gtk":
        themes = scanner.scan_gtk_themes(user_only=user_only)
    elif theme_type == "icon":
        themes = scanner.scan_icon_themes(user_only=user_only)
    elif theme_type == "cursor":
        themes = scanner.scan_cursor_themes(user_only=user_only)
    elif theme_type == "shell":
        themes = scanner.scan_shell_themes(user_only=user_only)
    else:
        themes = scanner.scan_all(user_only=user_only)

    if not themes:
        print(f"\nNessun tema trovato per la tipologia '{theme_type}' (user_only={user_only}).\n")
        return 0

    themes.sort(key=lambda t: (t.theme_type.value, t.name.lower()))

    headers = ["NOME", "TIPO", "ORIGINE", "PERCORSO"]
    rows = [
        [
            t.name,
            t.theme_type.value,
            "User" if t.is_user_level else "System",
            str(t.path),
        ]
        for t in themes
    ]

    print()
    print(format_table(headers, rows))
    print(f"\nTotale temi trovati: {len(themes)}\n")
    return 0


def handle_apply_command(
    gtk: Optional[str],
    icon: Optional[str],
    cursor: Optional[str],
    shell: Optional[str],
    color_scheme: Optional[str],
    no_gtk4_override: bool = False,
) -> int:
    """Gestisce il comando `apply` validando l'esistenza dei temi e applicandoli.

    Args:
        gtk: Nome del tema GTK da applicare (opzionale).
        icon: Nome del tema di icone da applicare (opzionale).
        cursor: Nome del tema dei cursori da applicare (opzionale).
        shell: Nome del tema GNOME Shell da applicare (opzionale).
        color_scheme: Valore dello schema colori ('default' o 'prefer-dark', opzionale).
        no_gtk4_override: Se True, non applica l'override dei symlink in ~/.config/gtk-4.0.

    Raises:
        ThemeNotFoundError: Se uno dei temi specificati non esiste sul filesystem.
    """
    if not any([gtk, icon, cursor, shell, color_scheme]):
        print(
            "Errore: Specificare almeno un'opzione da applicare "
            "(--gtk, --icon, --cursor, --shell o --color-scheme).",
            file=sys.stderr,
        )
        return 1

    scanner = ThemeScanner()

    # 1. Validazione preventiva dell'esistenza dei temi richiesti
    found_gtk_theme: Optional[Theme] = None
    if gtk is not None:
        found_gtk_theme = scanner.find_theme(gtk, ThemeType.GTK)
        if not found_gtk_theme:
            raise ThemeNotFoundError(f"Il tema GTK '{gtk}' non è stato trovato nel sistema.")

    if icon is not None:
        found_icon = scanner.find_theme(icon, ThemeType.ICON)
        if not found_icon:
            raise ThemeNotFoundError(f"Il tema icone '{icon}' non è stato trovato nel sistema.")

    if cursor is not None:
        found_cursor = scanner.find_theme(cursor, ThemeType.CURSOR)
        if not found_cursor:
            raise ThemeNotFoundError(f"Il tema cursori '{cursor}' non è stato trovato nel sistema.")

    if shell is not None:
        found_shell = scanner.find_theme(shell, ThemeType.SHELL)
        if not found_shell:
            raise ThemeNotFoundError(f"Il tema GNOME Shell '{shell}' non è stato trovato nel sistema.")

    # 2. Applicazione tramite GSettingsClient
    client = GSettingsClient()
    new_theme_set = ThemeSet(
        gtk_theme=gtk,
        icon_theme=icon,
        cursor_theme=cursor,
        color_scheme=color_scheme,
        shell_theme=shell,
    )
    client.apply(new_theme_set)

    # 3. Override GTK4 / Libadwaita (se impostato un tema GTK e non disabilitato da flag)
    gtk4_applied = False
    if found_gtk_theme is not None and not no_gtk4_override:
        linker = GTK4ThemeLinker()
        gtk4_applied = linker.apply_override(found_gtk_theme.path)

    # 4. Notifica all'utente
    print("\n✓ Modifiche applicate con successo:")
    if gtk:
        print(f"  - Tema GTK impostato su:         {gtk}")
        if gtk4_applied:
            print("    └─ Override GTK4/Libadwaita applicato in ~/.config/gtk-4.0")
        elif not no_gtk4_override:
            print("    └─ Nessun file GTK4 trovato nel tema (applicato solo a GTK2/GTK3)")
    if icon:
        print(f"  - Tema Icone impostato su:       {icon}")
    if cursor:
        print(f"  - Tema Cursori impostato su:     {cursor}")
    if shell:
        print(f"  - Tema GNOME Shell impostato su: {shell}")
    if color_scheme:
        print(f"  - Schema Colori impostato su:    {color_scheme}")
    print()
    return 0


def handle_install_command(
    archive_file: str,
    theme_type_str: Optional[str] = None,
    custom_name: Optional[str] = None,
    overwrite: bool = False,
) -> int:
    """Gestisce il comando `install` estraendo e installando temi da un archivio.

    Args:
        archive_file: Percorso del file archivio da installare.
        theme_type_str: Tipologia di tema opzionale ('gtk', 'icon', 'cursor', 'shell').
        custom_name: Nome personalizzato della cartella di destinazione.
        overwrite: Se True, sovrascrive eventuale tema esistente.
    """
    archive_path = Path(archive_file)
    theme_type = ThemeType(theme_type_str) if theme_type_str else None

    installer = ThemeInstaller()
    installed_themes = installer.install(
        archive_path=archive_path,
        theme_type=theme_type,
        custom_name=custom_name,
        overwrite=overwrite,
    )

    headers = ["NOME TEMA", "TIPO", "PERCORSO INSTALLATO"]
    rows = [
        [t.name, t.theme_type.value, str(t.path)]
        for t in installed_themes
    ]

    print(f"\n✓ Installazione completata con successo ({len(installed_themes)} tema/i installato/i):")
    print(format_table(headers, rows))
    print()
    return 0


def handle_uninstall_command(
    name: str,
    theme_type_str: str,
    assume_yes: bool = False,
) -> int:
    """Gestisce il comando `uninstall` per rimuovere temi utente.

    Args:
        name: Nome del tema da disinstallare.
        theme_type_str: Tipologia del tema ('gtk', 'icon', 'cursor', 'shell').
        assume_yes: Se True, disinstalla senza richiedere conferma interattiva.
    """
    theme_type = ThemeType(theme_type_str)

    if not assume_yes:
        confirm = input(
            f"Sei sicuro di voler disinstallare il tema '{name}' ({theme_type.value})? [s/N]: "
        ).strip().lower()
        if confirm not in ("s", "si", "y", "yes"):
            print("\nOperazione annullata dall'utente.\n")
            return 0

    installer = ThemeInstaller()
    installer.uninstall(theme_name=name, theme_type=theme_type)

    print(f"\n✓ Tema '{name}' ({theme_type.value}) disinstallato con successo.\n")
    return 0


# -----------------------------------------------------------------------------
# Main Router
# -----------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Esegue l'interfaccia a riga di comando.

    Args:
        argv: Argomenti da linea di comando opzionali (usa sys.argv se None).

    Returns:
        Codice di uscita: 0 per successo, 1 per errori applicativi/GSettings.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "current":
            return handle_current_command()
        elif args.command == "list":
            return handle_list_command(theme_type=args.type, user_only=args.user_only)
        elif args.command == "apply":
            return handle_apply_command(
                gtk=args.gtk,
                icon=args.icon,
                cursor=args.cursor,
                shell=args.shell,
                color_scheme=args.color_scheme,
                no_gtk4_override=args.no_gtk4_override,
            )
        elif args.command == "install":
            return handle_install_command(
                archive_file=args.file,
                theme_type_str=args.type,
                custom_name=args.name,
                overwrite=args.overwrite,
            )
        elif args.command == "uninstall":
            return handle_uninstall_command(
                name=args.name,
                theme_type_str=args.type,
                assume_yes=args.yes,
            )
        else:
            parser.print_help()
            return 0

    except GSettingsUnavailableError as err:
        print(f"\n[ERRORE GSETTINGS] {err}\n", file=sys.stderr)
        return 1
    except ThemeNotFoundError as err:
        print(f"\n[ERRORE TEMA] {err}\n", file=sys.stderr)
        return 1
    except ArchiveExtractionError as err:
        print(f"\n[ERRORE ESTRAZIONE ARCHIVIO] {err}\n", file=sys.stderr)
        return 1
    except ThemeValidationError as err:
        print(f"\n[ERRORE VALIDAZIONE TEMA] {err}\n", file=sys.stderr)
        return 1
    except FileExistsError as err:
        print(f"\n[ERRORE FILE GIA ESISTENTE] {err}\n", file=sys.stderr)
        return 1
    except GnomeThemeManagerError as err:
        print(f"\n[ERRORE GNOME THEME MANAGER] {err}\n", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"\n[ERRORE IMPREVISTO] {err}\n", file=sys.stderr)
        return 1



if __name__ == "__main__":
    sys.exit(main())
