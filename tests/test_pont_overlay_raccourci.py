"""src/ui/pont_overlay.py — le hook `sur_raccourci` ajouté pour les
dashboards d'intégration de l'île.

Protège le contrat : un message `{"type":"raccourci","id":...,"action":...}`
reçu sur le socket doit appeler `sur_raccourci(id, action, item, panel)` tel
quel (item/panel à None quand absents — c'est une demande de panneau entier,
pas le détail d'une ligne), et ne rien faire (pas de crash) si personne ne
l'a défini — exactement comme `sur_demande_commandes`, dont ce hook reprend
le patron.
"""
from __future__ import annotations

from src.ui.pont_overlay import PontOverlay


def test_raccourci_de_panneau_appelle_le_hook_sans_item_ni_panel():
    pont = PontOverlay()
    appels = []
    pont.sur_raccourci = lambda id_, action, item, panel: appels.append((id_, action, item, panel))

    pont._traiter({"type": "raccourci", "id": "abc123", "action": "gmail_non_lus"})

    assert appels == [("abc123", "gmail_non_lus", None, None)]


def test_raccourci_de_detail_transmet_item_et_panel():
    pont = PontOverlay()
    appels = []
    pont.sur_raccourci = lambda id_, action, item, panel: appels.append((id_, action, item, panel))

    pont._traiter({
        "type": "raccourci", "id": "xyz", "action": "gmail_resumer_mail",
        "item": "18abf0", "panel": "gmail_non_lus",
    })

    assert appels == [("xyz", "gmail_resumer_mail", "18abf0", "gmail_non_lus")]


def test_raccourci_sans_hook_ne_leve_pas():
    pont = PontOverlay()
    pont._traiter({"type": "raccourci", "id": "abc123", "action": "gmail_non_lus"})  # ne doit pas lever


# ── gestion des échéances depuis l'île (§3, lot 3) ──────────────────────

def test_creer_echeance_transmet_tous_les_champs():
    pont = PontOverlay()
    appels = []
    pont.sur_creer_echeance = lambda *a: appels.append(a)

    pont._traiter({"type": "creer_echeance", "id": "e1", "suivi_id": "suivi_a",
                   "titre": "Partiel", "type_echeance": "partiel", "date": "2026-11-25"})

    assert appels == [("e1", "suivi_a", "Partiel", "partiel", "2026-11-25")]


def test_maj_echeance_transmet_date_et_statut_absents_comme_none():
    """Un report n'envoie que `date`, une annulation que `statut` — l'autre
    champ doit arriver comme None, jamais comme la chaîne "None" ou vide."""
    pont = PontOverlay()
    appels = []
    pont.sur_maj_echeance = lambda *a: appels.append(a)

    pont._traiter({"type": "maj_echeance", "id": "e2", "suivi_id": "suivi_a",
                   "echeance_id": "ech_1", "date": "2026-12-01"})

    assert appels == [("e2", "suivi_a", "ech_1", "2026-12-01", None)]


def test_maj_echeance_avec_statut_seul():
    pont = PontOverlay()
    appels = []
    pont.sur_maj_echeance = lambda *a: appels.append(a)

    pont._traiter({"type": "maj_echeance", "id": "e3", "suivi_id": "suivi_a",
                   "echeance_id": "ech_1", "statut": "annulee"})

    assert appels == [("e3", "suivi_a", "ech_1", None, "annulee")]


def test_archiver_suivi_transmet_id_et_suivi_id():
    pont = PontOverlay()
    appels = []
    pont.sur_archiver_suivi = lambda *a: appels.append(a)

    pont._traiter({"type": "archiver_suivi", "id": "e4", "suivi_id": "suivi_a"})

    assert appels == [("e4", "suivi_a")]


def test_gestion_echeances_sans_hooks_ne_leve_pas():
    pont = PontOverlay()
    pont._traiter({"type": "creer_echeance", "id": "e1", "suivi_id": "s"})
    pont._traiter({"type": "maj_echeance", "id": "e2", "suivi_id": "s", "echeance_id": "ech"})
    pont._traiter({"type": "archiver_suivi", "id": "e3", "suivi_id": "s"})
