<script lang="ts">
 import {model,answer,chooseFreeform,navigate} from '../model';
 import {hauteurNative} from '../mesure';
 import {titreDuRappel} from '../rappels';
 import Bulle from './Bulle.svelte';
 import MascotStage from './MascotStage.svelte';
 import Mascot from './Mascot.svelte';
 import FreeformAnswer from './FreeformAnswer.svelte';
 import Icon from './Icon.svelte';
 //: Une demande HITL en petite notification : Axon à gauche, la question et
 //: ses réponses en ligne. Même logique de réponse que `RequestCard` — seul le
 //: format change ; « détails » ouvre la conversation pour un plan ou un diff
 //: trop long pour tenir ici.
 const AUTRE='Autre (préciser)';
 const GENRES:Record<string,string>={autorisation:'autorisation',plan:'plan proposé',diff:'modifications',envoi:'envoi de mail',clarification:'question'};
 const norm=(c:string)=>c.trim().toLowerCase().replace(/\.$/,'');
 $: request=$model.requests[0];
 $: question=request?.questions[request.answers.length];
 //: Les demandes passent avant les rappels : elles bloquent une tâche.
 $: rappel=request?undefined:$model.rappels[0];
 $: envoye=$model.popup?.envoye===true;
 $: pastille=$model.popup?.deplie===false;
 $: freeform=request?.freeform===true;
 //: Une autorisation, un plan, un diff ou un envoi ont déjà leurs propres
 //: issues (« Préciser », « Modifier ») : « Autre » n'y ajouterait que du bruit.
 $: autre=question?.libre!==false&&!['autorisation','plan','diff','envoi'].includes(request?.genre||'');
 $: choices=question&&question.choix.length?(autre?[...question.choix.filter(c=>norm(c)!==norm(AUTRE)),AUTRE]:[...question.choix]):[];
 $: busy=$model.busy||(!$model.connected&&!$model.demo);
 $: lignes=(request?.apercu||'').split('\n').map(l=>l.trim()).filter(Boolean);
 $: apercu=lignes[0]?.replace(/^\d+\.\s*/,'')||'';
 $: reste=Math.max(0,lignes.length-1);
 //: Les questions conditionnelles (`si`) ne comptent pas : « 1/2 » sur un plan
 //: annonçait une seconde question qui n'apparaît qu'après « Préciser ».
 $: totales=request?request.questions.filter(q=>!q.si).length:0;
 $: etape=request?`${Math.min(request.answers.length+1,totales)}/${totales}`:'';
 $: cle=request?`${request.id}:${request.answers.length}`:'';
 function choose(choice:string){if(choice===AUTRE)chooseFreeform();else answer(choice);}
 //: La fenêtre native suit la hauteur du contenu : avant, les réponses en trop
 //: partaient dans une rangée horizontale à barre masquée — invisibles.
 //: Au-delà du maximum natif, `.corps` défile, barre visible et fondu en bas.
 let defile:HTMLElement|undefined, deborde=false, enBas=true;
 function suivreDefilement(){if(!defile)return;deborde=defile.scrollHeight>defile.clientHeight+2;enBas=defile.scrollTop+defile.clientHeight>=defile.scrollHeight-2;}
