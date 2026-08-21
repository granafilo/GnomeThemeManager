# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Task 3.3: Execution permissions documentation and guidelines."""

from pathlib import Path


def test_readme_has_make_launcher_executable_section() -> None:
    """Verify README.md contains 'Make the launcher executable' section with chmod +x and permission details."""
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.is_file(), "README.md not found in project root"

    content = readme_path.read_text(encoding="utf-8")

    # Verify dedicated section for launcher execution permissions
    assert "Make the launcher executable" in content, (
        "README.md must contain a 'Make the launcher executable' section"
    )

    # Verify chmod +x instructions for AppImage and local launch scripts
    assert "chmod +x" in content, "README.md must specify chmod +x command"
    assert "scripts/run_cli.sh" in content or "scripts/" in content, (
        "README.md must document permissions for scripts or launchers"
    )
    assert "desktop" in content.lower() or "launcher" in content.lower(), (
        "README.md must document desktop launcher execution notes"
    )
