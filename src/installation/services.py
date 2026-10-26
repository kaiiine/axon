"""Les intégrations configurables, décrites comme des données.

Un service simple n'est qu'un titre, des explications et des clés du `.env` ;
les quelques services qui font plus (connexion Ollama, fichier OAuth Google,
dossier de projets, MCP) ajoutent une action `apres` ou un statut à eux.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.infra import chemins
from src.installation import console as c
from src.installation import systeme
from src.installation.fichier_env import FichierEnv

_FICHIER_OAUTH = "gcp-oauth.keys.json"


@dataclass(frozen=True)
class Contexte:
    racine: Path
    env: FichierEnv


@dataclass(frozen=True)
class Champ:
    cle: str
    libelle: str
    format: str


@dataclass(frozen=True)
class Service:
    titre: str
    menu: str
    statut: str
    explications: tuple[str, ...] = ()
    champs: tuple[Champ, ...] = ()
    apres: Callable[[Contexte], None] | None = None
    configure: Callable[[Contexte], bool] | None = None
    #: Le détail affiché dans le statut quand le service est configuré.
    resume: Callable[[Contexte], str] | None = None
    etapes: tuple[str, ...] = ()

    def est_configure(self, ctx: Contexte) -> bool:
        if self.configure is not None:
            return self.configure(ctx)
        return all(ctx.env.renseignee(champ.cle) for champ in self.champs)

    def configurer(self, ctx: Contexte) -> None:
        c.etape(self.titre)
        for ligne in self.explications:
            c.detail(ligne)
        if self.etapes:
            c.detail()
            c.titre("Étapes :")
            for i, ligne in enumerate(self.etapes, 1):
                c.detail(f"{i}. {ligne}")
        for champ in self.champs:
            demander_cle(ctx.env, champ)
        if self.apres is not None:
            self.apres(ctx)


def demander_cle(env: FichierEnv, champ: Champ) -> None:
    """Propose de garder la valeur actuelle ; une saisie vide ne l'efface pas."""
    actuelle = env.lire(champ.cle)
    print()
    c.titre(champ.libelle)
    c.detail(champ.format)
    if env.renseignee(champ.cle):
        c.detail(f"Valeur actuelle : {actuelle[:12]}…  (Entrée pour conserver)")
    saisie = c.demander("")
    if saisie:
        env.ecrire(champ.cle, saisie)
        c.ok(f"{champ.cle} enregistré")
    elif actuelle:
        c.ok(f"{champ.cle} conservé")
    else:
        c.alerte(f"{champ.cle} ignoré")


def configurer_identite(env: FichierEnv) -> None:
    c.etape("Ton identité")
    c.detail("Ton prénom ou alias sera utilisé par Axon pour te répondre personnellement.")
    actuelle = env.lire("USER_NAME")
    print()
    if env.renseignee("USER_NAME"):
        c.detail(f"Valeur actuelle : {actuelle}  (Entrée pour conserver)")
    saisie = c.demander("Ton prénom / alias : ")
    if saisie:
        env.ecrire("USER_NAME", saisie)
        c.ok(f"Bonjour, {saisie} !")
    elif env.renseignee("USER_NAME"):
        c.ok(f"Conservé : {actuelle}")
    else:
        c.alerte("USER_NAME ignoré — modifiable dans .env")


# ── Actions particulières ────────────────────────────────────────────────────

def _connexion_ollama(_ctx: Contexte) -> None:
    print()
    c.titre("Veux-tu aussi te connecter via la CLI Ollama ? (ollama signin)")
    c.detail("Utile si tu utilises des modèles cloud sans clé API.")
    if not c.oui("Se connecter"):
        return
    if not systeme.commande("ollama"):
        c.alerte("La CLI Ollama n'est pas installée.")
        c.detail(systeme.comment_installer_ollama())
        if not (c.oui("Lancer l'installation maintenant") and systeme.installer_ollama()
                and systeme.commande("ollama")):
            c.alerte("Connexion ignorée. Installe Ollama puis relance la configuration.")
            return
        c.ok("Ollama CLI installée.")
    c.info("Déconnexion préalable (ollama logout)...")
    systeme.lancer(["ollama", "logout"])
    c.info("Connexion à Ollama (ollama signin)...")
    if systeme.lancer(["ollama", "signin"]):
        c.ok("Connecté à Ollama Cloud.")
    else:
        c.alerte("Connexion échouée. Vérifie tes identifiants et réessaie.")


