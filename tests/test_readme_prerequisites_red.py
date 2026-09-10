# SPDX-License-Identifier: GPL-3.0-or-later

"""Test for the presence of the Prerequisites section in README.md."""

from pathlib import Path


def test_readme_has_prerequisites_section() -> None:
    """Verify that README.md contains the '## Prerequisites' section with expected details."""
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.is_file(), "README.md not found in project root"

    content = readme_path.read_text(encoding="utf-8")

    # Verify heading presence
    assert "## Prerequisites" in content, "README.md must contain '## Prerequisites' section"

    # Verify notes on Flatpak/Snap and launcher executable permissions
    assert "Flatpak" in content, "Missing references to Flatpak in Prerequisites section"
    assert "Snap" in content, "Missing references to Snap in Prerequisites section"
    assert "executable" in content or "permissions" in content or "chmod" in content, (
        "Missing instructions on launcher executable permissions"
    )
