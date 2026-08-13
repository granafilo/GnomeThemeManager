#!/usr/bin/env bash
# =============================================================================
# GnomeThemeManager - Script di Inizializzazione Ambiente di Sviluppo e Test
# =============================================================================
# Questo script:
# 1. Verifica la presenza di Python 3 e dei pacchetti di sistema richiesti (PyGObject).
# 2. Crea il virtual environment (.venv) con supporto a --system-site-packages.
# 3. Installa e aggiorna le dipendenze di runtime e di sviluppo (pytest, ruff, ecc.).
# 4. Installa il pacchetto in modalità editabile (pip install -e .).
# 5. Esegue un test di verifica diagnostico.
# =============================================================================

set -e

# Colori per l'output nel terminale
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Posizionamento nella radice del progetto
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  Inizializzazione Ambiente: GnomeThemeManager       ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Verifica Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERRORE] Python 3 non trovato. Installa Python con:${NC}"
    echo "  sudo apt update && sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}✓ Trovato:${NC} $PYTHON_VERSION"

# 2. Controllo dipendenze di sistema Ubuntu per PyGObject (GSettings / Gio) e Tkinter (GUI)
echo -e "\n${BLUE}[1/4] Verifica dipendenze di sistema GNOME/PyGObject e Tkinter...${NC}"
if ! dpkg -s python3-gi &> /dev/null || ! dpkg -s python3-tk &> /dev/null; then
    echo -e "${YELLOW}[AVVISO] Alcuni pacchetti di sistema consigliati non sembrano installati.${NC}"
    echo "Per garantire la piena compatibilità con GSettings e la GUI Tkinter su Ubuntu, esegui:"
    echo -e "${YELLOW}  sudo apt update && sudo apt install -y python3-gi python3-tk libglib2.0-0 gnome-shell-extension-user-theme${NC}"
else
    echo -e "${GREEN}✓ Pacchetti di sistema python3-gi e python3-tk presenti.${NC}"
fi

# 3. Creazione del Virtual Environment (.venv)
echo -e "\n${BLUE}[2/4] Configurazione del virtual environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    echo "Creazione nuovo virtualenv con accesso a system site packages..."
    python3 -m venv --system-site-packages .venv
    echo -e "${GREEN}✓ Cartella .venv creata con successo.${NC}"
else
    echo -e "${GREEN}✓ Virtualenv .venv già esistente.${NC}"
fi

# 4. Attivazione ed installazione dipendenze
echo -e "\n${BLUE}[3/4] Installazione dipendenze e pacchetto locale...${NC}"
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip --quiet
pip install -e .[dev] --quiet

echo -e "${GREEN}✓ Dipendenze installate (pytest, pytest-cov, ruff, gnome_theme_manager).${NC}"

# 5. Test diagnostico di import e verifica
echo -e "\n${BLUE}[4/4] Esecuzione verifica diagnostica...${NC}"
python3 -c "
import sys
from gnome_theme_manager.core import ThemeManager, PresetManager

manager = ThemeManager()
status = manager.get_system_status()

print('  - PyGObject / GSettings disponibile:', status.gsettings_available)
print('  - Supporto GNOME Shell Theme:       ', status.shell_theme_supported)
print('  - Cartella temi utente:             ', status.user_themes_path)
print('  - Cartella icone utente:            ', status.user_icons_path)
print('  - Preset disponibili:               ', len(manager.list_presets()))
"

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  ✓ Ambiente pronto all'uso!                         ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "Per attivare l'ambiente nella tua shell corrente, digita:\n"
echo -e "  ${YELLOW}source .venv/bin/activate${NC}\n"
echo -e "Per avviare la suite di test completa:\n"
echo -e "  ${YELLOW}pytest -v${NC}\n"
echo -e "Per usare la CLI del manager:\n"
echo -e "  ${YELLOW}gnome-theme-manager current${NC}"
echo -e "  ${YELLOW}gnome-theme-manager list${NC}"
echo -e "  ${YELLOW}gnome-theme-manager preset list${NC}\n"
