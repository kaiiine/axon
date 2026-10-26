#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  Axon — Script de déploiement
#  Usage : bash setup.sh [--config-only]
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# Toujours travailler dans le dépôt, quel que soit le dossier d'où on lance
# le script : sinon `bash ai-agent/setup.sh` créerait .venv et .env à côté.
cd "$(dirname "${BASH_SOURCE[0]}")"

# Le venv du dépôt : `.venv` s'il existe, sinon un `venv` historique réutilisé
# tel quel (voir l'étape « Environnement virtuel »), sinon `.venv` à créer.
dossier_venv() {
    if [[ -d ".venv" ]]; then
        echo ".venv"
    elif [[ -d "venv" ]]; then
        echo "venv"
    else
        echo ".venv"
    fi
}

ORANGE='\033[38;5;214m'
ORANGE_DIM='\033[38;5;172m'
WHITE='\033[0;97m'
GREEN='\033[38;5;78m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓  ${NC}$*"; }
info() { echo -e "${ORANGE}  →  ${NC}$*"; }
warn() { echo -e "${ORANGE_DIM}  ⚠  ${NC}$*"; }
fail() { echo -e "${RED}  ✗  ${NC}$*"; exit 1; }
step() { echo -e "\n${ORANGE}━━  ${WHITE}$*${NC}"; }

# ── Bannière ──────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${ORANGE}  ██████╗ ██╗  ██╗ ██████╗ ███╗  ██╗${NC}"
    echo -e "${ORANGE} ██╔══██╗╚██╗██╔╝██╔═══██╗████╗ ██║${NC}"
    echo -e "${ORANGE} ███████║ ╚███╔╝ ██║   ██║██╔██╗██║${NC}"
    echo -e "${ORANGE} ██╔══██║ ██╔██╗ ██║   ██║██║╚████║${NC}"
    echo -e "${ORANGE} ██║  ██║██╔╝ ██╗╚██████╔╝██║ ╚███║${NC}"
    echo -e "${ORANGE} ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚══╝${NC}"
    echo ""
}

# ── Configuration ─────────────────────────────────────────────
# Le menu des intégrations est commun à setup.sh et setup.ps1 :
# src/installation/configuration.py (bibliothèque standard uniquement).
configurer() {
    local python
    python="$(dossier_venv)/bin/python"
    [[ -x "$python" ]] || python="python3"
    "$python" -m src.installation.configuration "$@"
}

# Les modèles locaux : l'embedding (requis), un LLM local (optionnel).
installer_modeles_ollama() {
    step "Modèles Ollama"

    if ! command -v ollama &>/dev/null; then
        warn "Ollama absent — modèles ignorés. Relance le setup une fois Ollama installé."
        return
    fi
    if ! ollama list &>/dev/null 2>&1; then
        info "Démarrage d'Ollama en arrière-plan..."
        ollama serve &>/dev/null &
        sleep 3
    fi

    if ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
        ok "nomic-embed-text (embedding) déjà présent"
    else
        info "Téléchargement de nomic-embed-text (~274 MB, requis)..."
        ollama pull nomic-embed-text
        ok "nomic-embed-text prêt"
    fi

    echo ""
    if ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
        ok "qwen2.5:7b déjà présent"
    else
        echo -e "  ${DIM}Backend local optionnel — utile si tu n'as pas accès au cloud${NC}"
        read -rp "  $(echo -e "${ORANGE}?${NC}") Télécharger qwen2.5:7b pour le backend local ? [o/N] " pull_local
        if [[ "$pull_local" =~ ^[oOyY]$ ]]; then
            info "Téléchargement de qwen2.5:7b (~4.4 GB)..."
            ollama pull qwen2.5:7b
            ok "qwen2.5:7b prêt"
        fi
    fi
}

# ──────────────────────────────────────────────────────────────
#  RAPPELS ET ÎLE
# ──────────────────────────────────────────────────────────────

# Le démon des rappels (src/cron_daemon.py) avec la session : sans lui, aucun
# rappel d'échéance ni récapitulatif d'études ne part.
installer_rappels() {
    step "Démon des rappels"
    local venv="$1"
    case "$(uname -s)" in
        Linux)
            if ! command -v systemctl &>/dev/null || ! systemctl --user show-environment &>/dev/null; then
                warn "systemd utilisateur indisponible — lance le démon à la main :"
                warn "  $venv/bin/python -m src.cron_daemon"
                return
            fi
            # L'unité du dépôt vise ~/Documents/projets-perso/axon et .venv :
            # on l'écrit avec le vrai dossier et le vrai venv.
            mkdir -p "$HOME/.config/systemd/user"
            sed -e "s|%h/Documents/projets-perso/axon/.venv|$(pwd)/$venv|" \
                -e "s|%h/Documents/projets-perso/axon|$(pwd)|" \
                ops/systemd/axon-cron.service > "$HOME/.config/systemd/user/axon-cron.service"
            systemctl --user daemon-reload
            systemctl --user enable --now axon-cron.service &>/dev/null \
                && ok "axon-cron.service actif (démarre avec la session graphique)" \
                || warn "axon-cron.service installé mais pas démarré — systemctl --user status axon-cron"
            ;;
        Darwin)
            sh ops/launchd/installer-rappels.sh && ok "LaunchAgent fr.axon.rappels actif"
            ;;
        *)
            warn "Système non géré ici — Windows : ops\\windows\\installer-rappels.ps1"
            ;;
    esac
}

