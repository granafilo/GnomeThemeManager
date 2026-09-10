# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Multi-OS Cascading Icon Fallback System (Step 3).

Tests the 3-level cascading fallback resolution:
1. Level 1: Theme-specific icon (when icon is found in active/specified theme)
2. Level 2: System default icon (when missing from theme but found in system fallback chain)
3. Level 3: Bundled application icon (when missing from theme/system, resolved via data/icons)
4. Level 4: Generic emergency fallback

Also tests conceptual compatibility across 3 distinct Linux distribution scenarios:
- Ubuntu (Yaru icon set)
- Fedora (Adwaita vanilla icon set)
- Arch / openSUSE / Minimal (Breeze / third-party minimalist icon set)
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from gnome_theme_manager.core.icon_fallback import (
    IconFallbackResolver,
    IconResolutionResult,
    get_fallback_icon_name,
)
from gnome_theme_manager.core.manager import ThemeManager


def test_level_1_theme_specific_icon_found() -> None:
    """Verify that an icon available directly in the icon theme resolves at Level 1 without fallback."""
    mock_theme = MagicMock()
    mock_theme.has_icon.side_effect = lambda name: name == "user-home"

    resolver = IconFallbackResolver()
    result = resolver.resolve("user-home", icon_theme=mock_theme)

    assert result.requested_name == "user-home"
    assert result.resolved_name == "user-home"
    assert result.level == "theme"
    assert result.is_fallback is False


def test_level_2_system_fallback_chain_and_debug_logging(caplog: logging.LogCaptureFixture) -> None:
    """Verify that when an icon is absent from the theme, a Level 2 system candidate is selected and logged."""
    mock_theme = MagicMock()

    # The requested icon is missing, but candidate 'preferences-desktop-appearance-symbolic' exists
    def has_icon_stub(name: str) -> bool:
        return name == "preferences-desktop-appearance-symbolic"

    mock_theme.has_icon.side_effect = has_icon_stub

    resolver = IconFallbackResolver()
    with caplog.at_level(logging.DEBUG):
        result = resolver.resolve("app-logo-symbolic", icon_theme=mock_theme)

    assert result.requested_name == "app-logo-symbolic"
    assert result.resolved_name == "preferences-desktop-appearance-symbolic"
    assert result.level == "system"
    assert result.is_fallback is True

    # Verify debug log was emitted
    assert any(
        "Icon fallback activated (Level 2 - System)" in record.message
        and "app-logo-symbolic" in record.message
        for record in caplog.records
    )


def test_level_3_bundled_app_icon_and_debug_logging(caplog: logging.LogCaptureFixture) -> None:
    """Verify that when theme and system candidates fail, the resolver selects the bundled asset at Level 3."""
    mock_theme = MagicMock()
    # Theme has no icons at all
    mock_theme.has_icon.return_value = False

    resolver = IconFallbackResolver()
    with caplog.at_level(logging.DEBUG):
        result = resolver.resolve("app-logo-symbolic", icon_theme=mock_theme)

    assert result.requested_name == "app-logo-symbolic"
    assert result.resolved_name == "app-logo-symbolic"
    assert result.level == "bundled"
    assert result.is_fallback is True
    assert result.file_path is not None
    assert result.file_path.is_file()

    # Verify debug log was emitted
    assert any(
        "Icon fallback activated (Level 3 - Bundled)" in record.message
        and "app-logo-symbolic" in record.message
        for record in caplog.records
    )


def test_level_4_emergency_fallback_for_completely_unknown_icon(
    caplog: logging.LogCaptureFixture,
) -> None:
    """Verify that an unknown, non-bundled icon falls back to Level 4 generic with debug logging."""
    mock_theme = MagicMock()
    mock_theme.has_icon.return_value = False

    resolver = IconFallbackResolver()
    with caplog.at_level(logging.DEBUG):
        result = resolver.resolve("nonexistent-obscure-icon-xyz-123", icon_theme=mock_theme)

    assert result.requested_name == "nonexistent-obscure-icon-xyz-123"
    assert result.level in ("generic", "bundled")
    assert result.is_fallback is True

    assert any(
        "Icon fallback activated" in record.message
        and "nonexistent-obscure-icon-xyz-123" in record.message
        for record in caplog.records
    )


def test_empty_icon_name_handling() -> None:
    """Verify safe handling of empty or blank icon name inputs."""
    resolver = IconFallbackResolver()
    result = resolver.resolve("   ")

    assert result.requested_name == ""
    assert result.resolved_name == "image-missing"
    assert result.is_fallback is True


def test_get_fallback_icon_name_convenience_helper() -> None:
    """Verify convenience function get_fallback_icon_name returns string."""
    mock_theme = MagicMock()
    mock_theme.has_icon.side_effect = lambda name: name == "dialog-information-symbolic"

    resolved = get_fallback_icon_name("dialog-information-symbolic", icon_theme=mock_theme)
    assert resolved == "dialog-information-symbolic"


def test_theme_manager_icon_resolver_integration() -> None:
    """Verify ThemeManager exposes icon_resolver property and resolve_icon method."""
    mock_scanner = MagicMock()
    mock_gsettings = MagicMock()
    manager = ThemeManager(scanner=mock_scanner, gsettings=mock_gsettings)

    assert isinstance(manager.icon_resolver, IconFallbackResolver)

    mock_theme = MagicMock()
    mock_theme.has_icon.side_effect = lambda name: name == "starred-symbolic"

    res = manager.resolve_icon("starred-symbolic", icon_theme=mock_theme)
    assert isinstance(res, IconResolutionResult)
    assert res.resolved_name == "starred-symbolic"
    assert res.level == "theme"


# ==============================================================================
# Multi-OS Conceptual Testing Matrix (Ubuntu, Fedora, Arch/openSUSE)
# ==============================================================================


