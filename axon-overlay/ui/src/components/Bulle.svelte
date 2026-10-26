<script lang="ts">
 import {onDestroy, onMount} from 'svelte';
 import {model, agirSurRappel, replierPopup} from '../model';
 import {actionsDuRappel, parolesDuRappel, titreDuRappel} from '../rappels';
 import {PAROLE, revelation} from '../fluidite';
 import {hauteurNative} from '../mesure';
 import MascotStage from './MascotStage.svelte';
 import type {Rappel} from '../types';
 //: Un rappel du démon, dit par Axon dans une bulle : il arrive, parle, puis
 //: propose les actions du rappel. Sans survol, la bulle se replie en pastille
 //: une fois lue — le rappel reste, un survol le rouvre.
 export let rappel: Rappel;

 const DEBUT_PAROLE_MS = 340;
 const LECTURE_MS = 9000;

 const complet = parolesDuRappel(rappel.texte).join('\n');
 const actions = actionsDuRappel(rappel);
 let dit = '', fini = !complet, survole = false;
 let depart: ReturnType<typeof setTimeout> | undefined, repli: ReturnType<typeof setTimeout> | undefined;

 const voix = revelation(texte => {
  dit = texte;
  if (texte.length >= complet.length && !fini) { fini = true; programmerRepli(); }
 }, PAROLE);

 function programmerRepli() {
  clearTimeout(repli);
  if (fini && !survole) repli = setTimeout(replierPopup, LECTURE_MS);
 }
 function entrer() { survole = true; clearTimeout(repli); }
 function sortir() { survole = false; programmerRepli(); }

 onMount(() => {
  const anime = $model.motion;
  depart = setTimeout(() => voix.viser(complet, anime), anime ? DEBUT_PAROLE_MS : 0);
 });
 onDestroy(() => { clearTimeout(depart); clearTimeout(repli); voix.arreter(); });

 $: paroles = dit.split('\n').filter(Boolean);
</script>

<div class="rappel" class:parle={!fini} role="presentation" onpointerenter={entrer} onpointerleave={sortir}>
 <div class="axon"><div class="voix"><MascotStage state={fini ? 'idle' : 'thinking'} motion={$model.motion} visible={$model.visible}/></div></div>
 <div class="bulle" use:hauteurNative>
  <header>
   <span class="point"></span><strong>{titreDuRappel(rappel)}</strong>
   {#if $model.rappels.length > 1}<small>+{$model.rappels.length - 1}</small>{/if}
  </header>
  <div class="paroles" role="status" aria-live="polite" aria-label={complet}>
   {#if paroles.length > 1}
    <ul>{#each paroles as ligne}<li>{ligne}</li>{/each}</ul>
   {:else if paroles.length}
    <p>{paroles[0]}</p>
   {/if}
   {#if !fini}<span class="ecrit" aria-hidden="true"></span>{/if}
  </div>
  {#if fini}
   <div class="actions">
    {#each actions as action, i}
     <button style={`--i:${i}`} class:principal={action.principal} disabled={action.axon && !$model.connected}
      title={action.axon && !$model.connected ? 'Axon n’est pas connecté' : undefined}
      onclick={() => agirSurRappel(rappel.id, action.id)}>{action.libelle}</button>
    {/each}
   </div>
  {/if}
 </div>
</div>

<style>
 .rappel{height:100%;display:flex;align-items:center;gap:10px;padding:4px 10px 4px 2px}
 .axon{width:104px;height:104px;flex:none;animation:arrivee 560ms var(--spring) both}
 @keyframes arrivee{0%{opacity:0;transform:translateY(-14px) scale(.72) rotate(-6deg)}100%{opacity:1;transform:none}}
 .voix{width:100%;height:100%}
 .parle .voix{animation:parole 420ms 560ms ease-in-out infinite alternate}
 @keyframes parole{0%{transform:translateY(0) scale(1)}100%{transform:translateY(-2px) scale(1.025)}}

 .bulle{position:relative;flex:1;min-width:0;padding:11px 14px 12px;border-radius:18px;background:linear-gradient(135deg,#ffffff12,#ffffff07);border:1px solid #ffffff1c;box-shadow:inset 0 1px 0 #ffffff14,0 8px 24px #0000002a;transform-origin:-8px 30px;animation:eclot 480ms 180ms var(--spring) both}
 .bulle:before{content:"";position:absolute;left:-7px;top:26px;width:12px;height:12px;background:#ffffff10;border-left:1px solid #ffffff1c;border-bottom:1px solid #ffffff1c;transform:rotate(45deg);border-bottom-left-radius:3px}
 @keyframes eclot{0%{opacity:0;transform:translateX(-12px) scale(.55)}100%{opacity:1;transform:none}}

 header{display:flex;align-items:center;gap:7px;margin-bottom:5px}
 header strong{font-size:12.5px;font-weight:560;letter-spacing:-.15px;color:#eeeff4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 header small{margin-left:auto;color:#9b8c75;font:9px var(--mono)}
 .point{width:5px;height:5px;border-radius:50%;flex:none;background:var(--accent);box-shadow:0 0 9px #ffaf0066}

 .paroles{font-size:11.5px;line-height:1.5;color:#d3d6de;min-height:17px}
 .paroles p{display:inline}
 .paroles ul{list-style:none;display:flex;flex-direction:column;gap:2px}
 .paroles li{position:relative;padding-left:11px}
 .paroles li:before{content:"";position:absolute;left:1px;top:.62em;width:4px;height:4px;border-radius:50%;background:#ffaf0088}
 .ecrit{display:inline-block;width:5px;height:5px;margin-left:4px;border-radius:50%;background:var(--accent);animation:ecrit 900ms ease-in-out infinite}
 @keyframes ecrit{50%{opacity:.25;transform:scale(.7)}}

 .actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
 .actions button{font-size:11px;padding:6px 12px;border:1px solid #ffffff14;border-radius:16px;background:#ffffff08;animation:bouton 380ms calc(var(--i) * 60ms) var(--spring) both;transition:transform 150ms var(--spring),background 150ms,border-color 150ms}
 @keyframes bouton{0%{opacity:0;transform:translateY(6px) scale(.92)}100%{opacity:1;transform:none}}
 .actions button:hover:not(:disabled){background:#ffffff12;border-color:#ffffff22;transform:translateY(-1px)}
 .actions button.principal{background:var(--accent);color:#302000;border-color:var(--accent);box-shadow:0 4px 16px #ffaf0030}
 .actions button.principal:hover:not(:disabled){background:#ffc02e}
</style>
