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
from .errors import GSettingsUnavailableError, ThemeNotFoundError, ThemeValidationError
from .extensions import ExtensionsManager
from .global_themes import GlobalTheme, GlobalThemeManager
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
from .sandbox_theme import SystemThemePreviewSession
from .scanner import ThemeScanner
from .theme_editor import ThemeComposition, ThemeMixer
from .theme_validator import ThemeValidationResult, ThemeValidator

logger = logging.getLogger("gnome_theme_manager.core")


class ThemeManager:
    """Facade coordinator class for all GNOME theme operations.

    Abstracts and decouples subsystem complexity (GSettings, Filesystem,
    Linker, Installer, Presets, GlobalThemes, SandboxBridge, ExtensionsManager, ThemeValidator, ThemeMixer), offering
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
        global_themes: GlobalThemeManager | None = None,
        validator: ThemeValidator | None = None,
        theme_mixer: ThemeMixer | None = None,
    ) -> None:
        """Initialize ThemeManager with optional subsystem dependency injection.

        Args:
            scanner: Custom ThemeScanner instance (optional).
            gsettings: Custom GSettingsClient instance (optional).
            gtk4_linker: Custom GTK4ThemeLinker instance (optional).
            installer: Custom ThemeInstaller instance (optional).
            presets: Custom PresetManager instance (optional).
            sandbox_bridge: Custom SandboxBridge instance (optional).
            extensions: Custom ExtensionsManager instance (optional).
            global_themes: Custom GlobalThemeManager instance (optional).
            validator: Custom ThemeValidator instance (optional).
            theme_mixer: Custom ThemeMixer instance (optional).
        """
        self._scanner = scanner or ThemeScanner()
        self._gtk4_linker = gtk4_linker or GTK4ThemeLinker()
        self._installer = installer or ThemeInstaller()
        self._presets = presets or PresetManager()
        self._sandbox = sandbox_bridge or SandboxBridge()
        self._extensions = extensions or ExtensionsManager()
        self._validator = validator or ThemeValidator()
        self._theme_preview = SystemThemePreviewSession(
            get_current_themes_fn=self._get_current_themes_safe,
            apply_themes_fn=self.apply_themes,
        )

        # Protected initialization of GSettingsClient
        if gsettings is not None:
            self._gsettings: GSettingsClient | None = gsettings
        else:
            try:
                self._gsettings = GSettingsClient()
            except GSettingsUnavailableError as err:
                logger.warning("GSettingsClient could not be initialized: %s", err)
                self._gsettings = None

        self._global_themes = global_themes or GlobalThemeManager(
            scanner=self._scanner,
            current_themes_provider=self._get_current_themes_safe,
        )
        self._theme_mixer = theme_mixer or ThemeMixer(
            global_theme_manager=self._global_themes,
        )

    def _get_current_themes_safe(self) -> ThemeSet:
        """Helper to get current themes safely without raising exceptions."""
        try:
            return self.get_current_themes()
        except Exception:
            return ThemeSet()

    @property
    def theme_preview(self) -> SystemThemePreviewSession:
        """Return associated system theme preview session manager."""
        return self._theme_preview

    @property
    def is_preview_active(self) -> bool:
        """Return True if a system theme preview is currently active."""
        return self._theme_preview.is_preview_active

    def start_theme_preview(
        self,
        theme_name: str,
        component: ThemeType,
        also_apply_opposite: bool = False,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> bool:
        """Start a live system-wide preview of a theme component.

        Args:
            theme_name: Name of theme to preview.
            component: Component category (GTK, ICON, CURSOR, SHELL).
            also_apply_opposite: If True, also preview complementary GTK/Shell theme if available.
            apply_gtk4_override: Whether to apply GTK4 override.
            propagate_sandbox: Whether to propagate to Flatpak and Snap.

        Returns:
            True if preview started successfully, False otherwise.
        """
        found = self._scanner.find_theme(theme_name, component)
        if not found:
            raise ThemeNotFoundError(
                f"Theme '{theme_name}' for component '{component}' was not found."
            )

        kwargs: dict[str, str | None] = {}
        if component == ThemeType.GTK:
            kwargs["gtk_theme"] = theme_name
            if also_apply_opposite:
                opposite_shell = self._scanner.find_theme(theme_name, ThemeType.SHELL)
                if (
                    opposite_shell
                    and self._validator.validate(opposite_shell.path, ThemeType.SHELL).valid
                ):
                    kwargs["shell_theme"] = theme_name
            elif self._theme_preview.is_preview_active and self._theme_preview.snapshot_themes:
                kwargs["shell_theme"] = self._theme_preview.snapshot_themes.shell_theme
        elif component == ThemeType.ICON:
            kwargs["icon_theme"] = theme_name
        elif component == ThemeType.CURSOR:
            kwargs["cursor_theme"] = theme_name
        elif component == ThemeType.SHELL:
            kwargs["shell_theme"] = theme_name
            if also_apply_opposite:
                opposite_gtk = self._scanner.find_theme(theme_name, ThemeType.GTK)
                if (
                    opposite_gtk
                    and self._validator.validate(opposite_gtk.path, ThemeType.GTK).valid
                ):
                    kwargs["gtk_theme"] = theme_name
            elif self._theme_preview.is_preview_active and self._theme_preview.snapshot_themes:
                kwargs["gtk_theme"] = self._theme_preview.snapshot_themes.gtk_theme

        theme_set = ThemeSet(**kwargs)
        gtk_theme_found = (
            found
            if component == ThemeType.GTK
            else self._scanner.find_theme(theme_name, ThemeType.GTK)
            if also_apply_opposite
            else None
        )
        theme_path = gtk_theme_found.path if gtk_theme_found else None

        return self._theme_preview.start_preview(
            theme_set,
            theme_path=theme_path,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
            force=True,
        )

    def commit_theme_preview(self) -> bool:
        """Permanently commit the currently previewed theme to the system."""
        return self._theme_preview.commit_preview()

    def cancel_theme_preview(self) -> bool:
        """Cancel the preview and roll back the system to the original theme state."""
        orig_gtk_path: Path | None = None
        if self._theme_preview.is_preview_active and self._theme_preview._snapshot_themes:
            orig_gtk_name = self._theme_preview._snapshot_themes.gtk_theme
            if orig_gtk_name:
                found_orig = self._scanner.find_theme(orig_gtk_name, ThemeType.GTK)
                if found_orig:
                    orig_gtk_path = found_orig.path

        return self._theme_preview.cancel_preview(snapshot_theme_path=orig_gtk_path)

    def preview_gtk_theme(self, theme_name: str) -> bool:
        """Compatibility alias for start_theme_preview with GTK."""
        return self.start_theme_preview(theme_name, ThemeType.GTK)

    def revert_gtk_theme_preview(self) -> bool:
        """Compatibility alias for cancel_theme_preview."""
        return self.cancel_theme_preview()

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

    @property
    def global_themes(self) -> GlobalThemeManager:
        """Return associated global theme manager."""
        return self._global_themes

    @property
    def validator(self) -> ThemeValidator:
        """Return associated theme validator."""
        return self._validator

    def validate_theme(self, theme_path: Path, theme_type: ThemeType) -> ThemeValidationResult:
        """Validate structural integrity and compliance of a theme.

        Args:
            theme_path: Directory path of the theme to inspect.
            theme_type: Theme category (GTK, ICON, CURSOR, SHELL).

        Returns:
            ThemeValidationResult containing validity flag and warnings.
        """
        return self._validator.validate(theme_path, theme_type)

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
        force: bool = False,
    ) -> ApplyResult:
        """Validate and apply a set of themes to the GNOME desktop.

        Verifies physical presence of themes prior to modifying GSettings, optionally
        applies GTK4 / Libadwaita symlinks, and propagates configuration to Snap and Flatpak.

        Args:
            theme_set: Theme set to apply.
            apply_gtk4_override: If True, apply symlinks in ~/.config/gtk-4.0 for GTK themes.
            propagate_sandbox: If True, propagate GTK themes and icon packs to Flatpak and Snap.
            force: If True, bypass ThemeValidationError and apply anyway with warnings.

        Returns:
            ApplyResult containing applied components and warnings.

        Raises:
            ThemeNotFoundError: If a specified theme does not exist on the filesystem.
            ValueError: If color scheme is unsupported.
            GSettingsUnavailableError: If GSettings is unavailable.
        """
        logger.info(
            "Theme apply requested: %s (gtk4_override=%s, propagate_sandbox=%s, force=%s)",
            theme_set,
            apply_gtk4_override,
            propagate_sandbox,
            force,
        )
        client = self._ensure_gsettings()
        warnings: list[str] = []

        # 1. Pre-validation of theme existence and structural validity on filesystem
        found_gtk: Theme | None = None
        if theme_set.gtk_theme is not None:
            found_gtk = self._scanner.find_theme(theme_set.gtk_theme, ThemeType.GTK)
            if not found_gtk:
                raise ThemeNotFoundError(
                    f"GTK theme '{theme_set.gtk_theme}' was not found on the system."
                )
            gtk_val = self._validator.validate(found_gtk.path, ThemeType.GTK)
            if not gtk_val.valid:
                warn_msg = (
                    "; ".join(gtk_val.warnings) or "Theme structure is incomplete or invalid."
                )
                if force:
                    warnings.append(f"GTK theme '{theme_set.gtk_theme}' is incomplete: {warn_msg}")
                else:
                    raise ThemeValidationError(
                        f"GTK theme '{theme_set.gtk_theme}' is invalid: {warn_msg}"
                    )
            elif gtk_val.warnings:
                warnings.extend(gtk_val.warnings)

        if theme_set.icon_theme is not None:
            found_icon = self._scanner.find_theme(theme_set.icon_theme, ThemeType.ICON)
            if not found_icon:
                raise ThemeNotFoundError(
                    f"Icon theme '{theme_set.icon_theme}' was not found on the system."
                )
            icon_val = self._validator.validate(found_icon.path, ThemeType.ICON)
            if not icon_val.valid:
                warn_msg = "; ".join(icon_val.warnings) or "Icon pack is incomplete or invalid."
                if force:
                    warnings.append(
                        f"Icon theme '{theme_set.icon_theme}' is incomplete: {warn_msg}"
                    )
                else:
                    raise ThemeValidationError(
                        f"Icon theme '{theme_set.icon_theme}' is invalid: {warn_msg}"
                    )
            elif icon_val.warnings:
                warnings.extend(icon_val.warnings)

        if theme_set.cursor_theme is not None:
            found_cursor = self._scanner.find_theme(theme_set.cursor_theme, ThemeType.CURSOR)
            if not found_cursor:
                raise ThemeNotFoundError(
                    f"Cursor theme '{theme_set.cursor_theme}' was not found on the system."
                )
            cursor_val = self._validator.validate(found_cursor.path, ThemeType.CURSOR)
            if not cursor_val.valid:
                warn_msg = (
                    "; ".join(cursor_val.warnings) or "Cursor theme is incomplete or invalid."
                )
                if force:
                    warnings.append(
                        f"Cursor theme '{theme_set.cursor_theme}' is incomplete: {warn_msg}"
                    )
                else:
                    raise ThemeValidationError(
                        f"Cursor theme '{theme_set.cursor_theme}' is invalid: {warn_msg}"
                    )
            elif cursor_val.warnings:
                warnings.extend(cursor_val.warnings)

        found_shell: Theme | None = None
        if theme_set.shell_theme is not None:
            found_shell = self._scanner.find_theme(theme_set.shell_theme, ThemeType.SHELL)
            if not found_shell:
                raise ThemeNotFoundError(
                    f"GNOME Shell theme '{theme_set.shell_theme}' was not found on the system."
                )
            shell_val = self._validator.validate(found_shell.path, ThemeType.SHELL)
            if not shell_val.valid:
                warn_msg = "; ".join(shell_val.warnings) or "Shell theme is incomplete or invalid."
                if force:
                    warnings.append(
                        f"GNOME Shell theme '{theme_set.shell_theme}' is incomplete: {warn_msg}"
                    )
                else:
                    raise ThemeValidationError(
                        f"GNOME Shell theme '{theme_set.shell_theme}' is invalid: {warn_msg}"
                    )
            elif shell_val.warnings:
                warnings.extend(shell_val.warnings)

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
        force: bool = False,
    ) -> ApplyResult:
        """Apply a unified global theme (matching name across GTK and Shell).

        Args:
            theme_name: Theme name to look for as GTK and Shell.
            color_scheme: Optional color scheme ('default', 'prefer-dark', 'prefer-light').
            apply_gtk4_override: If True, apply GTK4 override when available.
            propagate_sandbox: If True, propagate themes to Flatpak and Snap apps.
            force: If True, bypass ThemeValidationError and apply anyway.

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
            force=force,
        )

    def apply_component(
        self,
        component: ThemeType,
        theme_name: str,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
        force: bool = False,
    ) -> ApplyResult:
        """Apply a single theme component (GTK, icons, cursors, shell).

        Args:
            component: Theme category (ThemeType.GTK, ICON, CURSOR, SHELL).
            theme_name: Theme name to apply.
            apply_gtk4_override: If True, apply GTK4 override for GTK themes.
            propagate_sandbox: If True, propagate GTK themes and icon packs to Flatpak and Snap.
            force: If True, bypass ThemeValidationError and apply anyway.

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
            force=force,
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
    # Global Themes Management (Phase 1)
    # -------------------------------------------------------------------------

    def list_global_themes(self) -> list[GlobalTheme]:
        """List all available global themes (bundled and user-created).

        Returns:
            Alphabetically ordered list of GlobalTheme instances.
        """
        return self._global_themes.list_global_themes()

    def get_global_theme(self, theme_id: str) -> GlobalTheme | None:
        """Find a global theme by ID or name.

        Args:
            theme_id: Identifier or name of the global theme.

        Returns:
            GlobalTheme if found, None otherwise.
        """
        return self._global_themes.get_global_theme(theme_id)

    def apply_global_theme(
        self,
        theme_id: str,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Apply all components of a global theme to the desktop.

        Args:
            theme_id: Identifier or name of the global theme to apply.
            propagate_sandbox: If True, propagate theme changes to sandbox runtimes.

        Returns:
            ApplyResult summarizing results and any warnings.

        Raises:
            ThemeNotFoundError: If the global theme ID is not found.
        """
        theme = self.get_global_theme(theme_id)
        if theme is None:
            raise ThemeNotFoundError(f"Global theme '{theme_id}' not found.")

        logger.info("Applying global theme: '%s' (%s)", theme.name, theme.id)
        return self.apply_themes(theme.components, propagate_sandbox=propagate_sandbox)

    def save_current_as_global_theme(
        self,
        name: str,
        description: str = "",
        overwrite: bool = False,
    ) -> GlobalTheme:
        """Save active desktop configuration as a user-created Global Theme.

        Args:
            name: User-facing name for the theme.
            description: Optional summary description.
            overwrite: If True, replace existing user theme with same name.

        Returns:
            Saved GlobalTheme instance.
        """
        current_themes = self.get_current_themes()
        return self._global_themes.save_global_theme(
            name=name,
            theme_set=current_themes,
            description=description,
            overwrite=overwrite,
        )

    def save_theme_composition(
        self,
        composition: ThemeComposition,
        overwrite: bool = False,
    ) -> GlobalTheme:
        """Save a ThemeComposition as a user-composed Global Theme.

        Args:
            composition: ThemeComposition object containing component selections.
            overwrite: If True, replace existing user theme with same name.

        Returns:
            Saved GlobalTheme instance.
        """
        return self._theme_mixer.mix_and_save(composition, overwrite=overwrite)

    def delete_global_theme(self, theme_id_or_name: str) -> bool:
        """Delete a user-created Global Theme.

        Args:
            theme_id_or_name: ID or name of the user global theme.

        Returns:
            True if deleted.
        """
        return self._global_themes.delete_global_theme(theme_id_or_name)

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
