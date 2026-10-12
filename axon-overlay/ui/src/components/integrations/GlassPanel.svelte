<script lang="ts">
 import Icon from '../Icon.svelte';
 export let color:string;
 export let icon:string;
 export let name:string;
 export let tagline:string='';
 export let onback:()=>void;
 export let badge:string='aperçu';
 export let badgeTone:'aperçu'|'direct'|'erreur'='aperçu';
</script>
<!-- Classe "dash-glass", pas "glass" : App.svelte a son propre .glass (voile
     décoratif derrière tout l'îlot) depuis la fusion avec la maquette front —
     même piège que .row/.detail plus tôt, cette fois entre deux fichiers
     distincts plutôt qu'au sein du même. -->
<div class="dash-glass" style={`--c:${color}`}>
 <span class="glow"></span>
 <header>
  <button class="back" onclick={onback} aria-label="Retour aux intégrations"><Icon name="back"/></button>
  <span class="mark"><Icon name={icon}/></span>
  <div class="meta"><strong>{name}</strong>{#if tagline}<small>{tagline}</small>{/if}</div>
  {#if badge}<span class="badge" data-tone={badgeTone}>{badge}</span>{/if}
 </header>
 <div class="body"><slot/></div>
</div>
<style>
 .dash-glass{position:relative;height:100%;display:flex;flex-direction:column;gap:11px;min-height:0;animation:panelIn 220ms var(--spring-soft) both;isolation:isolate}
 .glow{position:absolute;inset:-40px -20px auto -20px;height:280px;background:radial-gradient(60% 100% at 18% 0%,color-mix(in srgb,var(--c) 55%,transparent) 0%,transparent 72%);filter:blur(42px);opacity:.38;pointer-events:none;z-index:-1}
 @keyframes panelIn{0%{opacity:0;transform:translateY(6px) scale(.985)}100%{opacity:1;transform:translateY(0) scale(1)}}
 header{display:flex;align-items:center;gap:10px;flex:none}
 .back{width:26px;height:26px;border-radius:9px;display:grid;place-items:center;color:var(--muted);background:#ffffff07;flex:none;transition:transform 150ms var(--spring),background 150ms,color 150ms}
 .back:hover{background:#ffffff10;color:var(--text);transform:translateX(-1px)}
 .mark{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;color:var(--c);background:color-mix(in srgb,var(--c) 16%,#ffffff08);border:1px solid color-mix(in srgb,var(--c) 32%,transparent);flex:none}
 .meta{min-width:0;flex:1}
 .meta strong{display:block;font-size:13px;font-weight:600;letter-spacing:-.1px}
 .meta small{color:var(--muted);font-size:10px}
 .badge{font-size:8px;letter-spacing:.05em;text-transform:uppercase;color:#dfb86e;background:#ffaf0014;border:1px solid #ffaf0030;padding:4px 8px;border-radius:20px;flex:none}
 .badge[data-tone="direct"]{color:#7fd9a8;background:#2ecc7114;border-color:#2ecc7130}
 .badge[data-tone="direct"]::before{content:'';display:inline-block;width:4px;height:4px;border-radius:50%;background:currentColor;margin-right:5px;vertical-align:middle;animation:pulseDirect 1.8s ease-in-out infinite}
 .badge[data-tone="erreur"]{color:#e68a8a;background:#ff525214;border-color:#ff525230}
 @keyframes pulseDirect{50%{opacity:.4}}
 .body{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column;gap:9px;padding:1px}
</style>
