<script lang="ts">
 import {model,ouvrirEtudes,actualiserPageSuivi,demanderFlux,dernierFlux,demanderAxon,demanderDetail,creerEcheance,lierRessource} from '../model';
 import Icon from './Icon.svelte';
 import Row from './integrations/Row.svelte';
 import Skeleton from './integrations/Skeleton.svelte';
 import EcheanceRow from './EcheanceRow.svelte';
 import AjouterEcheance from './AjouterEcheance.svelte';
 import Section from './commun/Section.svelte';
 import TexteEnFlux from './commun/TexteEnFlux.svelte';
 import Calendrier from './commun/Calendrier.svelte';
 import {renderMarkdown} from '../markdown';

 const COULEURS={echeance:'#ffaf00',rappel:'#c39bff',commit:'#6ea8fe',resultat:'#7fd9a8',verification:'#f0a0a0'};
 const LIBELLES={echeance:'Échéance',rappel:'Rappel',commit:'Commit',resultat:'Fiche',verification:'Vérification'};
 const TYPES_RESSOURCE:Record<string,string>={depot_git:'Dépôt',dossier:'Dossier',document:'Document',lien:'Lien'};

 $: page=$model.pageSuivi;
 $: d=page?.donnees;

 //: Résumé IA : affiché tout de suite s'il a déjà été généré (gardé côté
 //: CLI), sinon demandé automatiquement à la première ouverture — une seule
 //: fois par suivi, puisque le flux demandé reste dans le store.
 $: flux=d?dernierFlux($model.flux,'resume_suivi',d.id):undefined;
 let resumeDemandePour:string|null=null;
 $: if(d&&!d.resume&&!flux&&$model.connected&&resumeDemandePour!==d.id)demanderResumeApres(d.id);
 //: Hors du bloc réactif : un store modifié PENDANT son exécution n'est pas
 //: relu par Svelte (c'est ce même bloc qui le lit) — le résumé restait
 //: affiché « vide » alors que le flux tournait.
 function demanderResumeApres(suiviId:string){
  resumeDemandePour=suiviId;
  queueMicrotask(()=>demanderFlux('resume_suivi',suiviId));
 }
 $: texteResume=flux?flux.texte:(d?.resume?.texte??'');
 $: statutResume=statutDuResume(flux?.statut,!!d?.resume);
 function statutDuResume(statutFlux:string|undefined,enCache:boolean):'repos'|'en_cours'|'fini'|'erreur'{
  if(statutFlux==='en_cours'||statutFlux==='fini'||statutFlux==='erreur')return statutFlux;
  return enCache?'fini':'repos';
 }
 function dateResume(iso:string):string{
  return new Date(iso).toLocaleString('fr-FR',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
 }

 function demander(intention:string){
  if(!d)return;
  demanderAxon(`${intention} « ${d.titre} » (suivi ${d.id}).`);
 }
 function ouvrirFichier(fichier:string){demanderDetail('etudes_fiches_recentes','etudes_ouvrir_fiche',fichier);}
 function metaRessource(r:{type:string;chemin:string;branche?:string;age?:string;sujet?:string}):string{
  if(r.type==='depot_git'&&r.branche)return `${r.branche} · ${r.age} · ${r.sujet}`;
  return r.chemin;
 }
 function tagRessource(r:{type:string;modifies?:number}):string{
  if(r.modifies)return `${r.modifies} non commité${r.modifies>1?'s':''}`;
  return TYPES_RESSOURCE[r.type]??r.type;
 }
</script>
<div class="page">
 <header>
  <button class="retour" onclick={ouvrirEtudes} aria-label="Retour aux études"><Icon name="back"/></button>
  <span class="mark"><Icon name="book"/></span>
  <div class="meta"><strong>{d?.titre??'…'}</strong>{#if d}<small>{d.type}</small>{/if}</div>
  <button class="refresh" onclick={actualiserPageSuivi} title="Actualiser" aria-label="Actualiser la page"><Icon name="refresh"/></button>
 </header>

 <!-- Toujours montée (vue cachée comme les autres) : rien tant qu'aucune
      page n'est demandée, sinon son squelette traînerait dans le DOM. -->
 {#if page&&!d&&page.statut==='error'}
  <p class="erreur">{page.message}</p>
 {:else if page&&!d}
  <Skeleton stats={false}/>
 {:else if d}
  <Section titre="Résumé">
   <button slot="actions" class="mini" onclick={()=>demanderFlux('resume_suivi',d.id)} disabled={statutResume==='en_cours'||!$model.connected} title="Régénérer le résumé"><Icon name="refresh"/>Régénérer</button>
   <TexteEnFlux texte={texteResume} statut={statutResume} message={flux?.message} vide="Pas encore de résumé."/>
   {#if d.resume&&statutResume!=='en_cours'}<small class="date">Mis à jour {dateResume(d.resume.date)}</small>{/if}
  </Section>

  <div class="ia">
   <button class="action" onclick={()=>demander('Vérifie l’avancement du projet, en inspectant ses dépôts et en les comparant au sujet et aux tâches :')}><Icon name="check"/>Vérifier l’avancement</button>
   <button class="action" onclick={()=>demander('Propose les prochaines tâches, d’après ses dépôts et ses échéances, pour le projet')}><Icon name="spark"/>Proposer des tâches</button>
   <button class="action" onclick={()=>demander('Faisons le point sur')}><Icon name="chat"/>Faire le point</button>
  </div>

  <Section titre="Échéances" compte={d.echeances.length}>
   <AjouterEcheance slot="actions" disabled={!$model.connected} suivis={[{id:d.id,title:d.titre}]} onCreer={creerEcheance}/>
   {#each d.echeances as e (e.id)}
    <EcheanceRow title={e.titre} meta={`${e.dateCourte} · ${e.restant}${e.rappels?` · ${e.rappels} rappel${e.rappels>1?'s':''}`:''}`} tag={e.type} suiviId={d.id} echeanceId={e.id} rappels={e.rappels}/>
   {:else}<p class="vide">Pas de date de rendu : ajoute une échéance avec le +.</p>{/each}
  </Section>

  <Section titre="Calendrier">
   <Calendrier evenements={d.calendrier} couleurs={COULEURS} libelles={LIBELLES}/>
  </Section>

  <Section titre="Dépôts et ressources" compte={d.ressources.length}>
   <div slot="actions" class="actions-ressources">
    <button class="mini" onclick={()=>lierRessource(d.id,'fichier')} disabled={!$model.connected} aria-label="Ajouter un fichier"><Icon name="paperclip"/></button>
    <button class="mini" onclick={()=>lierRessource(d.id,'dossier')} disabled={!$model.connected} aria-label="Ajouter un dossier ou un dépôt"><Icon name="folder"/></button>
   </div>
   {#each d.ressources as r (r.id)}<Row title={r.nom} meta={metaRessource(r)} tag={tagRessource(r)}/>
   {:else}<p class="vide">Aucune ressource liée.</p>{/each}
  </Section>

  <Section titre="Tâches" compte={d.taches.length}>
   {#each d.taches as t (t.id)}<Row title={t.titre} meta="" tag={t.statut==='fait'?'Fait':'À faire'}/>
   {:else}<p class="vide">Aucune tâche.</p>{/each}
  </Section>

  {#if d.resultats.length}
   <Section titre="Fiches et exercices" compte={d.resultats.length}>
    {#each d.resultats as r}<Row title={r.fichier} meta={r.date} tag={r.type} actions={[{label:'Ouvrir',icon:'file',onClick:()=>ouvrirFichier(r.fichier)}]}/>{/each}
   </Section>
  {/if}

  {#if d.verification}
   <Section titre={`Dernière vérification · ${d.verification.date}`}>
    <div class="md">{@html renderMarkdown(d.verification.texte)}</div>
   </Section>
  {/if}
 {/if}
</div>
<style>
 .page{height:100%;display:flex;flex-direction:column;gap:10px;min-height:0;overflow:auto;padding:1px}
 header{display:flex;align-items:center;gap:10px;flex:none}
 .retour,.refresh{width:26px;height:26px;border-radius:9px;display:grid;place-items:center;color:var(--muted);background:#ffffff07;flex:none}
 .retour:hover,.refresh:hover{background:#ffffff10;color:var(--text)}
 .retour :global(.icon),.refresh :global(.icon){width:12px;height:12px}
 .mark{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;color:#dfb86e;background:#ffaf0014;border:1px solid #ffaf0030;flex:none}
 .meta{min-width:0;flex:1}
 .meta strong{display:block;font-size:13px;font-weight:600;letter-spacing:-.1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .meta small{color:var(--muted);font-size:10px}
 .ia{display:flex;gap:6px;flex:none;flex-wrap:wrap}
 .action{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;font-size:10px;padding:8px 10px;border-radius:10px;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;white-space:nowrap;transition:transform 160ms var(--spring),background 150ms,border-color 150ms}
 .action:hover{background:#ffaf0014;border-color:#ffaf0040;transform:translateY(-1px)}
 .action :global(.icon){width:12px;height:12px}
 .mini{display:flex;align-items:center;gap:5px;font-size:9.5px;padding:4px 8px;border-radius:8px;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e}
 .mini:hover:not(:disabled){background:#ffaf0014;border-color:#ffaf0040}
 .mini :global(.icon){width:11px;height:11px}
 .actions-ressources{display:flex;gap:5px}
 .date{font-size:9px;color:var(--faint)}
 .vide{font-size:10px;color:var(--muted)}
 .erreur{font-size:11px;color:#e68a8a}
 .md{font-size:10.5px;line-height:1.6;color:#c7c9d4}
 .md :global(p){margin:0 0 6px}
</style>
