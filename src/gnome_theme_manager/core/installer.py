"""Modulo per l'estrazione sicura, la validazione e l'installazione di temi da archivi.

Questo modulo implementa la logica per:
1. Estrazione sicura di archivi (.zip, .tar.*) prevenendo attacchi Path Traversal / Zip Slip.
2. Ispezione della struttura interna dell'archivio (layout flat, single-root o multi-root).
3. Riconoscimento automatico del tipo di tema (GTK, Shell, Icone, Cursori).
4. Installazione e disinstallazione limitata all'ambito utente (~/.local/share/...).
"""

import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from typing import Optional, Sequence
import zipfile

from .constants import USER_ICONS_DIRS, USER_THEMES_DIRS
from .errors import ArchiveExtractionError, ThemeNotFoundError, ThemeValidationError
from .models import Theme, ThemeType


def safe_extract(archive_path: Path, target_dir: Path) -> Path:
    """Estrae in modo sicuro un archivio (.zip, .tar.*) all'interno di target_dir.

    Esegue verifiche anti-Path Traversal / Zip Slip per garantire che nessun file
    venga estratto al di fuori della directory temporanea di destinazione.

    Args:
        archive_path: Percorso del file archivio da decomprimere.
        target_dir: Directory di destinazione sicura.

    Returns:
        Il percorso target_dir in cui l'archivio è stato estratto.

    Raises:
        ArchiveExtractionError: Se il file non esiste, ha un formato non supportato,
            è corrotto o contiene percorsi malevoli (Path Traversal attempt).
    """
    archive_path = Path(archive_path)
    target_dir = Path(target_dir).resolve()

    if not archive_path.exists() or not archive_path.is_file():
        raise ArchiveExtractionError(f"Il file archivio '{archive_path}' non esiste o non è un file valido.")

    filename_lower = archive_path.name.lower()

    if filename_lower.endswith(".zip"):
        _extract_zip(archive_path, target_dir)
    elif (
        filename_lower.endswith(".tar.gz")
        or filename_lower.endswith(".tgz")
        or filename_lower.endswith(".tar.xz")
        or filename_lower.endswith(".txz")
        or filename_lower.endswith(".tar.bz2")
        or filename_lower.endswith(".tbz2")
        or filename_lower.endswith(".tar")
    ):
        _extract_tar(archive_path, target_dir)
    else:
        raise ArchiveExtractionError(
            f"Formato archivio non supportato per '{archive_path.name}'. "
            "Formati supportati: .zip, .tar.gz, .tar.xz, .tar.bz2, .tar"
        )

    return target_dir


def _is_within_directory(directory: Path, target: Path) -> bool:
    """Verifica se il percorso target risiede all'interno della directory specificata."""
    try:
        target.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _extract_zip(archive_path: Path, target_dir: Path) -> None:
    """Estrae un archivio ZIP eseguendo controlli di sicurezza anti-Zip Slip."""
    try:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                member_path = target_dir / member.filename
                if not _is_within_directory(target_dir, member_path):
                    raise ArchiveExtractionError(
                        f"Rilevato tentativo di Path Traversal nell'archivio ZIP: '{member.filename}'"
                    )
            zip_ref.extractall(target_dir)
    except zipfile.BadZipFile as err:
        raise ArchiveExtractionError(f"File ZIP non valido o corrotto '{archive_path.name}': {err}") from err
    except ArchiveExtractionError:
        raise
    except Exception as err:
        raise ArchiveExtractionError(f"Errore durante l'estrazione dell'archivio ZIP '{archive_path.name}': {err}") from err


def _extract_tar(archive_path: Path, target_dir: Path) -> None:
    """Estrae un archivio TAR eseguendo controlli di sicurezza anti-Path Traversal."""
    try:
        with tarfile.open(archive_path, "r:*") as tar_ref:
            for member in tar_ref.getmembers():
                member_path = target_dir / member.name
                if not _is_within_directory(target_dir, member_path):
                    raise ArchiveExtractionError(
                        f"Rilevato tentativo di Path Traversal nell'archivio TAR: '{member.name}'"
                    )

            if hasattr(tarfile, "data_filter"):
                tar_ref.extractall(target_dir, filter="data")
            else:
                tar_ref.extractall(target_dir)
    except ArchiveExtractionError:
        raise
    except tarfile.TarError as err:
        raise ArchiveExtractionError(f"File TAR non valido o corrotto '{archive_path.name}': {err}") from err
    except Exception as err:
        raise ArchiveExtractionError(f"Errore durante l'estrazione dell'archivio TAR '{archive_path.name}': {err}") from err



