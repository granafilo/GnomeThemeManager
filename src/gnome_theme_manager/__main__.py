"""Entry point principale per l'esecuzione del package con `python -m gnome_theme_manager`."""

import sys

from gnome_theme_manager.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
