"""Côté Axon : le client qui parle à l'overlay.

Ce module reste dans le plugin axon-overlay. À importer via le chargeur de
plugins du cœur Axon, sans recopier son code ailleurs. Aucune dépendance :
uniquement la bibliothèque standard.

Règle de sécurité centrale : si l'overlay est absent, ne répond pas ou se
déconnecte, `demander` renvoie None. None ne veut JAMAIS dire « accordé » :
l'appelant doit alors reposer la question dans le CLI.
"""
from __future__ import annotations

import json
import os
import queue
import socket
import threading
import uuid
from pathlib import Path

RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SOCKET = RUNTIME / "axon" / "overlay.sock"


class PontOverlay:
    def __init__(self, chemin: Path = SOCKET) -> None:
        self.chemin = chemin
        self.sock: socket.socket | None = None
        self.verrou = threading.Lock()
        self.attentes: dict[str, list] = {}       # id -> [Event, décision]
        self.commandes: queue.Queue[str] = queue.Queue()  # ce que tu tapes dans l'overlay
        #: Appelé quand l'île redemande la liste des commandes (elle vient de
        #: se (re)lancer et ne les a pas encore). À définir par l'appelant.
        self.sur_demande_commandes = None
        #: Appelé (id, action, item, panel) quand l'île demande un raccourci
        #: rapide — pour un dashboard entier (item/panel absents) ou pour le
        #: détail d'une ligne précise (item=son id, panel=l'action du
        #: dashboard parent). À définir par l'appelant — doit répondre via
        #: `pont.envoyer(type="raccourci_resultat"|"raccourci_erreur", ...)`.
        self.sur_raccourci = None
        #: Appelé (chemin) quand l'île demande d'attacher un fichier local —
        #: déposé par glisser-déposer sur la fenêtre, ou choisi via le
        #: sélecteur natif ouvert à sa demande (voir `sur_demander_picker`).
        #: À définir par l'appelant — doit répondre via `pont.pieces_jointes(...)`.
        self.sur_joindre = None
        #: Appelé (nom) quand l'île demande de retirer une pièce jointe.
        self.sur_detacher = None
        #: Appelé sans argument quand l'île demande d'ouvrir le sélecteur de
        #: fichier natif (même dialogue que `/attach` au clavier).
        self.sur_demander_picker = None
        #: Appelé (id, titre, type_suivi, matiere) quand l'île crée un suivi
        #: directement (formulaire dans l'onglet Études) — un CRUD simple
        #: n'a besoin d'aucun raisonnement LLM. `id` identifie CETTE
        #: soumission : répondre via `creer_suivi_resultat`/`creer_suivi_erreur`
        #: (voir src/ui/pont_overlay.py, copie jumelle de ce fichier).
        self.sur_creer_suivi = None
        #: Gestion des échéances depuis l'île (créer/reporter/annuler/
        #: archiver) — voir src/ui/pont_overlay.py, copie jumelle de ce
        #: fichier, pour le détail de la corrélation par id.
        self.sur_creer_echeance = None
        self.sur_maj_echeance = None
        self.sur_archiver_suivi = None

    # ---------- connexion ----------
    @property
    def connecte(self) -> bool:
        return self.sock is not None

    def connecter(self) -> bool:
        """Tente une connexion. Renvoie False sans bruit si l'overlay n'est pas lancé."""
        with self.verrou:
            if self.sock is not None:
                return True
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(str(self.chemin))
            except OSError:
                return False
            self.sock = s
        threading.Thread(target=self._lire, args=(s,), daemon=True).start()
        return True

    def _lire(self, s: socket.socket) -> None:
        try:
            with s.makefile("r", encoding="utf-8") as flux:
                for ligne in flux:
                    try:
                        message = json.loads(ligne)
                    except json.JSONDecodeError:
                        continue
                    self._traiter(message)
        except OSError:
            pass
        finally:
            self._perdre(s)

    def _traiter(self, message: dict) -> None:
        if message.get("type") == "reponse_demande":
            attente = self.attentes.get(message.get("id"))
            if attente is not None:
                attente[1] = list(message.get("reponses") or [])
                attente[0].set()
        elif message.get("type") == "commande":
            self.commandes.put(str(message.get("texte", "")))
        elif message.get("type") == "demander_commandes":
            if self.sur_demande_commandes:
                self.sur_demande_commandes()
        elif message.get("type") == "raccourci":
            if self.sur_raccourci:
                item = message.get("item")
                panel = message.get("panel")
                self.sur_raccourci(
                    str(message.get("id", "")), str(message.get("action", "")),
                    str(item) if item is not None else None,
                    str(panel) if panel is not None else None,
                )
        elif message.get("type") == "joindre":
            if self.sur_joindre:
                self.sur_joindre(str(message.get("chemin", "")))
        elif message.get("type") == "detacher":
            if self.sur_detacher:
                self.sur_detacher(str(message.get("nom", "")))
        elif message.get("type") == "demander_picker":
            if self.sur_demander_picker:
                self.sur_demander_picker()
        elif message.get("type") == "creer_suivi":
            if self.sur_creer_suivi:
                self.sur_creer_suivi(
                    str(message.get("id", "")), str(message.get("titre", "")),
                    str(message.get("type_suivi", "")), str(message.get("matiere", "")),
                )
        elif message.get("type") == "creer_echeance":
            if self.sur_creer_echeance:
                self.sur_creer_echeance(
                    str(message.get("id", "")), str(message.get("suivi_id", "")),
                    str(message.get("titre", "")), str(message.get("type_echeance", "")),
                    str(message.get("date", "")),
                )
        elif message.get("type") == "maj_echeance":
            if self.sur_maj_echeance:
                date = message.get("date")
                statut = message.get("statut")
                self.sur_maj_echeance(
                    str(message.get("id", "")), str(message.get("suivi_id", "")),
                    str(message.get("echeance_id", "")),
                    str(date) if date is not None else None,
                    str(statut) if statut is not None else None,
                )
        elif message.get("type") == "archiver_suivi":
            if self.sur_archiver_suivi:
                self.sur_archiver_suivi(str(message.get("id", "")), str(message.get("suivi_id", "")))

    def _perdre(self, s: socket.socket) -> None:
        with self.verrou:
            if self.sock is s:
                self.sock = None
        # Connexion perdue : toutes les questions en cours repartent vers le CLI.
        for attente in list(self.attentes.values()):
            attente[1] = None
            attente[0].set()

    # ---------- envoi ----------
    def envoyer(self, **message) -> bool:
        if not self.connecte and not self.connecter():
            return False
        ligne = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        with self.verrou:
            s = self.sock
        if s is None:
            return False
        try:
            s.sendall(ligne)
            return True
        except OSError:
            self._perdre(s)
            return False

    # ---------- API pratique ----------
    def etat(self, etat: str, texte: str = "") -> None:
        """etat : idle, thinking, working, finished, sleeping ou erreur."""
        self.envoyer(type="etat", etat=etat, texte=texte)

    def outil(self, nom: str, detail: str = "") -> None:
        self.envoyer(type="outil", nom=nom, detail=detail[:200])

    def message(self, texte: str) -> None:
        # 300 caractères coupait un résumé multi-mails à la première ligne de
        # tableau markdown. Le journal de l'île défile ; large marge plutôt
        # que tronquer une vraie réponse, mais toujours borné.
        self.envoyer(type="message", texte=texte[:8000])

    def pieces_jointes(self, items: list[dict]) -> None:
        """Snapshot complet des pièces jointes en attente (pas de delta : la
        liste est toujours petite — même logique que `raccourci_resultat`)."""
        self.envoyer(type="pieces_jointes", items=items)

    def demander(self, demande: dict, delai: float = 300) -> list[str] | None:
        """Pose n'importe quelle demande HITL (autorisation, clarification,
        diff, plan, envoi) à l'île. Bloque jusqu'à ta réponse.

        `demande` est `Demande.en_clair()` (genre, cle, apercu, extra,
        questions). Renvoie une chaîne par question — ou None si pas de
        réponse possible ici (overlay absent, délai dépassé, connexion
        perdue) : redemander dans le CLI.

        Bloquant : depuis du code async, appelle-le avec asyncio.to_thread(...).
        """
        id_ = uuid.uuid4().hex[:8]
        evenement = threading.Event()
        self.attentes[id_] = [evenement, None]
        try:
            if not self.envoyer(type="demande", id=id_, **demande):
                return None
            if not evenement.wait(delai):
                self.envoyer(type="annulation", id=id_)
                return None
            return self.attentes[id_][1]
        finally:
            self.attentes.pop(id_, None)

    def annuler(self, id_: str) -> None:
        """À appeler si la réponse est venue d'ailleurs (le CLI), pour fermer la carte."""
        self.envoyer(type="annulation", id=id_)
