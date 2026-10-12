import {it,expect} from 'vitest';
import {arrival} from '../ui/src/entrance';

//: `arrival()` pilote l'animation du mascot via la Web Animations API — les
//: stubs `Element.animate()` de l'environnement de test résolvent `.finished`
//: immédiatement, ce qui rend un test monté via App.svelte impossible à
//: observer de façon stable (l'arrivée « finit » avant le prochain tick). On
//: teste donc la logique de `arrival()` directement, avec un faux nœud dont
//: on contrôle `.finished` nous-mêmes.
function nœudFactice(){
 const anim={playbackRate:1,currentTime:0,finished:new Promise<void>(()=>{}),play(){},pause(){},cancel(){}};
 const area={clientWidth:752,clientHeight:215};
 const slot={classList:{contains:()=>false},offsetWidth:184,offsetHeight:184,offsetLeft:0,offsetTop:0,parentElement:area};
 const node={
  style:{willChange:'',removeProperty(){}},
  parentElement:slot,
  querySelector:()=>null,
  animate:()=>anim,
 };
 return {node:node as unknown as HTMLElement,anim};
}

it('un skip pendant la lecture accélère la même animation au lieu de la couper net',()=>{
 const {node,anim}=nœudFactice();
 let terminé=false;
 const action=arrival(node,{phase:'rest',done:()=>{terminé=true;},skip:0});
 action.update({phase:'playing',done:()=>{terminé=true;},skip:0});
 expect(anim.playbackRate).toBe(1); // vitesse normale tant qu'on ne saute pas
 action.update({phase:'playing',done:()=>{terminé=true;},skip:1}); // clic sur « passer »
 expect(anim.playbackRate).toBe(7); // la même Animation, juste accélérée
 expect(terminé).toBe(false); // pas coupée net : `done()` suit son propre `finished`
 action.destroy();
});

it('un skip hors lecture (armed/rest) ne touche à rien',()=>{
 const {node,anim}=nœudFactice();
 const action=arrival(node,{phase:'rest',done:()=>{},skip:0});
 action.update({phase:'rest',done:()=>{},skip:1});
 expect(anim.playbackRate).toBe(1);
 action.destroy();
});

it('plusieurs clics sur « passer » restent sans effet au-delà du premier',()=>{
 const {node,anim}=nœudFactice();
 const action=arrival(node,{phase:'rest',done:()=>{},skip:0});
 action.update({phase:'playing',done:()=>{},skip:0});
 action.update({phase:'playing',done:()=>{},skip:1});
 anim.playbackRate=7;
 action.update({phase:'playing',done:()=>{},skip:1}); // même jeton : rien à refaire
 expect(anim.playbackRate).toBe(7);
 action.destroy();
});
