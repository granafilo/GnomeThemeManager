# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per la presenza della sezione Prerequisiti nel file README.md (RED/GREEN)."""

from pathlib import Path


def test_readme_has_prerequisites_section() -> None:
    """Verifica che README.md contenga la sezione '## Prerequisiti' con i dettagli previsti."""
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.is_file(), "README.md non trovato nella radice del progetto"

    content = readme_path.read_text(encoding="utf-8")

    # Verifica la presenza del titolo
    assert "## Prerequisiti" in content, "README.md deve contenere la sezione '## Prerequisiti'"

    # Verifica la presenza delle note su Flatpak/Snap e permessi eseguibile launcher
    assert "Flatpak" in content, "Mancano riferimenti a Flatpak nella sezione Prerequisiti"
    assert "Snap" in content, "Mancano riferimenti a Snap nella sezione Prerequisiti"
    assert "eseguibile" in content or "permessi" in content or "chmod" in content, "Mancano indicazioni sui permessi di esecuzione del launcher"
