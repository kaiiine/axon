"""Outils `etude_*` pour les échéances d'un suivi (devoirs, partiels, rendus
de projet) et leurs rappels.

Les rappels d'échéance vivent ici, pas dans un module séparé : reporter une
échéance doit reprogrammer les siens dans le même geste (`etude_maj_echeance`
ci-dessous), les deux sont trop couplés pour les séparer utilement. Le rappel
récurrent de point d'avancement (pas lié à une échéance) vit ici aussi, pour
ne pas créer un fichier à trois fonctions.
"""
from __future__ import annotations

from langchain_core.tools import tool

from ._aide import (STATUTS_ECHEANCE, TYPES_ECHEANCE, avancement_exercices, deja_passe, jours_restants,
                    neuf_heures, temps_restant_texte)


# ── échéances ────────────────────────────────────────────────────────────

@tool("etude_ajouter_echeance")
def etude_ajouter_echeance(
    suivi_id: str, titre: str, date: str, type: str = "autre",
    ressources_ciblees: list[str] | None = None, chapitres: list[str] | None = None,
    notes: str = "",
) -> str:
    """
    Ajoute une échéance (devoir, partiel/contrôle, rendu de projet) à un
    suivi existant — crée d'abord le suivi avec `etude_creer_suivi` s'il
    n'existe pas encore. Une matière peut avoir plusieurs échéances portant
    sur des chapitres différents : utilise `ressources_ciblees` pour viser
    seulement certaines ressources du suivi plutôt que toutes.

    **N'invente JAMAIS une date ou un suivi manquant/ambigu** — utilise
    `ask_clarification`. Une date relative ("vendredi prochain") doit être
    résolue en YYYY-MM-DD avant l'appel (voir `get_current_time`).

    Mots-clés : partiel, contrôle, examen, devoir, rendu, projet, échéance,
    agenda, planning.

    **Args:**
        - `suivi_id` (str)
        - `titre` (str)
        - `type` (str, optionnel) : "devoir", "partiel", "rendu_projet" ou
          "autre" (défaut) — un jalon intermédiaire est un "autre"
        - `date` (str) : YYYY-MM-DD
        - `ressources_ciblees` (list[str], optionnel) : ids de ressources du
          suivi concernées ; vide = toutes
        - `chapitres` (list[str], optionnel)
        - `notes` (str, optionnel)

    **Returns:**
        - Confirmation avec l'identifiant de l'échéance.
    """
    from .store import ajouter_echeance

    if type not in TYPES_ECHEANCE:
        return f"Type inconnu : {type}. Attendu : {', '.join(TYPES_ECHEANCE)}."
    echeance = ajouter_echeance(suivi_id, titre, type, date, ressources_ciblees, chapitres, notes)
    if echeance is None:
        return f"Suivi introuvable : {suivi_id}"
    return (f"Échéance ajoutée — **{titre}** le {date}, {temps_restant_texte(date)}.\n"
            f"ID : `{echeance['id']}`")


@tool("etude_lister_echeances")
def etude_lister_echeances(a_venir_seulement: bool = True) -> str:
    """
    Liste TOUTES les échéances, tous suivis confondus, par ordre
    chronologique, avec le temps restant et l'avancement. Utilise ce tool
    pour « Quels sont mes prochains contrôles ? », « mon planning ».

    Mots-clés : agenda, planning, échéances, contrôles, partiels, devoirs,
    rendus, prochains, à venir.

    **Args:**
        - `a_venir_seulement` (bool) : True (défaut) ne montre que le futur.

    **Returns:**
        - Liste Markdown triée par date.
    """
    from .store import lister_echeances

    paires = lister_echeances(a_venir_seulement=a_venir_seulement)
    if not paires:
        return "Aucune échéance à venir." if a_venir_seulement else "Aucune échéance enregistrée."
    lignes = []
    for suivi, e in paires:
        exos_cibles = [x for x in suivi["exercices"] if x.get("echeance_id") == e["id"]]
        avancement = avancement_exercices(exos_cibles) if exos_cibles else avancement_exercices(suivi["exercices"])
        lignes.append(f"- **{e['titre']}** ({suivi['titre']}, {e['type']}) — {e['date']}, "
                       f"{temps_restant_texte(e['date'])} · avancement : {avancement} "
                       f"· suivi `{suivi['id']}` · échéance `{e['id']}`")
    return "\n".join(lignes)


