import { get, writable } from 'svelte/store';
import { entrance, finishEntrance } from './entrance';
import { isNative, post } from './bridge';
import type { AgentState, Model, Request, View } from './types';
import { INTEGRATIONS } from './integrations';
const fresh = (): Model => ({ view:'home', state:'idle', connected:false, visible:true, demo:false, detail:'', draft:'', messages:[], activity:[], requests:[], commands:[], file:null, busy:false, motion:true, sound:false, notice:'', unread:0, integration:null, integrationData:{}, attachments:[], dragActif:false, creationSuivi:null, actionEtudes:null });
export const model = writable<Model>(fresh());
let serial=0, unlock: ReturnType<typeof setTimeout> | undefined, realTraffic=false;
const txt=(v:unknown):string=>v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object' && v!==null && !Array.isArray(v);
//: Valide un statut de génération reçu du backend (§1, lot 3) — jamais une
//: valeur inconnue propagée telle quelle dans l'état, même si le backend a
//: un bug : `undefined` (= "jamais lancé") est le repli sûr.
const statutGeneration=(v:unknown):'en_cours'|'terminee'|'echouee'|undefined=>
  v==='en_cours'||v==='terminee'||v==='echouee'?v:undefined;
function nativeMode(view:View){return view==='home' ? 'accueil' : 'detail';}
export function navigate(view:View){finishEntrance();const previous=get(model).view;model.update(s=>({...s,view,unread:view==='chat'?0:s.unread,integration:view==='integrations'?s.integration:null}));if(nativeMode(view)!==nativeMode(previous))post({type:'mode',mode:nativeMode(view)});}
export function openIntegration(id:string|null){
  model.update(s=>({...s,integration:id}));navigate('integrations');
  const meta=id?INTEGRATIONS.find(i=>i.id===id):undefined;
  if(meta?.action&&get(model).connected&&!get(model).demo)demanderRaccourci(meta.action);
}
//: Un backend qui ne connaît pas encore "raccourci" (session Axon pas
//: relancée depuis la mise à jour de l'île) ignore le message sans
//: répondre — sans ce délai, le panneau restait bloqué sur le squelette de
//: chargement indéfiniment, perçu comme "rien ne s'affiche".
const DELAI_RACCOURCI_MS=12000;
const MESSAGE_SANS_REPONSE='Axon ne répond pas. Si tu viens de mettre à jour l’île, relance aussi ta session Axon (pas seulement l’île).';
//: Raccourci rapide (src/ui/raccourcis_overlay.py) : appelle le tool
//: directement, pas de passage par le graphe — une seconde ou deux au lieu
//: d'un tour d'agent complet. Résultat dans `integrationData[action]`.
export function demanderRaccourci(action:string){
  if(!get(model).connected||get(model).demo)return;
  // Les lignes déjà affichées restent pendant l'actualisation : les
  // remplacer par un squelette faisait clignoter tout le panneau à chaque
  // retour sur une vue.
  model.update(s=>({...s,integrationData:{...s.integrationData,[action]:{...s.integrationData[action],status:'loading'}}}));
  post({type:'raccourci',id:String(++serial),action});
  setTimeout(()=>{
    if(get(model).integrationData[action]?.status==='loading')
      model.update(s=>({...s,integrationData:{...s.integrationData,[action]:{status:'error',message:MESSAGE_SANS_REPONSE}}}));
  },DELAI_RACCOURCI_MS);
}
//: Raccourci de DÉTAIL pour une ligne précise (ex. résumer CE mail) — ne
//: recharge pas tout le panneau, patch juste la ligne concernée via `item`.
export function demanderDetail(panel:string,action:string,item:string){
  if(!get(model).connected||get(model).demo)return;
  model.update(s=>{
    const d=s.integrationData[panel];
    if(!d?.rows)return s;
    const rows=d.rows.map(r=>r.id===item?{...r,detailStatus:'loading' as const}:r);
    return {...s,integrationData:{...s.integrationData,[panel]:{...d,rows}}};
  });
  post({type:'raccourci',id:String(++serial),action,item,panel});
  setTimeout(()=>{
    const row=get(model).integrationData[panel]?.rows?.find(r=>r.id===item);
    if(row?.detailStatus!=='loading')return;
    model.update(s=>{
      const d=s.integrationData[panel];
      if(!d?.rows)return s;
      const rows=d.rows.map(r=>r.id===item?{...r,detailStatus:'error' as const,detail:MESSAGE_SANS_REPONSE}:r);
      return {...s,integrationData:{...s.integrationData,[panel]:{...d,rows}}};
    });
  },DELAI_RACCOURCI_MS);
}
//: Pour aller plus loin que le raccourci : passe par l'agent complet, dans
//: le chat normal (confirmation, écriture, nuance — tout ce qu'un raccourci
//: lecture seule ne peut pas faire).
export function demanderAxon(prompt:string){navigate('chat');setDraft(prompt);submit();}
//: Ouvre le même sélecteur de fichier natif que `/attach` au clavier — géré
//: entièrement côté CLI (zenity/kdialog/tkinter), l'île ne fait que déclencher.
export function demanderPicker(){if(!get(model).connected||get(model).demo)return;post({type:'demander_picker'});}
//: Même esprit que `openIntegration` : la vue « études » n'est pas une
//: intégration (pas de panneau Gmail/Jira), mais le geste est identique —
//: naviguer ET charger les récents en un seul clic depuis le header.
export function ouvrirEtudes(){navigate('etudes');if(get(model).connected&&!get(model).demo){demanderRaccourci('etudes_fiches_recentes');demanderRaccourci('etudes_suivis');demanderRaccourci('etudes_echeances');}}
export function detacherPiece(nom:string){if(!get(model).connected||get(model).demo)return;post({type:'detacher',nom});}
//: Direct côté CLI (store.creer_suivi, pas de passage par le graphe) — même
//: raison que demanderRaccourci : une création n'a besoin d'aucun
//: raisonnement LLM. `id` identifie CETTE soumission (§2, lot 3) : la
//: réponse arrive comme `creer_suivi_resultat`/`creer_suivi_erreur` pour ce
//: même id — c'est à l'appelant (CreerSuivi.svelte) de la suivre via l'id
//: renvoyé, pour ne refermer son formulaire qu'après confirmation.
export function creerSuivi(titre:string,typeSuivi:string,matiere?:string):string|undefined{
  if(!get(model).connected||get(model).demo)return undefined;
  const id=String(++serial);
  model.update(s=>({...s,creationSuivi:{id,statut:'en_cours'}}));
  post({type:'creer_suivi',id,titre,type_suivi:typeSuivi,matiere});
  return id;
}
//: Gestion d'échéances/archivage depuis l'île (§3, lot 3) — même raison que
//: `creerSuivi` : CRUD simple, pas de passage par le graphe. Les trois
//: partagent `actionEtudes` (voir types.ts) : contrairement à la création
//: de suivi (un formulaire qui doit bloquer pendant l'attente), ces actions
//: sont des clics ponctuels sur une ligne déjà affichée — rien à désactiver
//: en vol d'un composant à l'autre, juste à savoir si CETTE action a réussi.
function nouvelleActionEtudes():string{
  const id=String(++serial);
  model.update(s=>({...s,actionEtudes:{id,statut:'en_cours'}}));
  return id;
}
export function creerEcheance(suiviId:string,titre:string,typeEcheance:string,date:string):string|undefined{
  if(!get(model).connected||get(model).demo)return undefined;
  const id=nouvelleActionEtudes();
  post({type:'creer_echeance',id,suivi_id:suiviId,titre,type_echeance:typeEcheance,date});
  return id;
}
export function majEcheance(suiviId:string,echeanceId:string,champs:{date?:string;statut?:string}):string|undefined{
  if(!get(model).connected||get(model).demo)return undefined;
  const id=nouvelleActionEtudes();
  post({type:'maj_echeance',id,suivi_id:suiviId,echeance_id:echeanceId,...champs});
  return id;
}
export function archiverSuivi(suiviId:string):string|undefined{
  if(!get(model).connected||get(model).demo)return undefined;
  const id=nouvelleActionEtudes();
  post({type:'archiver_suivi',id,suivi_id:suiviId});
  return id;
}
export function open(visible:boolean){const previous=get(model).visible;model.update(s=>({...s,visible}));if(!visible)finishEntrance();else{if(!previous&&get(model).motion&&!get(model).requests.length)entrance.set('armed');post({type:'mode',mode:nativeMode(get(model).view)});}}
export function startEntrance(){if(get(entrance)==='armed'&&get(model).visible)entrance.set('playing');}
export function replayEntrance(){const s=get(model);if(!s.visible||!s.motion||s.requests.length)return;finishEntrance();queueMicrotask(()=>{const current=get(model);if(current.visible&&current.motion&&!current.requests.length)entrance.set('playing');});}
export function close(){post({type:'ouvrir',ouvert:false});}
export function setDraft(draft:string){model.update(s=>({...s,draft}));}
export function notice(message:string){model.update(s=>({...s,notice:message}));}
function log(who:'axon'|'toi',text:string){model.update(s=>({...s,messages:[...s.messages,{id:++serial,who,text}].slice(-200),unread:who==='axon'&&s.view!=='chat'?s.unread+1:s.unread}));}
export function reset(){finishEntrance();clearTimeout(unlock);model.set(fresh());realTraffic=false;}
export function receive(value:unknown){
  if(!object(value)||typeof value.type!=='string')return;
  if(get(model).demo){const s=get(model);model.set({...fresh(),motion:s.motion,sound:s.sound});}
  realTraffic=true; handle(value);
}
function handle(m:Record<string,unknown>){
  switch(m.type){
    case 'connexion': {
      const connected=m.connecte===true;
      // Les panneaux déjà ouverts (Études, Gmail…) gardent leur DERNIÈRE
      // valeur connue à travers une reconnexion (pas vidés comme à la
      // déconnexion) — mais sans réactualisation, une génération terminée
      // ou purgée PENDANT la coupure resterait affichée comme avant (§1,
      // lot 3 : « une reconnexion doit retrouver l'état réel »).
      const panneauxOuverts=connected?Object.keys(get(model).integrationData):[];
      model.update(s=>{
        // Une création de suivi en vol dont la réponse n'arrivera jamais
        // (connexion perdue avant `creer_suivi_resultat`/`_erreur`) doit
        // débloquer le formulaire plutôt que le laisser "en cours" pour
        // toujours (§2, lot 3).
        const creationSuivi=!connected&&s.creationSuivi?.statut==='en_cours'
          ?{...s.creationSuivi,statut:'erreur' as const,message:'Connexion à Axon perdue pendant la création.'}
          :s.creationSuivi;
        const actionEtudes=!connected&&s.actionEtudes?.statut==='en_cours'
          ?{...s.actionEtudes,statut:'erreur' as const,message:'Connexion à Axon perdue pendant l’action.'}
          :s.actionEtudes;
        return {...s,connected,requests:connected?s.requests:[],integrationData:connected?s.integrationData:{},attachments:connected?s.attachments:[],dragActif:false,busy:false,state:connected?'idle':'sleeping',notice:'',creationSuivi,actionEtudes};
      });
      clearTimeout(unlock);
      if(connected&&!get(model).demo){
        post({type:'demander_commandes'});
        panneauxOuverts.forEach(action=>demanderRaccourci(action));
      }
      break;
    }
    case 'etat': {const aliases:Record<string,AgentState>={approval:'waiting',question:'waiting',erreur:'error',error:'error',searching:'thinking'};const name=txt(m.etat);const state=aliases[name]||(['idle','thinking','working','waiting','finished','sleeping'].includes(name)?name as AgentState:'idle');model.update(s=>({...s,state,detail:txt(m.texte)||s.detail}));break;}
    case 'commandes': model.update(s=>({...s,commands:Array.isArray(m.liste)?m.liste.filter(object).filter(c=>typeof c.cmd==='string').map(c=>({cmd:txt(c.cmd),desc:txt(c.desc)})):[]}));break;
    case 'outil': {
      const nom=txt(m.nom),detail=txt(m.detail);
      // Même événement dans deux endroits : `activity` pour le résumé d'une
      // ligne sur l'accueil, `messages` pour le voir défiler dans la
      // conversation — avant, un outil appelé pendant une recherche n'était
      // visible nulle part une fois que `last` avait changé.
      model.update(s=>({...s,state:'working',detail:nom,
        activity:[...s.activity,{id:++serial,name:nom,detail}].slice(-150),
        messages:[...s.messages,{id:++serial,who:'outil' as const,text:nom,detail}].slice(-200)}));
      if(m.contenu!==undefined||m.diff!==undefined)file(m);
      break;
    }
    case 'fichier':case 'diff':file(m);break;
    case 'message':log('axon',txt(m.texte));break;
    case 'confirmation':case 'demande': {
      if(typeof m.id!=='string'&&typeof m.id!=='number')break;
      const legacy=m.type==='confirmation';
      const questions=legacy?[{texte:txt(m.raison)||'Autoriser cette commande ?',choix:['Autoriser','Refuser'],affirmatif:'Autoriser',libre:true}]:Array.isArray(m.questions)?m.questions.filter(object).map(q=>({texte:txt(q.texte),choix:Array.isArray(q.choix)?q.choix.filter((c):c is string=>typeof c==='string'):[],affirmatif:txt(q.affirmatif),libre:q.libre!==false})):[];
      if(!questions.length)questions.push({texte:txt(m.cle)||'Ta réponse est nécessaire.',choix:[],affirmatif:'',libre:true});
      const request:Request={id:m.id,genre:txt(m.genre),apercu:txt(legacy?m.commande:m.apercu),questions,answers:[],legacy};
      model.update(s=>{const index=s.requests.findIndex(p=>p.id===request.id);const requests=[...s.requests];if(index<0)requests.push(request);else{const previous=requests[index];requests[index]={...request,answers:JSON.stringify(previous.questions)===JSON.stringify(request.questions)?previous.answers:[]};}return {...s,requests,state:'waiting'};});navigate('chat');notifySound();break;
    }
    case 'annulation':model.update(s=>({...s,requests:s.requests.filter(p=>p.id!==m.id),state:s.connected?'idle':'sleeping'}));break;
    case 'raccourci_resultat': {
      const action=txt(m.action);
      if(!action)break;
      if(m.panel!==undefined&&m.item!==undefined){
        const panel=txt(m.panel),item=txt(m.item),texte=txt(m.text);
        model.update(s=>{
          const d=s.integrationData[panel];
          if(!d?.rows)return s;
          const rows=d.rows.map(r=>r.id===item?{...r,detail:texte,detailStatus:'ok' as const}:r);
          return {...s,integrationData:{...s.integrationData,[panel]:{...d,rows}}};
        });
        break;
      }
      const stats=Array.isArray(m.stats)?m.stats.filter(object).map(s=>({label:txt(s.label),value:txt(s.value),accent:s.accent===true})):[];
      const rows=Array.isArray(m.rows)?m.rows.filter(object).map(r=>({title:txt(r.title),meta:txt(r.meta),tag:r.tag!==undefined?txt(r.tag):undefined,accent:r.accent===true,id:r.id!==undefined?txt(r.id):undefined,detail:r.detail!==undefined&&r.detail!==null?txt(r.detail):undefined,generationFicheStatut:statutGeneration(r.generationFicheStatut),generationFicheFichier:r.generationFicheFichier!==undefined?txt(r.generationFicheFichier):undefined,generationExoStatut:statutGeneration(r.generationExoStatut),generationExoFichier:r.generationExoFichier!==undefined?txt(r.generationExoFichier):undefined,suiviId:r.suiviId!==undefined?txt(r.suiviId):undefined})):[];
      model.update(s=>({...s,integrationData:{...s.integrationData,[action]:{status:'ok',stats,rows,generationFicheStatut:statutGeneration(m.generationFicheStatut),generationFicheFichier:m.generationFicheFichier!==undefined?txt(m.generationFicheFichier):undefined,generationExoStatut:statutGeneration(m.generationExoStatut),generationExoFichier:m.generationExoFichier!==undefined?txt(m.generationExoFichier):undefined}}}));
      break;
    }
    case 'raccourci_erreur': {
      const action=txt(m.action);
      if(!action)break;
      if(m.panel!==undefined&&m.item!==undefined){
        const panel=txt(m.panel),item=txt(m.item),message=txt(m.message)||'Échec.';
        model.update(s=>{
          const d=s.integrationData[panel];
          if(!d?.rows)return s;
          const rows=d.rows.map(r=>r.id===item?{...r,detailStatus:'error' as const,detail:message}:r);
          return {...s,integrationData:{...s.integrationData,[panel]:{...d,rows}}};
        });
        break;
      }
      model.update(s=>({...s,integrationData:{...s.integrationData,[action]:{status:'error',message:txt(m.message)||'Échec du raccourci.'}}}));
      break;
    }
    case 'creer_suivi_resultat': {
      if(typeof m.id!=='string')break;
      model.update(s=>({...s,creationSuivi:{id:m.id as string,statut:'ok'}}));
      break;
    }
    case 'creer_suivi_erreur': {
      if(typeof m.id!=='string')break;
      model.update(s=>({...s,creationSuivi:{id:m.id as string,statut:'erreur',message:txt(m.message)||'Échec de la création.'}}));
      break;
    }
    case 'etudes_action_resultat': {
      if(typeof m.id!=='string')break;
      model.update(s=>({...s,actionEtudes:{id:m.id as string,statut:'ok'}}));
      break;
    }
    case 'etudes_action_erreur': {
      if(typeof m.id!=='string')break;
      model.update(s=>({...s,actionEtudes:{id:m.id as string,statut:'erreur',message:txt(m.message)||'Échec.'}}));
      break;
    }
    case 'pieces_jointes': {
      const items=Array.isArray(m.items)?m.items.filter(object).map(i=>({
        nom:txt(i.nom),
        statut:(['chargement','ok','erreur'] as const).includes(i.statut as 'chargement'|'ok'|'erreur')?i.statut as 'chargement'|'ok'|'erreur':'ok',
        message:i.message!==undefined?txt(i.message):undefined,
        estImage:i.est_image===true,
        taille:txt(i.taille),
      })):[];
      model.update(s=>({...s,attachments:items}));
      break;
    }
    case 'glisser':model.update(s=>({...s,dragActif:m.actif===true}));break;
  }
}
function file(m:Record<string,unknown>){const diff=m.type==='diff'||m.diff!==undefined;model.update(s=>({...s,file:{path:txt(m.chemin||m.fichier||m.detail)||'fichier',content:txt(diff?(m.diff??m.contenu):m.contenu),diff,start:typeof m.ligne==='number'&&Number.isInteger(m.ligne)&&m.ligne>0?m.ligne:1}}));}
export function submit(){const s=get(model),text=s.draft.trim();if(!text||(!s.connected&&!s.demo)||s.busy)return;if(s.requests.length){answer(text);return;}if(!s.demo&&!post({type:'commande',texte:text})){notice('Le lien avec Axon est indisponible. Ton brouillon est conservé.');return;}setDraft('');log('toi',text);model.update(s=>({...s,state:'thinking'}));if(s.demo)log('axon','Ceci est un aperçu. Aucune commande n’a été exécutée.');}
export function answer(text:string){const s=get(model),p=s.requests[0];if(!p||s.busy||(!s.connected&&!s.demo))return;const q=p.questions[p.answers.length];if(!q||(q.choix.length&&!p.freeform&&!q.choix.includes(text)))return;const answers=[...p.answers,text];if(answers.length===p.questions.length&&!s.demo){const ok=post(p.legacy?{type:'decision',id:p.id,accord:text==='Autoriser'}:{type:'reponse_demande',id:p.id,reponses:answers});if(!ok){notice('Réponse non envoyée. Tu peux réessayer.');return;}}
  log('toi',text);model.update(s=>({...s,draft:'',busy:true,requests:answers.length===p.questions.length?s.requests.slice(1):[{...p,answers,freeform:false},...s.requests.slice(1)],state:answers.length===p.questions.length?'working':'waiting'}));clearTimeout(unlock);unlock=setTimeout(()=>model.update(s=>({...s,busy:false})),300);
}
// « Autre » n'arrive jamais dans `choix` (l'agent a pour consigne de ne pas
// l'ajouter, voir src/agents/clarify/tools.py) : c'est à l'interface de
// l'ajouter et de lever la validation stricte le temps d'une réponse libre.
export function chooseFreeform(){const s=get(model),p=s.requests[0];if(!p||s.busy)return;model.update(s=>({...s,requests:[{...p,freeform:true},...s.requests.slice(1)]}));}
export function setPreference(key:'motion'|'sound',value:boolean){if(key==='motion'&&!value)finishEntrance();model.update(s=>({...s,[key]:value}));const s=get(model);try{localStorage.setItem('axon.overlay.preferences',JSON.stringify({motion:s.motion,sound:s.sound}));}catch{}if(key==='sound'&&value)prepareSound();}
let audio:AudioContext|undefined;
export function prepareSound(){if(!get(model).sound)return;try{audio??=new AudioContext();void audio.resume().catch(()=>{});}catch{}}
function notifySound(){if(!get(model).sound||!audio||audio.state!=='running')return;const o=audio.createOscillator(),g=audio.createGain();o.frequency.value=660;g.gain.setValueAtTime(.025,audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.18);o.connect(g);g.connect(audio.destination);o.start();o.stop(audio.currentTime+.2);}
export function loadPreferences(){try{const p=JSON.parse(localStorage.getItem('axon.overlay.preferences')||'{}');model.update(s=>({...s,motion:p.motion!==false,sound:p.sound===true}));}catch{}}
export function demo(){if(isNative()||realTraffic)return;reset();model.update(s=>({...s,demo:true,connected:true,state:'thinking',commands:[{cmd:'/help',desc:'Les commandes disponibles'},{cmd:'/marketplace',desc:'Explorer les extensions'}]}));handle({type:'outil',nom:'read_file',detail:'ui/src/App.svelte'});handle({type:'diff',chemin:'ui/src/palette.ts',diff:'@@ -1,3 +1,3 @@\n export const palette = {\n-  accent: "#ffffff",\n+  accent: "#ffaf00",\n };'});log('axon','L’interface reste en place pendant que je travaille. Le code et les messages se mettent à jour sans réinitialiser l’îlot.');}
