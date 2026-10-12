<script lang="ts">
 import {tick} from 'svelte';
 import {model} from '../model';
 import Icon from './Icon.svelte';
 //: Même patron « conditionally revealed » que FreeformAnswer — le "+"
 //: révèle le formulaire juste en dessous, pas une nouvelle vue.
 export let disabled=false;
 export let onCreer:(titre:string,type:string,matiere:string)=>string|undefined;
 const TYPES=[
  {valeur:'matiere',label:'Matière'},
  {valeur:'projet',label:'Projet'},
  {valeur:'ponctuel',label:'Ponctuel'},
  {valeur:'autre',label:'Autre'},
 ];
 let ouvert=false;
 let titre='';
 let type='matiere';
 let matiere='';
 let erreur='';
 let titreInput:HTMLInputElement;
 //: L'id de CETTE soumission (§2, lot 3) — jamais "la dernière création
 //: connue" : si une réponse tardive arrivait après que l'utilisateur a
 //: rouvert le formulaire pour une AUTRE création, elle ne doit pas la
 //: fermer à sa place.
 let idSuivi:string|null=null;
 //: `$model.creationSuivi` est la seule source de vérité pour "en cours" —
 //: plus de fermeture optimiste à l'envoi : le formulaire ne se referme
 //: que sur confirmation du backend (`statut==='ok'`). Sur échec (y compris
 //: une connexion perdue en vol), les champs restent tels quels et l'erreur
 //: s'affiche dans le formulaire.
 $: enCours=idSuivi!==null&&$model.creationSuivi?.id===idSuivi&&$model.creationSuivi.statut==='en_cours';
 $: if(idSuivi&&$model.creationSuivi?.id===idSuivi&&$model.creationSuivi.statut!=='en_cours'){
  if($model.creationSuivi.statut==='ok'){
   ouvert=false;titre='';matiere='';type='matiere';erreur='';
  }else{
   erreur=$model.creationSuivi.message||'Échec de la création.';
  }
  idSuivi=null;
 }
 $: if(ouvert&&titreInput)void tick().then(()=>titreInput?.isConnected&&titreInput.focus());
 function basculer(){ouvert=!ouvert;if(!ouvert){titre='';matiere='';type='matiere';erreur='';}}
 function soumettre(){
  const t=titre.trim();
  if(!t||disabled||enCours)return;
  erreur='';
  idSuivi=onCreer(t,type,matiere.trim())??null;
 }
 function key(e:KeyboardEvent){if(e.key==='Enter'){e.preventDefault();soumettre();}else if(e.key==='Escape'){e.preventDefault();basculer();}}
</script>
<button class="toggle" class:ouvert onclick={basculer} title="Nouveau suivi" aria-label="Nouveau suivi" aria-expanded={ouvert} disabled={disabled||enCours}>
 <Icon name="plus"/>
</button>
{#if ouvert}
 <div class="form">
  <input bind:this={titreInput} bind:value={titre} onkeydown={key} placeholder="Titre du suivi…" aria-label="Titre du suivi" autocomplete="off" disabled={disabled||enCours}/>
  <div class="row">
   <select bind:value={type} aria-label="Type de suivi" disabled={disabled||enCours}>
    {#each TYPES as t}<option value={t.valeur}>{t.label}</option>{/each}
   </select>
   {#if type==='matiere'}<input bind:value={matiere} onkeydown={key} placeholder="Matière (optionnel)" aria-label="Matière" autocomplete="off" disabled={disabled||enCours}/>{/if}
   <button class="send" title="Créer" aria-label="Créer" disabled={disabled||enCours||!titre.trim()} onclick={soumettre}><Icon name="send"/></button>
  </div>
  {#if erreur}<p class="erreur">{erreur}</p>{/if}
 </div>
{/if}
<style>
 .toggle{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;color:var(--muted);flex:none}
 .toggle:hover,.toggle.ouvert{background:#ffffff0a;color:var(--text)}
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
 select{flex:none;width:96px}
 .send{width:28px;height:28px;flex:none;border-radius:8px;display:grid;place-items:center;background:var(--accent);color:#241700;transition:transform 160ms var(--spring),background 150ms,opacity 150ms}
 .send:hover:not(:disabled){background:#ffc02e;transform:translateY(-1px)}
 .send:disabled{opacity:.35}
 .erreur{font-size:10px;color:#e68a8a;margin:0}
</style>
