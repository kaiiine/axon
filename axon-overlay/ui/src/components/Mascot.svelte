<script lang="ts">
  import EntranceActor from './EntranceActor.svelte';
  import type { AgentState } from '../types';
  export let entering=false;
  const asset=(path:string)=>window.__axonAssets?.[path]||path;
  export let state:AgentState='idle'; export let motion=true; export let visible=true;
  const faces=['idle','thinking','working','approval','finished','sleeping'];
  $: selected=state==='waiting'||state==='error'?'approval':state;
</script>
<div class="mascot" class:entering role="img" aria-label={`Axon · ${state}`} data-mascot>
  <div class="entrance-actor"><EntranceActor/></div>
  {#each faces as face (face)}
    <img class:shown={selected===face&&motion&&visible} src={asset(`./mascots/axon-${face}.svg`)} alt="" draggable="false" aria-hidden="true"/>
    <img class:shown={selected===face&&(!motion||!visible)} src={asset(`./mascots/static/axon-${face}.svg`)} alt="" draggable="false" aria-hidden="true"/>
  {/each}
</div>
<style>.entrance-actor{position:absolute;inset:0;opacity:0;transition:opacity 120ms}.entering .entrance-actor{opacity:1;transition:none}.mascot.entering img{opacity:0!important;transition:none}.mascot{position:relative;width:100%;height:100%;isolation:isolate}.mascot img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;opacity:0;transition:opacity 170ms ease;pointer-events:none}.mascot img.shown{opacity:1}@media(prefers-reduced-motion:reduce){.mascot img{transition:none}}</style>
