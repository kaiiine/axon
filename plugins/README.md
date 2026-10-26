# Plugins Axon

Un plugin étend Axon sans toucher à son code : un dépôt git (ou un sous-dossier
de dépôt) qui porte un `plugin.json`. Il s'installe dans `~/.axon/plugins/<id>`
et le cœur ne le connaît que par les **capacités** qu'il déclare.

```
/plugin                       la marketplace : choisir un plugin dans la liste
/plugin list                  le catalogue et ce qui est installé
/plugin install <id|url|dossier> [--ref <branche>] [--dossier <sous-dossier>]
/plugin update [id]           réinstalle depuis la même source
/plugin remove <id>           désinstalle
```

## Le catalogue

`catalogue.json` (ici, versionné avec Axon) liste les plugins proposés. Pour
ajouter les tiens sans modifier Axon, crée `~/.axon/plugins/catalogue.json` au
même format ; il l'emporte pour un même identifiant.

```json
{
  "plugins": [
    {
      "id": "mon-plugin",
      "nom": "Mon plugin",
      "description": "Ce qu'il apporte, en une ligne",
      "source": { "git": "https://github.com/moi/mon-plugin.git", "ref": "main", "dossier": "" }
    }
  ]
}
```

`dossier` désigne un sous-dossier quand le plugin vit dans un dépôt plus large ;
une source peut aussi être `"local": "/chemin/vers/le/dossier"`.

## Le contrat : `plugin.json`

```json
{
  "id": "mon-plugin",
  "name": "Mon plugin",
  "version": "1.0.0",
  "description": "…",
  "capacites": ["notifications"],
  "platforms": {
    "linux-wayland": {
      "entrypoint": "lancer.sh",
      "toggle": "basculer.sh",
      "commandes": ["npm"],
      "installation": [["npm", "ci"], ["npm", "run", "build"]]
    },
    "macos":   { "commandes": ["npm"], "installation": [["npm", "ci"]] },
    "windows": { "commandes": ["npm"], "installation": [["npm", "ci"]] }
  }
}
```

| Champ | Rôle |
|---|---|
| `id` | minuscules, chiffres, tirets ; nom du dossier d'installation |
| `capacites` | ce que le cœur active quand le plugin est installé (ci-dessous) |
| `platforms` | `linux-wayland`, `linux`, `macos`, `windows` ; un système absent = non pris en charge |
| `commandes` | programmes requis, vérifiés avant toute étape |
| `installation` | étapes, chacune une **liste d'arguments** — jamais une ligne de shell |
| `entrypoint`, `toggle` | fichiers du plugin, indiqués à l'utilisateur après l'installation |

Capacités reconnues par cette version d'Axon :

| Capacité | Effet |
|---|---|
| `ile` | la session CLI se connecte au canal `overlay` (demandes, réponses en direct) |
| `notifications` | les rappels du démon passent par le canal `controle` avant la notification système |

Une capacité inconnue fait refuser le plugin : il demande une version d'Axon
plus récente, au lieu de rester sans effet en silence. Les canaux sont décrits
dans `src/infra/canal_overlay.py`.

## Sécurité

Les étapes d'installation exécutent le code du dépôt : Axon les affiche en
clair et ne les lance qu'après confirmation. Tout se prépare dans
`~/.axon/plugins/.travail` ; la version installée n'est remplacée qu'à la fin,
et reste en place si une étape échoue.
