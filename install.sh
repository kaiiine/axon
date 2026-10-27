#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  Axon — Installateur
#  Depuis un dépôt déjà cloné :  bash install.sh
#  Sans dépôt (one-line)       :  curl -fsSL https://ton-serveur.com/install.sh | bash
#  (`| bash`, pas `| sh` : le script utilise des syntaxes bash, `[[ … ]]`.)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ORANGE='\033[38;5;214m'
WHITE='\033[0;97m'
GREEN='\033[38;5;78m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓  ${NC}$*"; }
info() { echo -e "${ORANGE}  →  ${NC}$*"; }
fail() { echo -e "${RED}  ✗  ${NC}$*" >&2; exit 1; }
warn() { echo -e "${ORANGE}  ⚠  ${NC}$*"; }
step() { echo -e "\n${ORANGE}━━  ${WHITE}$*${NC}"; }

# ── À modifier selon ton hébergement ──────────────────────────
REPO_URL="https://github.com/kaiiine/axon.git"

#: Seul dossier qu'Axon crée à la racine du home : son ÉTAT (logs, JSON,
#: mémoire, pool de clés). Le code n'y va jamais — effacer le dépôt pour
#: réinstaller ne doit pas emporter ce qu'Axon a appris.
STATE_DIR="$HOME/.axon"

#: Lancé depuis un dépôt cloné (`bash install.sh`), on installe SUR PLACE :
#: le `.venv` et le `.env` vont dans ce dépôt. Avant, le script clonait
#: toujours une seconde copie dans ~/axon et y créait le `.venv`, loin du
#: dépôt sur lequel on travaille. Le clonage ne sert plus qu'au one-line
#: `curl | bash`, où aucun dépôt local n'existe encore.
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.git" && -f "$SCRIPT_DIR/setup.sh" ]]; then
    INSTALL_DIR="${AXON_INSTALL_DIR:-$SCRIPT_DIR}"
else
    INSTALL_DIR="${AXON_INSTALL_DIR:-$HOME/ai-agent}"
fi

#: Emplacement des anciennes installations, signalé plutôt que laissé vivre
#: en silence à côté de la nouvelle.
ANCIEN_DIR="$HOME/axon"
# ──────────────────────────────────────────────────────────────

echo ""
echo -e "${ORANGE}  ██████╗ ██╗  ██╗ ██████╗ ███╗  ██╗${NC}"
echo -e "${ORANGE} ██╔══██╗╚██╗██╔╝██╔═══██╗████╗ ██║${NC}"
echo -e "${ORANGE} ███████║ ╚███╔╝ ██║   ██║██╔██╗██║${NC}"
echo -e "${ORANGE} ██╔══██║ ██╔██╗ ██║   ██║██║╚████║${NC}"
echo -e "${ORANGE} ██║  ██║██╔╝ ██╗╚██████╔╝██║ ╚███║${NC}"
echo -e "${ORANGE} ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚══╝${NC}"
echo ""

# ── Prérequis : git ───────────────────────────────────────────
step "Vérification des prérequis"

if ! command -v git &>/dev/null; then
    info "git non trouvé — installation..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y git
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm git
    elif command -v brew &>/dev/null; then
        brew install git
    else
        fail "Installe git manuellement puis relance."
    fi
fi
ok "git $(git --version | cut -d' ' -f3)"

# ── Dépôt ─────────────────────────────────────────────────────
step "Dépôt d'Axon"

# Une installation précédente a pu cloner une seconde copie dans ~/axon. Pas
# supprimée d'office (elle contient peut-être un .env), mais signalée : deux
# copies côte à côte, c'est se demander pourquoi une modification n'a aucun
# effet.
if [[ -d "$ANCIEN_DIR/.git" && "$INSTALL_DIR" != "$ANCIEN_DIR" ]]; then
    warn "Ancienne copie d'Axon détectée dans $ANCIEN_DIR — elle n'est plus utilisée."
    if [[ -f "$ANCIEN_DIR/.env" && ! -f "$INSTALL_DIR/.env" ]]; then
        echo -e "  ${DIM}Récupère son .env avant de la supprimer :${NC}"
        echo -e "    ${ORANGE}cp $ANCIEN_DIR/.env $INSTALL_DIR/.env${NC}"
    fi
    echo -e "  ${DIM}Puis :${NC} ${ORANGE}rm -rf $ANCIEN_DIR${NC}"
    echo ""
