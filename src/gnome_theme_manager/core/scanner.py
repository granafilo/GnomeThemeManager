# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo per la scansione del filesystem e il rilevamento dei temi installati.

Questo modulo implementa la classe `ThemeScanner`, responsabile di esplorare
le directory standard di GNOME (sia a livello utente che di sistema) per individuare:
- Temi per i controlli grafici delle finestre (GTK 2/3/4)
- Set di icone
- Temi per i cursori del mouse
- Temi per la GNOME Shell (pannello superiore, dock e menu di sistema)

Regole di business applicate:
1. Precedenza: i temi utente (~/.local/share/...) hanno priorità su quelli di sistema (/usr/share/...).
2. Cartelle ibride: directory in 'icons/' contenenti sia icone che cursori vengono registrate per entrambi i tipi.
3. Temi Shell: cartelle in 'themes/' contenenti 'gnome-shell/' vengono registrate per ThemeType.SHELL.
"""

from pathlib import Path

from .constants import (
    get_system_icons_dirs,
    get_system_themes_dirs,
    get_user_icons_dirs,
    get_user_themes_dirs,
)
from .models import Theme, ThemeType


class ThemeScanner:
    """Scanner per il rilevamento di temi GTK, icone, cursori e Shell nel filesystem.

    Esplora le directory utente e di sistema fornite (o quelle predefinite di GNOME)
    e identifica i temi validi mediante euristiche basate sulla presenza di file
    e sottocartelle caratteristiche (come 'gtk-3.0', 'cursors', 'gnome-shell', 'index.theme').
    """

    def __init__(
        self,
        user_theme_dirs: list[Path] | None = None,
        user_icon_dirs: list[Path] | None = None,
        system_theme_dirs: list[Path] | None = None,
        system_icon_dirs: list[Path] | None = None,
    ) -> None:
        """Inizializza lo scanner con i percorsi da analizzare.

        Se non vengono specificati percorsi personalizzati, vengono risolti
        dinamicamente i percorsi standard XDG e legacy.

        Args:
            user_theme_dirs: Lista di percorsi delle directory temi utente.
            user_icon_dirs: Lista di percorsi delle directory icone/cursori utente.
            system_theme_dirs: Lista di percorsi delle directory temi di sistema.
            system_icon_dirs: Lista di percorsi delle directory icone/cursori di sistema.
        """
        self.user_theme_dirs = (
            user_theme_dirs if user_theme_dirs is not None else get_user_themes_dirs()
        )
        self.user_icon_dirs = (
            user_icon_dirs if user_icon_dirs is not None else get_user_icons_dirs()
        )
        self.system_theme_dirs = (
            system_theme_dirs if system_theme_dirs is not None else get_system_themes_dirs()
        )
        self.system_icon_dirs = (
            system_icon_dirs if system_icon_dirs is not None else get_system_icons_dirs()
        )

    # -------------------------------------------------------------------------
    # Metodi di Scansione Pubblici
    # -------------------------------------------------------------------------

    def scan_gtk_themes(self, user_only: bool = False) -> list[Theme]:
        """Scansiona e restituisce tutti i temi GTK disponibili.

        Args:
            user_only: Se True, limita la ricerca alle directory utente (~/.local/share/themes, ecc.).

        Returns:
            Lista di oggetti Theme di tipo GTK, senza duplicati (precedenza Utente > Sistema).
        """
        return self._scan_themes_by_type(ThemeType.GTK, user_only=user_only)

    def scan_icon_themes(self, user_only: bool = False) -> list[Theme]:
        """Scansiona e restituisce tutti i set di icone disponibili.

        Args:
            user_only: Se True, limita la ricerca alle directory utente.

        Returns:
            Lista di oggetti Theme di tipo ICON, senza duplicati.
        """
        return self._scan_themes_by_type(ThemeType.ICON, user_only=user_only)

    def scan_cursor_themes(self, user_only: bool = False) -> list[Theme]:
        """Scansiona e restituisce tutti i temi per cursori disponibili.

        Args:
            user_only: Se True, limita la ricerca alle directory utente.

        Returns:
            Lista di oggetti Theme di tipo CURSOR, senza duplicati.
        """
        return self._scan_themes_by_type(ThemeType.CURSOR, user_only=user_only)

    def scan_shell_themes(self, user_only: bool = False) -> list[Theme]:
        """Scansiona e restituisce tutti i temi GNOME Shell disponibili.

        Args:
            user_only: Se True, limita la ricerca alle directory utente.

        Returns:
            Lista di oggetti Theme di tipo SHELL, senza duplicati.
        """
        return self._scan_themes_by_type(ThemeType.SHELL, user_only=user_only)

    def scan_all(self, user_only: bool = False) -> list[Theme]:
        """Scansiona e restituisce tutti i temi rilevati (GTK, icone, cursori e Shell).

        Args:
            user_only: Se True, limita la ricerca alle directory utente.

        Returns:
            Lista completa di oggetti Theme rilevati.
        """
        all_themes: list[Theme] = []
        all_themes.extend(self.scan_gtk_themes(user_only=user_only))
        all_themes.extend(self.scan_icon_themes(user_only=user_only))
        all_themes.extend(self.scan_cursor_themes(user_only=user_only))
        all_themes.extend(self.scan_shell_themes(user_only=user_only))
        return all_themes

    def find_theme(self, name: str, theme_type: ThemeType) -> Theme | None:
        """Cerca un tema specifico per nome e tipologia.

        La ricerca rispetta la regola di precedenza (se il tema esiste sia a livello
        utente che di sistema, viene restituito quello utente).

        Args:
            name: Il nome esatto della cartella del tema (es. 'Adwaita', 'Nordic').
            theme_type: La tipologia di tema cercata (ThemeType.GTK, ICON, CURSOR o SHELL).

        Returns:
            L'oggetto Theme trovato oppure None se il tema non esiste.
        """
        available_themes = self._scan_themes_by_type(theme_type, user_only=False)

        for theme in available_themes:
            if theme.name == name:
                return theme

        # Fallback case-insensitive
        for theme in available_themes:
            if theme.name.lower() == name.lower():
                return theme

        return None

    # -------------------------------------------------------------------------
    # Metodi Interni di Scansione ed Euristica
    # -------------------------------------------------------------------------

    def _scan_themes_by_type(self, target_type: ThemeType, user_only: bool = False) -> list[Theme]:
        """Esegue la scansione per una specifica tipologia di tema applicando le precedenze.

        Args:
            target_type: Tipologia di tema da cercare (GTK, ICON, CURSOR, SHELL).
            user_only: Se True, salta l'analisi delle cartelle di sistema.

        Returns:
            Lista di oggetti Theme univoci per la tipologia specificata.
        """
        themes: list[Theme] = []
        seen_names: set[str] = set()

        # Determiniamo quali cartelle sorgente analizzare
        if target_type in (ThemeType.GTK, ThemeType.SHELL):
            user_dirs = self.user_theme_dirs
            system_dirs = self.system_theme_dirs
        else:
            user_dirs = self.user_icon_dirs
            system_dirs = self.system_icon_dirs

        # 1. Scansione directory utente (priorità alta)
        for base_dir in user_dirs:
            for theme in self._scan_directory(base_dir, is_user_level=True):
                if theme.theme_type == target_type and theme.name not in seen_names:
                    seen_names.add(theme.name)
                    themes.append(theme)

        # 2. Scansione directory di sistema (priorità secondaria, solo se non user_only)
        if not user_only:
            for base_dir in system_dirs:
                for theme in self._scan_directory(base_dir, is_user_level=False):
                    if theme.theme_type == target_type and theme.name not in seen_names:
                        seen_names.add(theme.name)
                        themes.append(theme)

        return themes

    def _scan_directory(self, directory: Path, is_user_level: bool) -> list[Theme]:
        """Esplora una singola cartella alla ricerca di temi validi.

        Args:
            directory: Percorso della directory genitore (es. /usr/share/themes).
            is_user_level: Flag che indica se si tratta di un percorso utente.

        Returns:
            Lista di oggetti Theme individuati all'interno della directory.
        """
        import configparser

        found_themes: list[Theme] = []

        if not directory.exists() or not directory.is_dir():
            return found_themes

        try:
            entries = list(directory.iterdir())
        except (PermissionError, OSError):
            return found_themes

        for entry in entries:
            if not entry.is_dir():
                continue

            index_file = entry / "index.theme"
            invalid = False
            inherits_str = ""

            # Se c'è un file index.theme, proviamo a parsarlo per caricare metadati ed ereditarietà
            if index_file.is_file():
                config = configparser.ConfigParser(interpolation=None)
                try:
                    config.read(index_file, encoding="utf-8")
                    if config.has_section("Desktop Entry"):
                        inherits_str = config.get("Desktop Entry", "Inherits", fallback="")
                    elif config.has_section("Icon Theme"):
                        inherits_str = config.get("Icon Theme", "Inherits", fallback="")
                    elif config.has_section("X-GNOME-Metatheme"):
                        inherits_str = config.get("X-GNOME-Metatheme", "Inherits", fallback="")
                except Exception:
                    invalid = True

            # Calcolo ricorsivo della catena di ereditarietà (max depth 5)
            inheritance_chain: list[str] = []
            curr_inherits = inherits_str
            depth = 0

            while curr_inherits and depth < 4:
                # split e strip nel caso di valori multipli separati da virgola
                parents = [p.strip() for p in curr_inherits.split(",") if p.strip()]
                if not parents:
                    break

                # Aggiungiamo tutti i genitori trovati in questo livello
                for p in parents:
                    if p not in inheritance_chain:
                        inheritance_chain.append(p)

                # Cerchiamo il file index.theme del primo genitore per continuare la catena
                next_parent = parents[0]
                parent_path = None

                # Cerca nelle directory note per trovare il percorso del tema genitore
                for d in (
                    self.user_theme_dirs
                    + self.system_theme_dirs
                    + self.user_icon_dirs
                    + self.system_icon_dirs
                ):
                    candidate = d / next_parent
                    if candidate.is_dir():
                        parent_path = candidate
                        break

                if parent_path and (parent_path / "index.theme").is_file():
                    parent_config = configparser.ConfigParser(interpolation=None)
                    try:
                        parent_config.read(parent_path / "index.theme", encoding="utf-8")
                        next_inherits = ""
                        if parent_config.has_section("Desktop Entry"):
                            next_inherits = parent_config.get(
                                "Desktop Entry", "Inherits", fallback=""
                            )
                        elif parent_config.has_section("Icon Theme"):
                            next_inherits = parent_config.get("Icon Theme", "Inherits", fallback="")
                        elif parent_config.has_section("X-GNOME-Metatheme"):
                            next_inherits = parent_config.get(
                                "X-GNOME-Metatheme", "Inherits", fallback=""
                            )
                        curr_inherits = next_inherits
                    except Exception:
                        break
                else:
                    break
                depth += 1

            # Rilevamento delle tipologie supportate
            is_gtk = self._is_gtk_theme(entry)
            is_cursor = self._is_cursor_theme(entry)
            is_icon = self._is_icon_theme(entry)
            is_shell = self._is_shell_theme(entry)

            # Se l'index.theme è corrotto o non riconosce tipologie ma il file index.theme esiste comunque,
            # consideriamolo GTK o ICON con flag invalid=True per non scartarlo
            if not (is_gtk or is_cursor or is_icon or is_shell) and index_file.is_file():
                invalid = True
                is_gtk = True  # Fallback di classificazione

            # Registrazione temi trovati
            if is_gtk:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.GTK,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_icon:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.ICON,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_cursor:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.CURSOR,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_shell:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.SHELL,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )

        return found_themes

    # -------------------------------------------------------------------------
    # Euristiche di Riconoscimento Temi
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_gtk_theme(path: Path) -> bool:
        """Verifica se una directory contiene un tema GTK valido."""
        gtk_subdirs = ["gtk-4.0", "gtk-3.0", "gtk-3.20", "gtk-2.0"]
        for subdir in gtk_subdirs:
            if (path / subdir).is_dir():
                return True

        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if (
                    "GtkTheme" in content
                    or "[Desktop Entry]" in content
                    or "[X-GNOME-Metatheme]" in content
                ):
                    return True
            except OSError:
                pass

        return False

    @staticmethod
    def _is_shell_theme(path: Path) -> bool:
        """Verifica se una directory contiene un tema per GNOME Shell.

        La presenza della cartella 'gnome-shell' (tipicamente contenente 'gnome-shell.css')
        identifica un tema per la Shell di GNOME.
        """
        shell_dir = path / "gnome-shell"
        if shell_dir.is_dir():
            return True

        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if "[Shell Theme]" in content or "ShellTheme" in content:
                    return True
            except OSError:
                pass

        return False

    @staticmethod
    def _is_cursor_theme(path: Path) -> bool:
        """Verifica se una directory contiene un tema per cursori valido."""
        cursors_dir = path / "cursors"
        return cursors_dir.is_dir()

    @staticmethod
    def _is_icon_theme(path: Path) -> bool:
        """Verifica se una directory contiene un set di icone valido."""
        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if "[Icon Theme]" in content or "Directories=" in content:
                    return True
            except OSError:
                pass

        icon_subdirs = [
            "scalable",
            "symbolic",
            "16x16",
            "22x22",
            "24x24",
            "32x32",
            "48x48",
            "64x64",
            "128x128",
            "256x256",
            "512x512",
        ]
        for subdir in icon_subdirs:
            if (path / subdir).is_dir():
                return True

        return False