def detect_theme_types(theme_dir: Path) -> list[ThemeType]:
    """Auto-rileva le tipologie di tema presenti in una directory.

    Args:
        theme_dir: Directory di un tema estratto.

    Returns:
        Lista di ThemeType rilevati per la directory.
    """
    detected: list[ThemeType] = []

    # 1. Controllo GTK Theme
    gtk_subdirs = ["gtk-2.0", "gtk-3.0", "gtk-4.0"]
    has_gtk_dir = any((theme_dir / sub).is_dir() for sub in gtk_subdirs)
    index_theme = theme_dir / "index.theme"

    is_gtk = has_gtk_dir
    if index_theme.is_file() and not is_gtk:
        try:
            content = index_theme.read_text(encoding="utf-8", errors="ignore")
            if "[Desktop Entry]" in content or "[GtkTheme]" in content:
                is_gtk = True
        except Exception:
            pass

    if is_gtk:
        detected.append(ThemeType.GTK)

    # 2. Controllo GNOME Shell Theme
    shell_css = theme_dir / "gnome-shell" / "gnome-shell.css"
    if shell_css.is_file() or (theme_dir / "gnome-shell").is_dir():
        detected.append(ThemeType.SHELL)

    # 3. Controllo Cursori
    if (theme_dir / "cursors").is_dir():
        detected.append(ThemeType.CURSOR)

    # 4. Controllo Icone
    is_icon = False
    if index_theme.is_file():
        try:
            content = index_theme.read_text(encoding="utf-8", errors="ignore")
            if "[Icon Theme]" in content:
                is_icon = True
        except Exception:
            pass

    if not is_icon and not (theme_dir / "cursors").is_dir():
        icon_subdirs = ["scalable", "16x16", "22x22", "24x24", "32x32", "48x48", "64x64", "128x128", "256x256", "512x512"]
        if any((theme_dir / sub).is_dir() for sub in icon_subdirs):
            is_icon = True

    if is_icon and ThemeType.ICON not in detected:
        detected.append(ThemeType.ICON)

    return detected


def inspect_extracted_tree(
    extracted_root: Path, fallback_name: str
) -> list[tuple[str, Path, ThemeType]]:
    """Ispeziona l'albero di file estratti per identificare temi e relative tipologie.

    Gestisce:
    - Layout flat (i file di configurazione sono direttamente in extracted_root).
    - Layout a radice singola (es. NomeTema/gtk-3.0/...).
    - Layout multi-tema (più sottodirectory ciascuna contenente un tema).

    Args:
        extracted_root: Percorso radice di estrazione dell'archivio.
        fallback_name: Nome da assegnare al tema in caso di layout flat.

    Returns:
        Lista di tuple (nome_tema, percorso_directory, tipo_tema).

    Raises:
        ThemeValidationError: Se l'archivio non contiene alcuna struttura di tema valida.
    """
    targets: list[tuple[str, Path, ThemeType]] = []

    # 1. Verifica layout flat direttamente sulla radice estratta
    flat_types = detect_theme_types(extracted_root)
    if flat_types:
        for t_type in flat_types:
            targets.append((fallback_name, extracted_root, t_type))
        return targets

    # 2. Esplora sottodirectory (singola radice o multi-tema)
    subdirs = [
        p for p in extracted_root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "__MACOSX"
    ]

    for sub in subdirs:
        sub_types = detect_theme_types(sub)
        if sub_types:
            for t_type in sub_types:
                targets.append((sub.name, sub, t_type))
        else:
            # Controllo eventuale annidamento ulteriore (es. Archive/NestedFolder/ThemeFolder)
            nested_dirs = [
                n for n in sub.iterdir()
                if n.is_dir() and not n.name.startswith(".") and n.name != "__MACOSX"
            ]
            for nested in nested_dirs:
                nested_types = detect_theme_types(nested)
                for t_type in nested_types:
                    targets.append((nested.name, nested, t_type))

    if not targets:
        raise ThemeValidationError(
            f"L'archivio non contiene una struttura di tema riconosciuta (GTK, Shell, Icone o Cursori)."
        )

    return targets


