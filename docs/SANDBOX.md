# 📦 Sandbox Integration (Flatpak & Snap)

GNOME Theme Manager features native integration for sandboxed applications running in **Flatpak** and **Snap** environments, ensuring custom user themes apply seamlessly without visual breaks.

---

## 🔹 1. Flatpak Theme Propagation

User themes installed in `~/.themes` or `~/.icons` are normally isolated from Flatpak sandboxes by default.

When themes are applied, GNOME Theme Manager automatically propagates access across Flatpak applications using filesystem overrides:
```bash
flatpak override --user --filesystem=xdg-data/themes:ro
flatpak override --user --filesystem=xdg-data/icons:ro
```

You can inspect Flatpak status via:
```bash
gnome-theme-manager sandbox-status
```

---

## 🔹 2. Snap Custom Theme Support

Confined Snap applications (such as Firefox, Chromium, or Thunderbird) cannot directly read arbitrary user directories.

### Standard System Themes
Standard system themes rely on the official `gtk-common-themes` snap:
```bash
sudo snap install gtk-common-themes
```

### Custom User Themes (Content Snaps)
For third-party or user-created themes, GNOME Theme Manager dynamically generates and connects local **Content Snaps** (`custom-theme-<name>`):
1. Packages the theme directory using `mksquashfs`.
2. Registers the content snap in snapd.
3. Connects the theme slot to snap consumer plugs.

### Prerequisites for Snap Packaging
- `snapd` (standard on Ubuntu)
- `squashfs-tools` (provides `mksquashfs` for instant packaging):
  ```bash
  sudo apt install squashfs-tools
  ```
- `policykit-1` / `pkexec` (standard in GNOME for graphical root authorization)