</script>
{#if pastille}
<div class="bulle" title={request?.questions[request.answers.length]?.texte||(rappel?titreDuRappel(rappel):'Axon attend ta réponse')} aria-label={rappel&&!request?'Axon a un rappel — survole pour le lire':'Axon attend ta réponse — survole pour répondre'}>
 <div class="mini"><Mascot state="waiting" motion={$model.motion} visible={$model.visible}/></div>
 {#if $model.requests.length+$model.rappels.length>1}<span class="nombre">{$model.requests.length+$model.rappels.length}</span>{/if}
</div>
{:else if rappel&&!envoye}
{#key rappel.id}<Bulle {rappel}/>{/key}
{:else}
<div class="popup" class:envoye data-state={envoye?'working':'waiting'}>
 <div class="mascotte"><MascotStage state={envoye?'working':'waiting'} motion={$model.motion} visible={$model.visible}/></div>
 <div class="corps" class:deborde class:en-bas={enBas} bind:this={defile} onscroll={suivreDefilement}>
  {#if envoye}
   <div class="envoye-msg" role="status"><span class="coche"><Icon name="check"/></span>{$model.popup?.texte||'Réponse envoyée'}</div>
  {:else if request&&question}
   {#key cle}
    <div class="question" aria-live="polite" use:hauteurNative={suivreDefilement}>
     <div class="tete">
      <span class="dot"></span><span class="genre">{GENRES[request.genre]||'à toi de jouer'}</span>
      {#if totales>1}<small>{etape}</small>{/if}
      {#if $model.requests.length>1}<small>+{$model.requests.length-1}</small>{/if}
      {#if choices.length>3&&!freeform}<small class="nb-choix">{choices.length} choix</small>{/if}
      <button class="details" onclick={()=>navigate('chat')} title="Ouvrir dans la conversation">détails <Icon name="arrow"/></button>
     </div>
     <p class="texte">{question.texte}</p>
     {#if apercu}<code class="apercu" title={request.apercu}>{apercu}{#if reste}<em>+{reste}</em>{/if}</code>{/if}
     {#if freeform||!choices.length}
      <div class="libre"><FreeformAnswer disabled={busy} onSubmit={answer} placeholder={freeform?'Précise ta réponse…':'Ta réponse…'}/></div>
     {:else}
      <div class="choix">{#each choices as choice,i}<button style={`--i:${i}`} class:primary={choice===question.affirmatif} class:autre={choice===AUTRE} disabled={busy} onclick={()=>choose(choice)}>{choice}</button>{/each}</div>
     {/if}
    </div>
   {/key}
  {/if}
 </div>
</div>
{/if}
<style>
 .bulle{position:relative;width:100%;height:100%;display:grid;place-items:center;animation:bulleIn 520ms var(--spring) both}
 @keyframes bulleIn{0%{opacity:0;transform:translateY(-10px) scale(.6)}100%{opacity:1;transform:none}}
 .mini{width:32px;height:32px;pointer-events:none;animation:flotte 3.2s ease-in-out infinite;filter:drop-shadow(0 2px 6px #ffaf0040)}
 @keyframes flotte{0%,100%{transform:translateY(1px) rotate(-3deg)}50%{transform:translateY(-2px) rotate(3deg)}}
 .nombre{position:absolute;top:1px;right:1px;min-width:13px;height:13px;padding:0 3px;border-radius:7px;background:var(--accent);color:#302000;font:600 8px/13px var(--mono);text-align:center;box-shadow:0 0 0 2px #1d1f29}
 .popup{position:relative;height:100%;display:flex;align-items:center;gap:6px;padding:4px 8px 4px 2px;animation:popIn 520ms var(--spring) both}
 @keyframes popIn{0%{opacity:0;transform:translateY(-10px) scale(.96)}100%{opacity:1;transform:none}}
 .mascotte{width:112px;height:112px;flex:none;animation:mascotteIn 640ms 40ms var(--spring) both}
 @keyframes mascotteIn{0%{opacity:0;transform:scale(.7) rotate(-8deg)}60%{opacity:1}100%{opacity:1;transform:none}}
 .corps{flex:1;min-width:0;max-height:100%;overflow-y:auto;overscroll-behavior:contain;padding-right:4px}
 .corps.deborde:not(.en-bas){-webkit-mask-image:linear-gradient(#000 calc(100% - 26px),transparent);mask-image:linear-gradient(#000 calc(100% - 26px),transparent)}
 .corps::-webkit-scrollbar{width:4px}.corps::-webkit-scrollbar-thumb{background:#ffaf0055;border-radius:4px}
 .nb-choix{color:#d8ac58}
 .question{display:flex;flex-direction:column;gap:5px;animation:questionIn 380ms var(--spring-soft) both}
 @keyframes questionIn{0%{opacity:0;transform:translateX(10px)}100%{opacity:1;transform:none}}
 .tete{display:flex;align-items:center;gap:6px;font-size:10px;color:#d8ac58}
 .dot{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 9px #ffaf0066;animation:pouls 1.6s ease-in-out infinite}
 @keyframes pouls{50%{box-shadow:0 0 0 4px #ffaf0010,0 0 12px #ffaf0055}}
 small{color:#9b8c75;font:9px var(--mono)}
 .details{margin-left:auto;display:flex;align-items:center;gap:4px;font-size:9px;color:var(--muted);padding:3px 8px;border-radius:12px}
 .details:hover{color:var(--text);background:#ffffff0a}
 .details :global(svg){width:10px;height:10px}
 .texte{font-size:13px;line-height:1.35;font-weight:520;letter-spacing:-.15px;display:-webkit-box;-webkit-line-clamp:2;line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
 .apercu{display:block;font:10px/1.5 var(--mono);color:#b9bdc8;background:#0003;padding:3px 8px;border-radius:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .apercu em{font-style:normal;color:var(--faint);margin-left:6px}
 .choix{display:flex;flex-wrap:wrap;gap:6px;padding:2px 1px 3px}
 .choix button{max-width:100%;font-size:11px;line-height:1.35;text-align:left;padding:6px 12px;border:1px solid #ffffff14;border-radius:16px;background:#ffffff08;animation:boutonIn 420ms calc(120ms + var(--i) * 55ms) var(--spring) both;transition:transform 150ms var(--spring),background 150ms,border-color 150ms}
 @keyframes boutonIn{0%{opacity:0;transform:translateY(6px) scale(.92)}100%{opacity:1;transform:none}}
 .choix button:hover:not(:disabled){background:#ffffff12;border-color:#ffffff22;transform:translateY(-1px)}
 .choix button.primary{background:var(--accent);color:#302000;border-color:var(--accent);box-shadow:0 4px 16px #ffaf0030}
 .choix button.primary:hover:not(:disabled){background:#ffc02e}
 .choix button.autre{color:var(--muted);border-style:dashed}
 .libre :global(.freeform){margin-top:0}
 .libre :global(.freeform-label){display:none}
 .envoye-msg{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:520;color:#eed3a3;animation:questionIn 300ms var(--spring-soft) both}
 .coche{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:var(--accent);color:#302000;animation:coche 480ms var(--spring) both}
 .coche :global(svg){width:13px;height:13px}
 @keyframes coche{0%{transform:scale(.3);opacity:0}100%{transform:none;opacity:1}}
 .popup.envoye{animation:popOut 650ms 260ms cubic-bezier(.4,0,.2,1) both}
 @keyframes popOut{0%{opacity:1;transform:none}100%{opacity:0;transform:translateY(-8px) scale(.97)}}
</style>
