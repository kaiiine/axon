import re
from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from src.ui.config import SessionConfig
from src.ui.panels import banner, command_panel, final_panel, ACCENT
from src.infra.checkpoint import (
    load_last_thread, save_last_thread, get_recent_messages,
    load_thread_cwd, save_thread_cwd,
)
from src.agents.shell.tools import get_cwd, set_cwd

load_dotenv()
console = Console(highlight=True, emoji=True)


_HISTORY_LIMIT = 50


def _show_specialist_trace(content: str) -> None:
    from rich.panel import Panel
    from rich.text import Text as RText

    m = re.search(r'\[SPECIALIST-TRACE\](.*?)\[/SPECIALIST-TRACE\]', content, re.DOTALL)
    result_text = content
    trace_lines: dict = {}

    if m:
        raw = m.group(1).strip()
        result_text = content[m.end():].strip()
        for line in raw.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                trace_lines[k.strip()] = v.strip()

    body = RText()
    if "cwd" in trace_lines:
        body.append("  📁  ", style=f"dim {ACCENT}")
        body.append(trace_lines["cwd"] + "\n", style="dim")
    if "files" in trace_lines:
        for f in trace_lines["files"].split(","):
            body.append("  ✓  ", style="bold green")
            body.append(f.strip() + "\n", style="dim")
    if "plan" in trace_lines:
        for step in trace_lines["plan"].split("|"):
            done = step.startswith("✓")
            icon = "  ✓  " if done else "  ○  "
            body.append(icon, style="bold green" if done else "dim")
            body.append(step[1:].strip() + "\n", style="dim")
    if result_text:
        body.append("\n" + result_text[:3000], style="dim")

    console.print(Panel(
        body,
        border_style=f"dim {ACCENT}",
        title="[dim]agent code[/dim]",
        title_align="left",
        padding=(0, 2),
    ))


def _show_resume(thread_id: str) -> None:
    """Affiche l'historique complet du thread au démarrage."""
    messages = get_recent_messages(thread_id)
    if not messages:
        return

    visible = [m for m in messages
               if m["role"] in ("human", "ai", "coding_agent")
               and m["content"].strip() and not m.get("interne")]
    if not visible:
        return

    hidden = len(visible) - _HISTORY_LIMIT
    if hidden > 0:
        visible = visible[-_HISTORY_LIMIT:]

    console.print(Rule("reprise de session", characters="·", style=f"dim {ACCENT}"))
    console.print()

    if hidden > 0:
        console.print(Text(f"  … {hidden} messages plus anciens", style="dim"))
        console.print()

    for m in visible:
        role    = m["role"]
        content = m["content"].strip()
        if role == "human":
            label = Text()
            label.append("  ›  ", style=f"bold {ACCENT}")
            label.append(content, style=f"bold {ACCENT}")
            console.print(label)
        elif role == "ai":
            clean = re.sub(
                r'<axon:plan>.*?</axon:plan>\s*', '', content, flags=re.DOTALL
            ).strip()
            if clean:
                console.print(final_panel(clean))
        elif role == "coding_agent":
            _show_specialist_trace(content)

    console.print()
    console.print(
        Text(f"  thread : {thread_id}", style="dim"),
        Text("  ·  /history pour changer  ·  /new pour recommencer", style="dim"),
    )
    console.print()


