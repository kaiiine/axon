"""Ce qui diffère entre Linux, macOS et Windows pendant l'installation."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"


def commande(nom: str) -> str | None:
    return shutil.which(nom)


def lancer(arguments: list[str]) -> bool:
    """Lance une commande en laissant sa sortie à l'écran. Vrai si elle réussit."""
    try:
        return subprocess.run(arguments, check=False).returncode == 0
    except OSError:
        return False


def _sortie(arguments: list[str]) -> str:
    try:
        resultat = subprocess.run(arguments, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return resultat.stdout.strip() if resultat.returncode == 0 else ""


def choisir_dossier(titre: str, depart: str) -> str:
    """Le sélecteur de dossier natif ; "" s'il est absent ou annulé."""
    if WINDOWS:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = $env:AXON_TITRE; $d.SelectedPath = $env:AXON_DEPART;"
            "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
        )
        os.environ.update(AXON_TITRE=titre, AXON_DEPART=depart)
        return _sortie(["powershell", "-NoProfile", "-Command", script])
    if MACOS:
        return _sortie(["osascript", "-e", "on run argv",
                        "-e", "POSIX path of (choose folder with prompt (item 1 of argv))",
                        "-e", "end run", titre])
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return ""
    if commande("zenity"):
        return _sortie(["zenity", "--file-selection", "--directory", f"--title={titre}",
                        f"--filename={depart.rstrip('/')}/"])
    if commande("kdialog"):
        return _sortie(["kdialog", "--getexistingdirectory", depart, "--title", titre])
    return ""


def installer_ollama() -> bool:
    if WINDOWS:
        return bool(commande("winget")) and lancer(
            ["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-source-agreements"])
    if MACOS:
        return bool(commande("brew")) and lancer(["brew", "install", "ollama"])
    return lancer(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])


def comment_installer_ollama() -> str:
    if WINDOWS:
        return "winget install --id Ollama.Ollama -e   (ou https://ollama.com/download)"
    if MACOS:
        return "brew install ollama   (ou l'app : https://ollama.com/download)"
    return "curl -fsSL https://ollama.com/install.sh | sh"


def installer_uv() -> bool:
    """L'installeur officiel d'uv (pas `pip install uv`, qui peut omettre `uvx`)."""
    if WINDOWS:
        ok = lancer(["powershell", "-NoProfile", "-ExecutionPolicy", "ByPass", "-Command",
                     "irm https://astral.sh/uv/install.ps1 | iex"])
    else:
        ok = lancer(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"])
    dossier = str(Path.home() / ".local" / "bin")
    if dossier not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = dossier + os.pathsep + os.environ.get("PATH", "")
    return ok


def fichier_profil() -> Path:
    """Le fichier lu par le shell de l'utilisateur à chaque session (Unix)."""
    zsh = MACOS or os.environ.get("SHELL", "").endswith("zsh")
    return Path.home() / (".zshrc" if zsh else ".bashrc")


def variable_exportee(nom: str) -> bool:
    if WINDOWS:
        return bool(_sortie(["powershell", "-NoProfile", "-Command",
                             f"[Environment]::GetEnvironmentVariable('{nom}', 'User')"]))
    profil = fichier_profil()
    return profil.exists() and nom in profil.read_text(encoding="utf-8", errors="ignore")


def exporter_variable(nom: str, valeur: str, commentaire: str) -> str:
    """Rend la variable permanente pour les prochaines sessions ; dit où."""
    if WINDOWS:
        lancer(["setx", nom, valeur])
        return "les variables d'environnement de ton compte"
    profil = fichier_profil()
    echappee = valeur.replace("'", "'\\''")
    with profil.open("a", encoding="utf-8") as flux:
        flux.write(f"\n# {commentaire}\nexport {nom}='{echappee}'\n")
    return str(profil)


def dossier_telechargements() -> Path:
    for nom in ("Téléchargements", "Downloads"):
        if (Path.home() / nom).is_dir():
            return Path.home() / nom
    return Path.home() / "Downloads"


def telecharger(url: str, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as reponse:
            destination.write_bytes(reponse.read())
        return True
    except OSError:
        return False
