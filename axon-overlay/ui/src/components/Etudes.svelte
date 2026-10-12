<script lang="ts">
 import {model,demanderAxon,demanderPicker,detacherPiece,demanderRaccourci,demanderDetail,creerSuivi,creerEcheance,archiverSuivi} from '../model';
 import Icon from './Icon.svelte';
 import AttachmentChip from './AttachmentChip.svelte';
 import CreerSuivi from './CreerSuivi.svelte';
 import AjouterEcheance from './AjouterEcheance.svelte';
 import EcheanceRow from './EcheanceRow.svelte';
 import Row from './integrations/Row.svelte';
 import Skeleton from './integrations/Skeleton.svelte';

 const ACTION_RECENTS='etudes_fiches_recentes';
 const ACTION_SUIVIS='etudes_suivis';
 const ACTION_ECHEANCES='etudes_echeances';
 $: recents=$model.integrationData[ACTION_RECENTS];
 $: suivis=$model.integrationData[ACTION_SUIVIS];
 $: echeances=$model.integrationData[ACTION_ECHEANCES];
 //: Les images (captures d'écran, photos) n'ont pas de sens pour une fiche
 //: ou des exercices générés depuis un contenu — seuls les documents texte
 //: comptent pour activer le travail rapide.
 $: documents=$model.attachments.filter(a=>!a.estImage);

 function actualiserTout(){demanderRaccourci(ACTION_RECENTS);demanderRaccourci(ACTION_SUIVIS);demanderRaccourci(ACTION_ECHEANCES);}
 function ouvrirResultat(nom:string){demanderDetail(ACTION_RECENTS,'etudes_ouvrir_fiche',nom);}
 function actionsResultat(nom:string){return [{label:'Ouvrir',icon:'file',onClick:()=>ouvrirResultat(nom)}];}

 //: Plus de verrou LOCAL à durée fixe (§1, lot 3) : le backend garde l'état
 //: réel de chaque génération (`src/agents/study/store.py::generation_active`)
 //: et le pousse dans `suivis.rows[].generationFicheStatut`/`generationExoStatut`
 //: (ou `recents.generationFicheStatut`/… pour le travail rapide, suivi_id
 //: absent) — un changement d'onglet ou une reconnexion retrouve donc le
 //: VRAI statut, pas une estimation locale qui expire après 2,5s.
 function lancerGeneration(prompt:string){demanderAxon(prompt);}

 function libelleQuickWork(type:'fiche'|'exo'):string{
  const statut=type==='fiche'?recents?.generationFicheStatut:recents?.generationExoStatut;
  if(statut==='en_cours')return 'Génération…';
  if(statut==='terminee')return type==='fiche'?'Ouvrir la fiche':'Ouvrir les exercices';
  if(statut==='echouee')return type==='fiche'?'Réessayer la fiche':'Réessayer les exercices';
  return type==='fiche'?'Générer une fiche':'Générer des exercices';
 }
 function clicQuickWork(type:'fiche'|'exo'){
  const statut=type==='fiche'?recents?.generationFicheStatut:recents?.generationExoStatut;
  const fichier=type==='fiche'?recents?.generationFicheFichier:recents?.generationExoFichier;
  if(statut==='en_cours')return;
  if(statut==='terminee'&&fichier){ouvrirResultat(fichier);return;}
  lancerGeneration(`/${type}`);
 }

 //: « Créer une fiche »/« Générer des exercices » depuis UN suivi utilisent
 //: directement ses ressources déjà associées — pas besoin de re-/attach.
 //: Même mécanisme que `demanderAxon` : navigue au chat, où la clarification
 //: QCM/ouvert/mixte (si /exo) et le résultat final apparaissent normalement.
 function detailSuivi(id:string){demanderDetail(ACTION_SUIVIS,'etudes_detail_suivi',id);}
 function actionBoutonSuivi(id:string,type:'fiche'|'exo',labelDepart:string,icone:string,statut?:string,fichier?:string){
  if(statut==='en_cours')return {label:'Génération en cours',icon:icone,disabled:true,onClick:()=>{}};
  if(statut==='terminee'&&fichier)return {label:'Ouvrir le résultat',icon:'file',onClick:()=>ouvrirResultat(fichier)};
  if(statut==='echouee')return {label:'Réessayer',icon:'refresh',onClick:()=>lancerGeneration(`/${type} ${id}`)};
  return {label:labelDepart,icon:icone,onClick:()=>lancerGeneration(`/${type} ${id}`)};
 }
 function actionsSuivi(r:{id?:string;generationFicheStatut?:string;generationFicheFichier?:string;generationExoStatut?:string;generationExoFichier?:string}){
  const id=r.id??'';
  return [
   actionBoutonSuivi(id,'fiche','Créer une fiche','file',r.generationFicheStatut,r.generationFicheFichier),
   actionBoutonSuivi(id,'exo','Générer des exercices','spark',r.generationExoStatut,r.generationExoFichier),
   {label:'Archiver',icon:'flag',onClick:()=>archiverSuivi(id)},
  ];
 }
 //: Pour peupler le sélecteur de suivi d'AjouterEcheance.svelte — une
 //: échéance appartient toujours à un suivi existant (§3, lot 3).
 $: suivisPourSelect=(suivis?.rows??[]).map(r=>({id:r.id??'',title:r.title}));