class ThemeInstaller:
    """Gestisce l'installazione e la disinstallazione sicura dei temi utente."""

    def __init__(
        self,
        user_themes_dir: Optional[Path] = None,
        user_icons_dir: Optional[Path] = None,
    ) -> None:
        """Inizializza l'installer con i percorsi di destinazione utente.

        Args:
            user_themes_dir: Directory utente per temi GTK e Shell (default: ~/.local/share/themes).
            user_icons_dir: Directory utente per temi Icone e Cursori (default: ~/.local/share/icons).
        """
        self.user_themes_dir = (
            Path(user_themes_dir).expanduser()
            if user_themes_dir
            else USER_THEMES_DIRS[0]
        )
        self.user_icons_dir = (
            Path(user_icons_dir).expanduser()
            if user_icons_dir
            else USER_ICONS_DIRS[0]
        )

    def install(
        self,
        archive_path: Path,
        theme_type: Optional[ThemeType] = None,
        custom_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> list[Theme]:
        """Estrae, valida e installa uno o più temi da un archivio nelle directory utente.

        Args:
            archive_path: Percorso del file archivio (.zip, .tar.*).
            theme_type: Tipo di tema opzionale per filtrare o forzare un tipo specifico.
            custom_name: Nome personalizzato per la cartella di destinazione.
            overwrite: Se True, sovrascrive il tema se già esistente.

        Returns:
            Lista delle istanze Theme installate con successo.

        Raises:
            ArchiveExtractionError: Se l'estrazione fallisce o in caso di minaccia di sicurezza.
            ThemeValidationError: Se la struttura dell'archivio non è valida o non compatibile.
            FileExistsError: Se il tema esiste già e overwrite=False.
        """
        archive_path = Path(archive_path)
        fallback_name = custom_name or archive_path.name
        for ext in [".tar.gz", ".tar.xz", ".tar.bz2", ".tgz", ".txz", ".tbz2", ".zip", ".tar"]:
            if fallback_name.lower().endswith(ext):
                fallback_name = fallback_name[:-len(ext)]
                break

        installed_themes: list[Theme] = []

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            safe_extract(archive_path, tmp_dir)

            targets = inspect_extracted_tree(tmp_dir, fallback_name=fallback_name)

            if theme_type is not None:
                filtered = [t for t in targets if t[2] == theme_type]
                if not filtered:
                    raise ThemeValidationError(
                        f"L'archivio non contiene un tema compatibile con il tipo richiesto '{theme_type.value}'."
                    )
                targets = filtered

            if custom_name and len({t[1] for t in targets}) == 1:
                targets = [(custom_name, t[1], t[2]) for t in targets]

            processed_dirs: set[tuple[str, Path]] = set()

            for name, source_dir, t_type in targets:
                target_base_dir = (
                    self.user_themes_dir
                    if t_type in (ThemeType.GTK, ThemeType.SHELL)
                    else self.user_icons_dir
                )
                dest_dir = target_base_dir / name

                dir_key = (name, source_dir)
                if dir_key not in processed_dirs:
                    if dest_dir.exists():
                        if not overwrite:
                            raise FileExistsError(
                                f"Il tema '{name}' esiste già in '{dest_dir}'. Usare overwrite=True per sovrascrivere."
                            )
                        shutil.rmtree(dest_dir)

                    target_base_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_dir, dest_dir)
                    processed_dirs.add(dir_key)

                installed_themes.append(
                    Theme(
                        name=name,
                        theme_type=t_type,
                        path=dest_dir,
                        is_user_level=True,
                    )
                )

        return installed_themes

    def uninstall(self, theme_name: str, theme_type: ThemeType) -> bool:
        """Disinstalla un tema specifico rimovendolo esclusivamente dalle directory utente.

        Args:
            theme_name: Nome della directory del tema da rimuovere.
            theme_type: Tipologia del tema (GTK, SHELL, ICON, CURSOR).

        Returns:
            True se la disinstallazione è avvenuta con successo.

        Raises:
            ThemeNotFoundError: Se il tema non viene trovato nelle directory utente.
        """
        base_user_dirs = (
            USER_THEMES_DIRS
            if theme_type in (ThemeType.GTK, ThemeType.SHELL)
            else USER_ICONS_DIRS
        )

        custom_dir = (
            self.user_themes_dir
            if theme_type in (ThemeType.GTK, ThemeType.SHELL)
            else self.user_icons_dir
        )

        user_dirs: list[Path] = [custom_dir]
        for d in base_user_dirs:
            if d.expanduser() not in [ud.expanduser() for ud in user_dirs]:
                user_dirs.append(d)

        found_user_path: Optional[Path] = None
        for base_dir in user_dirs:
            candidate = base_dir.expanduser() / theme_name
            if candidate.exists() and candidate.is_dir():
                found_user_path = candidate
                break

        if not found_user_path:
            raise ThemeNotFoundError(
                f"Impossibile disinstallare il tema '{theme_name}' di tipo '{theme_type.value}': "
                "il tema non esiste nelle directory utente (~/.local/share/... o ~/.themes, ~/.icons)."
            )

        shutil.rmtree(found_user_path)
        return True

