# SPDX-License-Identifier: GPL-3.0-or-later

"""Entry point logico per l'interfaccia a riga di comando (CLI).

Questo modulo gestisce il routing dei comandi dell'utente (`current`, `list`, `apply`,
`install`, `uninstall`, `preset`), delegando interamente la logica di business alla
classe Facade `ThemeManager` e occupandosi esclusivamente dell'I/O con l'utente
(formattazione tabellare ASCII, messaggi di stato, gestione delle eccezioni).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from gnome_theme_manager import _

from ..core.errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from ..core.manager import ThemeManager
from ..core.models import ApplyResult, Theme, ThemeSet, ThemeType
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
        return _("Nessun elemento da mostrare.")

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(cell)))

    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    data_lines = [
        "| " + " | ".join(f"{cell!s:<{w}}" for cell, w in zip(row, col_widths)) + " |"
        for row in rows
    ]

    return "\n".join([separator, header_line, separator] + data_lines + [separator])


# -----------------------------------------------------------------------------
# Handlers per i singoli comandi CLI (consumano ThemeManager)
# -----------------------------------------------------------------------------


def handle_current_command(manager: ThemeManager) -> int:
    """Gestisce il comando `current` mostrando i temi attivi sul desktop."""
    current = manager.get_current_themes()
    status = manager.get_system_status()

    print(_("\nTemi attualmente attivi su GNOME:"))
    print(f"  {_('Tema GTK (Applicazioni)')}:  {current.gtk_theme or _('Non impostato')}")
    print(f"  {_('Tema Icone')}:               {current.icon_theme or _('Non impostato')}")
    print(f"  {_('Tema Cursori')}:             {current.cursor_theme or _('Non impostato')}")

    if status.shell_theme_supported:
        shell_val = current.shell_theme if current.shell_theme else _("Default di sistema")
        print(f"  {_('Tema GNOME Shell')}:         {shell_val}")
    else:
        print(_("  Tema GNOME Shell:         Non gestito (richiede estensione 'User Themes')"))

    if current.color_scheme:
        print(f"  {_('Schema Colori')}:            {current.color_scheme}")
    print()
    return 0


def handle_sandbox_status_command(manager: ThemeManager) -> int:
    """Gestisce il comando `sandbox-status` mostrando lo stato di Snap e Flatpak."""
    status = manager.get_system_status()
    sb = status.sandbox_status

    print(_("\n=== Stato Integrazione Sandbox (Snap & Flatpak) ==="))
    if sb is not None:
        snap_str = _("✅ Disponibile") if sb.snap_available else _("❌ Non disponibile")
        snap_themes_str = (
            _("✅ Installato") if sb.snap_gtk_common_themes_installed else _("❌ Non installato")
        )
        flatpak_str = _("✅ Disponibile") if sb.flatpak_available else _("❌ Non disponibile")
        flatpak_ov_str = _("✅ Attivo") if sb.flatpak_filesystem_override_active else _("❌ Non attivo")

        print(f"  Snap:    {snap_str:<16} | gtk-common-themes:   {snap_themes_str}")
        print(f"  Flatpak: {flatpak_str:<16} | Filesystem override: {flatpak_ov_str}")
    else:
        print(_("  Stato sandbox non disponibile."))
    print()
    return 0


def handle_list_command(manager: ThemeManager, theme_type: str, user_only: bool) -> int:
    """Gestisce il comando `list` scansionando e mostrando i temi disponibili.

    Args:
        manager: Istanza coordinatrice ThemeManager.
        theme_type: Tipologia di tema da elencare ('all', 'gtk', 'icon', 'cursor', 'shell').
        user_only: Se True, mostra esclusivamente i temi a livello utente.
    """
    t_type = ThemeType(theme_type) if theme_type != "all" else None
    themes: list[Theme] = manager.list_themes(theme_type=t_type, user_only=user_only)

    if not themes:
        print(_("\nNessun tema trovato per la tipologia '{theme_type}' (user_only={user_only}).\n").format(theme_type=theme_type, user_only=user_only))
        return 0

    headers = [_("NOME"), _("TIPO"), _("ORIGINE"), _("PERCORSO")]
    rows = [
        [
            t.name,
            t.theme_type.value,
            _("User") if t.is_user_level else _("System"),
            str(t.path),
        ]
        for t in themes
    ]

    print()
    print(format_table(headers, rows))
    print(_("\nTotale temi trovati: {count}\n").format(count=len(themes)))
    return 0


def _print_apply_result(result: ApplyResult, no_gtk4_override: bool = False) -> None:
    """Stampa un riepilogo leggibile dell'esito di applicazione temi all'utente."""
    print(_("\n✓ Modifiche applicate con successo:"))
    if result.gtk_theme:
        print(_("  - Tema GTK impostato su:         {theme}").format(theme=result.gtk_theme))
        if result.gtk4_override_applied:
            print(_("    └─ Override GTK4/Libadwaita applicato in ~/.config/gtk-4.0"))
        elif not no_gtk4_override:
            print(_("    └─ Nessun file GTK4 trovato nel tema (applicato solo a GTK2/GTK3)"))
    if result.icon_theme:
        print(_("  - Tema Icone impostato su:       {theme}").format(theme=result.icon_theme))
    if result.cursor_theme:
        print(_("  - Tema Cursori impostato su:     {theme}").format(theme=result.cursor_theme))
    if result.shell_theme:
        print(_("  - Tema GNOME Shell impostato su: {theme}").format(theme=result.shell_theme))
    if result.color_scheme:
        print(_("  - Schema Colori impostato su:    {scheme}").format(scheme=result.color_scheme))

    if result.sandbox_propagation:
        sb = result.sandbox_propagation
        if sb.flatpak_success:
            print(_("  - Propagazione Flatpak:          ✓ Accesso filesystem e variabili impostati"))
        if sb.snap_success and not sb.warnings:
            print(
                _("  - Propagazione Snap:             ✓ Compatibilità verificata con gtk-common-themes")
            )

    for warning in result.warnings:
        print(f"\n{_('[AVVISO]')} {warning}")
    print()


def handle_apply_command(
    manager: ThemeManager,
    gtk: str | None,
    icon: str | None,
    cursor: str | None,
    shell: str | None,
    color_scheme: str | None,
    no_gtk4_override: bool = False,
    theme: str | None = None,
    no_sandbox: bool = False,
) -> int:
    """Gestisce il comando `apply` validando l'esistenza dei temi e applicandoli.

    Args:
        manager: Istanza coordinatrice ThemeManager.
        gtk: Nome del tema GTK da applicare (opzionale).
        icon: Nome del tema di icone da applicare (opzionale).
        cursor: Nome del tema dei cursori da applicare (opzionale).
        shell: Nome del tema GNOME Shell da applicare (opzionale).
        color_scheme: Valore dello schema colori ('default' o 'prefer-dark', opzionale).
        no_gtk4_override: Se True, non applica l'override dei symlink in ~/.config/gtk-4.0.
        theme: Nome del tema unificato da applicare a GTK e Shell (opzionale).
        no_sandbox: Se True, non propaga i temi alle applicazioni Snap e Flatpak.
    """
    if not any([gtk, icon, cursor, shell, color_scheme, theme]):
        print(
            _("Errore: Specificare almeno un'opzione da applicare "
            "(--gtk, --theme, --icon, --cursor, --shell o --color-scheme)."),
            file=sys.stderr,
        )
        return 1

    if theme is not None:
        has_gtk = bool(manager.find_theme(theme, ThemeType.GTK))
        has_shell = bool(manager.find_theme(theme, ThemeType.SHELL))

        if not has_gtk and not has_shell:
            raise ThemeNotFoundError(
                _("Il tema '{theme}' non è stato trovato come GTK o GNOME Shell nel sistema.").format(theme=theme)
            )

        if has_gtk:
            gtk = theme
        if has_shell:
            shell = theme

    target_set = ThemeSet(
        gtk_theme=gtk,
        icon_theme=icon,
        cursor_theme=cursor,
        color_scheme=color_scheme,
        shell_theme=shell,
    )

    result = manager.apply_themes(
        target_set,
        apply_gtk4_override=not no_gtk4_override,
        propagate_sandbox=not no_sandbox,
    )
    _print_apply_result(result, no_gtk4_override=no_gtk4_override)
    return 0


def handle_install_command(
    manager: ThemeManager,
    archive_file: str,
    theme_type_str: str | None = None,
    custom_name: str | None = None,
    overwrite: bool = False,
    target_dir: str | Path | None = None,
) -> int:
    """Gestisce il comando `install` estraendo e installando temi da un archivio.

    Args:
        manager: Istanza coordinatrice ThemeManager.
        archive_file: Percorso del file archivio da installare.
        theme_type_str: Tipologia di tema opzionale ('gtk', 'icon', 'cursor', 'shell').
        custom_name: Nome personalizzato della cartella di destinazione.
        overwrite: Se True, sovrascrive eventuale tema esistente.
        target_dir: Destinazione di installazione ('xdg' per ~/.local/share, 'legacy' per ~/.themes e ~/.icons, o Path).
    """
    archive_path = Path(archive_file)
    theme_type = ThemeType(theme_type_str) if theme_type_str else None

    installed_themes = manager.install_theme_archive(
        archive_path=archive_path,
        theme_type=theme_type,
        custom_name=custom_name,
        overwrite=overwrite,
        target_dir=target_dir,
    )

    headers = [_("NOME TEMA"), _("TIPO"), _("PERCORSO INSTALLATO")]
    rows = [[t.name, t.theme_type.value, str(t.path)] for t in installed_themes]

    print(
        _("\n✓ Installazione completata con successo ({count} tema/i installato/i):").format(count=len(installed_themes))
    )
    print(format_table(headers, rows))
    print()
    return 0


def handle_uninstall_command(
    manager: ThemeManager,
    name: str,
    theme_type_str: str,
    assume_yes: bool = False,
) -> int:
    """Gestisce il comando `uninstall` per rimuovere temi utente.

    Args:
        manager: Istanza coordinatrice ThemeManager.
        name: Nome del tema da disinstallare.
        theme_type_str: Tipologia del tema ('gtk', 'icon', 'cursor', 'shell').
        assume_yes: Se True, disinstalla senza richiedere conferma interattiva.
    """
    theme_type = ThemeType(theme_type_str)

    if not assume_yes:
        confirm = (
            input(
                _("Sei sicuro di voler disinstallare il tema '{name}' ({type})? [s/N]: ").format(name=name, type=theme_type.value)
            )
            .strip()
            .lower()
        )
        if confirm not in ("s", "si", "y", "yes"):
            print(_("\nOperazione annullata dall'utente.\n"))
            return 0

    manager.uninstall_theme(name=name, theme_type=theme_type)
    print(_("\n✓ Tema '{name}' ({type}) disinstallato con successo.\n").format(name=name, type=theme_type.value))
    return 0


def handle_preset_command(manager: ThemeManager, args: argparse.Namespace) -> int:
    """Gestisce le azioni del comando `preset` (list, save, apply, delete).

    Args:
        manager: Istanza coordinatrice ThemeManager.
        args: Argomenti parsati della CLI.
    """
    action = getattr(args, "preset_action", None)

    if action == "list":
        presets = manager.list_presets()
        if not presets:
            print(_("\nNessun preset salvato.\n"))
            return 0

        rows = [[p] for p in presets]
        print(_("\nPreset salvati disponibili:"))
        print(format_table([_("NOME PRESET")], rows))
        print(_("\nTotale preset: {count}\n").format(count=len(presets)))
        return 0

    elif action == "save":
        saved_path = manager.save_current_as_preset(args.name, overwrite=args.overwrite)
        print(_("\n✓ Preset '{name}' salvato con successo in:\n  {path}\n").format(name=args.name, path=saved_path))
        return 0

    elif action == "apply":
        no_sb = getattr(args, "no_sandbox", False)
        result = manager.apply_preset(
            args.name,
            apply_gtk4_override=not args.no_gtk4_override,
            propagate_sandbox=not no_sb,
        )
        print(_("\n✓ Preset '{name}' applicato con successo:").format(name=args.name))
        _print_apply_result(result, no_gtk4_override=args.no_gtk4_override)
        return 0

    elif action == "delete":
        if not args.yes:
            confirm = (
                input(_("Sei sicuro di voler eliminare il preset '{name}'? [s/N]: ").format(name=args.name))
                .strip()
                .lower()
            )
            if confirm not in ("s", "si", "y", "yes"):
                print(_("\nOperazione annullata dall'utente.\n"))
                return 0

        manager.delete_preset(args.name)
        print(_("\n✓ Preset '{name}' eliminato con successo.\n").format(name=args.name))
        return 0

    else:
        print(
            _("Errore: Azione preset non specificata (usa 'list', 'save', 'apply' o 'delete')."),
            file=sys.stderr,
        )
        return 1


# -----------------------------------------------------------------------------
# Main Router
# -----------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Esegue l'interfaccia a riga di comando.

    Args:
        argv: Argomenti da linea di comando opzionali (usa sys.argv se None).

    Returns:
        Codice di uscita: 0 per successo, 1 per errori applicativi/GSettings.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        # Se è stato specificato il flag --gui o il subcomando 'gui', avvia la nuova GUI nativa GTK4/Libadwaita
        if getattr(args, "gui", False) or args.command == "gui":
            try:
                from ..gui_gtk import launch_gui as launch_gui_gtk
            except (ImportError, ModuleNotFoundError) as err:
                print(
                    _("\n[ERRORE GUI GTK4] GTK4/Libadwaita è richiesto per avviare l'interfaccia grafica. Dettagli: {err}\n"
                    "Installa le dipendenze richieste con:\n"
                    "    sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1\n").format(err=err),
                    file=sys.stderr,
                )
                return 1

            manager = ThemeManager()
            return launch_gui_gtk(manager=manager)

        if not args.command:
            parser.print_help()
            return 0

        manager = ThemeManager()

        if args.command == "current":
            return handle_current_command(manager)
        elif args.command == "sandbox-status":
            return handle_sandbox_status_command(manager)
        elif args.command == "list":
            return handle_list_command(manager, theme_type=args.type, user_only=args.user_only)
        elif args.command == "apply":
            return handle_apply_command(
                manager=manager,
                gtk=args.gtk,
                icon=args.icon,
                cursor=args.cursor,
                shell=args.shell,
                color_scheme=args.color_scheme,
                no_gtk4_override=args.no_gtk4_override,
                theme=args.theme,
                no_sandbox=getattr(args, "no_sandbox", False),
            )
        elif args.command == "install":
            target_dir = "legacy" if getattr(args, "legacy", False) else "xdg"
            return handle_install_command(
                manager=manager,
                archive_file=args.file,
                theme_type_str=args.type,
                custom_name=args.name,
                overwrite=args.overwrite,
                target_dir=target_dir,
            )
        elif args.command == "uninstall":
            return handle_uninstall_command(
                manager=manager,
                name=args.name,
                theme_type_str=args.type,
                assume_yes=args.yes,
            )
        elif args.command == "preset":
            return handle_preset_command(manager=manager, args=args)
        else:
            parser.print_help()
            return 0

    except KeyboardInterrupt:
        # Interruzione pulita dell'utente tramite Ctrl+C / SIGINT (exit code standard POSIX 130)
        return 130
    except GSettingsUnavailableError as err:
        print(f"\n{_('[ERRORE GSETTINGS]')} {err}\n", file=sys.stderr)
        return 1
    except ThemeNotFoundError as err:
        print(f"\n{_('[ERRORE TEMA]')} {err}\n", file=sys.stderr)
        return 1
    except ArchiveExtractionError as err:
        print(f"\n{_('[ERRORE ESTRAZIONE ARCHIVIO]')} {err}\n", file=sys.stderr)
        return 1
    except ThemeValidationError as err:
        print(f"\n{_('[ERRORE VALIDAZIONE TEMA]')} {err}\n", file=sys.stderr)
        return 1
    except FileExistsError as err:
        print(f"\n{_('[ERRORE FILE GIA ESISTENTE]')} {err}\n", file=sys.stderr)
        return 1
    except FileNotFoundError as err:
        print(f"\n{_('[ERRORE FILE NON TROVATO]')} {err}\n", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"\n{_('[ERRORE VALORE NON VALIDO]')} {err}\n", file=sys.stderr)
        return 1
    except GnomeThemeManagerError as err:
        print(f"\n{_('[ERRORE GNOME THEME MANAGER]')} {err}\n", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"\n{_('[ERRORE IMPREVISTO]')} {err}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