</script>
<div class="etudes">
 <header>
  <span class="mark"><Icon name="book"/></span>
  <div class="meta"><strong>Études</strong></div>
  <button class="refresh" onclick={actualiserTout} title="Actualiser" aria-label="Actualiser"><Icon name="refresh"/></button>
 </header>

 <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
 <div class="drop" class:actif={$model.dragActif} onclick={demanderPicker} title="Travail rapide : un document, sans créer de suivi">
  <Icon name="paperclip"/>
  <p>Déposer un document ou cliquer pour parcourir</p>
 </div>
 {#if $model.attachments.length}
  <div class="attachments" aria-label="Documents attachés">
   {#each $model.attachments as a (a.nom)}<AttachmentChip nom={a.nom} statut={a.statut} message={a.message} taille={a.taille} onRemove={()=>detacherPiece(a.nom)}/>{/each}
  </div>
 {/if}
 {#if documents.length}
  <!-- Classe "etudes-actions", pas "actions" : Header.svelte a déjà un
       .actions — même piège que .row/.detail/.glass ailleurs dans ce projet. -->
  <div class="etudes-actions">
   <button class="action" disabled={recents?.generationFicheStatut==='en_cours'} onclick={()=>clicQuickWork('fiche')}><Icon name="file"/>{libelleQuickWork('fiche')}</button>
   <button class="action" disabled={recents?.generationExoStatut==='en_cours'} onclick={()=>clicQuickWork('exo')}><Icon name="spark"/>{libelleQuickWork('exo')}</button>
  </div>
 {/if}

 <!-- Les lignes déjà chargées restent affichées pendant une actualisation :
      le squelette n'apparaît que s'il n'y a encore rien à montrer. -->
 <section>
  <div class="section-head"><span>Suivis</span><CreerSuivi disabled={!$model.connected} onCreer={creerSuivi}/></div>
  {#if suivis?.rows?.length}
   {#each suivis.rows as r}
    <Row title={r.title} meta={r.meta} tag={r.tag} detail={r.detail} detailStatus={r.detailStatus}
         detailLabel="Détail" onExpand={()=>detailSuivi(r.id??'')} actions={actionsSuivi(r)}/>
   {/each}
  {:else if suivis?.status==='loading'}
   <Skeleton stats={false}/>
  {:else if suivis?.status==='error'}
   <p class="empty error">{suivis.message}</p>
  {:else}
   <p class="empty">Aucun suivi</p>
  {/if}
 </section>

 <section>
  <div class="section-head"><span>Échéances</span><AjouterEcheance disabled={!$model.connected} suivis={suivisPourSelect} onCreer={creerEcheance}/></div>
  {#if echeances?.rows?.length}
   {#each echeances.rows as r}<EcheanceRow title={r.title} meta={r.meta} tag={r.tag} suiviId={r.suiviId??''} echeanceId={r.id??''}/>{/each}
  {:else if echeances?.status==='loading'}
   <Skeleton stats={false}/>
  {:else if echeances?.status==='error'}
   <p class="empty error">{echeances.message}</p>
  {:else}
   <p class="empty">Aucune échéance à venir</p>
  {/if}
 </section>

 <section class="grow">
  <div class="section-head"><span>Récents</span></div>
  {#if recents?.rows?.length}
   {#each recents.rows as r}<Row title={r.title} meta={r.meta} tag={r.tag} actions={actionsResultat(r.id??r.title)}/>{/each}
  {:else if recents?.status==='loading'}
   <Skeleton stats={false}/>
  {:else if recents?.status==='error'}
   <p class="empty error">{recents.message}</p>
  {:else}
   <p class="empty">Aucune fiche ni exercice</p>
  {/if}
 </section>
</div>
<style>
 .etudes{height:100%;display:flex;flex-direction:column;gap:11px;min-height:0;overflow:auto;padding:1px}
 header{display:flex;align-items:center;gap:10px;flex:none}
 .mark{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;color:#dfb86e;background:#ffaf0014;border:1px solid #ffaf0030;flex:none}
 .meta{min-width:0;flex:1}
 .meta strong{display:block;font-size:13px;font-weight:600;letter-spacing:-.1px}
 .drop{flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:18px 14px;border:1.5px dashed #ffffff20;border-radius:16px;color:var(--muted);text-align:center;cursor:pointer;transition:background 150ms,border-color 150ms,color 150ms}
 .drop:hover{background:#ffffff05;color:var(--text)}
 .drop.actif{background:#ffaf0014;border-color:#ffaf0060;color:#dfb86e}
 .drop :global(.icon){width:18px;height:18px}
 .drop p{font-size:10.5px;max-width:300px}
 .attachments{display:flex;flex-wrap:wrap;gap:6px;flex:none}
 .etudes-actions{display:flex;gap:8px;flex:none}
 .action{flex:1;display:flex;align-items:center;justify-content:center;gap:7px;font-size:10px;padding:9px 10px;border-radius:10px;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;transition:transform 160ms var(--spring),background 150ms,border-color 150ms}
 .action:hover:not(:disabled){background:#ffaf0014;border-color:#ffaf0040;transform:translateY(-1px)}
 .action:disabled{opacity:.45}
 .action :global(.icon){width:12px;height:12px}
 section{flex:none;display:flex;flex-direction:column;gap:8px}
 section.grow{flex:1;min-height:0}
 .section-head{font-size:10px;color:var(--muted);flex:none;display:flex;align-items:center;justify-content:space-between}
 .refresh{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;color:var(--muted);flex:none;margin-left:auto}
 .refresh:hover{background:#ffffff0a;color:var(--text)}
 .refresh :global(.icon){width:11px;height:11px}
 .empty{font-size:10px;color:var(--muted);padding:10px 2px}
 .empty.error{color:#e68a8a}
</style>
