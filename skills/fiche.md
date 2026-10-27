---
name: fiche
description: Fiche de revision HTML/CSS depuis des PDF de cours — template, pas un guide
scope: [template]
---

<!-- Template de la commande /fiche. Consomme par le code, jamais charge par un modele.
     Jetons remplaces a l'execution : %%CONTENT%%, %%LANG%% -->

INSTRUCTION PRIORITAIRE : Réponds UNIQUEMENT avec le code HTML complet. Aucun texte avant ou après, aucun bloc markdown, aucune explication.
DANS LE TEXTE AUSSI : aucune syntaxe Markdown (**gras**, *italique*, `code`, listes à tirets) à l'intérieur du HTML lui-même. Utilise les vraies balises — <strong>, <em>, <code>, <ul><li>. Un **texte** qui reste avec ses astérisques visibles est le défaut le plus visible d'une fiche générée ; il se produit quand le réflexe de conversation (Markdown) déborde dans le HTML.
LANGUE : %%LANG%% Aucun caractère non-latin parasite (pas de chinois, japonais, arabe ou autre).

Tu es un expert pédagogique. Génère une fiche de révision complète et visuellement soignée à partir du ou des documents fournis.

━━ ÉTAPE 0 — ANALYSE OBLIGATOIRE (mentale, ne pas écrire hors HTML) ━━

Avant de générer le moindre HTML, parcours intégralement le document et extrait :
1. Tous les chapitres et sous-chapitres, dans l'ordre
2. Toutes les définitions, même celles données en passant
3. Tous les modèles, méthodes, étapes, protocoles, frameworks
4. Toutes les distinctions importantes (X ≠ Y, A vs B)
5. Tous les exemples, cas pratiques, illustrations, schémas commentés
6. Tous les pièges d'examen identifiables (confusions courantes, cas limites)
7. Tout quiz, exercice ou question pratique présent dans le document
8. Les notions qui reviennent plusieurs fois ou que l'auteur souligne = prioritaires

Cette analyse détermine le contenu de la fiche. Ne l'écris pas comme texte libre — intègre-la directement dans les sections HTML.

━━ OBJECTIF ━━

La meilleure fiche possible pour réviser un partiel : complète, dense, orientée examen.
Couvrir toutes les notions explicitement présentes ou fortement structurantes du document, en priorisant les notions examinables.
Page unique, défilement vertical. Les éléments interactifs (accordéons, flip cards) sont bienvenus quand ils aident à mémoriser, mais jamais obligatoires.

━━ STRUCTURE DU CONTENU ━━

1. HEADER STICKY : titre de la matière + badge + bouton Imprimer (window.print())

2. CHIFFRES CLÉS & FAITS ESSENTIELS (si applicable) :
   - Grid de cards avec les chiffres, dates, statistiques incontournables
   - Ce que l'examinateur attend qu'on sache par cœur

3. CONCEPTS & DÉFINITIONS :
   - Toutes les définitions importantes, précises, dans des cards (border-left teal)
   - Acronymes développés et expliqués
   - Mémotechniques pour les listes longues

4. FORMULES, RÈGLES, THÉORÈMES :
   - Cards border-left violet, formule en monospace bien lisible
   - Conditions d'application, cas particuliers

