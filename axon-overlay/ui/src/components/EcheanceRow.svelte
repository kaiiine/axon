<script lang="ts">
 import {model,majEcheance,planifierRappels} from '../model';
 import Icon from './Icon.svelte';
 //: Pas une variante de Row.svelte (integrations/Row.svelte) : celui-là
 //: déplie un DÉTAIL markdown en lecture seule (Gmail, Jira…) ; une échéance
 //: a besoin d'un vrai formulaire inline (la date à reporter) — mélanger
 //: les deux dans un seul composant partagé aurait rendu Row.svelte plus
 //: dur à lire pour un besoin qui ne concerne qu'Études (§3, lot 3).
 export let title:string;
 export let meta:string;
 export let tag:string|undefined=undefined;
 export let suiviId:string;
 export let echeanceId:string;
 //: Nombre de rappels déjà programmés. La cloche n'apparaît qu'à 0 : la
 //: reprogrammer en créerait d'autres par-dessus. Inconnu (undefined), pas
 //: de cloche non plus.
 export let rappels:number|undefined=undefined;

 let reportOuvert=false;
 let nouvelleDate='';
 let erreur='';
 //: Même patron de corrélation par id que CreerSuivi.svelte — une réponse
 //: tardive à une ancienne action ne doit affecter QUE la ligne qui l'a
 //: envoyée.
 let idEnAttente:string|null=null;
 $: enAttente=idEnAttente!==null&&$model.actionEtudes?.id===idEnAttente&&$model.actionEtudes.statut==='en_cours';
 $: if(idEnAttente&&$model.actionEtudes?.id===idEnAttente&&$model.actionEtudes.statut!=='en_cours'){
  if($model.actionEtudes.statut==='ok'){
   reportOuvert=false;nouvelleDate='';erreur='';
  }else{
   erreur=$model.actionEtudes.message||'Échec.';
  }
  idEnAttente=null;
 }

 function basculerReport(){reportOuvert=!reportOuvert;erreur='';if(!reportOuvert)nouvelleDate='';}
 function confirmerReport(){
  if(!nouvelleDate||enAttente)return;
  erreur='';
  idEnAttente=majEcheance(suiviId,echeanceId,{date:nouvelleDate})??null;
 }
 function programmerRappels(){
  if(enAttente)return;
  erreur='';
  idEnAttente=planifierRappels(suiviId,echeanceId)??null;
 }
 function annuler(){
  if(enAttente)return;
  erreur='';
  idEnAttente=majEcheance(suiviId,echeanceId,{statut:'annulee'})??null;
 }
</script>
<div class="echeance">
 <div class="content">
  <div class="text"><b>{title}</b><span>{meta}</span></div>
  {#if tag}<i>{tag}</i>{/if}
  <div class="actions">
   {#if rappels===0}<button class="row-action" disabled={enAttente} title="Rappels 7, 3 et 1 jours avant" aria-label="Programmer les rappels" onclick={programmerRappels}><Icon name="bell"/></button>{/if}
   <button class="row-action" class:active={reportOuvert} disabled={enAttente} title="Reporter" aria-label="Reporter" onclick={basculerReport}><Icon name="chevron"/></button>
   <button class="row-action" disabled={enAttente} title="Annuler l’échéance" aria-label="Annuler l’échéance" onclick={annuler}><Icon name="close"/></button>
  </div>
 </div>
 {#if reportOuvert}
  <div class="report">
   <input type="date" bind:value={nouvelleDate} disabled={enAttente} aria-label="Nouvelle date"/>
   <button class="send" title="Confirmer le report" aria-label="Confirmer le report" disabled={enAttente||!nouvelleDate} onclick={confirmerReport}><Icon name="send"/></button>
  </div>
 {/if}
 {#if erreur}<p class="erreur">{erreur}</p>{/if}
</div>
<style>
 .echeance{padding:9px 11px;background:#ffffff05;border:1px solid #ffffff08;border-top-color:#ffffff14;border-radius:10px;transition:background 150ms,border-color 150ms}
 .echeance:hover{background:#ffffff09;border-color:#ffffff20}
 .content{display:flex;align-items:center;gap:8px;width:100%}
 .text{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}
 .text b{font-size:11px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .text span{font-size:9px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .echeance i{font-style:normal;font-size:8px;font-weight:600;padding:3px 7px;border-radius:20px;background:#ffffff08;color:#b0b2bc;flex:none}
 .actions{display:flex;gap:4px;flex:none;max-width:0;overflow:hidden;opacity:0;transform:translateX(-2px);transition:opacity 150ms,transform 150ms,max-width 150ms}
 .echeance:hover .actions,.actions:focus-within{max-width:110px;opacity:1;transform:translateX(0)}
 .row-action.active{opacity:1}
 .row-action{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;flex:none;transition:transform 150ms var(--spring),background 150ms,border-color 150ms,color 150ms}
 .row-action:hover:not(:disabled){background:#ffaf0014;border-color:#ffaf0040;color:#f0cf93;transform:translateY(-1px)}
 .row-action:disabled{opacity:.4;cursor:default}
 .row-action.active{background:#ffaf001f;border-color:#ffaf0050;color:#f0cf93}
 .row-action :global(.icon){width:12px;height:12px}
 .report{display:flex;gap:6px;margin-top:9px;padding-top:9px;border-top:1px solid #ffffff0a;animation:revealIn 180ms var(--spring-soft) both}
 @keyframes revealIn{0%{opacity:0;transform:translateY(-3px)}100%{opacity:1;transform:translateY(0)}}
 .report input{flex:1;min-width:0;border:1px solid #ffffff14;background:#ffffff06;color:var(--text);font:11px/1.4 var(--font);padding:7px 9px;border-radius:9px;outline:none}
 .report input:focus{border-color:#ffaf0045;background:#ffffff09}
 .send{width:28px;height:28px;flex:none;border-radius:8px;display:grid;place-items:center;background:var(--accent);color:#241700;transition:transform 160ms var(--spring),background 150ms,opacity 150ms}
 .send:hover:not(:disabled){background:#ffc02e;transform:translateY(-1px)}
 .send:disabled{opacity:.35}
 .erreur{font-size:10px;color:#e68a8a;margin:6px 0 0}
</style>
