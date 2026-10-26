"""Logique propre aux outils `etude_*` (pas déjà couverte par
tests/test_study_store.py, qui teste la couche `store.py`) : la vérification
de projet en deux temps (§11) et la reprogrammation automatique des rappels
au report d'une échéance (§10).

Même isolation que test_study_store.py : `AXON_STATE_DIR` redirigé, modules
rechargés après la surcharge (les deux modules lisent `_chemins.etudes()` à
l'import).
"""
from __future__ import annotations

import importlib
import types
from datetime import date, timedelta

import pytest


@pytest.fixture
def etude(monkeypatch, tmp_path):
    """Les outils `etude_*` sont répartis par domaine (tools_suivi.py,
    tools_echeance.py, tools_progression.py, tools_verification.py) — ce
    fixture les regroupe sous un seul espace de noms `etude.xxx`, pour que
    les tests ci-dessous n'aient pas à savoir dans quel fichier chacun vit."""
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.agents.cron.store as cron_store
    import src.agents.study.tools_suivi as tools_suivi
    import src.agents.study.tools_echeance as tools_echeance
    import src.agents.study.tools_progression as tools_progression
    import src.agents.study.tools_verification as tools_verification

    for module in (chemins, store, cron_store, tools_suivi, tools_echeance,
                   tools_progression, tools_verification):
        importlib.reload(module)

    outils = {}
    for module in (tools_suivi, tools_echeance, tools_progression, tools_verification):
        for nom in dir(module):
            if nom.startswith("etude_"):
                outils[nom] = getattr(module, nom)
    return types.SimpleNamespace(**outils)


def _iv(outil, **kw):
    return outil.invoke(kw)


# ── vérification de projet (§11) ──────────────────────────────────────

def test_contexte_verification_liste_ressources_et_exigences(etude):
    sid = _iv(etude.etude_creer_suivi, titre="Projet Algo", type="projet").split("`")[1]
    _iv(etude.etude_associer_ressource, suivi_id=sid, type="dossier", nom="src",
        chemin="/tmp/inexistant-mais-ok-ici", provenance="chemin_externe")
    _iv(etude.etude_ajouter_tache, suivi_id=sid, titre="Avoir un README")

    contexte = _iv(etude.etude_contexte_verification, suivi_id=sid)

    assert "src" in contexte
    assert "Avoir un README" in contexte


def test_contexte_verification_signale_une_ressource_deja_marquee_inaccessible(etude):
    from src.agents.study.store import marquer_ressource

    sid = _iv(etude.etude_creer_suivi, titre="Projet", type="projet").split("`")[1]
    rid = _iv(etude.etude_associer_ressource, suivi_id=sid, type="dossier", nom="x",
              chemin="/tmp/x", provenance="chemin_externe").split("`")[1]
    marquer_ressource(rid, False, "dossier supprimé")

    contexte = _iv(etude.etude_contexte_verification, suivi_id=sid)

    assert "inaccessible" in contexte and "dossier supprimé" in contexte


def test_contexte_verification_suivi_inconnu(etude):
    assert "introuvable" in _iv(etude.etude_contexte_verification, suivi_id="suivi_inexistant").lower()


def test_enregistrer_verification_persiste_et_reapparait_dans_le_detail(etude):
    sid = _iv(etude.etude_creer_suivi, titre="Projet", type="projet").split("`")[1]

    resultat = _iv(
        etude.etude_enregistrer_verification, suivi_id=sid,
        ressources_inspectees=["res_x"], elements_presents=["README.md"],
        exigences_couvertes=["Avoir un README"], elements_manquants=["Avoir des tests"],
        points_non_verifiables=["Tests non exécutés"], preuves=["README.md"],
        texte="Inspection de fichiers uniquement.",
    )
    assert "Vérification enregistrée" in resultat

    detail = _iv(etude.etude_detail_suivi, suivi_id=sid)
    assert "Dernières vérifications" in detail
    assert "1 couvertes" in detail and "1 manquantes" in detail and "1 non vérifiables" in detail


