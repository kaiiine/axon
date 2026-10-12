<script lang="ts">
 import {renderMarkdown} from '../../markdown';
 //: Texte Markdown qui s'écrit en temps réel (réponse LLM en flux). Ne sait
 //: rien de sa source : le parent passe le texte reçu et l'état du flux.
 //: Tant que rien n'est arrivé, un squelette ; pendant l'écriture, un curseur.
 export let texte:string='';
 export let statut:'repos'|'en_cours'|'fini'|'erreur'='repos';
 export let message:string|undefined=undefined;
 export let vide:string='';
</script>
<div class="flux" aria-live="polite" aria-busy={statut==='en_cours'}>
 {#if statut==='en_cours'&&!texte}
  <div class="attente" aria-label="Axon réfléchit"><span class="ligne"></span><span class="ligne"></span><span class="ligne courte"></span></div>
 {:else if texte}
  <div class="md" class:ecrit={statut==='en_cours'}>{@html renderMarkdown(texte)}</div>
 {:else if statut!=='erreur'&&vide}
  <p class="vide">{vide}</p>
 {/if}
 {#if statut==='erreur'}<p class="erreur">{message||'Échec.'}</p>{/if}
</div>
<style>
 .attente{display:flex;flex-direction:column;gap:7px;padding:2px 0}
 .ligne{display:block;height:9px;border-radius:5px;background:linear-gradient(90deg,#ffffff07 0%,#ffaf0018 50%,#ffffff07 100%);background-size:220% 100%;animation:shimmer 1.4s linear infinite}
 .ligne.courte{width:60%}
 @keyframes shimmer{from{background-position:160% 0}to{background-position:-60% 0}}
 .md{font-size:11px;line-height:1.65;color:#cfd1d9;user-select:text}
 .md :global(p){margin:0 0 7px}
 .md :global(p:last-child){margin-bottom:0}
 .md :global(strong){color:#eceef4;font-weight:600}
 .md :global(h1),.md :global(h2),.md :global(h3){font-size:11.5px;font-weight:600;color:#f0cf93;margin:9px 0 4px}
 .md :global(h1:first-child),.md :global(h2:first-child),.md :global(h3:first-child){margin-top:0}
 .md :global(ul),.md :global(ol){margin:4px 0 7px;padding-left:17px}
 .md :global(li){margin:2px 0}
 .md :global(code){font:10px var(--mono);background:#ffffff0d;padding:1px 4px;border-radius:4px}
 .md :global(a){color:var(--accent);text-decoration:underline;text-underline-offset:2px}
 /* Curseur d'écriture après le dernier bloc, le temps du flux. */
 .md.ecrit :global(> :last-child)::after{content:'';display:inline-block;width:6px;height:11px;margin-left:3px;vertical-align:-1px;border-radius:1px;background:var(--accent);animation:clignote 900ms steps(1) infinite}
 @keyframes clignote{50%{opacity:0}}
 .vide{font-size:10px;color:var(--muted)}
 .erreur{font-size:10px;color:#e68a8a;margin-top:6px}
</style>
