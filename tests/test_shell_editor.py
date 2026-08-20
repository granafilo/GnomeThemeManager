# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Shell Theme Editor and Fork Management (Task 2.7).

Tests extracting colors from gnome-shell.css, creating/reverting shell theme forks,
CSS override markers (GTM-OVERRIDE-START / GTM-OVERRIDE-END), and auto-revert timer.
"""

from pathlib import Path

from gnome_theme_manager.core.shell_editor import (
    ShellThemeForkManager,
    extract_shell_colors,
    generate_shell_css_override,
)


def test_extract_shell_colors_from_define_colors(tmp_path: Path) -> None:
    """Test extracting shell colors when @define-color definitions exist."""
    shell_dir = tmp_path / "gnome-shell"
    shell_dir.mkdir(parents=True)
    css_file = shell_dir / "gnome-shell.css"
    css_file.write_text(
        """
        @define-color selected_bg_color #3584e4;
        @define-color panel_bg #1e1e2e;
        @define-color panel_fg #ffffff;
        @define-color overview_bg rgba(0,0,0,0.8);
        """,
        encoding="utf-8",
    )

    colors = extract_shell_colors(tmp_path)
    assert colors.accent_color == "#3584e4"
    assert colors.panel_bg == "#1e1e2e"
    assert colors.panel_fg == "#ffffff"
    assert colors.overview_bg == "rgba(0,0,0,0.8)"


def test_extract_shell_colors_heuristics(tmp_path: Path) -> None:
    """Test extracting shell colors using CSS selector heuristics when no @define-color exist."""
    shell_dir = tmp_path / "gnome-shell"
    shell_dir.mkdir(parents=True)
    css_file = shell_dir / "gnome-shell.css"
    css_file.write_text(
        """
        #panel {
            background-color: rgba(20, 20, 20, 0.95);
            font-weight: bold;
        }
        .panel-button {
            color: #f0f0f0;
            font-weight: bold;
        }
        .overview {
            background-color: rgba(10, 10, 10, 0.8);
        }
        .selected {
            background-color: #ff5500;
            color: #ffffff;
        }
        """,
        encoding="utf-8",
    )

    colors = extract_shell_colors(tmp_path)
    assert colors.panel_bg == "rgba(20, 20, 20, 0.95)"
    assert colors.panel_fg == "#f0f0f0"
    assert colors.overview_bg == "rgba(10, 10, 10, 0.8)"
    assert colors.accent_color == "#ff5500"


def test_generate_shell_css_override_idempotent() -> None:
    """Test generating and replacing CSS overrides delimited by GTM markers."""
    initial_css = "/* Base CSS */\n#panel { height: 32px; }\n"
    colors = {
        "accent_color": "#ff0055",
        "panel_bg": "#121212",
        "panel_fg": "#ffffff",
        "overview_bg": "#000000",
    }

    override_css = generate_shell_css_override(initial_css, colors)
    assert "/* GTM-OVERRIDE-START */" in override_css
    assert "/* GTM-OVERRIDE-END */" in override_css
    assert "#panel {" in override_css
    assert "#ff0055" in override_css

    # Re-generating with new colors must replace previous block cleanly without duplication
    new_colors = {
        "accent_color": "#00ffaa",
        "panel_bg": "#222222",
        "panel_fg": "#eeeeee",
        "overview_bg": "#111111",
    }
    second_pass = generate_shell_css_override(override_css, new_colors)
    assert second_pass.count("/* GTM-OVERRIDE-START */") == 1
    assert second_pass.count("/* GTM-OVERRIDE-END */") == 1
    assert "#00ffaa" in second_pass
    assert "#ff0055" not in second_pass


def test_shell_theme_fork_create_and_revert(tmp_path: Path) -> None:
    """Test creating and reverting shell theme fork."""
    user_themes = tmp_path / "themes"
    state_file = tmp_path / "theme_forks.json"
    base_theme = tmp_path / "base-shell-theme"
    (base_theme / "gnome-shell").mkdir(parents=True)
    (base_theme / "gnome-shell" / "gnome-shell.css").write_text("#panel { color: #fff; }")

    mgr = ShellThemeForkManager(user_themes_dir=user_themes, state_file=state_file)
    fork = mgr.create_shell_fork(
        base_theme_name="base-shell-theme",
        base_theme_path=base_theme,
        custom_name="CustomShell",
        colors={"panel_bg": "#000000", "accent_color": "#123456"},
    )

    assert fork.fork_name == "CustomShell-shell"
    assert fork.fork_path.is_dir()
    assert (fork.fork_path / "gnome-shell" / "gnome-shell.css").is_file()
    assert "#123456" in (fork.fork_path / "gnome-shell" / "gnome-shell.css").read_text()

    # Revert fork
    reverted = mgr.revert_shell_fork("CustomShell-shell")
    assert reverted is True
    assert not fork.fork_path.exists()