def test_enregistrer_verification_ne_change_aucun_statut_dexercice_ou_tache(etude):
    """§11 : les changements de statut suggérés restent des propositions —
    `etude_enregistrer_verification` ne touche ni exercices ni tâches."""
    sid = _iv(etude.etude_creer_suivi, titre="Projet", type="projet").split("`")[1]
    tid = _iv(etude.etude_ajouter_tache, suivi_id=sid, titre="Avoir un README").split("`")[1]

    _iv(etude.etude_enregistrer_verification, suivi_id=sid, ressources_inspectees=[],
        elements_presents=["README.md présent"], exigences_couvertes=["Avoir un README"],
        elements_manquants=[], points_non_verifiables=[], preuves=["README.md"],
        texte="README trouvé.")

    from src.agents.study.store import obtenir_suivi
    tache = next(t for t in obtenir_suivi(sid)["taches"] if t["id"] == tid)
    assert tache["statut"] == "a_faire"  # pas changé automatiquement


def test_enregistrer_verification_suivi_inconnu(etude):
    resultat = _iv(etude.etude_enregistrer_verification, suivi_id="suivi_inexistant",
                    ressources_inspectees=[], elements_presents=[], exigences_couvertes=[],
                    elements_manquants=[], points_non_verifiables=[], preuves=[], texte="x")
    assert "introuvable" in resultat.lower()


# ── report d'échéance : reprogrammation automatique des rappels (§10) ──

def test_reporter_une_echeance_reprogramme_ses_rappels_aux_memes_offsets(etude):
    sid = _iv(etude.etude_creer_suivi, titre="ML", type="matiere").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Partiel", type="partiel",
              date=dans_30j).split("`")[1]
    _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid, offsets_jours=[7, 3])

    from src.agents.cron.store import get_tasks
    avant = {t["id"]: t for t in get_tasks()}
    assert len(avant) == 2 and all(t["active"] for t in avant.values())

    dans_50j = (date.today() + timedelta(days=50)).isoformat()
    confirmation = _iv(etude.etude_maj_echeance, suivi_id=sid, echeance_id=eid, date=dans_50j)
    assert "rappels reprogrammés" in confirmation

    apres = {t["id"]: t for t in get_tasks()}
    # les anciennes tâches sont désactivées, pas supprimées
    for tid in avant:
        assert apres[tid]["active"] is False
    # deux nouvelles tâches actives sont apparues, aux mêmes offsets
    nouvelles = {tid: t for tid, t in apres.items() if tid not in avant}
    assert len(nouvelles) == 2 and all(t["active"] for t in nouvelles.values())
    dates_attendues = {
        (date.today() + timedelta(days=50 - 7)).isoformat(),
        (date.today() + timedelta(days=50 - 3)).isoformat(),
    }
    dates_obtenues = {t["run_at"][:10] for t in nouvelles.values()}
    assert dates_obtenues == dates_attendues


def test_un_report_qui_rend_un_offset_passe_ne_le_reprogramme_pas(etude):
    sid = _iv(etude.etude_creer_suivi, titre="ML", type="matiere").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Partiel", type="partiel",
              date=dans_30j).split("`")[1]
    _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid, offsets_jours=[7])

    # reporte à DEMAIN : un rappel "7 jours avant" tomberait hier → pas reprogrammé
    demain = (date.today() + timedelta(days=1)).isoformat()
    confirmation = _iv(etude.etude_maj_echeance, suivi_id=sid, echeance_id=eid, date=demain)

    assert "rappels reprogrammés" not in confirmation
    from src.agents.study.store import trouver_echeance
    assert trouver_echeance(eid)[1]["rappels"] == []


def test_modifier_une_echeance_sans_changer_la_date_ne_touche_pas_les_rappels(etude):
    sid = _iv(etude.etude_creer_suivi, titre="ML", type="matiere").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Partiel", type="partiel",
              date=dans_30j).split("`")[1]
    _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid, offsets_jours=[7])

    from src.agents.cron.store import get_tasks
    avant = {t["id"] for t in get_tasks()}

    _iv(etude.etude_maj_echeance, suivi_id=sid, echeance_id=eid, notes="juste une note")

    apres = {t["id"]: t for t in get_tasks()}
    assert set(apres) == avant
    assert all(t["active"] for t in apres.values())