def _reprogrammer_rappels(suivi_id: str, echeance: dict, nouvelle_date: str, anciens_rappels: list[dict]):
    """Reprogramme les rappels "echeance" aux mêmes offsets, relatifs à la
    nouvelle date. Appelée par `etude_maj_echeance` quand la date change.

    Trois règles de fiabilité (§10, lot 3) :
    - un rappel dont l'`offset_jours` est inconnu (créé avant que ce champ
      existe) n'est JAMAIS reprogrammé en devinant une valeur — laissé tel
      quel, et signalé à l'appelant pour qu'il décide ;
    - un rappel dont le nouveau déclenchement tombe déjà dans le passé est
      désactivé plutôt que laissé actif sur l'ancienne date, qui n'a plus
      de sens une fois l'échéance reportée ;
    - pour tous les autres, le NOUVEAU rappel est créé avant de toucher à
      l'ancien : un crash ou un redémarrage entre les deux laisse au pire
      les deux actifs (un doublon visible, sans gravité), jamais aucun des
      deux (un rappel perdu, invisible).

    Renvoie (reprogrammes, tombes_dans_le_passe, offset_inconnu) — trois
    listes de libellés pour le message de confirmation.
    """
    from datetime import timedelta as _timedelta
    from src.agents.cron.store import add_task, deactivate_task
    from .store import ajouter_rappel_echeance, retirer_rappel_echeance

    reprogrammes, tombes_dans_le_passe, offset_inconnu = [], [], []

    for rappel in anciens_rappels:
        if rappel["type"] != "echeance":
            continue
        if rappel["offset_jours"] is None:
            offset_inconnu.append(rappel["cron_id"])
            continue

        quand = neuf_heures(nouvelle_date) - _timedelta(days=rappel["offset_jours"])
        if deja_passe(quand):
            # Règle explicite (lot 3) : un rappel dont le nouveau
            # déclenchement tombe déjà dans le passé n'a plus de sens —
            # désactivé plutôt que laissé actif sur l'ANCIENNE date, ce qui
            # serait plus trompeur qu'utile.
            deactivate_task(rappel["cron_id"])
            retirer_rappel_echeance(suivi_id, echeance["id"], rappel["cron_id"])
            tombes_dans_le_passe.append(f"{rappel['offset_jours']} j avant")
            continue

        prompt = (f"Rappelle à l’utilisateur : {echeance['type']} — {echeance['titre']}, "
                  f"dans {rappel['offset_jours']} jour(s) (le {nouvelle_date}).")
        nouveau_cron_id = add_task(description=f"Rappel · {echeance['titre']}", prompt=prompt,
                                    interval_sec=0, notif_channels=["desktop"], run_at=quand.isoformat())
        ajouter_rappel_echeance(suivi_id, echeance["id"], nouveau_cron_id, quand.isoformat(), rappel["offset_jours"])

        deactivate_task(rappel["cron_id"])
        retirer_rappel_echeance(suivi_id, echeance["id"], rappel["cron_id"])
        reprogrammes.append(f"{rappel['offset_jours']} j avant")

    return reprogrammes, tombes_dans_le_passe, offset_inconnu


