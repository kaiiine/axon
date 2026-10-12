<script lang="ts">
 export let label:string;
 export let value:string;
 export let color:string|undefined=undefined;
</script>
<!-- --c doit être réécrit ici, pas seulement en fallback : la variable du
     GlassPanel parent est héritée par tous les descendants, donc un simple
     var(--c, repli) ne retombe jamais sur le repli neutre. -->
<div class="stat" style={`--c:${color??'#c7c9d4'}`}><b>{value}</b><span>{label}</span></div>
<style>
 .stat{background:color-mix(in srgb,var(--c,#fff) 4%,#ffffff08);border:1px solid #ffffff10;border-top-color:#ffffff1c;border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:3px;box-shadow:0 6px 18px -10px color-mix(in srgb,var(--c,transparent) 30%,transparent)}
 .stat b{font-size:18px;font-weight:600;letter-spacing:-.3px;color:var(--c,#eceef4)}
 .stat span{font-size:9px;color:var(--muted)}
</style>