def _fichier_oauth(ctx: Contexte) -> None:
    cible = ctx.racine / _FICHIER_OAUTH
    print()
    if cible.exists():
        c.ok(f"{_FICHIER_OAUTH} déjà présent")
        c.detail("Le navigateur s'ouvrira au premier lancement pour l'autorisation OAuth.")
        return
    c.alerte(f"{_FICHIER_OAUTH} absent")
    source = Path(c.demander("Chemin vers ton fichier OAuth2 JSON (Entrée pour ignorer) : ", "?")).expanduser()
    if source.is_file():
        cible.write_bytes(source.read_bytes())
        c.ok(f"{_FICHIER_OAUTH} copié")
    else:
        c.alerte("Google Services non configurés — à faire manuellement")


def _dossier_projets(ctx: Contexte) -> None:
    actuel = ctx.env.lire("PROJECTS_DIR")
    if actuel:
        c.detail(f"Valeur actuelle : {actuel}")
    choisi = systeme.choisir_dossier("Sélectionne ton dossier de projets", actuel or str(Path.home()))
    if not choisi:
        choisi = c.demander("Chemin vers ton dossier de projets (Entrée pour ignorer) : ", "?")
    dossier = Path(choisi).expanduser() if choisi else None
    if dossier and dossier.is_dir():
        ctx.env.ecrire("PROJECTS_DIR", str(dossier))
        c.ok(f"PROJECTS_DIR → {dossier}")
    else:
        ctx.env.ecrire("PROJECTS_DIR", "")
        c.alerte("Non configuré — l'IA cherchera depuis ton dossier personnel")


_SERVEUR_BLENDER = {
    "transport": "stdio",
    "command": "uvx",
    "args": ["--python", "3.11", "blender-mcp"],
    "env": {
        "BLENDER_HOST": "localhost",
        "BLENDER_PORT": "9876",
        "DISABLE_TELEMETRY": "true",
        "UV_PYTHON_PREFERENCE": "only-managed",
    },
    "enabled": True,
    "timeouts": {"connect_s": 15, "list_tools_s": 15, "call_s": 90},
    "tool_timeouts": {"execute_blender_code": 180},
    "reconnect": {"max_retries": 5, "backoff_s": 2, "backoff_factor": 2},
    "health": {
        "probe_tool": "get_scene_info",
        "failure_patterns": ["Could not connect to Blender", "Make sure the Blender addon is running"],
        "consecutive_failures_to_degrade": 3,
    },
    "capabilities_hint": ("Blender, 3D modeling, mesh manipulation, materials, geometry, animation, "
                          "camera, lighting, rendering, scene editing, GLB export, Python bpy"),
    "risk_overrides": {"execute_blender_code": "execute"},
}


def nombre_serveurs_mcp() -> int:
    try:
        return len(json.loads(chemins.serveurs_mcp().read_text(encoding="utf-8")).get("servers", {}))
    except (OSError, ValueError, AttributeError):
        return 0