def run_cli(graph):
    import threading

    from src.ui.streaming import stream_once
    from src.ui.pont_overlay import pont
    from src.ui.completer import _COMMANDS

    # Seule la vraie session se connecte à l'île (voir `PontOverlay.activer`).
    pont.activer()

    def _envoyer_commandes() -> None:
        pont.envoyer(type="commandes", liste=[{"cmd": c, "desc": d} for c, d in _COMMANDS])

    # Si l'île tourne déjà, elle a tout de suite la même liste que le CLI.
    # Si elle démarre après coup, elle la redemande elle-même au premier
    # `{"type":"connexion","connecte":true}` qu'elle reçoit (voir index.html).
    pont.sur_demande_commandes = _envoyer_commandes
    _envoyer_commandes()

    def _gerer_raccourci(id_: str, action: str, item: str | None, panel: str | None) -> None:
        # Thread à part : ce sont de vrais appels réseau (Gmail/Jira/Calendar),
        # le thread de lecture du socket ne doit pas en dépendre pour
        # continuer à traiter d'autres messages pendant ce temps.
        # `item`/`panel` ne font qu'un aller-retour : c'est l'île qui a besoin
        # de savoir à quelle ligne de quel dashboard la réponse appartient,
        # `raccourcis_overlay.executer` ne s'en sert pas.
        def tache() -> None:
            from src.ui.raccourcis_overlay import executer

            reference = {}
            if item is not None:
                reference["item"] = item
            if panel is not None:
                reference["panel"] = panel
            try:
                resultat = executer(action, item)
                pont.envoyer(type="raccourci_resultat", id=id_, action=action, **reference, **resultat)
            except Exception as e:
                pont.envoyer(type="raccourci_erreur", id=id_, action=action, **reference, message=str(e))

        threading.Thread(target=tache, daemon=True).start()

    pont.sur_raccourci = _gerer_raccourci

    def _instantane_pieces_jointes() -> list[dict]:
        """Snapshot JSON-friendly de la liste courante, pour l'île — pas un
        état dérivé un à un : affiche ce que `attachments.items` contient
        MAINTENANT. `add_file` n'échoue jamais en levant (voir
        `src/ui/attachments.py` : une extraction ratée renvoie un contenu qui
        commence par « [erreur » / « [Erreur », au lieu de lever), donc
        l'erreur se détecte ici plutôt que par une exception à capturer.
        """
        from src.ui.attachments import attachments as _att

        items = []
        for a in _att.items:
            en_erreur = not a.is_image and a.content.lstrip().lower().startswith("[erreur")
            item = {"nom": a.name, "statut": "erreur" if en_erreur else "ok",
                     "est_image": a.is_image, "taille": a.size_hint}
            if en_erreur:
                item["message"] = a.content.strip()
            items.append(item)
        return items

    def _gerer_joindre(chemin: str) -> None:
        # Thread à part : l'extraction PDF/Office d'un gros fichier ne doit
        # pas geler la lecture du socket — même raison que `_gerer_raccourci`.
        def tache() -> None:
            from pathlib import Path as _Path
            from src.ui.attachments import attachments as _att

            nom = _Path(chemin).name or chemin
            if not _Path(chemin).exists():
                # Jamais ajouté au store : une entrée éphémère suffit, elle
                # disparaîtra au prochain instantané réel sans rien laisser
                # d'incohérent derrière elle.
                ephemere = _instantane_pieces_jointes() + [{
                    "nom": nom, "statut": "erreur",
                    "message": "fichier introuvable", "est_image": False, "taille": "",
                }]
                pont.pieces_jointes(ephemere)
                return
            if _Path(chemin).is_dir():
                # Un dossier n'a pas de texte à joindre : déposé sur l'île, il
                # devient un suivi à son nom (un dépôt Git → un projet), auquel
                # il est lié. Seule une erreur passe par la liste des pièces.
                erreur = _lier_chemin("", chemin)
                if erreur:
                    pont.pieces_jointes(_instantane_pieces_jointes() + [{
                        "nom": nom, "statut": "erreur", "message": erreur, "est_image": False, "taille": "",
                    }])
                return
            # Un gros PDF/Office prend une bonne seconde à extraire : sans ce
            # premier envoi, l'île n'a aucun retour entre le dépôt et la fin
            # de l'extraction — on pousse un chip "chargement" devant la
            # liste réelle, remplacé par l'instantané final juste après.
            en_cours = _instantane_pieces_jointes() + [{
                "nom": nom, "statut": "chargement", "est_image": False, "taille": "",
            }]
            pont.pieces_jointes(en_cours)
            _att.add_file(chemin)
            pont.pieces_jointes(_instantane_pieces_jointes())

        threading.Thread(target=tache, daemon=True).start()

    def _gerer_detacher(nom: str) -> None:
        from src.ui.attachments import attachments as _att

        _att.remove(nom)
        pont.pieces_jointes(_instantane_pieces_jointes())

    def _gerer_demander_picker() -> None:
        # Le dialogue natif (zenity/kdialog/tkinter) bloque jusqu'à 120s :
        # thread dédié, sinon plus aucun autre message de l'île n'est traité
        # pendant que la fenêtre de sélection est ouverte.
        def tache() -> None:
            from src.ui.attachments import attachments as _att, open_file_picker

            chemin = open_file_picker()
            if chemin:
                _att.add_file(chemin)
            pont.pieces_jointes(_instantane_pieces_jointes())

        threading.Thread(target=tache, daemon=True).start()

    def _gerer_creer_suivi(id_: str, titre: str, type_suivi: str, matiere: str) -> None:
        # Réutilise le TOOL (pas `store.creer_suivi` directement) pour ne pas
        # dupliquer sa validation du type — une seule source de vérité pour
        # ce qu'est un type de suivi valide, que l'appel vienne du chat ou
        # d'ici. Pas de thread : une écriture JSON verrouillée est rapide,
        # contrairement au dialogue natif ou à l'extraction d'un PDF.
        #
        # `creer_suivi_resultat`/`creer_suivi_erreur` (pas `raccourci_*`) :
        # ce sont des réponses à CETTE soumission précise (§2, lot 3), pas un
        # rafraîchissement de tout le panneau — l'île n'referme le formulaire
        # que sur `creer_suivi_resultat`, et affiche l'erreur DANS le
        # formulaire sur `creer_suivi_erreur`, sans jamais écraser la liste
        # des suivis déjà affichée par un message d'erreur qui n'a rien à
        # voir avec elle (c'est ce que faisait l'ancien `raccourci_erreur`
        # ici — champs jamais rouverts, liste remplacée par une erreur).
        #
        # try/except large : TOUT échec (pas seulement la validation du type)
        # doit répondre par `creer_suivi_erreur`, sinon le formulaire reste
        # bloqué « en cours » indéfiniment pour l'utilisateur.
        try:
            from src.agents.study.tools_suivi import etude_creer_suivi

            titre = titre.strip()
            if not titre:
                pont.envoyer(type="creer_suivi_erreur", id=id_, message="titre manquant")
                return
            reponse = etude_creer_suivi.invoke({"titre": titre, "type": type_suivi or "autre",
                                                 "matiere": matiere.strip()})
            if reponse.startswith("Type inconnu"):
                pont.envoyer(type="creer_suivi_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_suivis")
            pont.envoyer(type="creer_suivi_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="creer_suivi_erreur", id=id_, message=str(e))

    def _rafraichir_panneaux_etudes(*actions: str) -> None:
        from src.ui.raccourcis_overlay import executer

        for action in actions:
            resultat = executer(action, None)
            pont.envoyer(type="raccourci_resultat", action=action, **resultat)

    def _gerer_creer_echeance(id_: str, suivi_id: str, titre: str, type_echeance: str, date: str) -> None:
        # Même discipline que `_gerer_creer_suivi` (§2) étendue aux échéances
        # (§3) : réutilise le TOOL existant (sa validation du type/de la
        # date reste la seule source de vérité), répond par id pour que
        # l'île sache à QUELLE soumission la réponse correspond, et un
        # try/except large pour qu'aucun échec ne laisse le formulaire
        # bloqué « en cours ».
        from src.agents.study.tools_echeance import etude_ajouter_echeance

        try:
            reponse = etude_ajouter_echeance.invoke({
                "suivi_id": suivi_id, "titre": titre.strip() or titre,
                "type": type_echeance or "autre", "date": date,
            })
            if reponse.startswith(("Type inconnu", "Suivi introuvable")):
                pont.envoyer(type="etudes_action_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_suivis", "etudes_echeances")
            pont.envoyer(type="etudes_action_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

    def _gerer_maj_echeance(id_: str, suivi_id: str, echeance_id: str,
                             date: str | None, statut: str | None) -> None:
        # Couvre reporter (date), annuler (statut="annulee") et modifier —
        # une seule voie, le tool `etude_maj_echeance` décide déjà quoi
        # reprogrammer (§4, lot 3 : rappels liés à une date reportée).
        from src.agents.study.tools_echeance import etude_maj_echeance

        try:
            reponse = etude_maj_echeance.invoke({
                "suivi_id": suivi_id, "echeance_id": echeance_id, "date": date, "statut": statut,
            })
            if reponse.startswith(("Statut inconnu", "Suivi ou échéance introuvable")):
                pont.envoyer(type="etudes_action_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_suivis", "etudes_echeances")
            pont.envoyer(type="etudes_action_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

    def _gerer_archiver_suivi(id_: str, suivi_id: str) -> None:
        from src.agents.study.tools_suivi import etude_archiver_suivi

        try:
            reponse = etude_archiver_suivi.invoke({"suivi_id": suivi_id, "archive": True})
            if reponse.startswith("Suivi introuvable"):
                pont.envoyer(type="etudes_action_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_suivis")
            pont.envoyer(type="etudes_action_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

    def _gerer_supprimer_suivi(id_: str, suivi_id: str) -> None:
        # L'île demande une confirmation avant d'envoyer : ici, on supprime.
        from src.agents.study.tools_suivi import etude_supprimer_suivi

        try:
            reponse = etude_supprimer_suivi.invoke({"suivi_id": suivi_id})
            if reponse.startswith("Suivi introuvable"):
                pont.envoyer(type="etudes_action_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_suivis", "etudes_echeances", "etudes_fiches_recentes")
            pont.envoyer(type="etudes_action_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

    def _gerer_demander_flux(id_: str, genre: str, cible: str) -> None:
        # Thread à part : un appel LLM en flux dure plusieurs secondes.
        from src.ui.flux_overlay import diffuser

        threading.Thread(target=diffuser, args=(id_, genre, cible, pont.envoyer), daemon=True).start()

    def _gerer_planifier_rappels(id_: str, suivi_id: str, echeance_id: str) -> None:
        from src.agents.study.tools_echeance import etude_planifier_rappel_echeance

        try:
            reponse = etude_planifier_rappel_echeance.invoke({"suivi_id": suivi_id, "echeance_id": echeance_id})
            if reponse.startswith(("Échéance introuvable", "Aucun rappel programmé")):
                pont.envoyer(type="etudes_action_erreur", id=id_, message=reponse)
                return
            _rafraichir_panneaux_etudes("etudes_echeances")
            pont.envoyer(type="etudes_action_resultat", id=id_)
        except Exception as e:
            pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

    def _lier_chemin(suivi_id: str, chemin: str) -> str | None:
        """Lie `chemin` (voir `lier_chemin_local`) puis rafraîchit la liste
        des suivis de l'île. Renvoie un message d'erreur, ou None."""
        from src.agents.study.tools_suivi import lier_chemin_local

        _suivi_id, erreur = lier_chemin_local(suivi_id, chemin)
        _rafraichir_panneaux_etudes("etudes_suivis")
        return erreur

    def _gerer_lier_ressource(id_: str, suivi_id: str, mode: str) -> None:
        # Thread à part : le sélecteur natif bloque jusqu'à 120s, comme dans
        # `_gerer_demander_picker`.
        def tache() -> None:
            from src.ui.attachments import open_file_picker

            try:
                chemin = open_file_picker(dossier=(mode == "dossier"))
                if not chemin:
                    # Annulé : rien à lier, mais l'île doit savoir que c'est fini.
                    pont.envoyer(type="etudes_action_resultat", id=id_)
                    return
                erreur = _lier_chemin(suivi_id, chemin)
                if erreur:
                    pont.envoyer(type="etudes_action_erreur", id=id_, message=erreur)
                else:
                    pont.envoyer(type="etudes_action_resultat", id=id_)
            except Exception as e:
                pont.envoyer(type="etudes_action_erreur", id=id_, message=str(e))

        threading.Thread(target=tache, daemon=True).start()

    pont.sur_lier_ressource = _gerer_lier_ressource
    pont.sur_supprimer_suivi = _gerer_supprimer_suivi
    pont.sur_demander_flux = _gerer_demander_flux
    pont.sur_planifier_rappels = _gerer_planifier_rappels
    pont.sur_joindre = _gerer_joindre
    pont.sur_detacher = _gerer_detacher
    pont.sur_demander_picker = _gerer_demander_picker
    pont.sur_creer_suivi = _gerer_creer_suivi
    pont.sur_creer_echeance = _gerer_creer_echeance
    pont.sur_maj_echeance = _gerer_maj_echeance
    pont.sur_archiver_suivi = _gerer_archiver_suivi

    # Une génération encore "en_cours" au démarrage n'a pas pu terminer dans
    # CE processus — le précédent est mort (crash, kill, coupure) sans mettre
    # à jour son statut. Purgée une seule fois ici (§1, lot 3), pas à chaque
    # lecture du store : sinon une VRAIE génération en cours dans un autre
    # processus (l'île déjà ouverte pendant que le CLI redémarre) serait
    # faussement marquée en échec en boucle.
    from src.agents.study.store import purger_generations_bloquees
    purger_generations_bloquees()

    cfg   = SessionConfig()
    state = {"messages": []}

    # ── Reprise du dernier thread ──────────────────────────────────────────────
    last = load_last_thread()
    if last:
        cfg.thread_id = last
        saved_cwd = load_thread_cwd(last)
        if saved_cwd:
            set_cwd(saved_cwd)

    console.clear()
    console.print(banner())

    if last:
        _show_resume(last)

    try:
        while True:
            stream_once(graph, state, cfg)
            # Persiste le thread actif et le cwd courant après chaque échange
            save_last_thread(cfg.thread_id)
            save_thread_cwd(cfg.thread_id, str(get_cwd()))
    except KeyboardInterrupt:
        save_last_thread(cfg.thread_id)
        save_thread_cwd(cfg.thread_id, str(get_cwd()))
        console.print()
        console.print(Rule("à bientôt", characters="·", style=f"dim {ACCENT}"))
        console.print()
