"""src/cron_daemon.py — tâches avec et sans fuseau dans la même liste.

Les rappels d'études sont écrits avec leur fuseau (`…T09:00:00+01:00`),
`schedule_task` en heure locale naïve. `_reload_tasks` comparait les deux à
`datetime.now()` naïf : TypeError non rattrapé, et tout le daemon tombait —
toutes les tâches, pas seulement les rappels d'études.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src import cron_daemon


class FauxScheduler:
    def __init__(self):
        self.jobs: list[str] = []
        self.grace: dict[str, int] = {}

    def add_job(self, _fonction, trigger, id, misfire_grace_time=None, **_k):
        self.jobs.append(id)
        self.grace[id] = misfire_grace_time

    def remove_job(self, _id):
        pass


@pytest.fixture
def daemon(monkeypatch):
    planifie = FauxScheduler()
    desactivees: list[str] = []
    monkeypatch.setattr(cron_daemon, "scheduler", planifie)
    monkeypatch.setattr(cron_daemon, "_known_ids", set())
    monkeypatch.setattr(cron_daemon, "deactivate_task", desactivees.append)
    monkeypatch.setattr(cron_daemon, "append_log", lambda *_a: None)
    notifications: list[tuple[str, str]] = []
    monkeypatch.setattr(cron_daemon, "notifier", lambda titre, corps, contexte=None: notifications.append((titre, corps)))
    # Jamais le vrai store d'études de la machine dans ces tests.
    monkeypatch.setattr(cron_daemon, "_echeance_du_rappel", lambda _id: None)
    planifie.notifications = notifications
    return planifie, desactivees


def _tache(id_, run_at):
    return {"id": id_, "run_at": run_at, "interval_sec": 0, "description": id_}


def test_des_dates_avec_et_sans_fuseau_ne_font_pas_tomber_le_daemon(daemon, monkeypatch):
    planifie, desactivees = daemon
    futur = datetime.now() + timedelta(days=3)
    passe = datetime.now() - timedelta(days=3)
    monkeypatch.setattr(cron_daemon, "get_tasks", lambda active_only=True: [
        _tache("etude_futur", futur.astimezone().isoformat()),
        _tache("etude_passe", passe.astimezone().isoformat()),
        _tache("naif_futur", futur.isoformat()),
        _tache("naif_passe", passe.isoformat()),
    ])

    cron_daemon._reload_tasks()

    assert sorted(planifie.jobs) == ["etude_futur", "naif_futur"]
    assert sorted(desactivees) == ["etude_passe", "naif_passe"]



# ── rappels d'études : contenu réel quand ils sont manqués ─────────────

SUIVI = {"id": "suivi_x", "titre": "Projet Compilateur"}
ECHEANCE = {"id": "ech_1", "titre": "Rendu final", "date": "2099-12-10"}


def test_des_rappels_d_etudes_manques_donnent_une_seule_notification_avec_leur_contenu(daemon, monkeypatch):
    planifie, desactivees = daemon
    passe = (datetime.now() - timedelta(days=1)).astimezone().isoformat()
    monkeypatch.setattr(cron_daemon, "get_tasks", lambda active_only=True: [
        _tache("j7", passe), _tache("j3", passe), _tache("autre", passe),
    ])
    rappels = {"j7": (SUIVI, ECHEANCE), "j3": (SUIVI, ECHEANCE)}
    monkeypatch.setattr(cron_daemon, "_echeance_du_rappel", rappels.get)

    cron_daemon._reload_tasks()

    titres = [titre for titre, _corps in planifie.notifications]
    assert titres.count("Axon · Rendu final") == 1                 # J-7 et J-3 regroupés
    assert any("Projet Compilateur" in corps for _t, corps in planifie.notifications)
    assert "Axon · autre" in titres                                 # tâche ordinaire : message générique
    assert sorted(desactivees) == ["autre", "j3", "j7"]


def test_un_rappel_d_etudes_garde_12_h_de_tolerance_en_cas_de_veille(daemon, monkeypatch):
    planifie, _ = daemon
    futur = (datetime.now() + timedelta(days=2)).astimezone().isoformat()
    monkeypatch.setattr(cron_daemon, "get_tasks", lambda active_only=True: [_tache("etude", futur), _tache("autre", futur)])
    monkeypatch.setattr(cron_daemon, "_echeance_du_rappel", {"etude": (SUIVI, ECHEANCE)}.get)

    cron_daemon._reload_tasks()

    assert planifie.grace == {"etude": cron_daemon.GRACE_RAPPEL_ETUDE, "autre": 30}


# ── récapitulatif du jour ──────────────────────────────────────────────

@pytest.fixture
def recap(monkeypatch, tmp_path):
    envoyes: list[tuple[str, str]] = []
    monkeypatch.setattr(cron_daemon._chemins, "dernier_recap_etudes", lambda: tmp_path / "dernier_recap")
    monkeypatch.setattr(cron_daemon, "notifier", lambda titre, corps, contexte=None: envoyes.append((titre, corps)))
    monkeypatch.setattr(cron_daemon, "recap_du_jour", lambda: ("Axon · Études", "• Rendu final — dans 3 jours"))
    return envoyes


class _Horloge(datetime):
    heure = 9

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 13, cls.heure, 0)


def test_le_recapitulatif_part_une_seule_fois_par_jour(recap, monkeypatch):
    monkeypatch.setattr(cron_daemon, "datetime", _Horloge)

    cron_daemon._recap_etudes_si_nouveau_jour()
    cron_daemon._recap_etudes_si_nouveau_jour()   # redémarrage du daemon le même jour

    assert recap == [("Axon · Études", "• Rendu final — dans 3 jours")]


def test_pas_de_recapitulatif_avant_6_h(recap, monkeypatch):
    _Horloge.heure = 3
    monkeypatch.setattr(cron_daemon, "datetime", _Horloge)
    try:
        cron_daemon._recap_etudes_si_nouveau_jour()
    finally:
        _Horloge.heure = 9

    assert recap == []


def test_un_rappel_part_dans_l_ile_quand_elle_ecoute(monkeypatch, tmp_path):
    """L'île d'abord, si son plugin est installé ; sans elle, une notification
    système (dunst)."""
    import json
    import socket
    import subprocess

    from src.plugins import registre

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path / "etat"))
    registre.dossier_plugin("axon-overlay").mkdir(parents=True)
    registre.enregistrer(registre.Installe(id="axon-overlay", version="0.2.0", capacites=("notifications",),
                                           source={}, commit="", installe_le=""))
    (tmp_path / "axon").mkdir()
    serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    serveur.bind(str(tmp_path / "axon" / "controle.sock"))
    serveur.listen(1)
    lances = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: lances.append(a))
    try:
        cron_daemon.notifier("Axon · Études", "• Rendu CDS")
        client, _ = serveur.accept()
        recu = json.loads(client.makefile().readline())
        client.close()
    finally:
        serveur.close()
    assert recu["type"] == "rappel" and recu["titre"] == "Axon · Études"
    assert lances == []

    cron_daemon.notifier("Axon · Études", "• Rendu CDS")   # île arrêtée
    assert lances and lances[0][0][0] == "notify-send"