def declarer_blender(chemin: Path) -> bool:
    """Ajoute le serveur sans toucher aux autres. Faux s'il était déjà déclaré."""
    donnees = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    serveurs = donnees.setdefault("servers", {})
    if "blender" in serveurs:
        return False
    serveurs["blender"] = _SERVEUR_BLENDER
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(donnees, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _mcp(_ctx: Contexte) -> None:
    print()
    uvx = systeme.commande("uvx")
    if uvx:
        c.ok(f"uvx présent  → {uvx}")
    else:
        c.alerte("uvx introuvable — nécessaire pour lancer les serveurs MCP distribués par uv")
        c.detail("Installeur officiel (pas pip install uv : la commande uvx peut ne pas être créée).")
        if c.oui("Installer uv maintenant", defaut=True):
            systeme.installer_uv()
            uvx = systeme.commande("uvx")
            if uvx:
                c.ok(f"uvx installé → {uvx}")
            else:
                c.alerte("uvx toujours introuvable — ouvre un nouveau terminal puis relance")

    configuration = chemins.serveurs_mcp()
    print()
    c.titre("Serveur Blender")
    c.detail("Modélisation 3D, matériaux, animation, rendu, export GLB.")
    if c.oui(f"Déclarer le serveur blender dans {configuration}", defaut=True):
        try:
            ajoute = declarer_blender(configuration)
        except (OSError, ValueError):
            c.alerte(f"Écriture de {configuration} impossible")
        else:
            c.ok(f"blender déclaré dans {configuration}" if ajoute
                 else "blender déjà déclaré — configuration existante conservée")

    print()
    c.titre("Addon Blender  (côté Blender, une seule fois)")
    if systeme.commande("blender"):
        c.ok("Blender présent")
    else:
        c.alerte("Blender introuvable dans le PATH — installe-le avant d'utiliser ce serveur")
    addon = systeme.dossier_telechargements() / "addon.py"
    if c.oui(f"Télécharger l'addon vers {addon}", defaut=True):
        if systeme.telecharger("https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py", addon):
            c.ok(f"addon.py téléchargé → {addon}")
        else:
            c.alerte("Téléchargement échoué — récupère addon.py sur github.com/ahujasid/blender-mcp")
    for ligne in ("Dans Blender :",
                  "  1. Edit > Preferences > Add-ons > Install… > choisir addon.py",
                  "  2. Cocher « Interface: Blender MCP »",
                  "  3. Vue 3D > touche N > onglet BlenderMCP > bouton de connexion",
                  "  Blender doit tourner en mode GRAPHIQUE (jamais -b/--background) :",
                  "  l'addon exécute les commandes via la boucle principale."):
        c.detail(ligne)

    print()
    c.titre("Sketchfab  (optionnel — import de modèles 3D existants)")
    for ligne in ("La clé est lue par BLENDER, pas par Axon : elle ne va pas dans .env.",
                  "L'addon la cherche dans ses préférences, puis la scène, puis la variable",
                  "d'environnement BLENDERMCP_SKETCHFAB_API_KEY — la dernière est la plus sûre :",
                  "elle ne transite jamais par le contexte du modèle."):
        c.detail(ligne)
    if systeme.variable_exportee("BLENDERMCP_SKETCHFAB_API_KEY"):
        c.ok("BLENDERMCP_SKETCHFAB_API_KEY déjà exportée")
    else:
        cle = c.demander("Clé API Sketchfab (Entrée pour ignorer) : ", "?")
        if cle:
            ou = systeme.exporter_variable("BLENDERMCP_SKETCHFAB_API_KEY", cle,
                                           "blender-mcp — lue par Blender, pas par Axon")
            c.ok(f"Clé enregistrée dans {ou} — relance Blender depuis un nouveau terminal")
        else:
            c.info("Ignoré — l'import Sketchfab restera indisponible")
    c.detail("Puis dans Blender : onglet BlenderMCP > cocher « Use Sketchfab ».")
    c.detail("Sans cette case, l'addon n'enregistre pas les commandes Sketchfab et")
    c.detail("répond « Unknown command type » — le serveur MCP les annonce pourtant.")

    print()
    c.info("Vérification : lance Axon puis /mcp test blender")
    c.detail("Si « command resolved » est vide, le PATH d'Axon diffère de ce terminal :")
    c.detail(f"remplace \"command\": \"uvx\" par le chemin absolu dans {configuration}.")


# ── Le catalogue, dans l'ordre du menu ───────────────────────────────────────

SERVICES: tuple[Service, ...] = (
    Service(
        "Tavily — Recherche web", "Tavily       (recherche web — recommandé)", "Tavily    (recherche web)",
        ("Tavily permet la recherche web. Requis pour le tool web_research_report.",
         "Créer un compte gratuit → https://app.tavily.com", "Settings → API Keys → Copy"),
        (Champ("TAVILY_API_KEY", "Clé API Tavily", "Format : tvly-xxxxxxxxxxxxxxxxxxxx"),)),
    Service(
        "Google Gemini — Backend LLM gratuit (1M tokens de contexte)",
        "Gemini       (LLM gratuit — 1M tokens — recommandé)", "Gemini    (LLM gratuit — recommandé)",
        ("Gemini 2.5 Flash est gratuit avec 15 req/min et 1 500 req/jour.",
         "C'est le backend recommandé si tu veux éviter les quotas Groq/Ollama."),
        (Champ("GEMINI_API_KEY", "Clé API Gemini", "Format : AIzaSy..."),),
        etapes=("Aller sur https://aistudio.google.com/apikey", "Cliquer sur 'Create API key'",
                "Copier la clé générée")),
    Service(
        "Groq — Backend LLM cloud rapide", "Groq         (LLM cloud rapide)", "Groq      (LLM cloud)",
        ("Groq donne accès à LLaMA, Qwen, DeepSeek avec une latence très faible.",
         "Créer un compte → https://console.groq.com", "API Keys → Create API Key → Copy"),
        (Champ("GROQ_API_KEY", "Clé API Groq", "Format : gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"),)),
    Service(
        "Ollama Cloud — Backend cloud (optionnel)", "Ollama Cloud (optionnel)", "Ollama Cloud (optionnel)",
        ("Permet d'utiliser des modèles cloud via Ollama (ex: kimi-k2, qwen3-next).",
         "Compte Ollama → https://ollama.com/settings/api-keys"),
        (Champ("OLLAMA_API_KEY", "Clé API Ollama Cloud",
               "Format : ollama_xxxx  (laisser vide si tu utilises ollama signin)"),),
        apres=_connexion_ollama),
    Service(
        "NVIDIA — Backend LLM cloud (NIM)", "NVIDIA       (LLM cloud NIM)", "NVIDIA    (LLM cloud NIM)",
        ("NVIDIA NIM donne accès à des modèles hébergés (Llama, DeepSeek, Nemotron…).",
         "Créer un compte → https://build.nvidia.com", "Choisir un modèle → « Get API Key » → Copy",
         "Modèle utilisé : réglable dans configs/base.yaml (nvidia.model) ou /model dans Axon."),
        (Champ("NVIDIA_API_KEY", "Clé API NVIDIA", "Format : nvapi-xxxxxxxxxxxxxxxxxxxx"),)),
    Service(
        "Mistral — Backend LLM européen", "Mistral      (LLM européen · Codestral pour le code)",
        "Mistral   (LLM européen · Codestral)",
        ("Mistral fournit les modèles Mistral et Codestral (spécialisé code).",
         "Créer un compte → https://console.mistral.ai", "API Keys → Create new key → Copy"),
        (Champ("MISTRAL_API_KEY", "Clé API Mistral", "Format : xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),)),
    Service(
        "Slack — Intégration workspace", "Slack", "Slack",
        ("Permet de lire les canaux, DMs, mentions et d'envoyer des messages.",),
        (Champ("SLACK_USER_TOKEN", "User Token Slack",
               "Format : xoxp-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxx"),),
        etapes=("Aller sur https://api.slack.com/apps", "Créer une nouvelle app → From scratch",
                "OAuth & Permissions → User Token Scopes, ajouter : channels:read channels:history "
                "groups:read groups:history im:read im:history im:write mpim:read mpim:history "
                "mpim:write users:read search:read chat:write",
                "Install to Workspace → Copy User OAuth Token")),
    Service(
        "Google — Gmail · Calendar · Drive · Docs · Slides",
        "Google       (Gmail · Calendar · Drive · Docs · Slides)",
        "Google    (Gmail · Calendar · Drive · Docs · Slides)",
        ("Utilise OAuth2 via un fichier de credentials (pas une clé API).",
         "Le token est sauvegardé automatiquement à ~/.ai-agent/google_token.pickle."),
        apres=_fichier_oauth,
        configure=lambda ctx: (ctx.racine / _FICHIER_OAUTH).exists(),
        etapes=("Aller sur https://console.cloud.google.com",
                "Créer un projet (ou en sélectionner un existant)",
                "APIs & Services → Enable APIs : Gmail, Calendar, Drive, Docs, Slides, Sheets",
                "APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID → Desktop App",
                f"Download JSON → renommer en {_FICHIER_OAUTH}",
                f"Placer {_FICHIER_OAUTH} à la racine du projet")),
    Service(
        "Jira — Gestion de projet", "Jira         (gestion de tickets et projets)",
        "Jira      (gestion de projet)",
        ("Permet de lire, créer et gérer les tickets de tes projets Jira.",),
        (Champ("JIRA_URL", "URL Jira", "Format : https://ton-domaine.atlassian.net"),
         Champ("JIRA_EMAIL", "Email Atlassian", "Email de ton compte Atlassian"),
         Champ("JIRA_API_KEY", "Clé API Jira", "Format : ATATT3x...")),
        etapes=("Aller sur https://id.atlassian.com/manage-profile/security/api-tokens",
                "Create API token → copier la clé",
                "Ton URL Jira = https://ton-domaine.atlassian.net (visible dans la barre d'adresse)")),
    Service(
        "Dossier de projets", "Dossier de projets  (pour que l'IA trouve tes repos plus vite)",
        "Projets",
        ("Indiquer ton dossier racine de projets permet à l'IA de trouver tes repos git plus vite.",
         "Laisser vide → l'IA cherchera depuis ton dossier personnel (fonctionne, juste plus lent)."),
        apres=_dossier_projets,
        configure=lambda ctx: bool(ctx.env.lire("PROJECTS_DIR")),
        resume=lambda ctx: ctx.env.lire("PROJECTS_DIR")),
    Service(
        "API-Football — Value betting (Winamax)", "API-Football (value betting Winamax)",
        "API-Football (value betting Winamax)",
        ("Permet à Axon de calculer de vraies probabilités (Poisson/Elo) sur les",
         "matchs et de les comparer aux cotes Winamax pour détecter un edge réel.",
         "Gratuit : 100 requêtes/jour. Le tier gratuit bloque la saison en cours —",
         "c'est football-data.org qui la couvre, API-Football sert de source",
         "complémentaire (saisons passées, autres compétitions).",
         "Winamax ne demande aucune clé — les cotes sont déjà accessibles."),
        (Champ("API_FOOTBALL_KEY", "Clé API-Football",
               "Format : ta clé depuis le dashboard api-football.com"),),
        etapes=("Aller sur https://www.api-football.com/", "Créer un compte gratuit",
                "Dashboard → copier ta clé API (section 'My Access')")),
    Service(
        "football-data.org — Données saison en cours (value betting)",
        "football-data.org (saison en cours, value betting)", "football-data.org (saison en cours)",
        ("Complète API-Football : couvre la saison EN COURS gratuitement (Ligue 1,",
         "Premier League...), là où le tier gratuit d'API-Football bloque tout.",
         "Gratuit : 10 requêtes/minute, 12 compétitions majeures."),
        (Champ("FOOTBALL_DATA_ORG_KEY", "Clé football-data.org", "Format : ta clé reçue par email"),),
        etapes=("Aller sur https://www.football-data.org/client/register",
                "Créer un compte gratuit (aucune carte bancaire demandée)",
                "La clé API arrive par email — la copier ici")),
    Service(
        "MCP — serveurs d'outils externes", "MCP          (serveurs d'outils externes — Blender, etc.)",
        "MCP",
        ("Axon peut consommer des serveurs MCP tiers (Blender, filesystem, GitHub…).",
         "Ajouter une capacité = une ligne de configuration, aucun code à écrire.",
         "Gestion dans Axon : /mcp list · add · test · tools · refresh · restart"),
        apres=_mcp,
        configure=lambda _ctx: nombre_serveurs_mcp() > 0,
        resume=lambda _ctx: f"{nombre_serveurs_mcp()} serveur(s) déclaré(s) · /mcp list dans Axon"),
)
