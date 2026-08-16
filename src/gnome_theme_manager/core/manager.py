# SPDX-License-Identifier: GPL-3.0-or-later

"""Main Facade module orchestrating theme management in GNOME.

The `ThemeManager` class implements the Facade Pattern, serving as the
high-level entry point to consume all core package capabilities:
- Filesystem scanning and theme discovery (`ThemeScanner`)
- dconf/GSettings configuration read and write (`GSettingsClient`)
- GTK4 / Libadwaita symlink override management (`GTK4ThemeLinker`)
- Safe archive extraction and theme installation (`ThemeInstaller`)
- Profile and preset storage and management (`PresetManager`)
"""

import logging
from pathlib import Path

from .constants import GSETTINGS_COLOR_SCHEMES, GSETTINGS_KEY_COLOR_SCHEME
from .errors import GSettingsUnavailableError, ThemeNotFoundError
from .extensions import ExtensionsManager
from .gsettings import GSettingsClient
from .gtk4_linker import GTK4ThemeLinker
from .installer import ThemeInstaller
from .models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from .presets import PresetManager
from .sandbox_bridge import SandboxBridge
from .scanner import ThemeScanner

logger = logging.getLogger("gnome_theme_manager.core")


class ThemeManager:
    """Facade coordinator class for all GNOME theme operations.

    Abstracts and decouples subsystem complexity (GSettings, Filesystem,
    Linker, Installer, Presets, SandboxBridge, ExtensionsManager), offering
    a clean, UI-independent, highly testable API with optional dependency injection.
    """

    def __init__(
        self,
        scanner: ThemeScanner | None = None,
        gsettings: GSettingsClient | None = None,
        gtk4_linker: GTK4ThemeLinker | None = None,
        installer: ThemeInstaller | None = None,
        presets: PresetManager | None = None,
        sandbox_bridge: SandboxBridge | None = None,
        extensions: ExtensionsManager | None = None,
    ) -> None:
        """Initialize Facade coordinator with optional dependency injection.

        Args:
            scanner: Custom ThemeScanner instance (optional).
            gsettings: Custom or mock GSettingsClient instance (optional).
            gtk4_linker: Custom GTK4ThemeLinker instance (optional).
            installer: Custom ThemeInstaller instance (optional).
            presets: Custom PresetManager instance (optional).
            sandbox_bridge: Custom SandboxBridge instance (optional).
            extensions: Custom ExtensionsManager instance (optional).
        """
        self._scanner = scanner or ThemeScanner()
        self._gtk4_linker = gtk4_linker or GTK4ThemeLinker()
        self._installer = installer or ThemeInstaller()
        self._presets = presets or PresetManager()
        self._sandbox = sandbox_bridge or SandboxBridge()
        self._extensions = extensions or ExtensionsManager()

        # Protected initialization of GSettingsClient
        if gsettings is not None:
            self._gsettings: GSettingsClient | None = gsettings
        else:
            try:
                self._gsettings = GSettingsClient()
            except GSettingsUnavailableError as err:
                logger.warning("GSettingsClient could not be initialized: %s", err)
                self._gsettings = None

    @property
    def scanner(self) -> ThemeScanner:
        """Return associated theme scanner."""
        return self._scanner

    @property
    def gsettings(self) -> GSettingsClient | None:
        """Return associated GSettings client (None if unavailable)."""
        return self._gsettings

    @property
    def gtk4_linker(self) -> GTK4ThemeLinker:
        """Return associated GTK4 linker."""
        return self._gtk4_linker

    @property
    def installer(self) -> ThemeInstaller:
        """Return associated theme installer."""
        return self._installer

    @property
    def presets(self) -> PresetManager:
        """Return associated preset manager."""
        return self._presets

    @property
    def sandbox(self) -> SandboxBridge:
        """Return associated sandbox bridge."""
        return self._sandbox

    @property
    def extensions(self) -> ExtensionsManager:
        """Return associated GNOME Shell extensions manager."""
        return self._extensions

    def _ensure_gsettings(self) -> GSettingsClient:
        """Ensure GSettingsClient is available and return it.

        Raises:
            GSettingsUnavailableError: If GSettings is unavailable in current environment.
        """
        if self._gsettings is None:
            raise GSettingsUnavailableError(
                "GSettings is not available in this environment. "
                "Ensure you are running on GNOME and that PyGObject (Gio) is installed."
            )
        return self._gsettings

    # -------------------------------------------------------------------------
    # System Inspection and Diagnostics
    # -------------------------------------------------------------------------

    def get_current_themes(self) -> ThemeSet:
        """Retrieve active theme configuration from GNOME desktop.

        Returns:
            ThemeSet instance containing active values.

        Raises:
            GSettingsUnavailableError: If GSettings is unavailable.
        """
        client = self._ensure_gsettings()
        current = client.get_current()
        logger.debug("Retrieved active themes: %s", current)
        return current

    def get_system_status(self) -> SystemStatus:
        """Inspect and return current desktop environment compatibility and state.

        Returns:
            SystemStatus instance containing GSettings, extensions, paths, and sandbox info.
        """
        gsettings_avail = self._gsettings is not None
        shell_supported = bool(self._gsettings and self._gsettings.is_shell_theme_supported)

        color_scheme_supported = False
        if (
            self._gsettings
            and hasattr(self._gsettings, "_has_key")
            and hasattr(self._gsettings, "_settings")
        ):
            color_scheme_supported = self._gsettings._has_key(
                self._gsettings._settings, GSETTINGS_KEY_COLOR_SCHEME
            )

        sandbox_stat = self._sandbox.get_sandbox_status()
        gtk4_override_stat = self._gtk4_linker.is_override_active()

        override_status = None
        if self._gsettings:
            override_status = self._gsettings.detect_gtk4_override()

        return SystemStatus(
            gsettings_available=gsettings_avail,
            shell_theme_supported=shell_supported,
            color_scheme_supported=color_scheme_supported,
            user_themes_path=self._installer.user_themes_dir,
            user_icons_path=self._installer.user_icons_dir,
            sandbox_status=sandbox_stat,
            gtk4_override_active=gtk4_override_stat,
            gtk4_override_status=override_status,
        )

    def get_sandbox_status(self) -> SandboxStatus:
        """Return diagnostic status of sandbox runtimes (Flatpak and Snap).

        Returns:
            SandboxStatus instance.
        """
        return self._sandbox.get_sandbox_status()

    def propagate_sandbox(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Propagate active (or specified) themes to Flatpak and Snap environments.

        Does not require elevated privileges or auto-install packages.
        Grants filesystem overrides for Flatpak and verifies compatibility for Snap.

        Args:
            gtk_theme: Optional GTK theme name (if None, attempts to use active theme).
            icon_theme: Optional icon pack name (if None, attempts to use active theme).

        Returns:
            PropagationResult instance with messages, status, and warnings.
        """
        if gtk_theme is None or icon_theme is None:
            try:
                current = self.get_current_themes()
                gtk_theme = gtk_theme or current.gtk_theme
                icon_theme = icon_theme or current.icon_theme
            except GSettingsUnavailableError:
                logger.debug(
                    "GSettings unavailable to determine active themes for sandbox propagation."
                )

        return self._sandbox.propagate_all(gtk_theme=gtk_theme, icon_theme=icon_theme)

    def list_themes(
        self,
        theme_type: ThemeType | None = None,
        user_only: bool = False,
    ) -> list[Theme]:
        """List themes installed on the system, with optional filters.

        Args:
            theme_type: Specific theme type filter (GTK, ICON, CURSOR, SHELL) or None for all.
            user_only: If True, include only user-installed themes.

        Returns:
            Sorted list of detected Theme objects.
        """
        themes: list[Theme]
        if theme_type == ThemeType.GTK:
            themes = self._scanner.scan_gtk_themes(user_only=user_only)
        elif theme_type == ThemeType.ICON:
            themes = self._scanner.scan_icon_themes(user_only=user_only)
        elif theme_type == ThemeType.CURSOR:
            themes = self._scanner.scan_cursor_themes(user_only=user_only)
        elif theme_type == ThemeType.SHELL:
            themes = self._scanner.scan_shell_themes(user_only=user_only)
        else:
            themes = self._scanner.scan_all(user_only=user_only)

        return sorted(themes, key=lambda t: (t.theme_type.value, t.name.lower()))

    def find_theme(self, name: str, theme_type: ThemeType) -> Theme | None:
        """Find a specific theme by name and type on the filesystem.

        Args:
            name: Theme name to find.
            theme_type: Theme type.

        Returns:
            Matching Theme object or None if not found.
        """
        return self._scanner.find_theme(name=name, theme_type=theme_type)

    # -------------------------------------------------------------------------
    # Apply Themes and Presets
    # -------------------------------------------------------------------------

    def apply_themes(
        self,
        theme_set: ThemeSet,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Validate and apply a set of themes to the GNOME desktop.

        Verifies physical presence of themes prior to modifying GSettings, optionally
        applies GTK4 / Libadwaita symlinks, and propagates configuration to Snap and Flatpak.

        Args:
            theme_set: Theme set to apply.
            apply_gtk4_override: If True, apply symlinks in ~/.config/gtk-4.0 for GTK themes.
            propagate_sandbox: If True, propagate GTK themes and icon packs to Flatpak and Snap.

        Returns:
            ApplyResult containing applied components and warnings.

        Raises:
            ThemeNotFoundError: If a specified theme does not exist on the filesystem.
            ValueError: If color scheme is unsupported.
            GSettingsUnavailableError: If GSettings is unavailable.
        """
        logger.info(
            "Theme apply requested: %s (gtk4_override=%s, propagate_sandbox=%s)",
            theme_set,
            apply_gtk4_override,
            propagate_sandbox,
        )
        client = self._ensure_gsettings()
        warnings: list[str] = []

        # 1. Pre-validation of theme existence on filesystem
        found_gtk: Theme | None = None
        if theme_set.gtk_theme is not None:
            found_gtk = self._scanner.find_theme(theme_set.gtk_theme, ThemeType.GTK)
            if not found_gtk:
                raise ThemeNotFoundError(
                    f"GTK theme '{theme_set.gtk_theme}' was not found on the system."
                )

        if theme_set.icon_theme is not None:
            found_icon = self._scanner.find_theme(theme_set.icon_theme, ThemeType.ICON)
            if not found_icon:
                raise ThemeNotFoundError(
                    f"Icon theme '{theme_set.icon_theme}' was not found on the system."
                )

        if theme_set.cursor_theme is not None:
            found_cursor = self._scanner.find_theme(theme_set.cursor_theme, ThemeType.CURSOR)
            if not found_cursor:
                raise ThemeNotFoundError(
                    f"Cursor theme '{theme_set.cursor_theme}' was not found on the system."
                )

        found_shell: Theme | None = None
        if theme_set.shell_theme is not None:
            found_shell = self._scanner.find_theme(theme_set.shell_theme, ThemeType.SHELL)
            if not found_shell:
                raise ThemeNotFoundError(
                    f"GNOME Shell theme '{theme_set.shell_theme}' was not found on the system."
                )

        # 2. Color scheme validation
        if (
            theme_set.color_scheme is not None
            and theme_set.color_scheme not in GSETTINGS_COLOR_SCHEMES
        ):
            raise ValueError(
                f"Invalid color scheme '{theme_set.color_scheme}'. Allowed choices: {list(GSETTINGS_COLOR_SCHEMES)}"
            )

        # 3. Shell theme support check
        shell_to_apply = theme_set.shell_theme
        if shell_to_apply is not None and not client.is_shell_theme_supported:
            warning_msg = (
                "Cannot apply GNOME Shell theme: the 'User Themes' extension "
                "(schema org.gnome.shell.extensions.user-theme) is not installed or active."
            )
            logger.warning(warning_msg)
            warnings.append(warning_msg)
            shell_to_apply = None

        # 4. Apply via GSettings
        target_set = ThemeSet(
            gtk_theme=theme_set.gtk_theme,
            icon_theme=theme_set.icon_theme,
            cursor_theme=theme_set.cursor_theme,
            color_scheme=theme_set.color_scheme,
            shell_theme=shell_to_apply,
        )
        client.apply(target_set)

        # 5. GTK4 / Libadwaita override
        gtk4_applied = False
        if found_gtk is not None and apply_gtk4_override:
            gtk4_applied = self._gtk4_linker.apply_override(found_gtk.path)
            if gtk4_applied:
                logger.info("GTK4/Libadwaita override applied for '%s'", found_gtk.name)
            else:
                logger.debug("No GTK4/3 compatible CSS folder found in '%s'", found_gtk.name)

        # 6. Automatic propagation to sandboxes (Flatpak and Snap)
        propagation_result: PropagationResult | None = None
        if propagate_sandbox and (
            theme_set.gtk_theme is not None or theme_set.icon_theme is not None
        ):
            propagation_result = self._sandbox.propagate_all(
                gtk_theme=theme_set.gtk_theme,
                icon_theme=theme_set.icon_theme,
            )
            if propagation_result.warnings:
                warnings.extend(propagation_result.warnings)

        return ApplyResult(
            gtk_theme=theme_set.gtk_theme,
            gtk4_override_applied=gtk4_applied,
            icon_theme=theme_set.icon_theme,
            cursor_theme=theme_set.cursor_theme,
            shell_theme=shell_to_apply,
            color_scheme=theme_set.color_scheme,
            warnings=warnings,
            sandbox_propagation=propagation_result,
        )

    def apply_unified_theme(
        self,
        theme_name: str,
        color_scheme: str | None = None,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Apply a unified global theme (matching name across GTK and Shell).

        Args:
            theme_name: Theme name to look for as GTK and Shell.
            color_scheme: Optional color scheme ('default', 'prefer-dark', 'prefer-light').
            apply_gtk4_override: If True, apply GTK4 override when available.
            propagate_sandbox: If True, propagate themes to Flatpak and Snap apps.

        Returns:
            ApplyResult containing details of applied themes.

        Raises:
            ThemeNotFoundError: If theme exists neither as GTK nor as Shell.
        """
        has_gtk = bool(self._scanner.find_theme(theme_name, ThemeType.GTK))
        has_shell = bool(self._scanner.find_theme(theme_name, ThemeType.SHELL))

        if not has_gtk and not has_shell:
            raise ThemeNotFoundError(
                f"Theme '{theme_name}' was not found as GTK or GNOME Shell on the system."
            )

        theme_set = ThemeSet(
            gtk_theme=theme_name if has_gtk else None,
            shell_theme=theme_name if has_shell else None,
            color_scheme=color_scheme,
        )

        return self.apply_themes(
            theme_set,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
        )

    def apply_component(
        self,
        component: ThemeType,
        theme_name: str,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Apply a single theme component (GTK, icons, cursors, shell).

        Args:
            component: Theme category (ThemeType.GTK, ICON, CURSOR, SHELL).
            theme_name: Theme name to apply.
            apply_gtk4_override: If True, apply GTK4 override for GTK themes.
            propagate_sandbox: If True, propagate GTK themes and icon packs to Flatpak and Snap.

        Returns:
            ApplyResult with application outcome.

        Raises:
            ThemeNotFoundError: If the specified theme does not exist on the system.
            GSettingsUnavailableError: If GSettings is unavailable.
        """
        found = self._scanner.find_theme(theme_name, component)
        if not found:
            raise ThemeNotFoundError(
                f"Theme '{theme_name}' for component '{component}' was not found."
            )

        kwargs = {}
        if component == ThemeType.GTK:
            kwargs["gtk_theme"] = theme_name
        elif component == ThemeType.ICON:
            kwargs["icon_theme"] = theme_name
        elif component == ThemeType.CURSOR:
            kwargs["cursor_theme"] = theme_name
        elif component == ThemeType.SHELL:
            kwargs["shell_theme"] = theme_name

        theme_set = ThemeSet(**kwargs)
        return self.apply_themes(
            theme_set,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
        )

    def apply_preset(
        self,
        preset_name: str,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Load and apply a stored preset.

        Args:
            preset_name: Identifier name of saved preset.
            apply_gtk4_override: If True, apply GTK4 override for GTK theme in preset.
            propagate_sandbox: If True, propagate themes to Flatpak and Snap.

        Returns:
            ApplyResult with application outcome.

        Raises:
            FileNotFoundError: If preset does not exist.
            ThemeNotFoundError: If a theme in the preset is not installed.
        """
        theme_set = self._presets.load_preset(preset_name)
        logger.info("Applying preset '%s': %s", preset_name, theme_set)
        return self.apply_themes(
            theme_set,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
        )

    # -------------------------------------------------------------------------
    # Preset / Profile Management
    # -------------------------------------------------------------------------

    def save_current_as_preset(self, name: str, overwrite: bool = False) -> Path:
        """Save current desktop themes state as a reusable preset.

        Args:
            name: Identifier name of the preset.
            overwrite: If True, overwrite existing preset with same name.

        Returns:
            Path of the created JSON file.

        Raises:
            FileExistsError: If preset already exists and overwrite=False.
        """
        current_set = self.get_current_themes()
        return self._presets.save_preset(name, current_set, overwrite=overwrite)

    def load_preset(self, name: str) -> ThemeSet:
        """Load a stored preset and return associated ThemeSet.

        Args:
            name: Preset name to load.

        Returns:
            Corresponding ThemeSet instance.

        Raises:
            ValueError: If preset name is invalid.
            FileNotFoundError: If preset does not exist.
        """
        return self._presets.load_preset(name)

    def list_presets(self) -> list[str]:
        """Return alphabetically sorted list of available preset names."""
        return self._presets.list_presets()

    def delete_preset(self, name: str) -> bool:
        """Delete an existing preset.

        Args:
            name: Preset name to remove.

        Returns:
            True if preset was removed.

        Raises:
            FileNotFoundError: If preset does not exist.
        """
        return self._presets.delete_preset(name)

    # -------------------------------------------------------------------------
    # Theme Installation and Uninstallation
    # -------------------------------------------------------------------------

    def inspect_theme_source(self, source_path: Path) -> list[tuple[str, ThemeType]]:
        """Inspect a local source (archive or directory) detecting themes and components.

        Does not modify the source and performs no installation.

        Args:
            source_path: Path to archive file or folder to analyze.

        Returns:
            List of tuples (theme_name, theme_type) for each identified component.

        Raises:
            FileNotFoundError: If source_path does not exist.
            ArchiveExtractionError: If archive is corrupted or unsupported.
            ThemeValidationError: If no valid theme structure is detected.
        """
        logger.info("Theme source inspection requested: %s", source_path)
        results = self._installer.inspect_source(source_path=Path(source_path))
        return [(name, t_type) for name, _, t_type in results]

    def install_theme_directory(
        self,
        directory_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
        target_dir: str | Path | None = None,
    ) -> list[Theme]:
        """Install themes from a local directory into user directories.

        Does not modify or delete the source directory.

        Args:
            directory_path: Path to theme directory.
            theme_type: Optional type filter.
            custom_name: Custom destination folder name.
            overwrite: If True, overwrite pre-existing folders.
            target_dir: Optional destination ('xdg', 'legacy', or custom Path).

        Returns:
            List of successfully installed Theme instances.
        """
        logger.info(
            "Theme directory installation requested: %s (target_dir=%s)", directory_path, target_dir
        )
        return self._installer.install_directory(
            directory_path=Path(directory_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
            target_dir=target_dir,
        )

    def install_theme_archive(
        self,
        archive_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
        target_dir: str | Path | None = None,
    ) -> list[Theme]:
        """Extract, validate, and install themes from a compressed archive (.zip, .tar.*).

        Args:
            archive_path: Path to archive file.
            theme_type: Optional type filter.
            custom_name: Custom destination folder name.
            overwrite: If True, overwrite pre-existing folders.
            target_dir: Optional destination ('xdg', 'legacy', or custom Path).

        Returns:
            List of successfully installed Theme instances.
        """
        logger.info(
            "Theme archive installation requested: %s (target_dir=%s)", archive_path, target_dir
        )
        return self._installer.install(
            archive_path=Path(archive_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
            target_dir=target_dir,
        )

    def install_theme(
        self,
        source_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
        target_dir: str | Path | None = None,
    ) -> list[Theme]:
        """Install one or more themes from a local source (directory or archive).

        Automatically recognizes directory vs archive.

        Args:
            source_path: Path to archive file or theme directory.
            theme_type: Optional type filter.
            custom_name: Custom destination folder name.
            overwrite: If True, overwrite pre-existing folders.
            target_dir: Optional destination ('xdg', 'legacy', or custom Path).

        Returns:
            List of successfully installed Theme instances.
        """
        logger.info(
            "Theme installation requested from source: %s (target_dir=%s)", source_path, target_dir
        )
        return self._installer.install(
            archive_path=Path(source_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
            target_dir=target_dir,
        )

    def uninstall_theme(self, name: str, theme_type: ThemeType) -> bool:
        """Uninstall a specific theme from user directories.

        Args:
            name: Theme directory name to uninstall.
            theme_type: Theme type.

        Returns:
            True if theme was uninstalled successfully.

        Raises:
            ThemeNotFoundError: If theme is not found in user directories.
        """
        logger.info("Theme uninstallation requested: '%s' (%s)", name, theme_type)
        return self._installer.uninstall(theme_name=name, theme_type=theme_type)
