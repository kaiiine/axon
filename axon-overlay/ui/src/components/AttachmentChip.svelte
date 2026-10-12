<script lang="ts">
 import Icon from './Icon.svelte';
 export let nom:string;
 export let statut:'chargement'|'ok'|'erreur';
 export let message:string|undefined=undefined;
 export let taille:string='';
 //: Pas de retrait pendant la lecture — `/detach` n'a rien à annuler tant
 //: que l'extraction tourne côté CLI (voir app.py::_gerer_joindre).
 export let onRemove:(()=>void)|undefined=undefined;
</script>
<div class="chip" class:erreur={statut==='erreur'}>
 <span class="mark"><Icon name="paperclip"/></span>
 <div class="text">
  <b title={nom}>{nom}</b>
  {#if statut==='erreur'}<span class="err">{message||'échec de lecture'}</span>
  {:else if statut==='chargement'}<span class="muted">lecture…</span>
  {:else}<span class="muted">{taille}</span>{/if}
 </div>
 {#if onRemove&&statut!=='chargement'}<button class="remove" onclick={onRemove} aria-label={`Retirer ${nom}`} title="Retirer"><Icon name="close"/></button>{/if}
</div>
<style>
 .chip{display:flex;align-items:center;gap:8px;padding:6px 8px;background:#ffffff06;border:1px solid #ffffff0e;border-radius:10px;max-width:220px}
 .chip.erreur{background:#e68a8a0e;border-color:#e68a8a2a}
 .mark{width:20px;height:20px;border-radius:7px;display:grid;place-items:center;background:#ffffff08;color:#9299a8;flex:none}
 .mark :global(.icon){width:11px;height:11px}
 .text{min-width:0;flex:1;display:flex;flex-direction:column;gap:1px}
 .text b{font-size:10px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .muted{font-size:8.5px;color:var(--faint)}
 .err{font-size:8.5px;color:#e68a8a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .remove{width:16px;height:16px;border-radius:50%;display:grid;place-items:center;color:var(--faint);flex:none}
 .remove:hover{background:#ffffff10;color:var(--text)}
 .remove :global(.icon){width:8px;height:8px}
</style>
