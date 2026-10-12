"""Pont vers l'île flottante (axon-overlay, processus GTK séparé).

Copie quasi à l'identique de `axon-overlay/pont_axon.py` — gardée en double
volontairement : l'overlay est un processus séparé, potentiellement absent ou
jamais lancé, ce module ne doit donc dépendre que de la bibliothèque standard
(aucun import vers `src.*` dans la classe elle-même).

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
        #: se (re)lancer et ne les a pas encore). Défini par l'appelant
        #: (app.py) : cette classe ne dépend que de la bibliothèque standard,
        #: elle ne connaît donc pas elle-même `src.ui.completer`.
        self.sur_demande_commandes = None
        #: Appelé (id, action, item, panel) quand l'île demande un raccourci
        #: rapide — soit pour un dashboard entier (ex. "gmail_non_lus",
        #: item/panel absents), soit pour le détail d'UNE ligne précise
        #: (ex. "gmail_resumer_mail", item=l'id du mail, panel="gmail_non_lus"
        #: pour que l'île sache où ranger la réponse). Même raison que
        #: ci-dessus : le dispatch vers les tools vit dans `app.py`
        #: (via `src.ui.raccourcis_overlay`), pas ici. Doit répondre lui-même
        #: via `pont.envoyer(type="raccourci_resultat"|"raccourci_erreur", ...)`.
        self.sur_raccourci = None
        #: Appelé (chemin) quand l'île demande d'attacher un fichier local —
        #: déposé par glisser-déposer sur la fenêtre, ou choisi via le
        #: sélecteur natif ouvert à sa demande (voir `sur_demander_picker`).
        #: Même raison que `sur_raccourci` : `attachments.py` vit dans
        #: `app.py`, pas ici. Doit répondre via `pont.pieces_jointes(...)`.
        self.sur_joindre = None
        #: Appelé (nom) quand l'île demande de retirer une pièce jointe.
        self.sur_detacher = None
        #: Appelé sans argument quand l'île demande d'ouvrir le sélecteur de
        #: fichier natif (zenity/kdialog/tkinter, `open_file_picker()`) —
        #: c'est le même dialogue que `/attach` au clavier, juste déclenché
        #: depuis l'île.
        self.sur_demander_picker = None
        #: Appelé (id, titre, type_suivi, matiere) quand l'île crée un suivi
        #: directement (formulaire dans l'onglet Études) — même raison que
        #: `sur_raccourci` : un CRUD simple n'a besoin d'aucun raisonnement
        #: LLM. `id` identifie CETTE soumission précise (§2, lot 3) : le
        #: formulaire ne se referme qu'après avoir reçu, pour ce même id,
        #: `creer_suivi_resultat` (et rafraîchit la liste via un
        #: `raccourci_resultat` pour l'action `etudes_suivis`) ou
        #: `creer_suivi_erreur` (le formulaire reste ouvert, champs intacts).
        self.sur_creer_suivi = None
        #: Gestion des échéances DEPUIS l'île (§3, lot 3) — créer, reporter,
        #: annuler, archiver sans repasser par le chat. Même raison que
        #: `sur_creer_suivi` : CRUD simple, pas de raisonnement LLM, les
        #: handlers (app.py) appellent les tools `etude_*` EXISTANTS pour ne
        #: pas dupliquer leur validation. Chacun répond par
        #: `etudes_action_resultat`/`etudes_action_erreur` pour son `id`
        #: (même id-corrélation que `sur_creer_suivi`), puis rafraîchit les
        #: panneaux concernés via un `raccourci_resultat` ordinaire.
        #: Appelé (id, suivi_id, titre, type_echeance, date).
        self.sur_creer_echeance = None
        #: Appelé (id, suivi_id, echeance_id, date, statut) — `date` seule
        #: = reporter, `statut="annulee"` = annuler ; l'un et/ou l'autre
        #: peuvent être None si non fournis par l'île pour cet appel.
        self.sur_maj_echeance = None
        #: Appelé (id, suivi_id).
        self.sur_archiver_suivi = None
        #: Appelé (id, suivi_id, mode) — mode "fichier" ou "dossier" : ouvrir
        #: le sélecteur natif dans ce mode puis lier le chemin choisi au suivi.
        self.sur_lier_ressource = None
        #: Appelé (id, suivi_id) — suppression définitive d'un suivi.
        self.sur_supprimer_suivi = None
        #: Appelé (id, genre, cible) — l'île demande un flux de texte (réponse
        #: LLM en temps réel, voir src/ui/flux_overlay.py). Répondre par
        #: `flux_morceau`/`flux_fin`/`flux_erreur` pour cet id.
        self.sur_demander_flux = None
        #: Appelé (id, suivi_id, echeance_id) — programmer les rappels par
        #: défaut (7, 3 et 1 jours avant) d'une échéance.
        self.sur_planifier_rappels = None

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
        elif message.get("type") == "demander_flux":
            if self.sur_demander_flux:
                self.sur_demander_flux(str(message.get("id", "")), str(message.get("genre", "")),
                                       str(message.get("cible", "")))
        elif message.get("type") == "planifier_rappels":
            if self.sur_planifier_rappels:
                self.sur_planifier_rappels(str(message.get("id", "")), str(message.get("suivi_id", "")),
                                           str(message.get("echeance_id", "")))
        elif message.get("type") == "supprimer_suivi":
            if self.sur_supprimer_suivi:
                self.sur_supprimer_suivi(str(message.get("id", "")), str(message.get("suivi_id", "")))
        elif message.get("type") == "lier_ressource":
            if self.sur_lier_ressource:
                mode = "dossier" if message.get("mode") == "dossier" else "fichier"
                self.sur_lier_ressource(str(message.get("id", "")), str(message.get("suivi_id", "")), mode)

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
        # tableau markdown (vu avec « résume mes 7 mails non lus » → un seul
        # mail affiché). Le journal de l'île défile ; large marge plutôt que
        # tronquer une vraie réponse, mais toujours borné contre un texte
        # démesuré.
        self.envoyer(type="message", texte=texte[:8000])

    def pieces_jointes(self, items: list[dict]) -> None:
        """Snapshot complet des pièces jointes en attente (pas de delta : la
        liste est toujours petite — même logique que `raccourci_resultat` qui
        renvoie tout le panneau plutôt qu'un diff)."""
        self.envoyer(type="pieces_jointes", items=items)

    def demander(self, demande: dict, delai: float = 300) -> list[str] | None:
        """Pose n'importe quelle demande HITL (autorisation, clarification,
        diff, plan, envoi — cf. `src/orchestrator/commun/hitl.py`) à l'île.
        Bloque jusqu'à ta réponse.

        `demande` est `Demande.en_clair()` : genre, cle, apercu, extra,
        questions. Renvoie une chaîne par question, dans l'ordre — ou None si
        pas de réponse possible ici (overlay absent, délai dépassé, connexion
        perdue) : redemander dans le CLI. None ne veut JAMAIS dire « accordé ».
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


#: Singleton partagé par tout le CLI. La connexion est tentée une fois ici ;
#: si l'overlay n'est pas lancé, `connecter()` échoue vite et sans bruit, et
#: chaque appel d'`envoyer()` retentera — Axon marche exactement comme avant.
pont = PontOverlay()
pont.connecter()
