"""La commande `/plugin` (alias `/marketplace`).

Comme `/mcp`, le dispatcher rend du texte ; la sélection (`choisir`) et
l'affichage de la progression (`annoncer`) sont injectés — le CLI y branche son
menu aux flèches, les tests une simple liste.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.plugins import catalogue, installateur, registre
from src.plugins.catalogue import Source
from src.plugins.manifeste import ErreurPlugin, Manifeste, Plateforme, plateforme_courante

Choisir = Callable[[list[str], str], "str | None"]

USAGE = """\
/plugin                       la marketplace : choisir un plugin dans la liste
/plugin list                  le catalogue et ce qui est installé
/plugin install <id|url|dossier> [--ref <branche>] [--dossier <sous-dossier>]
/plugin update [id]           réinstalle depuis la même source (tous si omis)
/plugin remove <id>           désinstalle"""

_INSTALLER, _METTRE_A_JOUR, _RETIRER = "Installer", "Mettre à jour", "Désinstaller"
_LANCER, _ANNULER = "Lancer ces étapes", "Annuler"


def handle_plugin(arguments: list[str], *, choisir: Choisir,
                  annoncer: Callable[[str], None] = lambda _t: None) -> str:
    confirmer = _confirmateur(choisir, annoncer)
    sous_commande, *reste = arguments or [""]
    try:
        if sous_commande == "":
            return _marketplace(choisir, confirmer, annoncer)
        if sous_commande in ("list", "ls"):
            return lister()
        if sous_commande == "install" and reste:
            return _installer(reste, confirmer, annoncer)
        if sous_commande == "update":
            return _mettre_a_jour(reste[:1] or sorted(registre.installes()), confirmer, annoncer)
        if sous_commande in ("remove", "uninstall") and reste:
            installateur.desinstaller(reste[0])
            return f"{reste[0]} désinstallé."
    except ErreurPlugin as erreur:
        return f"✗ {erreur}"
    return USAGE


def lister() -> str:
    installes = registre.installes()
    lignes = [f"plateforme : {plateforme_courante()}", ""]
    for entree in catalogue.entrees():
        etat = f"installé {installes[entree.id].version}" if entree.id in installes else "disponible"
        lignes.append(f"  {entree.id:<20} {etat:<16} {entree.description}")
    for ident, plugin in sorted(installes.items()):
        if catalogue.trouver(ident) is None:
            lignes.append(f"  {ident:<20} {'installé ' + plugin.version:<16} hors catalogue")
    if len(lignes) == 2:
        lignes.append("  catalogue vide")
    lignes += ["", f"installés dans {registre.dossier()}"]
    return "\n".join(lignes)


def _marketplace(choisir: Choisir, confirmer, annoncer) -> str:
    entrees = catalogue.entrees()
    if not entrees:
        return "Le catalogue est vide."
    installes = registre.installes()
    libelles = {
        f"{e.nom} — {f'installé {installes[e.id].version}' if e.id in installes else 'disponible'}"
        f" · {e.description}": e for e in entrees}
    choix = choisir(list(libelles), "marketplace — choisis un plugin")
    if choix is None:
        return "annulé"
    entree = libelles[choix]
    actions = [_METTRE_A_JOUR, _RETIRER, _ANNULER] if entree.id in installes else [_INSTALLER, _ANNULER]
    action = choisir(actions, entree.nom)
    if action == _INSTALLER:
        return _resultat(installateur.installer(entree.source, confirmer=confirmer, annoncer=annoncer,
                                                id_attendu=entree.id))
    if action == _METTRE_A_JOUR:
        return _resultat(installateur.mettre_a_jour(entree.id, confirmer=confirmer, annoncer=annoncer))
    if action == _RETIRER:
        installateur.desinstaller(entree.id)
        return f"{entree.nom} désinstallé."
    return "annulé"


def _installer(arguments: list[str], confirmer, annoncer) -> str:
    cible, options = arguments[0], _options(arguments[1:])
    entree = catalogue.trouver(cible)
    if entree is not None:
        source, attendu = entree.source, entree.id
    elif "://" in cible or cible.startswith("git@") or cible.endswith(".git"):
        source, attendu = Source(git=cible, ref=options.get("ref", ""), dossier=options.get("dossier", "")), ""
    elif Path(cible).expanduser().is_dir():
        source, attendu = Source(local=str(Path(cible).expanduser().resolve()),
                                 dossier=options.get("dossier", "")), ""
    else:
        raise ErreurPlugin(f"« {cible} » n'est ni dans le catalogue, ni une URL git, ni un dossier")
    return _resultat(installateur.installer(source, confirmer=confirmer, annoncer=annoncer,
                                            id_attendu=attendu))


def _mettre_a_jour(idents: list[str], confirmer, annoncer) -> str:
    if not idents:
        return "Aucun plugin installé."
    return "\n".join(_resultat(installateur.mettre_a_jour(i, confirmer=confirmer, annoncer=annoncer))
                     for i in idents)


def _options(arguments: list[str]) -> dict[str, str]:
    options, i = {}, 0
    while i < len(arguments):
        if arguments[i] in ("--ref", "--dossier") and i + 1 < len(arguments):
            options[arguments[i][2:]] = arguments[i + 1]
            i += 2
        else:
            raise ErreurPlugin(f"option inconnue : {arguments[i]}")
    return options


def _resultat(plugin: registre.Installe) -> str:
    dossier = registre.dossier_plugin(plugin.id)
    lignes = [f"✓ {plugin.id} {plugin.version} installé dans {dossier}"]
    if plugin.capacites:
        lignes.append(f"  capacités : {', '.join(plugin.capacites)} — relance Axon pour les activer")
    plateforme = Manifeste.lire(dossier).pour(plateforme_courante())
    if plateforme and plateforme.entrypoint:
        lignes.append(f"  lancer : {dossier / plateforme.entrypoint}")
    if plateforme and plateforme.toggle:
        lignes.append(f"  ouvrir / masquer : {dossier / plateforme.toggle}")
    return "\n".join(lignes)


def _confirmateur(choisir: Choisir, annoncer: Callable[[str], None]):
    def confirmer(manifeste: Manifeste, plateforme: Plateforme) -> bool:
        annoncer(f"{manifeste.nom} {manifeste.version} va lancer, dans son dossier :")
        for etape in plateforme.installation:
            annoncer(f"    {' '.join(etape)}")
        return choisir([_LANCER, _ANNULER], f"installer {manifeste.id} ?") == _LANCER
    return confirmer
