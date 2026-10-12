<script lang="ts">
 import {tick} from 'svelte';
 import {model} from '../model';
 import Icon from './Icon.svelte';
 //: Même patron que CreerSuivi.svelte (§2, lot 3 posé comme modèle à
 //: reprendre pour ces actions-là aussi) : le "+" révèle le formulaire, qui
 //: ne se referme que sur confirmation du backend.
 export let disabled=false;
 export let suivis:{id:string;title:string}[]=[];
 export let onCreer:(suiviId:string,titre:string,typeEcheance:string,date:string)=>string|undefined;
 const TYPES=[
  {valeur:'devoir',label:'Devoir'},
  {valeur:'partiel',label:'Partiel'},
  {valeur:'rendu_projet',label:'Rendu de projet'},
  {valeur:'autre',label:'Autre'},
 ];
 let ouvert=false;
 let suiviId='';
 let titre='';
 let type='devoir';
 let date='';
 let erreur='';
 let titreInput:HTMLInputElement;
 let idEnAttente:string|null=null;
 $: enAttente=idEnAttente!==null&&$model.actionEtudes?.id===idEnAttente&&$model.actionEtudes.statut==='en_cours';
 $: if(idEnAttente&&$model.actionEtudes?.id===idEnAttente&&$model.actionEtudes.statut!=='en_cours'){
  if($model.actionEtudes.statut==='ok'){
   ouvert=false;titre='';date='';type='devoir';erreur='';
  }else{
   erreur=$model.actionEtudes.message||'Échec de la création.';
  }
  idEnAttente=null;
 }
 //: `suiviId` par défaut au PREMIER suivi dès que la liste arrive (elle
 //: peut être vide à l'ouverture, se remplir juste après).
 $: if(!suiviId&&suivis.length)suiviId=suivis[0].id;
 $: if(ouvert&&titreInput)void tick().then(()=>titreInput?.isConnected&&titreInput.focus());
 function basculer(){ouvert=!ouvert;if(!ouvert){titre='';date='';type='devoir';erreur='';}}
 function soumettre(){
  const t=titre.trim();
  if(!t||!date||!suiviId||disabled||enAttente)return;
  erreur='';
  idEnAttente=onCreer(suiviId,t,type,date)??null;
 }
 function key(e:KeyboardEvent){if(e.key==='Enter'){e.preventDefault();soumettre();}else if(e.key==='Escape'){e.preventDefault();basculer();}}
</script>
<button class="toggle" class:ouvert onclick={basculer} title="Nouvelle échéance" aria-label="Nouvelle échéance" aria-expanded={ouvert} disabled={disabled||enAttente||!suivis.length}>
 <Icon name="plus"/>
</button>
{#if ouvert}
 <div class="form">
  <div class="row">
   <select bind:value={suiviId} aria-label="Suivi concerné" disabled={disabled||enAttente}>
    {#each suivis as s}<option value={s.id}>{s.title}</option>{/each}
   </select>
   <select bind:value={type} aria-label="Type d’échéance" disabled={disabled||enAttente}>
    {#each TYPES as t}<option value={t.valeur}>{t.label}</option>{/each}
   </select>
  </div>
  <div class="row">
   <input bind:this={titreInput} bind:value={titre} onkeydown={key} placeholder="Titre de l’échéance…" aria-label="Titre de l’échéance" autocomplete="off" disabled={disabled||enAttente}/>
   <input type="date" bind:value={date} onkeydown={key} aria-label="Date de l’échéance" disabled={disabled||enAttente}/>
   <button class="send" title="Créer" aria-label="Créer" disabled={disabled||enAttente||!titre.trim()||!date} onclick={soumettre}><Icon name="send"/></button>
  </div>
  {#if erreur}<p class="erreur">{erreur}</p>{/if}
 </div>
{/if}
<style>
 .toggle{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;color:var(--muted);flex:none}
 .toggle:hover,.toggle.ouvert{background:#ffffff0a;color:var(--text)}
 .toggle:disabled{opacity:.4}
 .toggle :global(.icon){width:11px;height:11px}
 .toggle.ouvert :global(.icon){transform:rotate(45deg)}
 .toggle :global(.icon){transition:transform 150ms var(--spring)}
 .form{display:flex;flex-direction:column;gap:6px;flex:none;animation:revealIn 180ms var(--spring-soft) both}
 @keyframes revealIn{0%{opacity:0;transform:translateY(-3px)}100%{opacity:1;transform:translateY(0)}}
 .row{display:flex;gap:6px;align-items:center}
 input,select{border:1px solid #ffffff14;background:#ffffff06;color:var(--text);font:11px/1.4 var(--font);padding:7px 9px;border-radius:9px;outline:none;appearance:none;-webkit-appearance:none;transition:border-color 150ms,background 150ms}
 input{flex:1;min-width:0}
 input:focus,select:focus{border-color:#ffaf0045;background:#ffffff09}
 input:disabled,select:disabled{opacity:.5}
 select{flex:1;min-width:0}
 .send{width:28px;height:28px;flex:none;border-radius:8px;display:grid;place-items:center;background:var(--accent);color:#241700;transition:transform 160ms var(--spring),background 150ms,opacity 150ms}
 .send:hover:not(:disabled){background:#ffc02e;transform:translateY(-1px)}
 .send:disabled{opacity:.35}
 .erreur{font-size:10px;color:#e68a8a;margin:0}
</style>
