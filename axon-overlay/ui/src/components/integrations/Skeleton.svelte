<script lang="ts">export let stats=true;</script>
{#if stats}<div class="stats"><span class="bar bar-stat"></span><span class="bar bar-stat"></span></div>{/if}
<span class="bar bar-row"></span>
<span class="bar bar-row"></span>
<span class="bar bar-row"></span>
<style>
 .stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:none}
 .bar{display:block;border-radius:12px;background:linear-gradient(90deg,#ffffff07 0%,#ffffff12 50%,#ffffff07 100%);background-size:220% 100%;animation:shimmer 1.6s linear infinite}
 .bar-stat{height:56px;border-radius:12px}
 .bar-row{height:46px;border-radius:10px}
 @keyframes shimmer{from{background-position:160% 0}to{background-position:-60% 0}}
</style>