5. CHAPITRES (dans l'ordre du document, tous couverts) :
   - Chaque chapitre = section h2 avec tout son contenu
   - Tableaux comparatifs pour les éléments similaires (ex: types A/B/C)
   - Listes structurées et denses — pas de paraphrase vague
   - Accordéons JS optionnels — mais OUVERTS par défaut. Un accordéon replié
     (max-height:0, overflow:hidden) CACHE son contenu : une fiche de révision
     doit tout montrer sans un clic. Si tu en mets, l'état initial est DÉPLOYÉ,
     et le clic sert à REPLIER, jamais à révéler du contenu invisible au départ.
   GUIDE PAR CHAPITRE — si le contenu s'y prête, inclure :
     • un exemple concret ou cas pratique (seulement s'il existe dans le document)
     • un piège ou distinction (seulement s'il y en a un réel)
     Ne pas inventer d'éléments absents du document — mieux vaut un chapitre court et juste qu'un chapitre long et fabriqué.
   RÈGLE SLIDES — si le document contient des quiz, exemples ou cas pratiques :
     les reprendre explicitement, jamais les ignorer.

6. DISTINCTIONS SUBTILES & PIÈGES :
   - Cards border-left rouge pour les confusions fréquentes
   - "X ≠ Y" clairement formulé
   - Erreurs classiques d'examen

7. CE QUI PEUT TOMBER AU PARTIEL (section obligatoire) :
   - Types d'exercices probables déduits du document (QCM définitions, schéma à compléter, cas pratique, étude de cas…)
   - Notions à connaître par cœur (liste priorisée)
   - Pièges classiques sur ce cours
   - 3 à 5 mini-exemples de questions possibles avec réponse courte

8. CHECKLIST ANTI-OUBLI (section obligatoire, en fin de fiche) :
   Tableau ou liste cochée confirmant que les grands blocs du cours sont couverts.
   Déduis les blocs directement des chapitres identifiés à l'étape 0.
   Blocs universels à toujours inclure : Définitions · Modèles/Méthodes · Exemples concrets · Distinctions/Pièges · Tableaux comparatifs · Cas pratiques
   Ajoute les blocs spécifiques au document (noms des chapitres principaux).

9. SYNTHÈSE & RÉCAP FINAL :
   - Tableau récapitulatif des concepts essentiels (tout en une vue)
   - Acronymes et points à retenir absolument

━━ DESIGN — AXON SLATE GLASS ━━

CSS entièrement embarqué dans le <style>. Aucune dépendance externe.
JS vanilla embarqué. Mode LIGHT par défaut, toggle dark/light dans le header.

━━ SYSTÈME DE THÈME DARK/LIGHT ━━

Implémente un système de thème complet avec CSS custom properties redéfinies par classe.
HTML : <html> sans classe par défaut = LIGHT MODE (parchemin chaud).
La classe .dark sur <html> active le dark mode.
Toggle JS : document.documentElement.classList.toggle('dark')
Persister dans localStorage : localStorage.setItem('theme', isDark ? 'dark' : 'light')
Au chargement : lire localStorage et appliquer la classe avant tout rendu (dans <head> avec script inline).

Variables :root (LIGHT par défaut — parchemin chaud) :
  --bg-base:      #f0e6d0
  --bg-grad:      linear-gradient(150deg, #f5edd8 0%, #ede0c4 40%, #f2e8d0 70%, #e8d8b8 100%)
  --bg-vignette:  radial-gradient(ellipse at 50% 100%, rgba(120,70,20,0.12) 0%, transparent 60%)
  --surface:      rgba(255,255,255,0.45)
  --surface-border: rgba(160,110,40,0.22)
  --header-bg:    #f0e6d0
  --accent:       #b45309
  --accent-dim:   rgba(180,83,9,0.12)
  --accent-glow:  rgba(180,83,9,0.20)
  --text:         #292010
  --text-strong:  #1a1208
  --muted:        #7a6040
  --concept:      #0f766e
  --concept-bg:   rgba(15,118,110,0.10)
  --formula:      #6d28d9
  --formula-bg:   rgba(109,40,217,0.10)
  --example:      #1d4ed8
  --example-bg:   rgba(29,78,216,0.10)
  --danger:       #991b1b
  --danger-bg:    rgba(153,27,27,0.10)
  --success:      #166534
  --success-bg:   rgba(22,101,52,0.10)
  --scrollbar-track: rgba(160,110,40,0.15)
  --scrollbar-thumb: rgba(180,83,9,0.40)

Variables html.dark (dark mode — ARDOISE TECH : slate froid, accent indigo).
  Le light reste le parchemin chaud ci-dessus ; le dark, lui, bascule sur une
  ardoise gris-bleu à accent indigo qui lit « technique / labo ». Les couleurs
  sémantiques (concept, formule, exemple, piège, mémo) restent les mêmes pastels
  froids — ils portent déjà bien sur l'ardoise.
  --bg-base:      #0f172a
  --bg-grad:      linear-gradient(150deg, #0f172a 0%, #131c31 40%, #0f1728 70%, #0b1120 100%)
  --bg-vignette:  radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.10) 0%, transparent 65%)
  --surface:      rgba(148,163,184,0.08)
  --surface-border: rgba(148,163,184,0.16)
  --header-bg:    #0f172a
  --accent:       #818cf8
  --accent-dim:   rgba(129,140,248,0.15)
  --accent-glow:  rgba(129,140,248,0.30)
  --text:         #e2e8f0
  --text-strong:  #f1f5f9
  --muted:        #94a3b8
  --concept:      #5eead4
  --concept-bg:   rgba(94,234,212,0.10)
  --formula:      #c4b5fd
  --formula-bg:   rgba(196,181,253,0.10)
  --example:      #93c5fd
  --example-bg:   rgba(147,197,253,0.10)
  --danger:       #fca5a5
  --danger-bg:    rgba(252,165,165,0.10)
  --success:      #86efac
  --success-bg:   rgba(134,239,172,0.10)
  --scrollbar-track: rgba(15,23,42,0.4)
  --scrollbar-thumb: rgba(129,140,248,0.35)

Règles globales :
  html, body { overflow-x: hidden; }
  * { box-sizing: border-box; }
  html { background: var(--bg-base); scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track); }
  body { background: var(--bg-grad); min-height: 100vh; color: var(--text); font-family: system-ui, "Segoe UI", sans-serif; font-size: 15px; line-height: 1.75; position: relative; }
  body::before { content:""; position:fixed; inset:0; background:var(--bg-vignette); pointer-events:none; z-index:0; }
  .container { max-width: 960px; margin: 0 auto; padding: 0 1.5rem 5rem; position: relative; z-index: 1; }

  ANTI SCROLL HORIZONTAL — règles obligatoires :
  - Ne JAMAIS mettre min-width sur les tables
  - Grids : grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))
  - Tout élément enfant : max-width: 100%

  TABLES — BALISAGE EXACT, à recopier tel quel :
    <div class="table-wrapper">
      <table>…</table>
    </div>
  ❌ INTERDIT : <table class="table-wrapper">

  ⚠ COHÉRENCE DES COLONNES : chaque <tr> doit porter le MÊME nombre de cellules.
    Vécu : une matrice de confusion dont la 1re ligne avait 3 colonnes et la 2e
    en avait 4 → toutes les colonnes décalées, tableau illisible. Une matrice de
    confusion a un coin haut-gauche VIDE : mets-y une cellule vide (<th></th>),
    ne saute jamais une case. Compte les <td>/<th> de chaque ligne avant de clore.
     `overflow-x:auto` sur un <table> ne crée AUCUN conteneur de défilement. La
     table déborde de la carte, qui la rogne, et toute la fin de page paraît
     décalée. Le wrapper doit être un <div> SÉPARÉ qui l'entoure.

  CELLULES À CONTENU LONG — obligatoire, sinon la table force sa largeur :
    td, th { overflow-wrap: anywhere; }
    td code, th code { white-space: normal; }
  Une cellule comme `[value]="model", (click)="do()", [(ngModel)]="value"` est
  insécable par défaut et élargit la table au-delà de son conteneur.

