"""Modulo GUI Tkinter (Prototipo Fase 4).

Questo package fornisce l'interfaccia grafica desktop sviluppata con Tkinter e TTK.
"""

try:
    from .app import ThemeManagerWindow, launch_gui

    __all__ = ["ThemeManagerWindow", "launch_gui"]
except (ImportError, ModuleNotFoundError):
    # Consente l'ispezione del package anche se python3-tk non è ancora installato nel sistema
    ThemeManagerWindow = None  # type: ignore
    launch_gui = None  # type: ignore
    __all__ = ["ThemeManagerWindow", "launch_gui"]