# L'île est un plugin (axon-overlay), installé par la marketplace depuis ce
# dépôt : GTK sous Linux/Wayland, l'app Tauri sous macOS et Windows.
installer_ile() {
    step "Île (plugin axon-overlay)"
    echo -e "  ${DIM}Demandes, rappels d'études et réponses en direct dans la barre du système.${NC}"
    read -rp "  $(echo -e "${ORANGE}?${NC}") Installer l'île ? [o/N] " rep
    if [[ ! "$rep" =~ ^[oOyY]$ ]]; then
        info "Plus tard, dans Axon : /plugin"
        return
    fi

    if [[ "$(uname -s)" == "Linux" ]]; then
        local manquants=()
        /usr/bin/python3 -c "import gi" &>/dev/null || manquants+=("python-gobject")
        /usr/bin/python3 -c "import gi; gi.require_version('Gtk', '4.0')" &>/dev/null || manquants+=("gtk4")
        /usr/bin/python3 -c "import gi; gi.require_version('WebKit', '6.0')" &>/dev/null || manquants+=("webkitgtk-6.0")
        [[ -e /usr/lib/libgtk4-layer-shell.so ]] || manquants+=("gtk4-layer-shell")
        if (( ${#manquants[@]} )); then
            warn "Dépendances système manquantes : ${manquants[*]}"
            warn "  sudo pacman -S ${manquants[*]}"
            return
        fi
        ok "GTK4, gtk4-layer-shell et WebKitGTK présents"
    fi

    "$(dossier_venv)/bin/python" -m src.plugins install ./axon-overlay \
        || warn "Installation de l'île échouée — dans Axon : /plugin install ./axon-overlay"
}

# ──────────────────────────────────────────────────────────────
#  DÉPLOIEMENT
# ──────────────────────────────────────────────────────────────

deploy() {
    # ── 1. Prérequis système ──────────────────────────────────
    step "Prérequis système"

    local systeme
    systeme="$(uname -s)"
    local conseil_python="sudo pacman -S python   ou   sudo apt install python3 python3-venv"
    [[ "$systeme" == "Darwin" ]] && conseil_python="brew install python@3.12   (ou https://www.python.org/downloads/)"

    if ! command -v python3 &>/dev/null; then
        fail "Python 3 introuvable. Installe Python 3.11+ puis relance : $conseil_python"
    fi
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ) ]]; then
        fail "Python 3.11+ requis (version actuelle : $PY_VERSION) : $conseil_python"
    fi
    ok "Python $PY_VERSION"

    if command -v ollama &>/dev/null; then
        ok "Ollama $(ollama --version 2>/dev/null | head -1)"
    elif [[ "$systeme" == "Darwin" ]]; then
        # Le script d'installation d'ollama.com ne vise que Linux.
        if command -v brew &>/dev/null; then
            info "Ollama non installé — installation via Homebrew..."
            brew install ollama && ok "Ollama installé"
        else
            warn "Ollama absent — installe l'app : https://ollama.com/download"
        fi
    else
        warn "Ollama non installé — installation..."
        curl -fsSL https://ollama.com/install.sh | sh && ok "Ollama installé"
    fi

    if command -v libreoffice &>/dev/null || command -v soffice &>/dev/null; then
        ok "LibreOffice (export PDF)"
    else
        warn "LibreOffice absent — export PDF des lettres indisponible"
        if [[ "$systeme" == "Darwin" ]]; then
            warn "  brew install --cask libreoffice"
        else
            warn "  sudo pacman -S libreoffice-still   ou   sudo apt install libreoffice"
        fi
    fi

    # macOS : /paste lit le presse-papiers par Pillow, sans outil externe.
    if [[ "$systeme" == "Linux" ]]; then
        if command -v wl-paste &>/dev/null || command -v xclip &>/dev/null || command -v xsel &>/dev/null; then
            ok "Presse-papiers ($(command -v wl-paste &>/dev/null && echo 'wl-clipboard' || echo 'xclip/xsel'))"
        else
            warn "Presse-papiers absent — commande /paste indisponible"
            warn "  Wayland : sudo pacman -S wl-clipboard   ou   sudo apt install wl-clipboard"
            warn "  X11     : sudo pacman -S xclip           ou   sudo apt install xclip"
        fi
    fi

    # ── 2. Environnement virtuel ──────────────────────────────
    step "Environnement virtuel Python"

    # `.venv` pour une installation neuve : c'est la convention que suivent uv,
    # Poetry, VS Code et PyCharm. Un `venv` déjà présent est RÉUTILISÉ, jamais
    # renommé : `bin/activate` et les scripts (`pip`…) gardent le chemin
    # absolu d'origine, un `mv` les casse — et les services systemd qui
    # pointent sur `venv/bin/python` (axon-cron…) avec.
    VENV_DIR="$(dossier_venv)"
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Création du venv..."
        python3 -m venv "$VENV_DIR"
        ok "$VENV_DIR créé → $(pwd)/$VENV_DIR"
    else
        ok "$VENV_DIR déjà présent → $(pwd)/$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    ok "$VENV_DIR activé"

    # ── 3. Dépendances ────────────────────────────────────────
    step "Dépendances Python"

    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    ok "requirements.txt installé"

    # ── 3b. Playwright (browser headless) ────────────────────
    echo ""
    if "$VENV_DIR/bin/python" -c "from playwright.sync_api import sync_playwright; b = sync_playwright().start(); b.stop()" &>/dev/null 2>&1; then
        ok "Playwright — navigateur déjà installé"
    else
        info "Installation des binaires Playwright (Chromium, ~200 MB)..."
        "$VENV_DIR/bin/python" -m playwright install chromium --with-deps --quiet 2>/dev/null \
            || "$VENV_DIR/bin/python" -m playwright install chromium 2>/dev/null \
            || warn "Playwright install échoué — l'agent browser sera indisponible"
        ok "Playwright — Chromium prêt"
    fi

    # ── 3c. RTK (proxy CLI token-efficient) ───────────────────
    echo ""
    if command -v rtk &>/dev/null; then
        ok "rtk déjà installé ($(rtk --version 2>/dev/null || echo 'version inconnue'))"
    else
        echo -e "  ${DIM}rtk compresse les outputs shell pour économiser 60-90% de tokens LLM${NC}"
        read -rp "  $(echo -e "${ORANGE}?${NC}") Installer rtk ? [o/N] " install_rtk
        if [[ "$install_rtk" =~ ^[oOyY]$ ]]; then
            info "Installation de rtk..."
            curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
            ok "rtk installé"
        else
            info "rtk ignoré (optionnel)"
        fi
    fi

    # ── 4. .env ───────────────────────────────────────────────
    step "Fichier de configuration"

    # Le CHEMIN, pas seulement le fait. Le setup s'exécute dans le dossier
    # d'installation, qui n'est pas forcément celui d'où on l'a lancé : dire
    # « .env déjà présent » sans dire où envoie chercher le fichier au mauvais
    # endroit, et conclure qu'il n'a pas été créé.
    if [[ ! -f ".env" ]]; then
        cp .env.sample .env
        ok ".env créé → $(pwd)/.env"
    else
        ok ".env déjà présent → $(pwd)/.env"
    fi
    configurer identite

    # ── 5. Modèles Ollama ─────────────────────────────────────
    installer_modeles_ollama

    # ── 6. Rappels et île ─────────────────────────────────────
    installer_rappels "$VENV_DIR"
    installer_ile

    # ── 7. Configuration des services ─────────────────────────
    configurer menu
}

# ──────────────────────────────────────────────────────────────
#  ENTRÉE
# ──────────────────────────────────────────────────────────────

banner

if [[ "${1:-}" == "--config-only" ]]; then
    # Juste reconfigurer les services sans tout réinstaller
    if [[ ! -f ".env" ]]; then
        cp .env.sample .env
        ok ".env créé depuis .env.sample"
    fi
    configurer identite
    configurer menu
else
    deploy
fi

# ── Récapitulatif final ───────────────────────────────────────
echo ""
configurer statut
echo -e "${ORANGE}  ─────────────────────────────────────${NC}"
echo -e "${ORANGE}  Prêt.${NC}"
echo ""
echo -e "  ${WHITE}Lancer Axon :${NC}"
echo -e "    ${ORANGE}source $(dossier_venv)/bin/activate${NC}"
echo -e "    ${ORANGE}python -m src.ui.main${NC}"
echo ""
echo -e "  ${DIM}Reconfigurer les intégrations :${NC}  ${ORANGE}bash setup.sh --config-only${NC}"
echo ""
