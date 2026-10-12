<script lang="ts">
 import Icon from '../Icon.svelte';
 import {casesDuMois,isoLocal} from '../../calendrier';
 import type {EvenementCalendrier} from '../../types';
 //: Calendrier mensuel générique : des événements datés (`date` ISO), un
 //: point coloré par genre sur chaque jour, la liste du jour choisi dessous.
 export let evenements:EvenementCalendrier[]=[];
 export let couleurs:Record<string,string>={};
 export let libelles:Record<string,string>={};

 const aujourdhui=isoLocal(new Date());
 let affiche=new Date();
 let choisi=aujourdhui;

 $: annee=affiche.getFullYear();
 $: mois=affiche.getMonth();
 $: cases=casesDuMois(annee,mois);
 $: titreMois=affiche.toLocaleDateString('fr-FR',{month:'long',year:'numeric'});
 $: parJour=grouper(evenements);
 $: duJour=parJour.get(choisi)??[];

 function grouper(liste:EvenementCalendrier[]):Map<string,EvenementCalendrier[]>{
  const carte=new Map<string,EvenementCalendrier[]>();
  for(const ev of liste){
   const jour=carte.get(ev.date)??[];
   jour.push(ev);
   carte.set(ev.date,jour);
  }
  return carte;
 }
 //: `carte` passée en argument : lue dans le corps, Svelte ne verrait pas
 //: qu'elle change et ne redessinerait pas les points.
 function genresDuJour(carte:Map<string,EvenementCalendrier[]>,iso:string):string[]{
  return [...new Set((carte.get(iso)??[]).map(ev=>ev.genre))].slice(0,3);
 }
 function changerMois(delta:number){affiche=new Date(annee,mois+delta,1);}
 function revenirAujourdhui(){affiche=new Date();choisi=aujourdhui;}
</script>
<div class="calendrier">
 <div class="nav">
  <button onclick={()=>changerMois(-1)} aria-label="Mois précédent"><Icon name="back"/></button>
  <button class="mois" onclick={revenirAujourdhui} title="Revenir à aujourd’hui">{titreMois}</button>
  <button class="suivant" onclick={()=>changerMois(1)} aria-label="Mois suivant"><Icon name="back"/></button>
 </div>
 <div class="grille" role="grid" aria-label={titreMois}>
  {#each ['L','M','M','J','V','S','D'] as j}<span class="entete">{j}</span>{/each}
  {#each cases as c (c.iso)}
   <button class="jour" class:hors={!c.dansLeMois} class:aujourdhui={c.iso===aujourdhui} class:choisi={c.iso===choisi} onclick={()=>choisi=c.iso} aria-label={c.iso}>
    {c.jour}
    <span class="points">{#each genresDuJour(parJour,c.iso) as g}<i style={`--c:${couleurs[g]??'#9395a0'}`}></i>{/each}</span>
   </button>
  {/each}
 </div>
 <div class="liste">
  {#each duJour as ev}<div class="evenement"><i style={`--c:${couleurs[ev.genre]??'#9395a0'}`}></i><span>{ev.libelle}</span><small>{libelles[ev.genre]??ev.genre}</small></div>
  {:else}<p class="vide">Rien ce jour-là</p>{/each}
 </div>
</div>
<style>
 .calendrier{display:flex;flex-direction:column;gap:6px}
 .nav{display:flex;align-items:center;gap:4px}
 .nav button{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;color:var(--muted)}
 .nav button:hover{background:#ffffff0a;color:var(--text)}
 .nav :global(.icon){width:11px;height:11px}
 .nav .suivant :global(.icon){transform:rotate(180deg)}
 .nav .mois{flex:1;width:auto;font-size:10.5px;color:var(--text);text-transform:capitalize}
 .grille{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
 .entete{font-size:8.5px;color:var(--faint);text-align:center;padding-bottom:2px}
 .jour{position:relative;height:26px;border-radius:7px;font-size:10px;color:#c3c5cf;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border:1px solid transparent;transition:background 150ms,border-color 150ms}
 .jour:hover{background:#ffffff08}
 .jour.hors{color:#ffffff30}
 .jour.aujourdhui{border-color:#ffaf0050;color:#f0cf93}
 .jour.choisi{background:#ffaf0014;border-color:#ffaf0040}
 .points{display:flex;gap:2px;height:4px}
 .points i{width:4px;height:4px;border-radius:50%;background:var(--c)}
 .liste{display:flex;flex-direction:column;gap:4px;min-height:20px}
 .evenement{display:flex;align-items:center;gap:7px;font-size:10px}
 .evenement i{width:6px;height:6px;border-radius:50%;background:var(--c);flex:none}
 .evenement span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .evenement small{color:var(--faint);font-size:9px;flex:none}
 .vide{font-size:10px;color:var(--faint)}
</style>