def test_les_rappels_sont_explicitement_en_europe_paris(etude):
    sid = _iv(etude.etude_creer_suivi, titre="ML", type="matiere").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Partiel", type="partiel",
              date=dans_30j).split("`")[1]
    _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid, offsets_jours=[7])

    from src.agents.cron.store import get_tasks
    run_at = next(iter(get_tasks()))["run_at"]
    assert run_at.endswith(("+01:00", "+02:00"))  # CET/CEST selon la saison, jamais naive


def test_neuf_heures_traverse_le_changement_d_heure_europe_paris():
    """Pas juste « +01:00 ou +02:00 » (déjà couvert ci-dessus pour la date du
    jour) : une vraie date d'hiver et une vraie date d'été doivent donner des
    décalages DIFFÉRENTS, preuve que `zoneinfo` applique le changement
    d'heure plutôt qu'un offset fixe codé en dur."""
    from src.agents.study._aide import neuf_heures

    assert neuf_heures("2026-01-15").isoformat().endswith("+01:00")
    assert neuf_heures("2026-07-15").isoformat().endswith("+02:00")


def test_un_offset_inconnu_n_est_jamais_invente_mais_signale(etude):
    """Rappel « legacy » (créé avant que `offset_jours` soit persisté, donc
    `None`) : un report ne doit ni l'inventer, ni le supprimer silencieusement
    — seulement le signaler à l'appelant pour qu'il décide."""
    sid = _iv(etude.etude_creer_suivi, titre="ML", type="matiere").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Partiel", type="partiel",
              date=dans_30j).split("`")[1]

    from src.agents.cron.store import add_task, get_tasks
    from src.agents.study.store import ajouter_rappel_echeance, trouver_echeance

    run_at_initial = f"{dans_30j}T09:00:00"
    cron_id = add_task(description="Rappel · Partiel", prompt="Rappelle...",
                        interval_sec=0, notif_channels=["desktop"], run_at=run_at_initial)
    ajouter_rappel_echeance(sid, eid, cron_id, run_at_initial, offset_jours=None)

    demain = (date.today() + timedelta(days=1)).isoformat()
    confirmation = _iv(etude.etude_maj_echeance, suivi_id=sid, echeance_id=eid, date=demain)

    assert "délai d'origine inconnu" in confirmation
    assert "rappels reprogrammés" not in confirmation

    # ni inventé (toujours actif), ni perdu (toujours là, à l'ancienne date —
    # aucune tentative de deviner la nouvelle)
    taches = {t["id"]: t for t in get_tasks()}
    assert taches[cron_id]["active"] is True
    assert taches[cron_id]["run_at"] == run_at_initial

    rappels = trouver_echeance(eid)[1]["rappels"]
    assert len(rappels) == 1
    assert rappels[0]["cron_id"] == cron_id
    assert rappels[0]["offset_jours"] is None


def test_type_ressource_pour_chemin(tmp_path):
    from src.agents.study._aide import type_ressource_pour_chemin
    depot = tmp_path / "depot"; (depot / ".git").mkdir(parents=True)
    dossier = tmp_path / "cours"; dossier.mkdir()
    fichier = tmp_path / "sujet.pdf"; fichier.write_text("x")

    assert type_ressource_pour_chemin(str(depot)) == "depot_git"
    assert type_ressource_pour_chemin(str(dossier)) == "dossier"
    assert type_ressource_pour_chemin(str(fichier)) == "document"


def _depot(chemin):
    (chemin / ".git").mkdir(parents=True)
    return chemin


def test_un_dossier_front_back_cree_un_projet_et_lie_chaque_depot(etude, tmp_path):
    """Le dossier parent n'est pas un dépôt, mais ses deux sous-dossiers le
    sont : les deux dépôts doivent être liés, et le suivi est un projet."""
    from src.agents.study.store import obtenir_ressource, obtenir_suivi
    from src.agents.study.tools_suivi import lier_chemin_local
    projet = tmp_path / "conseil-des-sages"
    _depot(projet / "be-cds"); _depot(projet / "fe-cds")

    suivi_id, erreur = lier_chemin_local("", str(projet))

    assert erreur is None
    suivi = obtenir_suivi(suivi_id)
    assert (suivi["titre"], suivi["type"]) == ("conseil-des-sages", "projet")
    liees = sorted((r["type"], r["nom"]) for r in map(obtenir_ressource, suivi["ressources"]))
    assert liees == [("depot_git", "be-cds"), ("depot_git", "fe-cds"), ("dossier", "conseil-des-sages")]