def test_os_compatibility_ubuntu_yaru_profile() -> None:
    """Simulate Ubuntu 24.04 with Yaru icon theme.

    On Ubuntu with Yaru, icons like face-slightly-smiling-plus-symbolic and
    preferences-desktop-appearance-symbolic are natively present in the theme.
    """
    yaru_theme = MagicMock()
    yaru_available_icons = {
        "face-slightly-smiling-plus-symbolic",
        "preferences-desktop-appearance-symbolic",
        "system-software-install-symbolic",
        "utilities-terminal-symbolic",
        "starred-symbolic",
    }
    yaru_theme.has_icon.side_effect = lambda name: name in yaru_available_icons

    resolver = IconFallbackResolver()

    # 1. Native Yaru icon resolves Level 1
    res1 = resolver.resolve("face-slightly-smiling-plus-symbolic", icon_theme=yaru_theme)
    assert res1.resolved_name == "face-slightly-smiling-plus-symbolic"
    assert res1.level == "theme"
    assert res1.is_fallback is False

    # 2. app-logo-symbolic is absent in Yaru; falls back to preferences-desktop-appearance-symbolic (Level 2)
    res2 = resolver.resolve("app-logo-symbolic", icon_theme=yaru_theme)
    assert res2.resolved_name == "preferences-desktop-appearance-symbolic"
    assert res2.level == "system"
    assert res2.is_fallback is True


def test_os_compatibility_fedora_adwaita_profile() -> None:
    """Simulate Fedora with vanilla Adwaita icon theme.

    Vanilla Adwaita does NOT contain app-logo-symbolic nor face-slightly-smiling-plus-symbolic.
    Instead, it provides face-smile-symbolic and system-software-install-symbolic.
    """
    adwaita_theme = MagicMock()
    adwaita_available_icons = {
        "face-smile-symbolic",
        "system-software-install-symbolic",
        "utilities-terminal-symbolic",
        "preferences-desktop-font-symbolic",
        "user-desktop-symbolic",
    }
    adwaita_theme.has_icon.side_effect = lambda name: name in adwaita_available_icons

    resolver = IconFallbackResolver()

    # 1. face-slightly-smiling-plus-symbolic falls back to face-smile-symbolic (Level 2 System)
    res_cursor = resolver.resolve("face-slightly-smiling-plus-symbolic", icon_theme=adwaita_theme)
    assert res_cursor.resolved_name == "face-smile-symbolic"
    assert res_cursor.level == "system"
    assert res_cursor.is_fallback is True

    # 2. software-store-symbolic falls back to system-software-install-symbolic (Level 2 System)
    res_store = resolver.resolve("software-store-symbolic", icon_theme=adwaita_theme)
    assert res_store.resolved_name == "system-software-install-symbolic"
    assert res_store.level == "system"
    assert res_store.is_fallback is True

    # 3. app-logo-symbolic has no match in vanilla Adwaita; resolves to Level 3 Bundled SVG
    res_logo = resolver.resolve("app-logo-symbolic", icon_theme=adwaita_theme)
    assert res_logo.resolved_name == "app-logo-symbolic"
    assert res_logo.level == "bundled"
    assert res_logo.is_fallback is True
    assert res_logo.file_path is not None
    assert res_logo.file_path.is_file()


def test_os_compatibility_arch_breeze_minimal_profile() -> None:
    """Simulate Arch Linux or openSUSE with Breeze or minimalist icon theme.

    Minimalist themes may omit emblem-synchronizing-symbolic, changes-allow-symbolic,
    and app-logo-symbolic. The fallback cascade must handle all of them gracefully.
    """
    minimal_theme = MagicMock()
    # Minimalist theme only has basic view-refresh and security-high
    minimal_available_icons = {
        "view-refresh-symbolic",
        "security-high-symbolic",
        "terminal-symbolic",
        "edit-find-symbolic",
    }
    minimal_theme.has_icon.side_effect = lambda name: name in minimal_available_icons

    resolver = IconFallbackResolver()

    # 1. emblem-synchronizing-symbolic resolves to view-refresh-symbolic (Level 2)
    res_sync = resolver.resolve("emblem-synchronizing-symbolic", icon_theme=minimal_theme)
    assert res_sync.resolved_name == "view-refresh-symbolic"
    assert res_sync.level == "system"
    assert res_sync.is_fallback is True

    # 2. changes-allow-symbolic resolves to security-high-symbolic (Level 2)
    res_perm = resolver.resolve("changes-allow-symbolic", icon_theme=minimal_theme)
    assert res_perm.resolved_name == "security-high-symbolic"
    assert res_perm.level == "system"
    assert res_perm.is_fallback is True

    # 3. utilities-terminal-symbolic resolves to terminal-symbolic (Level 2)
    res_term = resolver.resolve("utilities-terminal-symbolic", icon_theme=minimal_theme)
    assert res_term.resolved_name == "terminal-symbolic"
    assert res_term.level == "system"
    assert res_term.is_fallback is True

    # 4. system-search-symbolic resolves to edit-find-symbolic (Level 2)
    res_search = resolver.resolve("system-search-symbolic", icon_theme=minimal_theme)
    assert res_search.resolved_name == "edit-find-symbolic"
    assert res_search.level == "system"
    assert res_search.is_fallback is True


def test_bundled_icons_indexing_is_cached() -> None:
    """Verify that bundled icon indexing caches its result on successive calls."""
    resolver = IconFallbackResolver()
    index1 = resolver._get_bundled_icons_index()
    index2 = resolver._get_bundled_icons_index()
    assert index1 is index2
    assert "app-logo-symbolic" in index1
    assert "software-store-symbolic" in index1
    assert "changes-allow-symbolic" in index1
