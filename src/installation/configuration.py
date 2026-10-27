"""Configuration des intégrations d'Axon — le menu de `setup.sh` et `setup.ps1`.

    python -m src.installation.configuration identite   ton prénom (USER_NAME)
    python -m src.installation.configuration menu       le menu des intégrations
    python -m src.installation.configuration statut     l'état de chaque intégration

À lancer depuis la racine du dépôt : c'est là que vivent `.env` et
`gcp-oauth.keys.json`.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from src.installation import console as c
from src.installation.fichier_env import FichierEnv
from src.installation.services import SERVICES, Contexte, configurer_identite

RACINE = Path(__file__).resolve().parents[2]


def contexte() -> Contexte:
    env = RACINE / ".env"
    exemple = RACINE / ".env.sample"
    if not env.exists() and exemple.exists():
        shutil.copyfile(exemple, env)
    return Contexte(racine=RACINE, env=FichierEnv(env))


def afficher_statut(ctx: Contexte) -> None:
    print()
    print(f"  {c.BLANC}Statut des intégrations :{c.FIN}\n")
    nom = ctx.env.lire("USER_NAME")
    if ctx.env.renseignee("USER_NAME"):
        c.ok(f"Identité  {c.SOURD}→ {nom}{c.FIN}")
    else:
        c.alerte(f"Identité  {c.SOURD}(USER_NAME non configuré){c.FIN}")
    for service in SERVICES:
        if not service.est_configure(ctx):
            c.alerte(f"{service.statut} {c.SOURD}(non configuré){c.FIN}")
        elif service.resume is not None:
            c.ok(f"{service.statut:<9} {c.SOURD}→ {service.resume(ctx)}{c.FIN}")
        else:
            c.ok(service.statut)
    print()


def menu(ctx: Contexte) -> None:
    while True:
        c.etape("Configuration des intégrations")
        afficher_statut(ctx)
        print(f"  {c.BLANC}Que veux-tu configurer ?{c.FIN}\n")
        for numero, service in enumerate(SERVICES, 1):
            libelle, _, note = service.menu.partition("(")
            note = f"{c.SOURD}({note}{c.FIN}" if note else ""
            print(f"  {c.ORANGE}{numero:<2}{c.FIN} {libelle}{note}")
        print(f"  {c.ORANGE}a{c.FIN}  Tout configurer")
        print(f"  {c.ORANGE}q{c.FIN}  Quitter le menu\n")

        choix = c.demander("Choix : ").lower()
        if choix in ("q", ""):
            c.info("Configuration terminée.")
            return
        if choix == "a":
            for service in SERVICES:
                service.configurer(ctx)
        elif choix.isdigit() and 1 <= int(choix) <= len(SERVICES):
            SERVICES[int(choix) - 1].configurer(ctx)
        else:
            c.alerte("Choix invalide — entre un numéro, 'a' ou 'q' pour quitter.")


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(prog="python -m src.installation.configuration",
                                        description="Configuration des intégrations d'Axon.")
    analyseur.add_argument("action", choices=("identite", "menu", "statut"))
    action = analyseur.parse_args(arguments).action
    ctx = contexte()
    try:
        if action == "identite":
            configurer_identite(ctx.env)
        elif action == "menu":
            menu(ctx)
        else:
            afficher_statut(ctx)
    except KeyboardInterrupt:
        print()
        c.info("Configuration interrompue — relance-la quand tu veux.")


if __name__ == "__main__":
    main()
