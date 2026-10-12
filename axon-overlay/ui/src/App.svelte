<script lang="ts">
 import {entrance,arrival,finishEntrance} from './entrance';
 import {model,navigate,close,notice,prepareSound} from './model';import Header from './components/Header.svelte';import MascotStage from './components/MascotStage.svelte';import Overview from './components/Overview.svelte';import Chat from './components/Chat.svelte';import Code from './components/Code.svelte';import Settings from './components/Settings.svelte';import Etudes from './components/Etudes.svelte';import Icon from './components/Icon.svelte';
 $: shownState=$model.requests.length?'waiting':$model.state;
 const labels={idle:'disponible',thinking:'réflexion',working:'en cours',waiting:'à toi de jouer',finished:'terminé',sleeping:'en veille',error:'à vérifier'};
 function key(e:KeyboardEvent){if(e.key==='Escape'){e.preventDefault();if($model.notice)notice('');else if($model.view!=='home')navigate('home');else close();}}
 //: Pendant l'arrivée, header/rail/vues sont en pointer-events:none (voir
 //: .introducing plus bas) : un clic traverse jusqu'à .island. On ne fait
 //: qu'accélérer l'animation déjà en cours (voir entrance.ts) — elle termine
 //: sa trajectoire au lieu de se figer, et finishEntrance() suit comme à
 //: l'accoutumée, fondu CSS existant compris.
 let skipEntree=0;
 function passerEntree(){if($entrance==='playing')skipEntree++;}
</script>
<svelte:window onkeydown={key} onpointerdown={prepareSound}/>
<div class="island" class:introducing={$entrance!=='rest'} class:arriving={$entrance==='playing'} class:reduced={!$model.motion} class:paused={!$model.visible} data-state={shownState} data-view={$model.view}>
 <div class="glass" aria-hidden="true"></div>
 <Header/>
 {#if $entrance==='playing'}<button class="skip-entree" onclick={passerEntree} aria-label="Passer l’arrivée"></button>{/if}
 <main>
  <div class="mascot-position" class:detail={$model.view!=='home'}><div class="arrival-flight" use:arrival={{phase:$entrance,done:finishEntrance,skip:skipEntree}}><MascotStage state={shownState} motion={$model.motion} visible={$model.visible} entering={$entrance!=='rest'}/></div></div>
  <div class="rail" hidden={$model.view==='home'}><strong>axon</strong><span class="status"><i></i>{labels[shownState]}</span><button onclick={()=>navigate('code')} class:current={$model.view==='code'}><Icon name="code"/>fichiers</button><button onclick={()=>navigate('chat')} class:current={$model.view==='chat'}><Icon name="chat"/>conversation</button></div>
  <div class="view home" hidden={$model.view!=='home'}><Overview/></div>
  <div class="view expanded" hidden={$model.view!=='chat'}><Chat/></div>
  <div class="view expanded" hidden={$model.view!=='code'}><Code/></div>
  <div class="view expanded" hidden={$model.view!=='settings'}><Settings/></div>
  <div class="view expanded" hidden={$model.view!=='integrations'}><Settings integrations/></div>
  <div class="view expanded" hidden={$model.view!=='etudes'}><Etudes/></div>
  {#if $model.requests.length&&$model.view!=='chat'}<button class="pending" onclick={()=>navigate('chat')}>Réponse attendue ↗</button>{/if}
 </main>
 {#if $model.notice}<div class="notice" role="status"><span>{$model.notice}</span><button onclick={()=>notice('')} aria-label="Fermer le message"><Icon name="close"/></button></div>{/if}
</div>
<style>
.arrival-flight{width:100%;height:100%;transform-origin:50% 46%}.skip-entree{position:absolute;inset:0;z-index:6;background:transparent;border:none;cursor:pointer}.introducing .glass{opacity:0;transition:none}.introducing :global(header),.introducing .view,.introducing .rail{opacity:0;visibility:hidden;pointer-events:none;transform:translateY(6px);transition:none}.introducing .mascot-position{z-index:5;transition:none;pointer-events:none}
.glass{position:absolute;inset:-1px;border-radius:inherit;pointer-events:none;opacity:1;transition:opacity 700ms cubic-bezier(.22,1,.36,1)}.view,.rail{opacity:1;transform:translateY(0);transition:opacity 650ms 100ms cubic-bezier(.22,1,.36,1),transform 750ms 100ms cubic-bezier(.22,1,.36,1)}:global(.island>header){opacity:1;transition:opacity 600ms 80ms ease;transform:none}
.island{height:100%;display:flex;flex-direction:column;padding:9px 13px 13px;isolation:isolate;border:1px solid transparent;border-radius:32px;overflow:hidden;position:relative}.glass{background:radial-gradient(ellipse at 8% 105%,#ffb34b0e,transparent 44%),linear-gradient(125deg,#35323d8c,#1719237d 55%,#27243680);border:1px solid #ffffff22;border-radius:inherit;backdrop-filter:blur(30px) saturate(145%);-webkit-backdrop-filter:blur(30px) saturate(145%);box-shadow:inset 0 1px 0 #ffffff19,inset 0 -1px 0 #ffffff05}.glass:before{content:"";position:absolute;top:0;left:12%;right:24%;height:1px;background:linear-gradient(90deg,transparent,#ffffff66,transparent);pointer-events:none}main{position:relative;flex:1;min-height:0}.view{height:100%;min-height:0}.expanded{margin-left:188px;padding:18px;background:linear-gradient(135deg,#ffffff07,#13172038);border:1px solid #ffffff0e;border-radius:25px;box-shadow:inset 0 1px 0 #ffffff08}.mascot-position{position:absolute;left:0;top:calc(50% - 91px);width:184px;height:184px;z-index:2;transition:top 300ms cubic-bezier(.2,.8,.2,1)}.mascot-position.detail{top:5px}.rail{position:absolute;left:0;top:195px;width:188px;padding:0 24px;display:flex;flex-direction:column;gap:9px;z-index:2}.rail strong{font-size:19px;font-weight:550;letter-spacing:-.7px}.status{display:flex;align-items:center;gap:6px;font:9px var(--mono);color:var(--muted);margin-bottom:18px}.status i{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 9px #ffaf0044}.rail button{display:flex;align-items:center;gap:8px;padding:9px 11px;font-size:10px;color:#9299a8;text-align:left;border:1px solid transparent;border-radius:18px}.rail button.current{color:#e6e7ee;background:#ffffff09;border-color:#ffffff0a}.rail button:hover{background:#ffffff0a}.pending{position:absolute;bottom:8px;left:8px;z-index:3;font-size:10px;padding:8px 12px;background:#48361cdd;border:1px solid #ffaf0030;border-radius:20px;color:#eed3a3}.notice{position:absolute;bottom:18px;left:22px;right:22px;background:#292c39ed;border:1px solid #ffffff1a;border-radius:20px;padding:14px;z-index:8;display:flex;align-items:center;gap:12px;font-size:11px;backdrop-filter:blur(16px)}.notice span{flex:1}.notice button{color:var(--muted)}.reduced :global(*),.paused :global(*){animation:none!important;transition:none!important}@media(max-width:590px){.island{padding:7px 9px 10px;border-radius:27px}.mascot-position{width:138px;height:158px;top:calc(50% - 79px)}.expanded{margin-left:139px;padding:13px;border-radius:22px}.rail{width:139px;top:171px;padding:0 12px}.rail button{font-size:9px;padding:8px}.rail strong{font-size:16px}}@media(prefers-reduced-motion:reduce){.mascot-position{transition:none}}
</style>