def test_relier_le_meme_dossier_ne_cree_pas_de_doublon(etude, tmp_path):
    from src.agents.study.store import obtenir_suivi
    from src.agents.study.tools_suivi import lier_chemin_local
    projet = tmp_path / "projet"
    _depot(projet / "back")

    suivi_id, _ = lier_chemin_local("", str(projet))
    lier_chemin_local(suivi_id, str(projet))

    assert len(obtenir_suivi(suivi_id)["ressources"]) == 2


def test_un_simple_dossier_sans_depot_reste_un_suivi_autre(etude, tmp_path):
    from src.agents.study.store import obtenir_suivi
    from src.agents.study.tools_suivi import lier_chemin_local
    cours = tmp_path / "cours"; cours.mkdir()

    suivi_id, _ = lier_chemin_local("", str(cours))

    assert obtenir_suivi(suivi_id)["type"] == "autre"


def test_supprimer_un_suivi_desactive_ses_rappels(etude):
    """Sans ça, un suivi supprimé continuerait d'envoyer des notifications."""
    from src.agents.cron.store import get_tasks
    sid = _iv(etude.etude_creer_suivi, titre="be-cds", type="projet").split("`")[1]
    dans_30j = (date.today() + timedelta(days=30)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Rendu", type="rendu_projet",
              date=dans_30j).split("`")[1]
    _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid, offsets_jours=[7, 3])
    assert sum(t["active"] for t in get_tasks()) == 2

    confirmation = _iv(etude.etude_supprimer_suivi, suivi_id=sid)

    assert "supprimé" in confirmation and "2 rappel" in confirmation
    assert sum(t["active"] for t in get_tasks()) == 0


def test_une_echeance_trop_proche_pour_j7_j3_j1_recoit_quand_meme_un_rappel(etude):
    """Échéance créée la veille : J-7, J-3 et J-1 sont déjà passés. Avant, aucun
    rappel n'était programmé et rien ne prévenait le jour J."""
    sid = _iv(etude.etude_creer_suivi, titre="CDS", type="projet").split("`")[1]
    demain = (date.today() + timedelta(days=1)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Suivi de projet", type="rendu_projet",
              date=demain).split("`")[1]
    from src.agents.study.store import trouver_echeance

    confirmation = _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid,
                       offsets_jours=[7, 3])

    assert "échéance proche" in confirmation
    rappels = trouver_echeance(eid)[1]["rappels"]
    assert len(rappels) == 1
    assert rappels[0]["quand"].startswith(demain)          # le jour J, à 9h


def test_une_echeance_deja_passee_ne_recoit_aucun_rappel(etude):
    sid = _iv(etude.etude_creer_suivi, titre="CDS", type="projet").split("`")[1]
    hier = (date.today() - timedelta(days=1)).isoformat()
    eid = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Vieux rendu", type="rendu_projet",
              date=hier).split("`")[1]
    confirmation = _iv(etude.etude_planifier_rappel_echeance, suivi_id=sid, echeance_id=eid)
    assert "déjà passée" in confirmation


def test_une_echeance_sans_type_est_un_jalon_autre(etude):
    """Vécu : quatre appels ratés d'affilée parce que le modèle omettait `type`
    pour un jalon intermédiaire — autant de tours, autant de risques de panne."""
    sid = _iv(etude.etude_creer_suivi, titre="CDS", type="projet").split("`")[1]
    dans_3j = (date.today() + timedelta(days=3)).isoformat()
    confirmation = _iv(etude.etude_ajouter_echeance, suivi_id=sid, titre="Revue du design UI", date=dans_3j)
    eid = confirmation.split("`")[1]
    from src.agents.study.store import trouver_echeance
    assert trouver_echeance(eid)[1]["type"] == "autre"
