"""Outils `etude_*` pour vérifier l'avancement d'un projet (§11).

En DEUX temps, volontairement : ce module ne lit ni dépôt ni fichier
lui-même (ça resterait une seconde logique d'inspection qui diverge de
`local_list_directory`/`local_grep`/`git_status`/`git_log`, déjà là et déjà
testés) — il dit QUOI vérifier, laisse l'agent vérifier avec ses outils
habituels, encaisse ensuite la conclusion.
"""
from __future__ import annotations

from langchain_core.tools import tool


@tool("etude_contexte_verification")
def etude_contexte_verification(suivi_id: str) -> str:
    """
    Première étape de « vérifie l'avancement de mon projet » : donne le
    contexte à vérifier pour un suivi — ses ressources (dépôts, dossiers,
    documents) avec leurs chemins/branches, et ses exigences (chapitres,
    tâches, échéances). N'inspecte RIEN elle-même.

    Après cet appel, inspecte réellement avec tes outils habituels —
    `local_list_directory`, `local_read_file`, `local_grep` pour les
    fichiers/dossiers, `git_status`/`git_log`/`git_diff` pour un dépôt Git —
    **en lecture seule : n'exécute aucune commande qui modifie ou lance du
    code récupéré depuis un dépôt juste pour inspecter son avancement**
    (une vraie exécution de tests passe par `shell_run`, avec sa
    confirmation normale, à part, si l'utilisateur la demande vraiment).
    Distingue dans ta réponse ce que tu as lu (inspection), ce que tu as
    exécuté s'il y a lieu (tests), et ce que tu en déduis (hypothèse) — la
    présence d'un fichier ne prouve pas qu'une fonctionnalité marche.

    Termine TOUJOURS par `etude_enregistrer_verification` pour garder une
    trace datée de ce que tu as trouvé.

    Mots-clés : vérifier avancement, état du projet, où en est le dépôt,
    vérifier le rendu, comparer au sujet.

    **Args:**
        - `suivi_id` (str)

    **Returns:**
        - Contexte Markdown : ressources à inspecter, exigences à comparer.
    """
    from .store import obtenir_suivi, obtenir_ressource

    s = obtenir_suivi(suivi_id)
    if s is None:
        return f"Suivi introuvable : {suivi_id}"

    lignes = [f"# Contexte de vérification — {s['titre']}"]

    lignes.append("\n**Ressources à inspecter :**")
    if not s["ressources"]:
        lignes.append("_Aucune ressource associée — rien à inspecter. "
                       "Associe-en avec `etude_associer_ressource` d'abord._")
    for rid in s["ressources"]:
        r = obtenir_ressource(rid)
        if r is None:
            continue
        if not r["accessible"]:
            lignes.append(f"- ⚠️ **{r['nom']}** (`{r['id']}`) marquée inaccessible : "
                           f"{r['message_erreur']} — à confirmer avant d'aller plus loin.")
            continue
        detail = f", branche {r['branche']}, commit {r['commit']}" if r["type"] == "depot_git" else ""
        lignes.append(f"- [{r['type']}] **{r['nom']}** (`{r['id']}`) — `{r['chemin']}`{detail}")

    exigences = []
    for e in s["echeances"]:
        exigences.extend(e.get("chapitres") or [])
    for t in s["taches"]:
        exigences.append(t["titre"])
    if exigences:
        lignes.append("\n**Exigences à comparer (chapitres des échéances, tâches) :**")
        for ex in exigences:
            lignes.append(f"- {ex}")
    else:
        lignes.append("\n**Exigences :** aucune tâche ni chapitre enregistré pour ce suivi — "
                       "demande à l'utilisateur ce qui doit être couvert plutôt que de l'inventer.")

    if s["description"]:
        lignes.append(f"\n**Description du suivi :** {s['description']}")

    return "\n".join(lignes)


@tool("etude_enregistrer_verification")
def etude_enregistrer_verification(
    suivi_id: str, ressources_inspectees: list[str], elements_presents: list[str],
    exigences_couvertes: list[str], elements_manquants: list[str],
    points_non_verifiables: list[str], preuves: list[str], texte: str,
) -> str:
    """
    Deuxième étape : consigne le résultat d'une vérification que tu viens de
    faire (après `etude_contexte_verification` et une inspection réelle avec
    tes outils). Reste factuel — ce que tu consignes ici est gardé tel quel
    et montré à l'utilisateur comme une PROPOSITION de constat, pas une
    vérité appliquée automatiquement (aucun statut d'exercice/tâche n'est
    changé par cet appel : fais-le toi-même séparément avec
    `etude_maj_exercice`/`etude_maj_tache` si tu es sûr, ou propose-le à
    l'utilisateur).

    **Args:**
        - `suivi_id` (str)
        - `ressources_inspectees` (list[str]) : ids des ressources
          réellement regardées
        - `elements_presents` (list[str]) : ce qui existe concrètement
          (fichiers, modules, fonctions trouvés)
        - `exigences_couvertes` (list[str]) : parmi les chapitres/tâches du
          suivi, ceux qui semblent couverts
        - `elements_manquants` (list[str]) : ce qui semble absent
        - `points_non_verifiables` (list[str]) : ce que tu n'as pas pu
          vérifier (accès refusé, dépôt distant non cloné, ambiguïté) —
          jamais classé comme "manquant" par défaut
        - `preuves` (list[str]) : chemins, commits, extraits à l'appui de
          chaque constat
        - `texte` (str) : résumé en quelques phrases, qui distingue
          explicitement inspection / tests exécutés / hypothèses

    **Returns:**
        - Confirmation avec l'identifiant de la vérification enregistrée.
    """
    from .store import ajouter_verification

    v = ajouter_verification(suivi_id, ressources_inspectees, elements_presents,
                              exigences_couvertes, elements_manquants,
                              points_non_verifiables, preuves, texte)
    if v is None:
        return f"Suivi introuvable : {suivi_id}"
    return (f"Vérification enregistrée : {len(exigences_couvertes)} exigence(s) couverte(s), "
            f"{len(elements_manquants)} manquante(s), {len(points_non_verifiables)} non "
            f"vérifiable(s).\nID : `{v['id']}`")
