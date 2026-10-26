# Axon Overlay — Svelte + TypeScript

Migration de ton archive. Tout le code reste dans `axon-overlay` : GTK, pont, composants, SVG, build et scripts. Le front compilé est inclus ; Node.js n’est pas nécessaire pour lancer l’overlay.

## Installation

Depuis le dossier décompressé `axon-overlay` :

```bash
python3 installer.py --root ~/Documents/projets-perso/ai-agent
```

Destination : `~/Documents/projets-perso/ai-agent/.axon/plugins/axon-overlay`. Adapte `--root` à la racine réelle de ton projet. Avec `--root ~`, la destination est `~/.axon/plugins/axon-overlay`.

Un plugin déjà installé avec le même manifeste est sauvegardé à côté avant remplacement. Un dossier inconnu est laissé intact et l’installation s’arrête. L’installateur ne modifie ni le cœur Axon, ni Hyprland, ni Waybar.

Arrête l’ancien processus overlay, puis depuis le dossier installé :

```bash
sh lancer.sh
```

Dans un autre terminal, ouvre ou ferme l’îlot :

```bash
sh waybar-toggle.sh
```

Le lanceur garde l’îlot fermé jusqu’à une bascule ou une demande de l’agent. La bascule attend le gestionnaire de signal : le délai fixe de démarrage a été supprimé.

Dépendances natives inchangées : Python système, PyGObject, GTK4, gtk4-layer-shell et WebKitGTK 6. Sur Arch : `python-gobject gtk4 gtk4-layer-shell webkitgtk-6.0`. Le chemin de la bibliothèque layer-shell est configurable avec `AXON_LAYER_SHELL_LIB`.

## Aperçu

Ouvre `ui/apercu.html` dans ton navigateur. C’est le même build Svelte que GTK, avec une session fictive. Clique sur la carte pour voir le diff ou sur la bulle pour ouvrir le chat. Les SVG originaux sont conservés. Les intégrations externes restent explicitement non connectées.

## Correction des flashs

- Racine, vues et mascotte restent montées ; les événements ne reconstruisent plus tout l’affichage.
- Expressions préchargées, puis transition d’opacité entre images persistantes. Aucun changement de `src` sur le SVG courant.
- Suppression de l’introduction centre/dashboard, de ses temporisations concurrentes et de l’animation d’apparition de l’îlot entier. Les mouvements propres aux SVG restent présents.
- Fermeture et réouverture conservent vue, chat et brouillon.
- Une seule navigation WebKit pour toute la vie du processus. GTK attend le signal `pret`, envoyé après montage Svelte et décodage des images, avant de présenter la fenêtre. Les événements précoces sont conservés.
- Une fermeture gagne sur les callbacks d’ouverture tardifs.
- Redimensionnement uniquement quand le mode natif change, jamais à chaque frappe ou événement d’activité.

## Rectangle noir et GTK

Le rayon CSS seul ne garantissait pas le découpage du rendu WebKit. `CadreArrondi`, dans `overlay.py`, utilise maintenant `Gtk.Snapshot.push_rounded_clip` autour du contenu WebKit. Les fonds GTK/WebKit sont transparents. Les coins du bas sont découpés à 22 px ; le haut reste droit pour rejoindre la barre.

Tailles centralisées dans `overlay.py` : 680 × 184 pour l’accueil, 680 × 420 pour les vues détaillées. Le redimensionnement natif est direct, sans boucle d’animation d’allocations Wayland. Le comportement réel sur ton pilote NVIDIA reste à vérifier.

Le contournement du sandbox WebKit de ton archive est conservé pour ne pas réintroduire le problème bwrap documenté dans ton lanceur. Il concerne ce front local. Sur une machine compatible, `AXON_WEBKIT_SANDBOX=1 sh lancer.sh` permet de réactiver le sandbox.

## Développement

Node.js 24 LTS recommandé. Versions fixées dans `package-lock.json`.

```bash
npm ci
npm run dev
npm run check
npm test
npm run build
python3 -m unittest discover -s tests -p 'test_*.py'
```

Le serveur ouvre `dev.html`. Ajoute `?demo=1` pour simuler une session. Le build génère les variantes statiques des mascottes et `ui/dist/axon.js` + `axon.css`. Le bundle classique IIFE fonctionne sans chargement de modules ES par `file://`. `ui/index.html` n’est plus qu’un point d’entrée de 11 lignes.

