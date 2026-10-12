<script lang="ts">
 import {tick} from 'svelte';
 import Icon from './Icon.svelte';
 //: Patron "conditionally revealed input" (GOV.UK Design System) : le champ
 //: apparaît directement là où « Autre » a été choisi, reçoit le focus tout
 //: seul, et reste une question — pas un aller ailleurs dans l'île pour
 //: répondre à ce qu'on vient de choisir ici.
 export let label:string='Autre réponse';
 export let placeholder:string='Précise ta réponse…';
 export let disabled=false;
 export let onSubmit:(value:string)=>void;
 let value='';
 let input:HTMLInputElement;
 $: if(input)void tick().then(()=>input?.isConnected&&input.focus());
 function submit(){const v=value.trim();if(!v||disabled)return;onSubmit(v);value='';}
 function key(e:KeyboardEvent){if(e.key==='Enter'){e.preventDefault();submit();}}
</script>
<div class="freeform">
 <label for="freeform-input" class="freeform-label">{label}</label>
 <div class="freeform-row">
  <input id="freeform-input" type="text" bind:this={input} bind:value {placeholder} {disabled} onkeydown={key} autocomplete="off"/>
  <button class="freeform-send" title="Envoyer" aria-label="Envoyer" disabled={disabled||!value.trim()} onclick={submit}><Icon name="send"/></button>
 </div>
</div>
<style>
 .freeform{display:flex;flex-direction:column;gap:6px;margin-top:9px;animation:revealIn 180ms var(--spring-soft) both}
 @keyframes revealIn{0%{opacity:0;transform:translateY(-3px)}100%{opacity:1;transform:translateY(0)}}
 .freeform-label{font-size:9px;color:var(--faint);text-transform:uppercase;letter-spacing:.04em}
 .freeform-row{display:flex;gap:6px;align-items:center}
 input{flex:1;min-width:0;border:1px solid #ffffff14;background:#ffffff06;color:var(--text);font:12px/1.4 var(--font);padding:8px 10px;border-radius:9px;outline:none;appearance:none;-webkit-appearance:none;transition:border-color 150ms,background 150ms}
 input:focus{border-color:#ffaf0045;background:#ffffff09}
 input:disabled{opacity:.5}
 .freeform-send{width:28px;height:28px;flex:none;border-radius:8px;display:grid;place-items:center;background:var(--accent);color:#241700;transition:transform 160ms var(--spring),background 150ms,opacity 150ms}
 .freeform-send:hover:not(:disabled){background:#ffc02e;transform:translateY(-1px)}
 .freeform-send:disabled{opacity:.35}
</style>