@tool("etude_maj_echeance")
def etude_maj_echeance(
    suivi_id: str, echeance_id: str, date: str | None = None, statut: str | None = None,
    notes: str | None = None, chapitres: list[str] | None = None,
) -> str:
    """
    Modifie une échéance : la reporter (nouvelle `date`), l'annuler (`statut`
    = "annulee"), ou mettre à jour ses notes/chapitres. Un report RE-
    PROGRAMME automatiquement les rappels déjà posés (mêmes offsets,
    relatifs à la nouvelle date) — rien à refaire à la main, sauf un rappel
    trop ancien dont le délai d'origine n'est plus connu : il est alors
    laissé tel quel et signalé, jamais reprogrammé sur une valeur devinée.

    Mots-clés : reporter, annuler, modifier échéance, changer la date.

    **Args:**
        - `suivi_id`, `echeance_id` (str)
        - `date` (str, optionnel) : nouvelle date YYYY-MM-DD
        - `statut` (str, optionnel) : "a_venir", "passee", "reportee", "annulee"
        - `notes`, `chapitres` (optionnels)

    **Returns:**
        - Confirmation, ou erreur si l'échéance est introuvable.
    """
    from .store import maj_echeance, trouver_echeance

    if statut is not None and statut not in STATUTS_ECHEANCE:
        return f"Statut inconnu : {statut}. Attendu : {', '.join(STATUTS_ECHEANCE)}."

    avant = trouver_echeance(echeance_id)
    ancienne_date = avant[1]["date"] if avant else None
    anciens_rappels = list(avant[1]["rappels"]) if avant else []

    e = maj_echeance(suivi_id, echeance_id, date=date, statut=statut, notes=notes, chapitres=chapitres)
    if e is None:
        return f"Suivi ou échéance introuvable ({suivi_id} / {echeance_id})."

    morceaux = []
    if date is not None and date != ancienne_date:
        reprogrammes, tombes, inconnus = _reprogrammer_rappels(suivi_id, e, date, anciens_rappels)
        if reprogrammes:
            morceaux.append(f"rappels reprogrammés : {', '.join(reprogrammes)}")
        if tombes:
            morceaux.append(f"non reprogrammés car désormais dans le passé : {', '.join(tombes)}")
        if inconnus:
            morceaux.append(f"{len(inconnus)} rappel(s) laissé(s) tel(s) quel(s) — délai d'origine "
                             f"inconnu, reprogramme-les toi-même avec etude_planifier_rappel_echeance "
                             f"si besoin")

    extra = f" · {' · '.join(morceaux)}" if morceaux else ""
    return f"Échéance **{e['titre']}** mise à jour (date : {e['date']}, statut : {e['statut']}){extra}."


# ── rappels ──────────────────────────────────────────────────────────────

@tool("etude_planifier_rappel_echeance")
def etude_planifier_rappel_echeance(suivi_id: str, echeance_id: str, offsets_jours: list[int] | None = None) -> str:
    """
    Programme des rappels desktop avant une échéance (défaut 7, 3 et 1 jour
    avant, à 9h) — survivent à la fermeture d'Axon tant que le service de
    rappels tourne. Un offset tombant dans le passé est ignoré ; si TOUS le
    sont alors que l'échéance est à venir, un seul rappel est programmé le
    jour J à 9h (ou dans la minute si 9h est passé).

    Mots-clés : rappel, alerte, notification, prévenir, me rappeler.

    **Args:**
        - `suivi_id`, `echeance_id` (str)
        - `offsets_jours` (list[int], optionnel) : défaut [7, 3, 1]

    **Returns:**
        - Confirmation listant les rappels effectivement programmés.
    """
    from datetime import datetime as _datetime, timedelta as _timedelta
    from src.agents.cron.store import add_task
    from .store import trouver_echeance, ajouter_rappel_echeance

    trouve = trouver_echeance(echeance_id)
    if trouve is None or trouve[0]["id"] != suivi_id:
        return f"Échéance introuvable dans ce suivi ({suivi_id} / {echeance_id})."
    suivi, echeance = trouve

    offsets = offsets_jours or [7, 3, 1]
    programmes = []
    for offset in offsets:
        quand = neuf_heures(echeance["date"]) - _timedelta(days=offset)
        if deja_passe(quand):
            continue
        prompt = (f"Rappelle à l’utilisateur : {echeance['type']} — {echeance['titre']} "
                  f"({suivi['titre']}), dans {offset} jour(s) (le {echeance['date']}).")
        cron_id = add_task(description=f"Rappel · {echeance['titre']}", prompt=prompt,
                            interval_sec=0, notif_channels=["desktop"], run_at=quand.isoformat())
        ajouter_rappel_echeance(suivi_id, echeance_id, cron_id, quand.isoformat(), offset)
        programmes.append(f"{offset} j avant ({quand.strftime('%d/%m %H:%M')})")

    # Échéance trop proche pour J-7/J-3/J-1 : un seul rappel, à 9h le jour J
    # (ou dans la minute si 9h est passé).
    restants = jours_restants(echeance["date"])
    if not programmes and restants >= 0:
        quand = neuf_heures(echeance["date"])
        if deja_passe(quand):
            quand = _datetime.now(quand.tzinfo) + _timedelta(minutes=1)
        delai = "aujourd’hui" if restants == 0 else f"dans {restants} jour(s)"
        prompt = (f"Rappelle à l’utilisateur : {echeance['type']} — {echeance['titre']} "
                  f"({suivi['titre']}), {delai} (le {echeance['date']}).")
        cron_id = add_task(description=f"Rappel · {echeance['titre']}", prompt=prompt,
                           interval_sec=0, notif_channels=["desktop"], run_at=quand.isoformat())
        ajouter_rappel_echeance(suivi_id, echeance_id, cron_id, quand.isoformat(), restants)
        programmes.append(f"échéance proche ({quand.strftime('%d/%m %H:%M')})")

    if not programmes:
        return "Aucun rappel programmé : l’échéance est déjà passée."
    return "Rappels programmés : " + ", ".join(programmes) + "."


