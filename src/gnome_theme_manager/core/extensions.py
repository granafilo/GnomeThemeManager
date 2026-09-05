# SPDX-License-Identifier: GPL-3.0-or-later

"""GNOME Shell extensions management module.

Provides inspection, listing, enable/disable toggle, and metadata parsing for
GNOME Shell extensions.
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import UI_PREFS_FILE

# Try importing Gio and GLib safely
try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    _GIO_AVAILABLE = True
except (ImportError, ValueError, AttributeError):  # pragma: no cover
    Gio = None
    GLib = None
    _GIO_AVAILABLE = False

logger = logging.getLogger("gnome_theme_manager.core")

USER_THEME_EXTENSION_ID = "user-theme@gnome-shell-extensions.gcampax.github.com"
USER_THEMES_IDS: tuple[str, ...] = (
    "user-theme@gnome-shell-extensions.gcampax.github.com",  # GNOME upstream, Ubuntu, Fedora, Zorin OS
    "user-theme@gnome-shell-extensions",  # Debian/variants
    "user-theme",  # Short name / CLI
    "user-theme@zorin.com",  # Legacy Zorin OS identifier
    "zorin-appearance@zorin.com",  # Zorin appearance helper
    "zorin-appearance@zorinos.com",  # Modern Zorin appearance extension
)
DEFAULT_USER_EXTENSIONS_DIR = Path("~/.local/share/gnome-shell/extensions").expanduser()
DEFAULT_SYSTEM_EXTENSIONS_DIR = Path("/usr/share/gnome-shell/extensions")


@dataclass
class GnomeExtension:
    """Represents an installed GNOME Shell extension."""

    uuid: str
    name: str
    description: str
    enabled: bool
    state: str = "INITIALIZED"
    version: str | None = None
    url: str | None = None
    is_user_level: bool = True
    path: Path | None = None
    error: str | None = None
    has_prefs: bool = False


@dataclass
class UIPrefs:
    """User UI preferences stored in ui_prefs.json."""

    auto_enable_user_theme: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            "auto_enable_user_theme": self.auto_enable_user_theme,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIPrefs":
        """Load preferences from dictionary."""
        return cls(
            auto_enable_user_theme=bool(data.get("auto_enable_user_theme", False)),
        )


class ExtensionsManager:
    """Manager for GNOME Shell extensions and extension-related UI preferences."""

    def __init__(
        self,
        prefs_file: Path | None = None,
        user_extensions_dir: Path | None = None,
        system_extensions_dir: Path | None = None,
    ) -> None:
        """Initialize ExtensionsManager.

        Args:
            prefs_file: Optional Path to ui_prefs.json state file.
            user_extensions_dir: Optional path to user extensions directory.
            system_extensions_dir: Optional path to system extensions directory.
        """
        self.prefs_file = (
            Path(prefs_file).expanduser() if prefs_file is not None else UI_PREFS_FILE.expanduser()
        )
        self.user_extensions_dir = (
            Path(user_extensions_dir).expanduser()
            if user_extensions_dir is not None
            else DEFAULT_USER_EXTENSIONS_DIR
        )
        self.system_extensions_dir = (
            Path(system_extensions_dir).expanduser()
            if system_extensions_dir is not None
            else DEFAULT_SYSTEM_EXTENSIONS_DIR
        )

    def get_prefs(self) -> UIPrefs:
        """Load UI preferences from ui_prefs.json or return defaults."""
        if not self.prefs_file.is_file():
            return UIPrefs()
        try:
            content = self.prefs_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return UIPrefs.from_dict(data)
        except Exception as err:
            logger.warning("Failed to parse ui_prefs.json: %s", err)
        return UIPrefs()

    def save_prefs(self, prefs: UIPrefs) -> None:
        """Save UI preferences to ui_prefs.json atomically."""
        try:
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.prefs_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(prefs.to_dict(), f, indent=2)
            temp_file.replace(self.prefs_file)
        except Exception as err:
            logger.error("Failed to save ui_prefs.json: %s", err)

    def set_auto_enable_user_theme(self, enabled: bool) -> None:
        """Update the auto_enable_user_theme preference."""
        prefs = self.get_prefs()
        prefs.auto_enable_user_theme = enabled
        self.save_prefs(prefs)

    def get_enabled_uuids(self) -> set[str]:
        """Fetch set of enabled extension UUIDs via DBus, GSettings, or CLI."""
        # 1. Primary: DBus org.gnome.Shell.Extensions ListExtensions
        if _GIO_AVAILABLE and Gio is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                res = proxy.call_sync(
                    "ListExtensions",
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                if res is not None:
                    exts_dict = res.get_child_value(0).unpack()
                    if isinstance(exts_dict, dict) and exts_dict:
                        return {
                            str(uuid)
                            for uuid, info in exts_dict.items()
                            if isinstance(info, dict)
                            and (
                                bool(info.get("enabled", False))
                                or info.get("state") == 1.0
                                or info.get("state") == 1
                                or str(info.get("state")) in ("1", "1.0", "ACTIVE")
                            )
                        }
            except Exception as err:
                logger.debug("DBus ListExtensions for enabled UUIDs failed: %s", err)

        # 2. GSettings org.gnome.shell enabled-extensions
        if _GIO_AVAILABLE and Gio is not None:
            try:
                source = Gio.SettingsSchemaSource.get_default()
                if source is not None and source.lookup("org.gnome.shell", True) is not None:
                    settings = Gio.Settings(schema_id="org.gnome.shell")
                    raw = settings.get_strv("enabled-extensions")
                    if raw is not None:
                        return set(raw)
            except Exception as err:
                logger.debug("GSettings enabled-extensions query failed: %s", err)

        # 3. CLI if gnome-extensions is installed on PATH
        if shutil.which("gnome-extensions"):
            try:
                res = subprocess.run(
                    ["gnome-extensions", "list", "--enabled"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    return {line.strip() for line in res.stdout.splitlines() if line.strip()}
            except Exception as err:
                logger.debug("Failed to query enabled extensions via CLI: %s", err)

        return set()

    def is_user_theme_enabled(self) -> bool:
        """Check if the user-theme extension is enabled on GNOME Shell."""
        enabled_uuids = self.get_enabled_uuids()

        # 1. Exact match on supported user-theme UUIDs (fallback chain)
        for cand in USER_THEMES_IDS:
            if cand in enabled_uuids:
                logger.debug("User Themes extension detected active with UUID: %s", cand)
                return True

        # 2. Match any enabled extension with 'user-theme' or 'user theme' in UUID/name
        for ext in self.list_extensions():
            if ext.enabled and (
                "user-theme" in ext.uuid.lower()
                or "user theme" in ext.name.lower()
                or "user-theme" in ext.name.lower()
            ):
                logger.debug(
                    "User Themes extension matched enabled extension: uuid=%s name=%s",
                    ext.uuid,
                    ext.name,
                )
                return True

        # 3. Direct DBus query via org.gnome.Shell.Extensions (GetExtensionInfo)
        if _GIO_AVAILABLE and Gio is not None and GLib is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                for cand in USER_THEMES_IDS:
                    try:
                        res = proxy.call_sync(
                            "GetExtensionInfo",
                            GLib.Variant("(s)", (cand,)),
                            Gio.DBusCallFlags.NONE,
                            1000,
                            None,
                        )
                        if res is not None:
                            info = res.get_child_value(0).unpack()
                            if isinstance(info, dict):
                                state = info.get("state")
                                if (
                                    bool(info.get("enabled", False))
                                    or state == 1.0
                                    or state == 1
                                    or str(state) in ("1", "1.0", "ACTIVE")
                                ):
                                    logger.debug(
                                        "User Themes extension detected active via DBus GetExtensionInfo: %s",
                                        cand,
                                    )
                                    return True
                    except Exception as loop_err:
                        logger.debug("Error checking candidate %s: %s", cand, loop_err)
                        continue
            except Exception as dbus_err:
                logger.debug("DBus GetExtensionInfo check failed: %s", dbus_err)

        # 4. GSettings schema availability fallback
        if _GIO_AVAILABLE and Gio is not None:
            try:
                source = Gio.SettingsSchemaSource.get_default()
                if (
                    source is not None
                    and source.lookup("org.gnome.shell.extensions.user-theme", True) is not None
                ):
                    logger.debug("User Themes schema available in GSettings")
                    return True
            except Exception:
                pass

        # 5. Check if dconf has active shell theme configuration
        if shutil.which("dconf"):
            try:
                res = subprocess.run(
                    ["dconf", "read", "/org/gnome/shell/extensions/user-theme/name"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    logger.debug(
                        "User Themes dconf configuration detected: %s",
                        res.stdout.strip(),
                    )
                    return True
            except Exception:
                pass

        return False

    def enable_user_theme(self) -> bool:
        """Attempt to enable the user-theme extension."""
        for ext in self.list_extensions():
            if (
                "user-theme" in ext.uuid.lower() or "user theme" in ext.name.lower()
            ) and self.enable_extension(ext.uuid):
                return True
        for cand in USER_THEMES_IDS:
            if self.enable_extension(cand):
                return True
        return False

    def enable_extension(self, uuid: str) -> bool:
        """Enable an extension by UUID via DBus, GSettings, or CLI."""
        if not uuid:
            return False

        # 1. Try DBus org.gnome.Shell.Extensions
        if _GIO_AVAILABLE and Gio is not None and GLib is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                proxy.call_sync(
                    "EnableExtension",
                    GLib.Variant("(s)", (uuid,)),
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                return True
            except Exception as err:
                logger.debug("DBus EnableExtension failed for %s: %s", uuid, err)

        # 2. Try GSettings
        if _GIO_AVAILABLE and Gio is not None:
            try:
                source = Gio.SettingsSchemaSource.get_default()
                if source is not None and source.lookup("org.gnome.shell", True) is not None:
                    settings = Gio.Settings(schema_id="org.gnome.shell")
                    current = list(settings.get_strv("enabled-extensions"))
                    if uuid not in current:
                        current.append(uuid)
                        settings.set_strv("enabled-extensions", current)
                        return True
                    return True
            except Exception as err:
                logger.debug("GSettings EnableExtension failed for %s: %s", uuid, err)

        # 3. Try CLI if available
        if shutil.which("gnome-extensions"):
            try:
                res = subprocess.run(
                    ["gnome-extensions", "enable", uuid],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return res.returncode == 0
            except Exception as err:
                logger.debug("CLI enable failed for %s: %s", uuid, err)

        return False

    def disable_extension(self, uuid: str) -> bool:
        """Disable an extension by UUID via DBus, GSettings, or CLI."""
        if not uuid:
            return False

        # 1. Try DBus org.gnome.Shell.Extensions
        if _GIO_AVAILABLE and Gio is not None and GLib is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                proxy.call_sync(
                    "DisableExtension",
                    GLib.Variant("(s)", (uuid,)),
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                return True
            except Exception as err:
                logger.debug("DBus DisableExtension failed for %s: %s", uuid, err)

        # 2. Try GSettings
        if _GIO_AVAILABLE and Gio is not None:
            try:
                source = Gio.SettingsSchemaSource.get_default()
                if source is not None and source.lookup("org.gnome.shell", True) is not None:
                    settings = Gio.Settings(schema_id="org.gnome.shell")
                    current = list(settings.get_strv("enabled-extensions"))
                    if uuid in current:
                        current.remove(uuid)
                        settings.set_strv("enabled-extensions", current)
                        return True
                    return True
            except Exception as err:
                logger.debug("GSettings DisableExtension failed for %s: %s", uuid, err)

        # 3. Try CLI if available
        if shutil.which("gnome-extensions"):
            try:
                res = subprocess.run(
                    ["gnome-extensions", "disable", uuid],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return res.returncode == 0
            except Exception as err:
                logger.debug("CLI disable failed for %s: %s", uuid, err)

        return False

    def toggle_extension(self, uuid: str, enable: bool) -> bool:
        """Toggle an extension's active status."""
        return self.enable_extension(uuid) if enable else self.disable_extension(uuid)

    def uninstall_extension(self, uuid: str) -> bool:
        """Uninstall a user-level extension by UUID via DBus, CLI, or filesystem removal."""
        if not uuid:
            return False

        # 1. Try DBus org.gnome.Shell.Extensions UninstallExtension
        if _GIO_AVAILABLE and Gio is not None and GLib is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                proxy.call_sync(
                    "UninstallExtension",
                    GLib.Variant("(s)", (uuid,)),
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                return True
            except Exception as err:
                logger.debug("DBus UninstallExtension failed for %s: %s", uuid, err)

        # 2. Try CLI if available
        if shutil.which("gnome-extensions"):
            try:
                res = subprocess.run(
                    ["gnome-extensions", "uninstall", uuid],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    return True
            except Exception as err:
                logger.debug("gnome-extensions uninstall failed for %s: %s", uuid, err)

        # 3. Fallback: Direct directory deletion
        user_ext_dir = self.user_extensions_dir / uuid
        if user_ext_dir.is_dir():
            try:
                shutil.rmtree(user_ext_dir)
                return True
            except Exception as err:
                logger.error("Failed to delete extension directory %s: %s", user_ext_dir, err)
        return False

    def list_extensions(self) -> list[GnomeExtension]:
        """List all installed extensions (user and system)."""
        # 1. Primary: Query GNOME Shell DBus API
        if _GIO_AVAILABLE and Gio is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                res = proxy.call_sync(
                    "ListExtensions",
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                if res is not None:
                    exts_dict = res.get_child_value(0).unpack()
                    if isinstance(exts_dict, dict) and exts_dict:
                        result: list[GnomeExtension] = []
                        for uuid, info in exts_dict.items():
                            if not isinstance(info, dict):
                                continue
                            enabled_val = bool(info.get("enabled", False))
                            state_val = info.get("state")
                            state_str = (
                                "ACTIVE"
                                if enabled_val or state_val == 1.0
                                else ("ERROR" if state_val == 2.0 else "INITIALIZED")
                            )
                            is_user = info.get("type") == 2.0 or info.get("type") == 2
                            path_str = info.get("path")
                            path_obj = Path(path_str) if path_str else None
                            ver_raw = info.get("version")
                            version_str = (
                                str(int(ver_raw))
                                if isinstance(ver_raw, float) and ver_raw.is_integer()
                                else (str(ver_raw) if ver_raw is not None else None)
                            )

                            ext = GnomeExtension(
                                uuid=str(uuid),
                                name=str(info.get("name") or uuid),
                                description=str(info.get("description") or ""),
                                enabled=enabled_val or state_val == 1.0,
                                state=state_str,
                                version=version_str,
                                url=str(info.get("url")) if info.get("url") else None,
                                is_user_level=is_user,
                                path=path_obj,
                                error=str(info.get("error")) if info.get("error") else None,
                                has_prefs=bool(info.get("hasPrefs", False)),
                            )
                            result.append(ext)
                        return sorted(result, key=lambda e: e.name.lower())
            except Exception as err:
                logger.debug("DBus ListExtensions query failed: %s", err)

        # 2. Fallback: Directory scanner
        enabled_uuids = self.get_enabled_uuids()
        extensions_by_uuid: dict[str, GnomeExtension] = {}

        # Scan directories: user extensions have precedence over system
        search_dirs: list[tuple[Path, bool]] = [
            (self.user_extensions_dir, True),
            (self.system_extensions_dir, False),
            (Path("/run/host/share/gnome-shell/extensions"), False),
        ]

        for base_dir, is_user in search_dirs:
            if not base_dir.is_dir():
                continue
            for item in sorted(base_dir.iterdir()):
                if not item.is_dir():
                    continue
                meta_file = item / "metadata.json"
                if not meta_file.is_file():
                    continue
                try:
                    meta_raw = json.loads(meta_file.read_text(encoding="utf-8"))
                    if not isinstance(meta_raw, dict):
                        continue
                    uuid = str(meta_raw.get("uuid") or item.name)
                    if uuid in extensions_by_uuid:
                        continue  # Already processed from higher precedence dir

                    name = str(meta_raw.get("name") or uuid)
                    desc = str(meta_raw.get("description") or "")
                    ver_raw = meta_raw.get("version")
                    version = str(ver_raw) if ver_raw is not None else None
                    url = str(meta_raw.get("url")) if meta_raw.get("url") else None
                    is_enabled = uuid in enabled_uuids
                    has_prefs = (
                        (item / "prefs.js").is_file()
                        or (item / "prefs.ui").is_file()
                        or bool(meta_raw.get("hasPrefs"))
                    )

                    ext = GnomeExtension(
                        uuid=uuid,
                        name=name,
                        description=desc,
                        enabled=is_enabled,
                        state="ACTIVE" if is_enabled else "INITIALIZED",
                        version=version,
                        url=url,
                        is_user_level=is_user,
                        path=item,
                        has_prefs=has_prefs,
                    )
                    extensions_by_uuid[uuid] = ext
                except Exception as err:
                    logger.debug("Failed reading extension metadata in %s: %s", item, err)

        return sorted(extensions_by_uuid.values(), key=lambda e: e.name.lower())

    def get_extension(self, uuid: str) -> GnomeExtension | None:
        """Find an installed extension by its UUID."""
        for ext in self.list_extensions():
            if ext.uuid == uuid:
                return ext
        return None

    def get_store_url(self, uuid: str) -> str:
        """Get the extensions.gnome.org website URL for an extension or the main portal."""
        if uuid:
            return f"https://extensions.gnome.org/extension/{uuid}/"
        return "https://extensions.gnome.org/"

    def open_prefs(self, uuid: str) -> bool:
        """Launch preferences dialog for an extension via DBus or CLI."""
        if not uuid:
            return False

        # 1. Try DBus org.gnome.Shell.Extensions OpenExtensionPrefs
        if _GIO_AVAILABLE and Gio is not None and GLib is not None:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None,
                )
                try:
                    proxy.call_sync(
                        "OpenExtensionPrefs",
                        GLib.Variant("(ssa{sv})", (uuid, "", {})),
                        Gio.DBusCallFlags.NONE,
                        2000,
                        None,
                    )
                    return True
                except Exception:
                    proxy.call_sync(
                        "OpenExtensionPrefs",
                        GLib.Variant("(ss)", (uuid, "")),
                        Gio.DBusCallFlags.NONE,
                        2000,
                        None,
                    )
                    return True
            except Exception as err:
                logger.debug("DBus OpenExtensionPrefs failed for %s: %s", uuid, err)

        # 2. Try CLI if available
        if shutil.which("gnome-extensions"):
            try:
                subprocess.Popen(["gnome-extensions", "prefs", uuid])
                return True
            except Exception as err:
                logger.warning("Failed to launch prefs for extension %s: %s", uuid, err)

        return False

    def is_extensions_app_installed(self) -> bool:
        """Check if official GNOME Extensions or Extension Manager app is available on the system."""
        is_flatpak = Path("/.flatpak-info").exists()
        if is_flatpak and shutil.which("flatpak-spawn"):
            try:
                # 1. Check if com.mattjakeman.ExtensionManager or org.gnome.Extensions flatpak exists on host
                res = subprocess.run(
                    [
                        "flatpak-spawn",
                        "--host",
                        "flatpak",
                        "info",
                        "com.mattjakeman.ExtensionManager",
                    ],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if res.returncode == 0:
                    return True
                res_ext = subprocess.run(
                    ["flatpak-spawn", "--host", "flatpak", "info", "org.gnome.Extensions"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if res_ext.returncode == 0:
                    return True
                # 2. Check if host binaries exist
                for app in (
                    "extension-manager",
                    "gnome-extensions-app",
                    "gnome-shell-extension-prefs",
                ):
                    res_bin = subprocess.run(
                        ["flatpak-spawn", "--host", "which", app],
                        capture_output=True,
                        timeout=2,
                        check=False,
                    )
                    if res_bin.returncode == 0:
                        return True
            except Exception as err:
                logger.debug("Failed checking extension app via flatpak-spawn: %s", err)

        # Host checks
        for cmd in (
            "extension-manager",
            "gnome-extensions-app",
            "gnome-shell-extension-prefs",
        ):
            if shutil.which(cmd):
                return True

        if shutil.which("flatpak"):
            try:
                res = subprocess.run(
                    ["flatpak", "info", "com.mattjakeman.ExtensionManager"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if res.returncode == 0:
                    return True
                res2 = subprocess.run(
                    ["flatpak", "info", "org.gnome.Extensions"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if res2.returncode == 0:
                    return True
            except Exception:
                pass

        return False

    def open_extensions_app(self) -> bool:
        """Launch Extension Manager (com.mattjakeman.ExtensionManager) or fallback system app."""
        is_flatpak = Path("/.flatpak-info").exists()

        if is_flatpak and shutil.which("flatpak-spawn"):
            spawn_cmds = [
                ["flatpak-spawn", "--host", "flatpak", "run", "com.mattjakeman.ExtensionManager"],
                ["flatpak-spawn", "--host", "extension-manager"],
                ["flatpak-spawn", "--host", "gnome-extensions-app"],
                ["flatpak-spawn", "--host", "flatpak", "run", "org.gnome.Extensions"],
                ["flatpak-spawn", "--host", "gnome-shell-extension-prefs"],
                [
                    "flatpak-spawn",
                    "--host",
                    "gio",
                    "launch",
                    "com.mattjakeman.ExtensionManager.desktop",
                ],
            ]
            for cmd in spawn_cmds:
                try:
                    subprocess.Popen(cmd)
                    logger.info("Launched extension manager via flatpak-spawn: %s", cmd)
                    return True
                except Exception as err:
                    logger.debug("Failed flatpak-spawn launch %s: %s", cmd, err)

        # Host / non-flatpak execution
        for cmd in [
            ["extension-manager"],
            ["flatpak", "run", "com.mattjakeman.ExtensionManager"],
            ["gnome-extensions-app"],
            ["gnome-shell-extension-prefs"],
            ["flatpak", "run", "org.gnome.Extensions"],
        ]:
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    logger.info("Launched extension manager via: %s", cmd)
                    return True
                except Exception as err:
                    logger.debug("Failed launching %s: %s", cmd, err)

        logger.warning("No Extension Manager app found on the system.")
        return False
