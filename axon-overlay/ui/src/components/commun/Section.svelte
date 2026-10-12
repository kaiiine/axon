<script lang="ts">
 //: Bloc titré d'une page (projet, ou toute autre vue détaillée) : un titre,
 //: un compteur optionnel, des actions à droite (slot "actions").
 export let titre:string;
 export let compte:number|undefined=undefined;
</script>
<section class="bloc">
 <div class="tete">
  <span>{titre}{#if compte!==undefined}<i>{compte}</i>{/if}</span>
  <div class="actions-bloc"><slot name="actions"/></div>
 </div>
 <slot/>
</section>
<style>
 .bloc{display:flex;flex-direction:column;gap:7px;padding:11px 12px;border:1px solid #ffffff0b;border-top-color:#ffffff14;border-radius:14px;background:linear-gradient(135deg,#ffffff06,#ffffff02)}
 .tete{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;color:var(--muted);min-height:22px}
 .tete i{font-style:normal;margin-left:6px;padding:1px 6px;border-radius:10px;background:#ffffff0a;color:#b0b2bc;font-size:9px}
 .actions-bloc{display:flex;align-items:center;gap:6px}
</style>
