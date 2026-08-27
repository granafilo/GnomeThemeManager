# 📦 Sandbox Integration Guide (Flatpak & Snap)

GNOME Theme Manager features native integration for sandboxed applications running in **Flatpak** and **Snap** environments, ensuring custom GTK themes, icons, and cursor styles apply seamlessly without visual breakage or fallback glitches.

This guide provides both automated workflows (via GUI/CLI) and manual step-by-step instructions for troubleshooting and advanced customization.

---

## 🔹 1. Flatpak Theme Overrides

Flatpak applications run inside isolated mount namespaces. By default, they do not have read access to user-installed theme directories (`~/.local/share/themes`, `~/.local/share/icons`, `~/.themes`, or `~/.icons`).

### Automated Propagation (Recommended)

When you apply a theme in GNOME Theme Manager or click **Propagate Theme to Sandboxed Apps** in the **Sandbox** page, the application automatically executes user-level filesystem overrides for you:

```bash
# Handled automatically by GNOME Theme Manager:
flatpak override --user --filesystem=xdg-data/themes:ro
flatpak override --user --filesystem=xdg-data/icons:ro
flatpak override --user --filesystem=~/.themes:ro
flatpak override --user --filesystem=~/.icons:ro
```

### Manual Configuration Guide

If you need to configure Flatpak overrides manually via terminal:

#### 1. User-Level Global Overrides (Applies to all Flatpak apps)
Run the following commands in your terminal:
```bash
# Grant read-only access to standard user theme and icon folders
flatpak override --user --filesystem=xdg-data/themes:ro
flatpak override --user --filesystem=xdg-data/icons:ro
flatpak override --user --filesystem=~/.themes:ro
flatpak override --user --filesystem=~/.icons:ro
```

#### 2. System-Wide Global Overrides (Optional, requires root)
```bash
sudo flatpak override --filesystem=xdg-data/themes:ro
sudo flatpak override --filesystem=xdg-data/icons:ro
```

#### 3. Single Application Override
To grant theme access to a specific Flatpak app (e.g., Firefox or Spotify):
```bash
# Replace org.mozilla.firefox with the target application ID
flatpak override --user org.mozilla.firefox --filesystem=xdg-data/themes:ro
flatpak override --user org.mozilla.firefox --filesystem=xdg-data/icons:ro
```

#### 4. Verifying Flatpak Overrides
To verify active overrides on your system:
```bash
# List global user overrides
flatpak override --user --show

# Check status via GNOME Theme Manager CLI
gnome-theme-manager sandbox-status
```

#### 5. Resetting / Removing Overrides
If you ever want to reset all user-level Flatpak overrides:
```bash
flatpak override --user --reset
```

> **Note:** After applying filesystem overrides, running Flatpak applications must be restarted for the changes to take effect.

---

## 🔹 2. Snap Custom Theme Support & Content Snaps

Confined Snap applications (such as Chromium, Firefox, Thunderbird, or VS Code) use AppArmor profiles and cannot read arbitrary directories under `~/.local/share/themes` or `/usr/share/themes`.

### Standard System Themes (`gtk-common-themes`)

System themes provided by Ubuntu and GNOME (such as *Yaru*, *Adwaita*, *HighContrast*) are distributed via the official `gtk-common-themes` snap package:

```bash
# Install common themes snap if not present
sudo snap install gtk-common-themes
```

### Custom Themes via Content Snaps (GNOME Theme Manager Engine)

For third-party and custom themes, GNOME Theme Manager provides an instant Content Snap builder (`core/theme_snap_manager`):
1. Packages the custom theme using `mksquashfs` into a local Snap in `< 1s`.
2. Installs the Content Snap locally using `snap install --dangerous`.
3. Connects the theme slot to all installed Snap application plugs under a single, unified PolicyKit (`pkexec`) authorization prompt.

### Manual Snap Connection Guide

If you need to connect standard or custom theme plugs manually:

#### 1. Inspect Available Theme Plugs on a Snap App
```bash
# Check theme connections for a specific snap (e.g., firefox)
snap connections firefox | grep -E "gtk-3-themes|icon-themes"
```

#### 2. Connect GTK Theme and Icon Plugs Manually
```bash
# Connect GTK-3 themes from gtk-common-themes to an app
sudo snap connect <snap-name>:gtk-3-themes gtk-common-themes:gtk-3-themes

# Connect Icon themes from gtk-common-themes to an app
sudo snap connect <snap-name>:icon-themes gtk-common-themes:icon-themes
```
*Example for Firefox:*
```bash
sudo snap connect firefox:gtk-3-themes gtk-common-themes:gtk-3-themes
sudo snap connect firefox:icon-themes gtk-common-themes:icon-themes
```

#### 3. Installing a Locally Built Custom Theme Snap Manually
If you have packaged a theme snap file (`custom-theme-<name>.snap`):
```bash
sudo snap install --dangerous ./custom-theme-mytheme.snap
sudo snap connect <snap-name>:gtk-3-themes custom-theme-mytheme:gtk-3-themes
```

### Prerequisites for Snap Theming
- `snapd` (standard on Ubuntu)
- `squashfs-tools` (provides `mksquashfs`):
  ```bash
  sudo apt install squashfs-tools
  ```
- `policykit-1` / `pkexec` (standard in GNOME for graphical privilege escalation)

---

## 🔹 3. Live Sandbox Diagnostics

You can inspect the real-time status of both Flatpak and Snap environments at any time:
- **GUI:** Open GNOME Theme Manager and navigate to the **Sandbox** page or **Desktop Status** page.
- **CLI:** Run `gnome-theme-manager sandbox-status`.
