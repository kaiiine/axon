<script lang="ts">
 import Icon from './Icon.svelte';
 import {model,navigate,openIntegration} from '../model';
 import {INTEGRATIONS} from '../integrations';
 import {LIBELLES_ETAT} from '../etat';

 $: last=$model.activity.at(-1);
 $: shownState=$model.requests.length?'waiting':$model.state;
 $: detail=sousTitre($model.detail,LIBELLES_ETAT[shownState],last?.name);
 //: `detail` répète souvent le libellé d'état ou le nom de l'outil déjà
 //: affiché juste en dessous : dans ces cas, pas de sous-titre.
 function sousTitre(texte:string,libelleEtat:string,outil:string|undefined):string{
  if(!texte||texte===libelleEtat||texte===outil)return '';
  return texte;
 }
</script>
<section class="overview">
 <button class="panel session" onclick={()=>navigate($model.file?'code':'chat')} title={$model.file?'Ouvrir le fichier':'Ouvrir la conversation'}>
  <div class="who"><i class:online={$model.connected}></i><strong>axon</strong><span>{$model.connected?'connecté':'hors ligne'}</span></div>
  <h1>{LIBELLES_ETAT[shownState]}</h1>
  {#if detail}<p class="description">{detail}</p>{/if}
  <div class="snippet"><Icon name={last?'code':'chat'}/><span>{last?.detail||'Ouvrir la conversation'}</span><Icon name="arrow"/></div>
  {#if last}<span class="session-note">{last.name}</span>{/if}
 </button>
 <div class="panel providers">
  <div class="providers-head"><span>intégrations</span><i>✦</i></div>
  <div class="pills">
   {#each INTEGRATIONS as p}<button class="pill" style={`--pill:${p.color}`} onclick={()=>openIntegration(p.id)} title={p.name}><span class="mark"><Icon name={p.icon}/></span><span>{p.name}</span></button>{/each}
  </div>
  <button class="explore" onclick={()=>navigate('integrations')}>tout voir <Icon name="arrow"/></button>
 </div>
</section>
<style>
.overview{display:grid;grid-template-columns:58% 1fr;gap:11px;height:100%}.session{position:relative;width:100%;padding:20px 20px 18px 187px;text-align:left;display:flex;flex-direction:column;justify-content:center;background:radial-gradient(ellipse at 15% 65%,#ffc3690a,transparent 60%),linear-gradient(125deg,#ffffff08,#ffffff03)}.who{display:flex;align-items:center;gap:6px;white-space:nowrap;font-size:11px;margin-bottom:12px}.who i{width:5px;height:5px;border-radius:50%;background:#8f8b91}.who i.online{background:#ffc35e;box-shadow:0 0 10px #ffc35e55}.who strong{font-weight:600;letter-spacing:.4px}.who span{color:#aaa6b0;font-size:9px;margin-left:3px}h1{font-size:22px;font-weight:500;letter-spacing:-.9px;line-height:1.25;color:#f4efe5;white-space:nowrap;margin-bottom:14px}.description{font-size:10px;color:#aca6b2;margin:-7px 0 14px;line-height:1.5}.snippet{display:flex;gap:8px;align-items:center;border:1px solid #ffffff12;border-radius:16px;padding:10px;color:#d0bec3;background:linear-gradient(115deg,#ffffff09,#ffffff02);font:9px var(--mono);min-width:0}.snippet :global(.icon){width:12px;height:12px;color:#dfb982}.snippet span{display:block;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.session:hover .snippet{background:#ffffff0b;border-color:#ffdcab2e}.session-note{color:#96909b;font:8px var(--mono);margin-top:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.providers{display:flex;flex-direction:column;justify-content:center;padding:18px 18px 15px}.providers-head{display:flex;align-items:center;justify-content:space-between;font:9px var(--mono);color:#b4adb9;margin-bottom:15px}.providers-head i{color:#9e8eb4;font-size:12px;font-style:normal}.pills{display:grid;grid-template-columns:1fr 1fr;gap:9px}.pill{height:36px;border:1px solid #ffffff0c;background:linear-gradient(130deg,#ffffff0a,#ffffff02);border-radius:22px;display:flex;align-items:center;gap:5px;color:#c3bdca;font-size:10px;box-shadow:inset 0 1px 0 #ffffff06}.pill:hover{border-color:var(--pill);background:#ffffff0d;box-shadow:0 0 16px #ffffff04}.mark{margin-left:10px;color:var(--pill);background:#ffffff05;border-radius:50%;padding:4px}.mark :global(.icon){width:12px;height:12px}.pill>span:last-child{flex:1;text-align:center;padding-right:8px}.explore{display:flex;gap:7px;align-items:center;color:#aaa0b4;font-size:9px;margin:16px auto 0}.explore :global(.icon){width:11px;height:11px}.explore:hover{color:#f0dfc2}@media(max-width:590px){.overview{grid-template-columns:62% 1fr;gap:7px}.session{padding-left:139px;padding-right:12px}h1{font-size:18px}.description{font-size:9px}.providers{padding:12px 9px}.pills{grid-template-columns:1fr;gap:5px}.pill{height:29px}.providers-head{font-size:8px;margin-bottom:8px}.explore{font-size:8px;margin-top:9px}.providers-head i{display:none}.session-note{font-size:7px}}
</style>
