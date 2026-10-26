<script lang="ts">import {model,answer,chooseFreeform} from '../model';import FreeformAnswer from './FreeformAnswer.svelte';
 const AUTRE='Autre (préciser)';
 const norm=(c:string)=>c.trim().toLowerCase().replace(/\.$/,'');
 $: request=$model.requests[0];
 $: question=request?.questions[request.answers.length];
 $: freeform=request?.freeform===true;
 //: « Autre » seulement si la question le permet (`libre!==false`) — un
 //: picker à choix fermé comme /backend n'a rien de valide à ajouter hors
 //: de sa liste, lui proposer un champ libre ne ferait que renvoyer un refus
 //: silencieux une fois la réponse tapée.
 $: choices=question&&question.choix.length?(question.libre!==false?[...question.choix.filter(c=>norm(c)!==norm(AUTRE)),AUTRE]:[...question.choix]):[];
 $: busy=$model.busy||(!$model.connected&&!$model.demo);
 function choose(choice:string){if(choice===AUTRE)chooseFreeform();else answer(choice);}
</script>
{#if request&&question&&!$model.popup}<aside class="request" aria-live="polite"><div class="label"><span class="dot"></span>question <small>{request.answers.length+1}/{request.questions.length}{#if $model.requests.length>1} · {$model.requests.length} demandes{/if}</small></div><p>{question.texte}</p>{#if request.apercu}<pre>{request.apercu}</pre>{/if}{#if freeform&&question.choix.length}<FreeformAnswer disabled={busy} onSubmit={answer}/>{:else if choices.length}<div class="choices">{#each choices as choice}<button class:primary={choice===question.affirmatif} disabled={busy} onclick={()=>choose(choice)}>{choice}</button>{/each}</div>{:else}<span class="hint">Réponds ci-dessous.</span>{/if}</aside>{/if}
<style>.request{padding:13px 14px;background:#ffaf0007;border:1px solid #ffaf0024;border-radius:20px;flex:none;max-height:55%;overflow:auto}.label{display:flex;align-items:center;gap:6px;font-size:10px;color:#d8ac58}.dot{width:4px;height:4px;background:var(--accent);border-radius:50%}small{margin-left:auto;color:#9b8c75;font-size:9px}p{font-size:12px;line-height:1.6;margin:7px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.6 var(--mono);background:#0003;padding:8px;border-radius:12px;max-height:100px;overflow:auto}.choices{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.choices button{font-size:11px;padding:6px 11px;border:1px solid #ffffff12;border-radius:18px;background:#ffffff06}.choices button.primary{background:var(--accent);color:#302000;border-color:var(--accent)}.hint{color:var(--muted);font-size:10px}</style>
