#!/usr/bin/env python3
"""Standalone script to detect GNOME version and output required theme structure.

Self-contained: requires only Python 3 standard library.
Can be copied and executed directly on any Linux distribution (Ubuntu, Fedora, Arch, Debian, etc.).
"""

import os
import re
import subprocess


def detect_gnome_version() -> tuple[str, int, int]:
    """Detect GNOME version via shell command, gdbus, xml, or environment."""
    # 1. Environment variable override
    env_ver = os.environ.get("GNOME_VERSION", "").strip()
    if env_ver:
        m = re.search(r"(\d+)(?:\.(\d+|alpha|beta|rc\d*))?", env_ver)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else 0
            return (env_ver, major, minor)

    # 2. gnome-shell --version command
    try:
        res = subprocess.run(
            ["gnome-shell", "--version"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            raw = res.stdout.strip()
            m = re.search(r"(\d+)(?:\.(\d+|alpha|beta|rc\d*))?", raw)
            if m:
                major = int(m.group(1))
                minor = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else 0
                return (raw.replace("GNOME Shell ", ""), major, minor)
    except Exception:
        pass

    # 3. gdbus query to org.gnome.Shell
    try:
        res = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell",
                "--object-path",
                "/org/gnome/Shell",
                "--method",
                "org.freedesktop.DBus.Properties.Get",
                "org.gnome.Shell",
                "ShellVersion",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            m = re.search(r"<'([^']+)'", res.stdout)
            if m:
                ver_str = m.group(1)
                m2 = re.search(r"(\d+)(?:\.(\d+|alpha|beta|rc\d*))?", ver_str)
                if m2:
                    major = int(m2.group(1))
                    minor = int(m2.group(2)) if m2.group(2) and m2.group(2).isdigit() else 0
                    return (ver_str, major, minor)
    except Exception:
        pass

    # 4. Fallback XML parsing
    xml_path = "/usr/share/gnome/gnome-version.xml"
    if os.path.isfile(xml_path):
        try:
            with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            p_match = re.search(r"<platform>(\d+)</platform>", content)
            m_match = re.search(r"<minor>(\d+)</minor>", content)
            if p_match:
                major = int(p_match.group(1))
                minor = int(m_match.group(1)) if m_match else 0
                return (f"{major}.{minor}", major, minor)
        except Exception:
            pass

    return ("non rilevata", 0, 0)


def get_required_structure(major: int, minor: int) -> dict:
    if major >= 50:
        return {
            "summary": "gtk-4.0/gtk.css + gtk-4.0/libadwaita.css (o libadwaita.css) + gnome-shell/gnome-shell.css",
            "details": [
                "1. ThemeName/gtk-4.0/gtk.css (obbligatorio per GTK 4)",
                "2. ThemeName/gtk-4.0/libadwaita.css oppure ThemeName/libadwaita.css (obbligatorio per Libadwaita)",
                "3. ThemeName/gnome-shell/gnome-shell.css (obbligatorio per Shell theme)",
                "4. ThemeName/index.theme (metadati)",
            ],
            "note": (
                "GNOME 50+ richiede tassativamente i fogli di stile Libadwaita dedicati. "
                "La variabile d'ambiente GTK_THEME non ha più effetto sulle app Libadwaita."
            ),
        }
    elif major >= 42:
        return {
            "summary": "gtk-4.0/gtk.css + gnome-shell/gnome-shell.css + gtk-3.0/gtk.css (opzionale: libadwaita.css)",
            "details": [
                "1. ThemeName/gtk-4.0/gtk.css (obbligatorio per GTK 4/Libadwaita override)",
                "2. ThemeName/gnome-shell/gnome-shell.css (obbligatorio per Shell theme)",
                "3. ThemeName/gtk-3.0/gtk.css (per retrocompatibilità con app GTK 3)",
                "4. ThemeName/index.theme (metadati)",
            ],
            "note": "GNOME 42-49 supporta GTK4 e GTK3 tramite symlink in ~/.config/gtk-4.0/.",
        }
    elif major > 0:
        return {
            "summary": "gtk-3.0/gtk.css + gnome-shell/gnome-shell.css",
            "details": [
                "1. ThemeName/gtk-3.0/gtk.css (obbligatorio per GTK 3)",
                "2. ThemeName/gnome-shell/gnome-shell.css (per Shell theme)",
                "3. ThemeName/index.theme (metadati)",
            ],
            "note": "Versioni legacy di GNOME (< 42) non utilizzano Libadwaita.",
        }
    else:
        return {
            "summary": "gnome-shell non rilevato; struttura consigliata standard: gtk-4.0/gtk.css + gtk-4.0/libadwaita.css + gtk-3.0/gtk.css",
            "details": [
                "ThemeName/gtk-4.0/gtk.css",
                "ThemeName/gtk-4.0/libadwaita.css (oppure libadwaita.css)",
                "ThemeName/gnome-shell/gnome-shell.css",
            ],
            "note": "Ambiente GNOME non rilevato o shell non installata.",
        }


def main() -> None:
    ver_str, major, minor = detect_gnome_version()
    req = get_required_structure(major, minor)

    # Output richiesto dall'utente:
    print(f"versione {ver_str} rilevata - struttura richiesta: {req['summary']}")
    print("-" * 75)
    print("Dettagli struttura richiesta:")
    for item in req["details"]:
        print(f"  • {item}")
    print(f"\nNota: {req['note']}")

    # Verifica veloce dei temi utente locali
    user_theme_dir = os.path.expanduser("~/.local/share/themes")
    if os.path.isdir(user_theme_dir):
        print(f"\nVerifica temi installati in {user_theme_dir}:")
        themes = sorted(os.listdir(user_theme_dir))
        found = 0
        for t in themes:
            t_path = os.path.join(user_theme_dir, t)
            if not os.path.isdir(t_path):
                continue
            found += 1
            has_gtk4 = os.path.isfile(os.path.join(t_path, "gtk-4.0", "gtk.css"))
            has_libadw = (
                os.path.isfile(os.path.join(t_path, "gtk-4.0", "libadwaita.css"))
                or os.path.isfile(os.path.join(t_path, "libadwaita.css"))
                or os.path.isfile(os.path.join(t_path, "libadwaita", "libadwaita.css"))
            )
            has_shell = os.path.isfile(os.path.join(t_path, "gnome-shell", "gnome-shell.css"))

            status_tags = []
            if has_gtk4:
                status_tags.append("GTK4")
            if has_libadw:
                status_tags.append("Libadwaita")
            if has_shell:
                status_tags.append("Shell")

            tag_str = ", ".join(status_tags) if status_tags else "incompleto / solo GTK3"
            compat_flag = "✓" if (major < 50 or (has_gtk4 and has_libadw)) else "⚠"
            print(f"  [{compat_flag}] {t:<24} -> [{tag_str}]")

        if found == 0:
            print("  (Nessun tema installato in directory utente)")


if __name__ == "__main__":
    main()
