# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for ThemeValidator and ThemeValidationResult (Task 1.2)."""

from pathlib import Path

from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.core.theme_validator import ThemeValidationResult, ThemeValidator


def test_theme_validation_result_structure() -> None:
    """Test ThemeValidationResult dataclass properties."""
    res = ThemeValidationResult(valid=True, warnings=["Some warning"], missing_files=[])
    assert res.valid is True
    assert len(res.warnings) == 1
    assert len(res.missing_files) == 0


def test_validate_nonexistent_theme_path(tmp_path: Path) -> None:
    """Validate a non-existent path returns invalid result."""
    validator = ThemeValidator()
    res = validator.validate(tmp_path / "nonexistent", ThemeType.GTK)
    assert res.valid is False
    assert any("not exist" in w.lower() or "not found" in w.lower() for w in res.warnings)


def test_validate_gtk_theme_valid_gtk3_gtk4(tmp_path: Path) -> None:
    """Validate a complete GTK theme with index.theme, gtk-3.0 and gtk-4.0 directories."""
    theme_dir = tmp_path / "ValidGTK"
    theme_dir.mkdir(parents=True)
    (theme_dir / "gtk-3.0").mkdir()
    (theme_dir / "gtk-3.0" / "gtk.css").write_text("/* gtk3 css */", encoding="utf-8")
    (theme_dir / "gtk-4.0").mkdir()
    (theme_dir / "gtk-4.0" / "gtk.css").write_text("/* gtk4 css */", encoding="utf-8")

    index_theme = """[Desktop Entry]
Type=X-GNOME-Metatheme
Name=ValidGTK
Comment=A valid GTK theme
"""
    (theme_dir / "index.theme").write_text(index_theme, encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(theme_dir, ThemeType.GTK)
    assert res.valid is True
    assert len(res.missing_files) == 0


def test_validate_gtk_theme_missing_css_and_header(tmp_path: Path) -> None:
    """Validate a GTK theme missing index.theme header and missing gtk css files."""
    theme_dir = tmp_path / "BrokenGTK"
    theme_dir.mkdir(parents=True)
    # Empty dir without gtk-3.0/gtk-4.0
    (theme_dir / "index.theme").write_text("[InvalidSection]\nFoo=Bar\n", encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(theme_dir, ThemeType.GTK)
    assert res.valid is False
    assert len(res.warnings) > 0


def test_validate_gtk_theme_gtk2_only_is_invalid_for_modern_gnome(tmp_path: Path) -> None:
    """Validate a legacy theme with only gtk-2.0 and no gtk-3.0/gtk-4.0 is marked invalid."""
    theme_dir = tmp_path / "Gtk2OnlyTheme"
    theme_dir.mkdir(parents=True)
    (theme_dir / "gtk-2.0").mkdir()
    (theme_dir / "gtk-2.0" / "gtkrc").write_text("/* gtk2 rc */", encoding="utf-8")
    (theme_dir / "gnome-shell").mkdir()
    (theme_dir / "gnome-shell" / "gnome-shell.css").write_text("/* shell css */", encoding="utf-8")
    (theme_dir / "index.theme").write_text("[Desktop Entry]\nName=Gtk2Only\n", encoding="utf-8")

    validator = ThemeValidator()
    # As GTK theme, it must be invalid because GTK3/4 stylesheets are absent
    gtk_res = validator.validate(theme_dir, ThemeType.GTK)
    assert gtk_res.valid is False
    assert "gtk-3.0/gtk.css or gtk-4.0/gtk.css" in gtk_res.missing_files

    # As SHELL theme, it is valid because gnome-shell.css exists
    shell_res = validator.validate(theme_dir, ThemeType.SHELL)
    assert shell_res.valid is True


def test_validate_cursor_theme_valid(tmp_path: Path) -> None:
    """Validate a cursor theme with cursors/ directory and index.theme."""
    cursor_dir = tmp_path / "ValidCursor"
    cursor_dir.mkdir(parents=True)
    cursors_sub = cursor_dir / "cursors"
    cursors_sub.mkdir()
    (cursors_sub / "default").write_text("cursor-binary", encoding="utf-8")

    index_theme = """[Icon Theme]
Name=ValidCursor
Comment=A valid cursor theme
"""
    (cursor_dir / "index.theme").write_text(index_theme, encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(cursor_dir, ThemeType.CURSOR)
    assert res.valid is True
    assert len(res.missing_files) == 0


def test_validate_cursor_theme_missing_cursors_dir(tmp_path: Path) -> None:
    """Validate a cursor theme missing cursors directory."""
    cursor_dir = tmp_path / "IncompleteCursor"
    cursor_dir.mkdir(parents=True)
    (cursor_dir / "index.theme").write_text("[Icon Theme]\nName=Incomplete\n", encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(cursor_dir, ThemeType.CURSOR)
    assert res.valid is False
    assert "cursors" in res.missing_files


def test_validate_icon_theme_valid_with_standard_icons(tmp_path: Path) -> None:
    """Validate an icon theme with index.theme and standard icons."""
    icon_dir = tmp_path / "ValidIcons"
    icon_dir.mkdir(parents=True)
    (icon_dir / "48x48" / "apps").mkdir(parents=True)

    # Add standard icon files
    for icon_name in [
        "folder.svg",
        "system-file-manager.svg",
        "user-home.svg",
        "preferences-system.svg",
        "document-open.svg",
        "edit-cut.svg",
    ]:
        (icon_dir / "48x48" / "apps" / icon_name).write_text("<svg/>", encoding="utf-8")

    index_theme = """[Icon Theme]
Name=ValidIcons
Comment=Test icon theme
Directories=48x48/apps

[48x48/apps]
Size=48
Context=Applications
Type=Fixed
"""
    (icon_dir / "index.theme").write_text(index_theme, encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(icon_dir, ThemeType.ICON)
    assert res.valid is True
    assert len(res.missing_files) == 0


def test_validate_icon_theme_malformed_missing_size(tmp_path: Path) -> None:
    """Validate that an icon theme with Directories declared but no Size field is marked invalid."""
    icon_dir = tmp_path / "MalformedIcons"
    icon_dir.mkdir(parents=True)
    (icon_dir / "48x48" / "apps").mkdir(parents=True)

    index_theme = """[Icon Theme]
Name=MalformedIcons
Comment=Malformed icon theme
Directories=48x48/apps

[48x48/apps]
Context=Applications
Type=Fixed
"""
    (icon_dir / "index.theme").write_text(index_theme, encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(icon_dir, ThemeType.ICON)
    assert res.valid is False
    assert any("Size" in w for w in res.warnings)


def test_validate_icon_theme_too_few_icons(tmp_path: Path) -> None:
    """Validate an icon theme with index.theme but fewer than 5 standard icons produces warning."""
    icon_dir = tmp_path / "SparseIcons"
    icon_dir.mkdir(parents=True)
    (icon_dir / "48x48" / "apps").mkdir(parents=True)
    (icon_dir / "48x48" / "apps" / "single-icon.svg").write_text("<svg/>", encoding="utf-8")

    index_theme = """[Icon Theme]
Name=SparseIcons
Comment=Sparse icons
"""
    (icon_dir / "index.theme").write_text(index_theme, encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(icon_dir, ThemeType.ICON)
    assert len(res.warnings) > 0


def test_validate_shell_theme_valid(tmp_path: Path) -> None:
    """Validate a GNOME Shell theme containing gnome-shell.css."""
    shell_dir = tmp_path / "ValidShell"
    shell_dir.mkdir(parents=True)
    gs_dir = shell_dir / "gnome-shell"
    gs_dir.mkdir()
    (gs_dir / "gnome-shell.css").write_text("/* shell css */", encoding="utf-8")

    validator = ThemeValidator()
    res = validator.validate(shell_dir, ThemeType.SHELL)
    assert res.valid is True
    assert len(res.missing_files) == 0
