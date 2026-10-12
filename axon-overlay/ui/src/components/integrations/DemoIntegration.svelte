<script lang="ts">
 import Stat from './Stat.svelte';
 import Row from './Row.svelte';
 //: Données fictives du mode démo (ui/apercu.html) uniquement. Jamais
 //: affichées dans l'île réelle : des mails ou tickets inventés y seraient
 //: pris pour les vrais.
 export let id:string;
 export let color:string;
</script>
{#if id==='gmail'}
 <div class="stats"><Stat label="Non lus" value="4" {color}/><Stat label="Reçus aujourd’hui" value="11"/></div>
 <Row title="Point hebdo équipe" meta="Camille · il y a 18 min" tag="non lu" tagColor={color}/>
 <Row title="Renouvellement du domaine" meta="Service client · hier" tag="info"/>
 <Row title="Re : proposition de calendrier" meta="Hugo · il y a 2 j" tag="répondu"/>
{:else if id==='workspace'}
 <div class="stats"><Stat label="Événements aujourd’hui" value="3" {color}/><Stat label="Fichiers récents" value="6"/></div>
 <Row title="Point hebdo" meta="14:00 · Google Meet" tag="Agenda" tagColor={color}/>
 <Row title="Roadmap Q1.docx" meta="modifié il y a 1 h" tag="Docs"/>
{:else if id==='slack'}
 <div class="stats"><Stat label="Non lus" value="7" {color}/><Stat label="Canaux actifs" value="3"/></div>
 <Row title="#general" meta="Camille : on valide pour vendredi ?" tag="3" tagColor={color}/>
 <Row title="#dev" meta="Hugo : build cassé sur main" tag="1"/>
{:else if id==='jira'}
 <div class="stats"><Stat label="Assignés à toi" value="5" {color}/><Stat label="En retard" value="1"/></div>
 <Row title="AXON-142 · Flash au démarrage" meta="priorité haute" tag="en cours" tagColor={color}/>
 <Row title="AXON-121 · Nettoyer les anciens tests" meta="terminé hier" tag="fait"/>
{/if}
<style>
 .stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:none}
</style>