@tool("etude_planifier_point_avancement")
def etude_planifier_point_avancement(suivi_id: str, frequence_jours: int) -> str:
    """
    Programme une invitation RÉCURRENTE à faire le point sur un suivi (pas
    liée à une échéance précise) — « où en es-tu ? » tous les N jours.
    Distinct d'un rappel d'échéance.

    Mots-clés : point régulier, check-in, où j'en suis, rappel régulier.

    **Args:**
        - `suivi_id` (str)
        - `frequence_jours` (int) : intervalle entre deux invitations

    **Returns:**
        - Confirmation, ou erreur si le suivi est introuvable.
    """
    from src.agents.cron.store import add_task
    from .store import obtenir_suivi, ajouter_rappel_suivi

    suivi = obtenir_suivi(suivi_id)
    if suivi is None:
        return f"Suivi introuvable : {suivi_id}"
    if frequence_jours < 1:
        return "`frequence_jours` doit être au moins 1."
    prompt = (f"Demande à l’utilisateur où il en est sur « {suivi['titre']} » — propose de faire "
              f"le point (etude_detail_suivi puis etude_point_avancement selon sa réponse).")
    cron_id = add_task(description=f"Point d’avancement · {suivi['titre']}", prompt=prompt,
                        interval_sec=frequence_jours * 86400, notif_channels=["desktop"])
    from datetime import datetime as _datetime, timedelta as _td
    ajouter_rappel_suivi(suivi_id, cron_id, (_datetime.now() + _td(days=frequence_jours)).isoformat(), frequence_jours)
    return f"Point d’avancement programmé tous les {frequence_jours} jour(s) pour **{suivi['titre']}**."


@tool("etude_gerer_rappel")
def etude_gerer_rappel(
    suivi_id: str, cron_id: str, action: str, cible: str = "echeance",
    echeance_id: str | None = None, nouvelle_date: str | None = None,
) -> str:
    """
    Reporte ou désactive un rappel déjà programmé (échéance ou point
    d'avancement récurrent). Pour changer une fréquence de point
    d'avancement, désactive l'ancien rappel puis reprogramme avec
    `etude_planifier_point_avancement`.

    Mots-clés : reporter, snooze, désactiver, annuler rappel, suspendre.

    **Args:**
        - `suivi_id`, `cron_id` (str)
        - `action` (str) : "reporter" ou "desactiver"
        - `cible` (str) : "echeance" (défaut, nécessite `echeance_id`) ou "suivi"
        - `echeance_id` (str, requis si `cible="echeance"`)
        - `nouvelle_date` (str, requis si `action="reporter"`) : ISO, ex.
          "2026-11-23T09:00:00"

    **Returns:**
        - Confirmation, ou erreur si les identifiants/l'action ne sont pas
          valides.
    """
    from src.agents.cron.store import update_task, deactivate_task
    from .store import retirer_rappel_echeance, retirer_rappel_suivi

    if cible not in ("echeance", "suivi"):
        return 'Cible inconnue. Attendu : "echeance" ou "suivi".'
    if cible == "echeance" and not echeance_id:
        return "`echeance_id` est requis pour un rappel d’échéance."

    if action == "reporter":
        if not nouvelle_date:
            return "`nouvelle_date` est requise pour reporter un rappel."
        update_task(cron_id, run_at=nouvelle_date)
        return f"Rappel reporté au {nouvelle_date}."
    if action == "desactiver":
        deactivate_task(cron_id)
        if cible == "echeance":
            retirer_rappel_echeance(suivi_id, echeance_id, cron_id)
        else:
            retirer_rappel_suivi(suivi_id, cron_id)
        return "Rappel désactivé."
    return f"Action inconnue : {action}. Attendu : reporter, desactiver."
