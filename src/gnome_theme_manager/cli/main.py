"""Entry point logico per l'interfaccia a riga di comando."""

import sys
from typing import Optional, Sequence
from .args import create_parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Esegue l'interfaccia a riga di comando.

    Args:
        argv: Argomenti da linea di comando opzionali (usa sys.argv se None).

    Returns:
        Codice di uscita (0 per successo, >0 per errore).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "current":
        print("Controllo temi attivi (Fase 1 in sviluppo)...")
    elif args.command == "list":
        print(f"Elenco temi ({args.type}) (Fase 1 in sviluppo)...")
    elif args.command == "apply":
        print("Applicazione temi (Fase 1 in sviluppo)...")
    elif args.command == "install":
        print(f"Installazione archivio {args.file} (Fase 2 in sviluppo)...")
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
