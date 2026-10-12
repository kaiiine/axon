import {writable} from 'svelte/store';
export type EntrancePhase='rest'|'armed'|'playing';
export const entrance=writable<EntrancePhase>('rest');
export const finishEntrance=()=>entrance.set('rest');

//: Un clic pendant l'arrivée doit couper court, mais pas d'un coup sec — le
//: personnage continue sa trajectoire, juste beaucoup plus vite, jusqu'à sa
//: pose finale. `done()` (→ finishEntrance) se déclenche alors naturellement,
//: et le fondu CSS existant de l'interface prend le relais sans rien de neuf
//: à synchroniser.
const VITESSE_SKIP=7;

/** Animate the already-mounted character; never replace its SVGs or its node. */
export function arrival(node:HTMLElement,initial:{phase:EntrancePhase;done:()=>void;skip?:number}){
 let limbs:Animation[]=[];
 let animation:Animation|undefined,phase:EntrancePhase='rest',generation=0,measured=false,playingSince=0,dernierSkip=initial.skip??0;
 function cancel(){generation++;animation?.cancel();limbs.forEach(a=>a.cancel());limbs=[];animation=undefined;node.style.removeProperty('will-change');}
 function update(config:typeof initial){
  if(config.skip!==undefined&&config.skip!==dernierSkip){
   dernierSkip=config.skip;
   if(phase==='playing'&&animation){
    animation.playbackRate=VITESSE_SKIP;
    limbs.forEach(a=>{a.playbackRate=VITESSE_SKIP;});
   }
  }
  if(config.phase===phase)return;
  phase=config.phase;
  if(phase==='rest'){cancel();return;}
  if(phase==='playing'&&!measured&&node.parentElement?.parentElement?.clientWidth)cancel();
  if(!animation){
   if(typeof node.animate!=='function'){config.done();return;}
   const slot=node.parentElement!,area=slot.parentElement!;
   measured=area.clientWidth>0&&slot.offsetWidth>0;
   const detail=slot.classList.contains('detail');
   const width=slot.offsetWidth||184,height=slot.offsetHeight||184;
   const areaWidth=area.clientWidth||752,areaHeight=area.clientHeight||(detail?435:215);
   const x=(areaWidth-width)/2-slot.offsetLeft;
   const y=(areaHeight-height)/2-(measured?slot.offsetTop:detail?5:(areaHeight-height)/2);
   const t=(dx:number,dy:number,s:number,r:number)=>`translate3d(${dx}px,${dy}px,0) scale(${s}) rotate(${r}deg)`;
   const close=Math.max(4.8,areaHeight/42);
   node.style.willChange='transform';
   animation=node.animate([
    {offset:0,transform:t(x,y+20,.48,0),easing:'cubic-bezier(.45,0,.7,.55)'},
    {offset:.42,transform:t(x,y+16,close,-2),easing:'ease-out'},
    {offset:.49,transform:t(x-5,y+17,close,2),easing:'ease-in-out'},
    {offset:.57,transform:t(x,y+16,close,0),easing:'cubic-bezier(.3,0,.5,1)'},
    {offset:.68,transform:t(x,y,1.12,-8),easing:'linear'},
    {offset:.92,transform:t(12,0,1,-8),easing:'ease-out'},
    {offset:1,transform:t(0,0,1,0)}
   ],{duration:4200,fill:'both'});
   // Alternating planted / lifted paws, opposite arm swing, weight transfer.
   // All tracks share the same clock, including pause and cancellation.
   const track=(selector:string,frame:(p:number)=>string)=>{
    const element=node.querySelector(selector);if(!element)return;
    const frames=Array.from({length:241},(_,i)=>({offset:i/240,transform:frame(i/240)}));
    const movement=element.animate(frames,{duration:4200,fill:'both',easing:'linear'});
    movement.pause();movement.currentTime=0;limbs.push(movement);
   };
   const gait=(p:number)=>{
    const walking=p<.42,running=p>=.64&&p<.98;
    const envelope=walking?Math.min(1,p/.04,(.42-p)/.04):running?Math.min(1,(p-.64)/.035,(.98-p)/.035):0;
    return {angle:(walking?p/.42*4:(p-.64)/.34*7)*Math.PI*2,weight:Math.max(0,envelope),run:running};
   };
   for(const [side,shift] of [['left',0],['right',Math.PI]] as const){
    track(`[data-leg="${side}"]`,p=>{const g=gait(p),v=Math.sin(g.angle+shift),lift=Math.max(0,Math.cos(g.angle+shift));return `translate(${v*(g.run?22:13)*g.weight}px,${-lift*(g.run?18:11)*g.weight}px) rotate(${v*(g.run?24:14)*g.weight}deg)`;});
    track(`.actor .hand-${side}`,p=>{const g=gait(p);return `rotate(${-Math.sin(g.angle+shift)*(g.run?32:16)*g.weight}deg)`;});
   }
   track('.actor .breathe',p=>{const g=gait(p);return `translateY(${-Math.abs(Math.sin(g.angle))*(g.run?9:4)*g.weight}px) rotate(${Math.sin(g.angle)*1.8*g.weight}deg)`;});
   track('.actor .head-group',p=>{const g=gait(p);return `rotate(${-Math.sin(g.angle)*1.5*g.weight}deg)`;});
   track('.actor #eyes',p=>`translateX(${p>.6&&p<.96?-8:0}px)`);
   animation.pause();animation.currentTime=0;
   const current=++generation;
   animation.finished.then(()=>{if(current===generation)config.done();}).catch(()=>{});
  }
  if(phase==='playing'){playingSince=performance.now();animation.play();limbs.forEach(a=>a.play());}
 }
 update(initial);
 // Changing available space during the flight lands immediately in the real slot.
 // Mais la toute première bascule d'une fenêtre GTK layer-shell (present()
 // puis le compositeur qui fige la géométrie) déclenche elle-même un resize
 // côté page, à quelques ms du début de la lecture — sans ce délai de grâce,
 // ce resize auto-infligé annulait l'arrivée avant même qu'elle ne soit visible.
 const resized=()=>{if(phase!=='rest'&&performance.now()-playingSince>300)initial.done();};
 window.addEventListener('resize',resized);
 return {update,destroy(){cancel();window.removeEventListener('resize',resized);}};
}
