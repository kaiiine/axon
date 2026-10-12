<script lang="ts">
 import Icon from '../Icon.svelte';
 import {renderMarkdown} from '../../markdown';
 export let title:string;
 export let meta:string;
 export let tag:string|undefined=undefined;
 export let tagColor:string|undefined=undefined;
 export let detail:string|undefined=undefined;
 export let detailStatus:'loading'|'ok'|'error'|undefined=undefined;
 export let detailLabel:string='Résumer';
 export let onExpand:(()=>void)|undefined=undefined;
 //: Fourni : le titre de la ligne devient un lien (ex. ouvrir la page
 //: d'un projet) plutôt qu'un simple texte.
 export let onOpen:(()=>void)|undefined=undefined;
 //: Actions révélées au survol, en plus du résumé — ex. "Générer une
 //: réponse" sur Gmail. Ce composant ne sait rien de Gmail/Jira : c'est
 //: IntegrationDetail qui les fournit, service par service.
 //: `disabled` — ex. une génération en cours (§1, lot 3) : l'action reste
 //: visible (on voit qu'il y a quelque chose en train de se passer) mais
 //: n'est pas cliquable, plutôt que disparaître ou rester cliquable sans effet.
 export let actions:{label:string;icon:string;onClick:()=>void;disabled?:boolean;danger?:boolean}[]=[];
 //: Une ligne est dépliable si on a déjà de quoi afficher (Workspace, détail
 //: prérempli) OU un moyen d'aller le chercher (Gmail/Jira, à la demande).
 $: canExpand=detail!==undefined||onExpand!==undefined;
 let open=false;
 function toggleExpand(){
  if(!open&&detail===undefined&&onExpand&&detailStatus!=='loading')onExpand();
  open=!open;
 }
</script>
<div class="row" class:open>
 <div class="content">
  {#if onOpen}<button class="text ouvrir" onclick={onOpen} title={`Ouvrir ${title}`}><b>{title}</b><span>{meta}</span></button>
  {:else}<div class="text"><b>{title}</b><span>{meta}</span></div>{/if}
  {#if tag}<!-- --c toujours réécrit : hérité sinon du GlassPanel parent, voir Stat.svelte --><i style={`--c:${tagColor??'#9395a0'}`}>{tag}</i>{/if}
  {#if canExpand||actions.length}
   <div class="row-actions">
    {#each actions as a}<button class="row-action" class:danger={a.danger} disabled={a.disabled} title={a.label} aria-label={a.label} onclick={a.onClick}><Icon name={a.icon}/></button>{/each}
    {#if canExpand}<button class="row-action expand-toggle" class:active={open} title={open?'Replier':detailLabel} aria-label={open?'Replier':detailLabel} aria-expanded={open} onclick={toggleExpand}><Icon name="spark"/></button>{/if}
   </div>
  {/if}
 </div>
 {#if open}
  <!-- Classe "expand", pas "detail" : App.svelte a déjà .mascot-position.detail
       et IntegrationDetail a .error .errmsg — querySelector('.detail') dans les
       tests attrapait le mascot, pas cette ligne. -->
  <div class="expand">
   {#if detailStatus==='loading'}<span class="state">chargement…</span>
   {:else if detailStatus==='error'}<span class="state err">{detail}</span>
   {:else if detail}<div class="md">{@html renderMarkdown(detail)}</div>
   {/if}
  </div>
 {/if}
</div>
<style>
 .row{padding:9px 11px;background:#ffffff05;border:1px solid #ffffff08;border-top-color:#ffffff14;border-radius:10px;transition:background 150ms,border-color 150ms}
 .row:hover{background:#ffffff09;border-color:#ffffff20}
 .content{display:flex;align-items:center;gap:8px;width:100%}
 .text{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}
 .text.ouvrir{text-align:left;align-items:stretch}
 .text.ouvrir:hover b{color:#f0cf93}
 .text b{font-size:11px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .text span{font-size:9px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .row i{font-style:normal;font-size:8px;font-weight:600;padding:3px 7px;border-radius:20px;background:color-mix(in srgb,var(--c,#9395a0) 18%,#ffffff08);color:var(--c,#b0b2bc);flex:none}
 .row-actions{display:flex;gap:4px;flex:none;max-width:0;overflow:hidden;opacity:0;transform:translateX(-2px);transition:opacity 150ms,transform 150ms,max-width 150ms}
 /* max-width : cachées, elles ne réservent pas de place — l'étiquette reste calée à droite. */
 .row:hover .row-actions,.row-actions:focus-within{max-width:260px;opacity:1;transform:translateX(0)}
 .row.open .row-actions{max-width:260px;opacity:1;transform:translateX(0)} /* repliable sans re-survoler */
 .row-action{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;border:1px solid #ffaf0024;background:#ffaf0009;color:#dfb86e;flex:none;transition:transform 150ms var(--spring),background 150ms,border-color 150ms,color 150ms}
 .row-action:hover:not(:disabled){background:#ffaf0014;border-color:#ffaf0040;color:#f0cf93;transform:translateY(-1px)}
 .row-action:disabled{opacity:.4;cursor:default}
 .row-action.active{background:#ffaf001f;border-color:#ffaf0050;color:#f0cf93}
 .row-action.danger{border-color:#e68a8a55;background:#ff52521a;color:#f0a0a0}
 .row-action.danger:hover:not(:disabled){background:#ff525230;border-color:#e68a8a90;color:#ffc0c0}
 .row-action :global(.icon){width:12px;height:12px}
 .expand{margin-top:9px;padding-top:9px;border-top:1px solid #ffffff0a;animation:expandIn 180ms var(--spring-soft) both}
 @keyframes expandIn{0%{opacity:0;transform:translateY(-3px)}100%{opacity:1;transform:translateY(0)}}
 .state{font-size:10px;color:var(--muted)}
 .state.err{color:#e68a8a}
 .md{font-size:10.5px;line-height:1.6;color:#c7c9d4}
 .md :global(p){margin:0 0 6px}
 .md :global(p:last-child){margin-bottom:0}
 .md :global(strong){color:#e2e4eb;font-weight:600}
 .md :global(a){color:var(--accent);text-decoration:underline;text-underline-offset:2px}
 .md :global(h1),.md :global(h2),.md :global(h3){font-size:11px;font-weight:600;color:#e2e4eb;margin:0 0 6px}
 .md :global(ul),.md :global(ol){margin:0 0 6px;padding-left:16px}
 .md :global(code){font:9.5px var(--mono);background:#ffffff0d;padding:1px 4px;border-radius:4px}
 .md :global(.table-wrap){margin:6px 0;overflow-x:auto;border:1px solid #ffffff0f;border-radius:8px}
 .md :global(table){border-collapse:collapse;width:100%;font-size:9.5px}
 .md :global(th),.md :global(td){padding:5px 8px;text-align:left;border-bottom:1px solid #ffffff0a;white-space:nowrap}
 .md :global(th:last-child),.md :global(td:last-child){white-space:normal}
 .md :global(th){background:#ffffff06;color:#c7c9d4;font-weight:600}
 .md :global(tr:last-child td){border-bottom:none}
</style>