fi

# ~/.axon ne doit contenir que l'état. Un dépôt cloné là par une très
# ancienne version mélange code et données.
if [[ -d "$STATE_DIR/.git" && "$INSTALL_DIR" != "$STATE_DIR" ]]; then
    warn "$STATE_DIR contient un dépôt git — il ne devrait contenir que l'état d'Axon (logs, JSON…)."
    echo ""
fi

if [[ "$INSTALL_DIR" == "${SCRIPT_DIR:-}" ]]; then
    ok "Installation sur place → $INSTALL_DIR"
elif [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Mise à jour de l'installation existante..."
    git -C "$INSTALL_DIR" pull --ff-only
    ok "Mis à jour → $INSTALL_DIR"
else
    if [[ -d "$INSTALL_DIR" ]]; then
        fail "$INSTALL_DIR existe déjà mais n'est pas un repo git. Supprime-le ou définis AXON_INSTALL_DIR."
    fi
    info "Clonage dans $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Cloné → $INSTALL_DIR"
fi

mkdir -p "$STATE_DIR"
ok "État d'Axon → $STATE_DIR"

# ── Lancement du setup ────────────────────────────────────────
# setup.sh crée le .venv dans le dossier COURANT : c'est ce `cd` qui le place
# dans le dépôt, et nulle part ailleurs.
cd "$INSTALL_DIR"
exec < /dev/tty
bash setup.sh

# ── Alias global (optionnel) ──────────────────────────────────
step "Commande globale 'axon'"

SHELL_RC=""
if [[ -f "$HOME/.zshrc" ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_RC="$HOME/.bashrc"
fi

# Même choix que setup.sh : `.venv`, ou un `venv` historique réutilisé.
VENV_DIR=".venv"
if [[ ! -d "$INSTALL_DIR/.venv" && -d "$INSTALL_DIR/venv" ]]; then
    VENV_DIR="venv"
fi

ALIAS_LINE="alias axon='cd $INSTALL_DIR && source $VENV_DIR/bin/activate && PYTHONIOENCODING=utf-8 LANG=fr_FR.UTF-8 python -m src.ui.main'"

if [[ -n "$SHELL_RC" ]]; then
    if grep -qxF "$ALIAS_LINE" "$SHELL_RC" 2>/dev/null; then
        ok "Alias 'axon' déjà à jour dans $SHELL_RC"
    elif grep -q "^alias axon=" "$SHELL_RC" 2>/dev/null; then
        # Un alias laissé par une ancienne installation pointe peut-être vers
        # ~/axon : le garder tel quel lancerait toujours l'ancienne copie.
        grep -v "^alias axon=" "$SHELL_RC" > "$SHELL_RC.axon-tmp"
        echo "$ALIAS_LINE" >> "$SHELL_RC.axon-tmp"
        # Réécrit le CONTENU plutôt que `mv` : un .zshrc souvent lien
        # symbolique (dotfiles) serait sinon remplacé par un fichier ordinaire.
        cat "$SHELL_RC.axon-tmp" > "$SHELL_RC"
        rm -f "$SHELL_RC.axon-tmp"
        ok "Alias 'axon' mis à jour dans $SHELL_RC → $INSTALL_DIR"
    else
        echo "" >> "$SHELL_RC"
        echo "# Axon — assistant IA" >> "$SHELL_RC"
        echo "$ALIAS_LINE" >> "$SHELL_RC"
        ok "Alias 'axon' ajouté dans $SHELL_RC"
    fi
fi

echo ""
echo -e "${ORANGE}  ─────────────────────────────────────${NC}"
echo -e "${ORANGE}  Installation terminée.${NC}"
echo ""
echo -e "  Lance Axon avec :"
echo -e "    ${ORANGE}axon${NC}   ${DIM}(après avoir rechargé ton shell : source $SHELL_RC)${NC}"
echo ""
echo -e "  Ou directement :"
echo -e "    ${ORANGE}cd $INSTALL_DIR && source $VENV_DIR/bin/activate && python -m src.ui.main${NC}"
echo ""
