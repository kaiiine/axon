"""Une notification à l'utilisateur, hors conversation : par le plugin qui en
fournit (l'île), sinon le mécanisme natif du système.

Le titre et le texte ne passent jamais dans une ligne de commande interprétée :
arguments séparés pour `osascript`, variables d'environnement pour PowerShell.
Un rappel contenant des guillemets ne peut donc rien exécuter.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

from src.infra import canal_overlay
from src.plugins import registre

#: Identifiant d'application de PowerShell : Windows n'affiche une notification
#: que pour une application connue, et celle-ci l'est sur toute installation.
_APP_ID_POWERSHELL = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_SCRIPT_WINDOWS = f"""
$gestionnaire = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$xml = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]::new()
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text/><text/></binding></visual></toast>')
$lignes = $xml.GetElementsByTagName('text')
$lignes.Item(0).AppendChild($xml.CreateTextNode($env:AXON_TITRE)) | Out-Null
$lignes.Item(1).AppendChild($xml.CreateTextNode($env:AXON_TEXTE)) | Out-Null
$gestionnaire::CreateToastNotifier('{_APP_ID_POWERSHELL}').Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""

_SCRIPT_MACOS = ("on run argv",
                 "display notification (item 2 of argv) with title (item 1 of argv)",
                 "end run")


def notifier(titre: str, texte: str, contexte: dict | None = None) -> None:
    """Par un plugin de notifications s'il est installé et tourne (l'île :
    Axon qui le dit dans une bulle) ; sinon le système.

    `contexte` ne sert qu'à l'île, pour proposer les bonnes actions :
    `genre` (`echeance`, `recapitulatif`, `tache`), `suivi_id`, `echeance_id`.
    """
    if registre.avec_capacite("notifications"):
        rappel = {**(contexte or {}), "type": "rappel", "id": uuid.uuid4().hex[:8],
                  "titre": titre, "texte": texte}
        if canal_overlay.envoyer_une_fois(canal_overlay.CONTROLE, rappel):
            return
    notifier_systeme(titre, texte)


def notifier_systeme(titre: str, texte: str) -> None:
    """La notification native. Ne lève jamais : un rappel perdu vaut mieux
    qu'un démon qui tombe."""
    try:
        subprocess.run(_commande(titre, texte), timeout=10, check=False,
                       env=_environnement(titre, texte),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def _commande(titre: str, texte: str) -> list[str]:
    if sys.platform == "win32":
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT_WINDOWS]
    if sys.platform == "darwin":
        return ["osascript", *(a for ligne in _SCRIPT_MACOS for a in ("-e", ligne)), titre, texte]
    return ["notify-send", "-u", "normal", "-a", "Axon", titre, texte]


def _environnement(titre: str, texte: str) -> dict[str, str] | None:
    if sys.platform != "win32":
        return None
    return {**os.environ, "AXON_TITRE": titre, "AXON_TEXTE": texte}
