import {mount,tick} from 'svelte';
import App from './App.svelte';
import {get} from 'svelte/store';
import {entrance} from './entrance';
import {receive,open,demo,loadPreferences,setPreference,model,startEntrance,replayEntrance} from './model';
import {post,isNative} from './bridge';
import './app.css';

// Keep the root, views and mascot images alive throughout the process lifetime.
window.axon={recevoir:receive,ouvrir:open,apercu:demo,entree:startEntrance,rejouer:replayEntrance};
loadPreferences();
if(isNative())open(false);
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
if(reducedMotion.matches)setPreference('motion',false);
reducedMotion.addEventListener('change',event=>{if(event.matches)setPreference('motion',false);});
if(!isNative()&&get(model).motion)entrance.set('armed');
mount(App,{target:document.getElementById('app')!});
if(window.parent!==window)model.subscribe(s=>window.parent.postMessage({source:'axon-overlay-preview',height:s.view==='home'?280:500},'*'));
async function ready(){
 await tick();
 await Promise.all(Array.from(document.images,img=>img.decode().catch(()=>undefined)));
 // GTK presents the first window only after assets have been decoded.
 post({type:'pret'});
 if(!isNative()){if((window.__axonPreview||new URLSearchParams(location.search).get('demo')==='1'))demo();replayEntrance();}
}
void ready();
