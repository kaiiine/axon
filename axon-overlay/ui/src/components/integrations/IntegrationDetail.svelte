<script lang="ts">
 import {INTEGRATIONS} from '../../integrations';
 import {model,openIntegration,demanderRaccourci,demanderDetail,demanderAxon} from '../../model';
 import GlassPanel from './GlassPanel.svelte';
 import Stat from './Stat.svelte';
 import Row from './Row.svelte';
 import Skeleton from './Skeleton.svelte';
 import DemoIntegration from './DemoIntegration.svelte';
 import Icon from '../Icon.svelte';
 export let id:string;
 $: meta=INTEGRATIONS.find(i=>i.id===id);
 $: data=meta?.action?$model.integrationData[meta.action]:undefined;
 $: aDesLignes=!!data?.rows?.length;
 $: badge=badgePour(data?.status,$model.connected,$model.demo);
 function badgePour(statut:string|undefined,connecte:boolean,demo:boolean):{texte:string;ton:'aperçu'|'direct'|'erreur'}{
  if(demo)return {texte:'Démo',ton:'aperçu'};
  if(statut==='ok')return {texte:'En direct',ton:'direct'};
  if(statut==='error')return {texte:'Erreur',ton:'erreur'};
  if(statut==='loading')return {texte:'Chargement',ton:'aperçu'};
  if(!connecte)return {texte:'Hors ligne',ton:'aperçu'};
  return {texte:'',ton:'aperçu'};
 }
 function actualiser(){if(meta?.action)demanderRaccourci(meta.action);}
 function expandRow(item:string|undefined){
  if(!meta?.action||!meta.detailAction||!item)return undefined;
  const panel=meta.action,action=meta.detailAction;
  return ()=>demanderDetail(panel,action,item);
 }
 function rowActions(item:string|undefined,title:string,rowMeta:string){
  if(id!=='gmail'||!item)return [];
  return [{label:'Générer une réponse',icon:'chat',onClick:()=>demanderAxon(
   `Relis le mail Gmail d'ID "${item}" puis rédige un brouillon de réponse adapté. Pour contexte : "${title}" — ${rowMeta}.`
  )}];
 }
</script>
{#if meta}
<GlassPanel color={meta.color} icon={meta.icon} name={meta.name} onback={()=>openIntegration(null)} badge={badge.texte} badgeTone={badge.ton}>
 {#if $model.demo}
  <DemoIntegration {id} color={meta.color}/>
 {:else if aDesLignes&&data}
  {#if data.stats?.length}<div class="stats">{#each data.stats as s}<Stat label={s.label} value={s.value} color={s.accent?meta.color:undefined}/>{/each}</div>{/if}
  {#each data.rows??[] as r}<Row title={r.title} meta={r.meta} tag={r.tag} tagColor={r.accent?meta.color:undefined}
   detail={r.detail} detailStatus={r.detailStatus} detailLabel={meta.detailLabel}
   onExpand={expandRow(r.id)} actions={rowActions(r.id,r.title,r.meta)}/>{/each}
 {:else if data?.status==='loading'}
  <Skeleton/>
 {:else if data?.status==='error'}
  <div class="error">
   <p>Impossible de charger {meta.name}.</p>
   <p class="errmsg">{data.message}</p>
   <button class="action" onclick={actualiser}><Icon name="refresh"/>Réessayer</button>
  </div>
 {:else if data?.status==='ok'}
  {#if data.stats?.length}<div class="stats">{#each data.stats as s}<Stat label={s.label} value={s.value} color={s.accent?meta.color:undefined}/>{/each}</div>{/if}
  <p class="empty">Rien de nouveau.</p>
 {:else if !meta.action}
  <p class="empty">Pas de tableau de bord pour {meta.name}.</p>
 {:else if !$model.connected}
  <p class="empty">Lance Axon pour voir tes données.</p>
 {/if}
 <div class="footer">
  <button class="ask" onclick={()=>demanderAxon(meta.ask)}><Icon name="spark"/>{meta.ask}</button>
  {#if meta.action&&$model.connected&&!$model.demo}<button class="action ghost" onclick={actualiser} title="Actualiser" aria-label="Actualiser"><Icon name="refresh"/></button>{/if}
 </div>
</GlassPanel>
{/if}
<style>
 .stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:none}
 .empty{font-size:10px;color:var(--muted);padding:14px 2px}
 .error{display:flex;flex-direction:column;gap:8px;align-items:flex-start;padding:10px 2px}
 .error p{font-size:11px;color:var(--text)}
 .error .errmsg{font-size:9px;color:var(--faint);font-family:var(--mono)}
 .action{display:flex;align-items:center;gap:6px;font-size:10px;padding:7px 11px;border-radius:8px;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;transition:transform 160ms var(--spring),background 150ms,border-color 150ms,color 150ms}
 .action:hover{background:#ffaf0014;border-color:#ffaf0040;color:#f0cf93;transform:translateY(-1px)}
 .action :global(.icon){width:12px;height:12px}
 .action.ghost{flex:none;padding:9px}
 .footer{display:flex;gap:6px;margin-top:auto;flex:none}
 .ask{flex:1;min-width:0;display:flex;align-items:center;gap:7px;font-size:10px;padding:9px 12px;border-radius:10px;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;transition:transform 160ms var(--spring),background 150ms,border-color 150ms;text-align:left}
 .ask:hover{background:#ffaf0014;border-color:#ffaf0040;transform:translateY(-1px)}
 .ask :global(.icon){width:13px;height:13px;flex:none}
</style>
