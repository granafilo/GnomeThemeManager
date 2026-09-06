# SPDX-License-Identifier: GPL-3.0-or-later

"""Main entry point for executing the package with `python -m gnome_theme_manager`."""

import sys

from gnome_theme_manager.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