| Fichier | Rôle |
| --- | --- |
| `ui/src/App.svelte` | Structure persistante et navigation |
| `ui/src/components/Mascot.svelte` | Expressions préchargées sans remontage |
| `Header.svelte`, `Overview.svelte` | Barre et cartes compactes |
| `Chat.svelte`, `RequestCard.svelte` | Messages, commandes `/`, réponses humaines |
| `Code.svelte`, `ui/src/diff.ts` | Fichiers et diffs unifiés |
| `Settings.svelte` | Préférences et intégrations |
| `ui/src/model.ts`, `types.ts` | État et protocole typés |
| `ui/src/bridge.ts` | Messages vers Python |
| `overlay.py` | Fenêtre, clipping, readiness et socket |
| `pont_axon.py` | Client Python conservé dans le plugin |
| `installer.py`, `plugin.json` | Installation relogeable et métadonnées |

Les composants de la table sont dans `ui/src/components`. Le socket et le PID restent dans `$XDG_RUNTIME_DIR/axon` : ce sont des données temporaires, pas du code installé ailleurs.

## Protocole conservé

Entrées publiques : `window.axon.recevoir(m)` et `window.axon.ouvrir(ouvert)`. Même socket Unix, JSON par ligne.

Événements entrants : `connexion`, `etat`, `outil`, `message`, `commandes`, `demande`, `annulation`, `fichier`, `diff`. L’ancien `confirmation` est également accepté.

Sorties vers Axon : `commande`, `demander_commandes`, `reponse_demande`. Une demande de plusieurs questions envoie toutes les réponses dans leur ordre, à la fin. Annulation et déconnexion invalident les demandes. Un échec d’envoi conserve le brouillon. Aucune autorisation automatique.

`pret`, `mode`, `ouvrir` restent locaux à `overlay.py`. La démo est effacée au premier événement réel. `integration_axon.py` reste un exemple de branchement, pas un programme autonome. Le cœur peut charger `pont_axon.py` depuis le plugin, sans en copier le code ailleurs.

## Hôtes par système

La page (`ui/`) et le protocole sont communs. Seul l’hôte natif change :

| Système | Hôte | Ouvrir / masquer | Verre |
|---|---|---|---|
| Linux (Wayland) | `overlay.py` (GTK4 + layer-shell) | module Waybar, `waybar-toggle.sh` | flou du compositeur |
| macOS | `src-tauri/` (Tauri 2) | icône de la barre des menus, ⌘⇧Espace | Liquid Glass (macOS 26), flou HUD avant |
| Windows | `src-tauri/` (Tauri 2) | icône de la zone de notification, Ctrl+Maj+Espace | Mica (Windows 11), Acrylic (Windows 10) |

Construire l’hôte Tauri, sur le système visé :

```bash
npm ci
npm run shell:build      # .app / .dmg sous macOS, installeur NSIS / MSI sous Windows
npm run shell:dev        # lancer sans empaqueter
```

Prérequis : Rust stable ; Xcode Command Line Tools (macOS) ; Visual Studio Build Tools et WebView2 (Windows, fourni avec Windows 11). Les icônes se régénèrent avec `npm run shell:icones`.

Les deux canaux (`overlay` pour la session CLI, `controle` pour les rappels et la bascule) suivent le même contrat sur tous les systèmes — voir `src/infra/canal_overlay.py` dans le cœur : socket Unix sous Linux et macOS, TCP local à jeton sous Windows.

Le démon des rappels se lance avec la session : `ops/systemd/axon-cron.service` (Linux), `ops/launchd/installer-rappels.sh` (macOS), `ops/windows/installer-rappels.ps1` (Windows).

L’hôte Tauri est compilé et testé sous Linux (canaux, page, rappels) ; ses parties propres à macOS et Windows — verre, barre système, raccourci, position sous la barre — restent à valider sur ces systèmes.

## Marketplace

Le dossier est autonome et relogeable dans `.axon/plugins/axon-overlay`. `plugin.json` décrit, par système, l’hôte, son lanceur ou son paquet, et ses dépendances. Le contrat du chargeur marketplace du cœur reste à définir : ce manifeste est la convention locale à y raccorder.

## Vérifications

- Svelte/TypeScript : zéro erreur et zéro avertissement.
- Build de production compilé et inclus.
- 9 tests front : protocole, questions multiples, déconnexion, échec d’envoi, diff et conservation des nœuds DOM sur 20 mises à jour successives.
- 7 tests Python : ouverture différée, événement en attente, ancien callback, redimensionnement, chargement unique, installation et sauvegarde.
- Syntaxe Python et shell vérifiée.

Les tests natifs utilisent des doublures de GTK. Le rendu GPU, les frames réelles, le clipping et le résultat visuel dans Hyprland n’ont pas pu être vérifiés ici. Les causes de réinitialisation identifiées sont supprimées ; la validation sur ton pilote reste nécessaire.
