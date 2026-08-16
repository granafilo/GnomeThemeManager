# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per la presenza della sezione Prerequisites nel file README.md."""

from pathlib import Path


def test_readme_has_prerequisites_section() -> None:
    """Verifica che README.md contenga la sezione '## Prerequisites' con i dettagli previsti."""
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.is_file(), "README.md non trovato nella radice del progetto"

    content = readme_path.read_text(encoding="utf-8")

    # Verifica la presenza del titolo
    assert "## Prerequisites" in content, "README.md deve contenere la sezione '## Prerequisites'"

    # Verifica la presenza delle note su Flatpak/Snap e permessi eseguibile launcher
    assert "Flatpak" in content, "Mancano riferimenti a Flatpak nella sezione Prerequisites"
    assert "Snap" in content, "Mancano riferimenti a Snap nella sezione Prerequisites"
    assert "executable" in content or "permissions" in content or "chmod" in content, (
        "Mancano indicazioni sui permessi di esecuzione del launcher"
    )