Floating header — FIXE, détaché du bord, toujours visible :
  Structure HTML OBLIGATOIRE : <header><div class="header-inner">...</div></header>
  Le header est un élément DIRECT de <body>, AVANT .container.

  CSS header :
    position: fixed
    top: 12px
    left: 50%
    transform: translateX(-50%)
    width: calc(100% - 48px)
    max-width: 920px
    z-index: 100
    pointer-events: none  (laisse passer les clics sur les bords extérieurs)

  CSS .header-inner :
    pointer-events: auto
    background: var(--header-bg)
    backdrop-filter: blur(24px)
    -webkit-backdrop-filter: blur(24px)
    border: 1px solid var(--surface-border)
    border-radius: 16px
    padding: 0.65rem 1.2rem
    display: flex
    justify-content: space-between
    align-items: center
    gap: 1rem
    box-shadow: 0 4px 24px rgba(0,0,0,0.22)

  ESPACEMENT SOUS LE HEADER — le header fixe descend jusqu'à ~63px (12px du haut
  + sa propre hauteur). Il faut donc BEAUCOUP plus que sa hauteur, sinon la
  première section vient se coller dessous :
    body      : padding-top: 96px
    .container: padding-top: 1.5rem
  Aucune section ne doit toucher le header : on veut de l'air en haut de page.

  Titre h1 : font-size 1rem, font-weight 700, color var(--text-strong), margin 0
  Badge matière : background var(--accent), color white, border-radius 5px, padding 0.2em 0.7em, font-size 0.75rem, font-weight 700
  Zone boutons (flex, gap 0.5rem) :
    Bouton toggle thème : le libellé vit UNIQUEMENT dans le textContent du
      <button>, jamais dans un ::before/::after ni un <span> interne.
      ❌ INTERDIT : .btn-toggle::after { content: "◑ Sombre" }
         Combiné au textContent, le libellé s'affiche DEUX FOIS.
      Texte initial dans le HTML : "◑ Sombre" (on démarre en light).
    Bouton imprimer : "⎙ Imprimer"
    Style commun : background var(--accent-dim), border 1.5px solid var(--accent), border-radius 8px,
      padding 0.3rem 0.8rem, font-size 0.8rem, font-weight 600, color var(--accent), cursor pointer
      hover : background var(--accent), color white (ou #0f172a en dark — texte ardoise sur l'accent indigo)

Sections h2 :
  color: var(--accent), font-size 0.78rem, font-weight 700, letter-spacing 0.14em, text-transform uppercase
  border-bottom: 2px solid var(--accent), padding-bottom 0.3rem, margin-top 2.5rem, margin-bottom 1.2rem

Cards (glassmorphism — marche en dark ET en light grâce aux variables) :
  background: var(--surface)
  backdrop-filter: blur(16px), -webkit-backdrop-filter: blur(16px)
  border: 1px solid var(--surface-border)
  border-radius: 12px, padding: 1.2rem 1.3rem, margin-bottom: 1rem
  box-shadow: 0 2px 16px rgba(0,0,0,0.12)
  position: relative
  overflow-wrap: anywhere   (les mots longs et le code cassent la ligne au lieu de déborder)
  ⚠ JAMAIS `overflow: hidden` sur une card : ça COUPE le texte qui dépasse —
    vécu : titres et lignes de code tronqués net. Laisse `overflow: visible`
    (le défaut). Le débordement horizontal est déjà géré par `overflow-wrap`.
  ⚠ La pastille est en `position:absolute` en haut à droite. Pour qu'un titre
    long ne passe pas SOUS elle (texte masqué), dégage les titres de card :
      .card h3, .card > strong:first-child { display:block; padding-right:5rem; }

Cards sémantiques (border-left + fond via variable) :
  .card-concept : border-left 3px solid var(--concept), background var(--concept-bg), backdrop-filter blur(16px)
  .card-formula : border-left 3px solid var(--formula), background var(--formula-bg), backdrop-filter blur(16px)
  .card-example : border-left 3px solid var(--example), background var(--example-bg), backdrop-filter blur(16px)
  .card-danger  : border-left 3px solid var(--danger),  background var(--danger-bg),  backdrop-filter blur(16px)
  .card-mnemo   : border-left 3px solid var(--success), background var(--success-bg), backdrop-filter blur(16px)
    → sa pastille est TOUJOURS <label class="label success">, jamais "example".

Labels pill (haut à droite, position absolute) — CSS À RECOPIER TEL QUEL.
Le défaut le plus fréquent et le plus laid d'une fiche générée est une pastille
GRISE, sans couleur : elle arrive quand le HTML écrit `class="label-concept"`
ou `class="label label-concept"` alors que le CSS n'attend que `.label.concept`.
Ce bloc couvre les DEUX formes de sélecteur (point ET tiret) pour chaque
catégorie : quelle que soit la syntaxe que tu écris dans le HTML, la pastille
est stylée. Recopie-le sans le modifier.

  .label { font-size:0.65rem; font-weight:700; text-transform:uppercase; border-radius:4px; padding:0.12em 0.5em; position:absolute; top:0.8rem; right:0.8rem; }
  .label.concept, .label-concept { color:var(--concept); background:var(--concept-bg); border:1px solid var(--concept); }
  .label.formula, .label-formula { color:var(--formula); background:var(--formula-bg); border:1px solid var(--formula); }
  .label.example, .label-example { color:var(--example); background:var(--example-bg); border:1px solid var(--example); }
  .label.danger,  .label-danger  { color:var(--danger);  background:var(--danger-bg);  border:1px solid var(--danger); }
  .label.success, .label-success, .label.mnemo, .label-mnemo { color:var(--success); background:var(--success-bg); border:1px solid var(--success); }

  Une card .card-mnemo porte une pastille « Mémo » : écris `class="label success"`
  — et `class="label mnemo"` est désormais stylé à l'identique, par sécurité.

Chiffres clés :
  grid repeat(auto-fit, minmax(160px, 1fr)), gap 1rem, margin-bottom 1.5rem
  Chaque card : display flex, flex-direction column, align-items center, justify-content center
    (⚠ centrage RÉEL des deux axes : `text-align:center` seul laisse le chiffre
     décalé quand la valeur tient sur deux lignes ou que les cards d'une rangée
     n'ont pas la même hauteur. Le flex centre pour de vrai.)
    background var(--surface), backdrop-filter blur(16px), border 1px solid var(--surface-border)
    border-radius 12px, padding 1.2rem 1rem, text-align center
  Chiffre : font-size 2.2rem, font-weight 800, color var(--accent), line-height 1.1
  Label : font-size 0.78rem, color var(--muted), margin-top 0.25rem

Code inline : background var(--formula-bg), color var(--formula), border 1px solid var(--formula), border-radius 4px, padding 0.1em 0.4em, font-family monospace
Code bloc : background rgba(0,0,0,0.25), backdrop-filter blur(8px), border 1px solid var(--surface-border), border-radius 10px, padding 1rem, font-family monospace, overflow-x auto

Tableaux (TOUJOURS dans un <div class="table-wrapper"> séparé) :
  .table-wrapper : overflow-x auto, width 100%, border-radius 10px, max-width 100%
  table : border-collapse collapse, width 100%
  th : background var(--accent-dim), color var(--accent), font-weight 700, padding 0.7rem 1rem, border-bottom 2px solid var(--accent), text-align left
  td : padding 0.6rem 1rem, border-bottom 1px solid var(--surface-border), color var(--text)
  tr:nth-child(even) : background var(--surface)

Mémotechniques : background var(--success-bg), border-left 3px solid var(--success), border-radius 10px, padding 0.9rem 1.1rem
  .mnemo-label : color var(--success), font-size 0.72rem, font-weight 700, display block, margin-bottom 0.3rem

@media print :
  header, .header-inner { display: none }
  body background white !important, color #1c1917 !important
  .card { background #f9f6f0 !important; border 1px solid #d0c8b8 !important; backdrop-filter none !important; }
  h2 { color #8b5e3c !important; border-color #8b5e3c !important; }

━━ JS THÈME ━━

Script dans <head> (avant tout rendu, évite le flash) :
  const saved = localStorage.getItem('axon-theme');
  if (saved === 'dark') document.documentElement.classList.add('dark');
  // pas de classe = light (défaut)

Bouton toggle dans le header — le JS est la SEULE chose qui change son libellé :
  onclick :
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('axon-theme', isDark ? 'dark' : 'light');
    this.textContent = isDark ? '☀ Clair' : '◑ Sombre';

━━ CONTENU ━━

Fusionne intelligemment si plusieurs documents.
Inclure des mémotechniques quand les listes sont longues (acronymes, phrases).
Les tableaux comparatifs sont préférables aux listes pour les éléments similaires.

CONTRÔLE QUALITÉ (vérification mentale avant de produire le HTML — ne pas écrire hors du HTML) :
Avant de clore le </body>, valide mentalement :
  ✓ Ai-je couvert chaque chapitre identifié à l'étape 0 ?
  ✓ Ai-je inclus toutes les définitions, même celles données brièvement ?
  ✓ Ai-je inclus les notions qui revenaient plusieurs fois dans le document ?
  ✓ Ai-je inclus les pièges et distinctions ?
  ✓ Ai-je inclus des exemples concrets pour chaque concept majeur ?
  ✓ La section "CE QUI PEUT TOMBER AU PARTIEL" est-elle présente et utile ?
  ✓ La CHECKLIST ANTI-OUBLI confirme-t-elle la couverture complète ?
Si une case n'est pas cochée → ajouter le contenu manquant avant de fermer le HTML.

━━ DOCUMENTS À ANALYSER ━━
%%CONTENT%%
