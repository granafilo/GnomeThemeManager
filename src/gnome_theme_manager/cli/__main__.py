# SPDX-License-Identifier: GPL-3.0-or-later

"""Entry point for direct execution with `python -m gnome_theme_manager.cli`."""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
