import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {get} from 'svelte/store';
import {model,reset,receive,navigate,setDraft,submit,answer,chooseFreeform,open,openIntegration,demanderRaccourci,demanderDetail,demanderPicker,detacherPiece,creerSuivi,majEcheance,demanderFlux,ouvrirSuivi} from '../ui/src/model';
describe('contrat Axon et état stable',()=>{
 let post=vi.fn();
 beforeEach(()=>{reset();post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};});
 afterEach(()=>{reset();delete window.webkit;});
 it('annonce les vrais modes natifs sans redimensionnement sur chaque frappe',()=>{navigate('code');setDraft('a');setDraft('ab');navigate('chat');navigate('home');expect(post.mock.calls.map(c=>c[0])).toEqual([{type:'mode',mode:'detail'},{type:'mode',mode:'accueil'}]);});
 it('rouvre sans réinitialiser la vue ni la conversation',()=>{navigate('chat');receive({type:'message',texte:'conservé'});open(false);open(true);expect(get(model).view).toBe('chat');expect(get(model).messages[0].text).toBe('conservé');});
 it('préserve le brouillon si le pont échoue',()=>{receive({type:'connexion',connecte:true});post.mockImplementation(()=>{throw Error('déconnecté')});setDraft('important');submit();expect(get(model).draft).toBe('important');expect(get(model).messages).toHaveLength(0);});
 it('répond à toutes les questions avant de transmettre, ID 0 inclus',()=>{vi.useFakeTimers();receive({type:'connexion',connecte:true});receive({type:'demande',id:0,questions:[{texte:'A ?',choix:['oui','non']},{texte:'B ?',choix:[]}]});answer('oui');expect(post.mock.calls.filter(c=>c[0].type==='reponse_demande')).toHaveLength(0);vi.advanceTimersByTime(301);answer('texte libre');expect(post).toHaveBeenLastCalledWith({type:'reponse_demande',id:0,reponses:['oui','texte libre']});expect(get(model).requests).toHaveLength(0);vi.useRealTimers();});
 it('bloque le double clic entre deux demandes',()=>{receive({type:'connexion',connecte:true});for(const id of ['A','B'])receive({type:'demande',id,questions:[{texte:'?',choix:['oui']}]});answer('oui');answer('oui');expect(post.mock.calls.filter(c=>c[0].type==='reponse_demande')).toHaveLength(1);expect(get(model).requests[0].id).toBe('B');});
 it('déconnexion et annulation invalident les réponses',()=>{receive({type:'connexion',connecte:true});receive({type:'demande',id:'A',questions:[{texte:'?',choix:[]}]});receive({type:'annulation',id:'A'});answer('oui');receive({type:'demande',id:'B',questions:[{texte:'?',choix:[]}]});receive({type:'connexion',connecte:false});answer('oui');expect(post.mock.calls.filter(c=>c[0].type==='reponse_demande')).toHaveLength(0);expect(get(model).requests).toHaveLength(0);});
 it('ignore les messages mal formés et conserve le texte comme donnée',()=>{receive(null);receive('x');receive({type:'demande',id:{},questions:[]});receive({type:'message',texte:'<img onerror="attack()">'});expect(get(model).requests).toHaveLength(0);expect(get(model).messages[0].text).toContain('<img');});
 it('une réponse tapée face à des boutons part quand la question accepte « Autre »',()=>{
  // Avant : ignorée en silence tant qu'on n'avait pas cliqué « Autre » — le CLI attendait, l'île semblait bloquée.
  receive({type:'connexion',connecte:true});receive({type:'demande',id:0,questions:[{texte:'?',choix:['oui','non']}]});
  answer('texte libre');
  expect(post).toHaveBeenLastCalledWith({type:'reponse_demande',id:0,reponses:['texte libre']});
  expect(get(model).requests).toHaveLength(0);
 });
 it('une réponse tapée retrouve le bouton correspondant, quelle que soit la casse',()=>{
  receive({type:'connexion',connecte:true});receive({type:'demande',id:1,questions:[{texte:'Lancer ?',choix:['Autoriser','Refuser'],affirmatif:'Autoriser'}]});
  answer('autoriser');
  expect(post).toHaveBeenLastCalledWith({type:'reponse_demande',id:1,reponses:['Autoriser']});
 });
 it('une question fermée refuse une réponse hors liste, mais le dit au lieu de se taire',()=>{
  receive({type:'connexion',connecte:true});receive({type:'demande',id:2,questions:[{texte:'Backend ?',choix:['gemini','mistral'],libre:false}]});
  post.mockClear();
  answer('ollama');
  expect(post).not.toHaveBeenCalled();
  expect(get(model).requests).toHaveLength(1);
  expect(get(model).notice).toContain('gemini, mistral');
  chooseFreeform();answer('ollama'); // « Autre » explicite reste possible côté protocole
  expect(post).toHaveBeenLastCalledWith({type:'reponse_demande',id:2,reponses:['ollama']});
 });
 it('répondre hors connexion prévient au lieu de ne rien faire',()=>{
  receive({type:'connexion',connecte:true});receive({type:'demande',id:3,questions:[{texte:'?',choix:[]}]});
  model.update(s=>({...s,connected:false}));
  post.mockClear();
  answer('ok');
  expect(post).not.toHaveBeenCalled();
  expect(get(model).notice).toContain('pas été envoyée');
 });
 it('repart sans freeform sur la question suivante',()=>{vi.useFakeTimers();receive({type:'connexion',connecte:true});receive({type:'demande',id:0,questions:[{texte:'A ?',choix:['oui']},{texte:'B ?',choix:['oui']}]});chooseFreeform();answer('libre');expect(get(model).requests[0].freeform).toBe(false);vi.useRealTimers();});
 it('ouvrir une intégration connectée avec raccourci déclenche le raccourci et passe en chargement',()=>{receive({type:'connexion',connecte:true});post.mockClear();openIntegration('gmail');expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'raccourci',action:'gmail_non_lus'}));expect(get(model).integrationData['gmail_non_lus'].status).toBe('loading');});
 it("n'envoie pas de raccourci pour une intégration sans action (Slack) ni hors connexion",()=>{receive({type:'connexion',connecte:true});post.mockClear();openIntegration('slack');expect(post.mock.calls.filter(c=>c[0].type==='raccourci')).toHaveLength(0);reset();post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};openIntegration('gmail');expect(post.mock.calls.filter(c=>c[0].type==='raccourci')).toHaveLength(0);});
 it('raccourci_resultat remplit integrationData, raccourci_erreur signale l’échec',()=>{receive({type:'connexion',connecte:true});demanderRaccourci('jira_mes_tickets');receive({type:'raccourci_resultat',action:'jira_mes_tickets',stats:[{label:'Assignés',value:'3',accent:true}],rows:[{title:'AXON-1',meta:'haute',tag:'en cours',accent:true}]});const d=get(model).integrationData['jira_mes_tickets'];expect(d.status).toBe('ok');expect(d.stats?.[0]).toEqual({label:'Assignés',value:'3',accent:true});expect(d.rows?.[0].title).toBe('AXON-1');receive({type:'raccourci_erreur',action:'jira_mes_tickets',message:'401'});expect(get(model).integrationData['jira_mes_tickets']).toEqual({status:'error',message:'401'});});
 it('déconnexion efface les données de raccourci déjà chargées',()=>{receive({type:'connexion',connecte:true});receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[],rows:[]});expect(get(model).integrationData['gmail_non_lus']).toBeDefined();receive({type:'connexion',connecte:false});expect(get(model).integrationData).toEqual({});});
 it('demanderDetail ne patch que la ligne demandée, pas tout le panneau',()=>{
  receive({type:'connexion',connecte:true});
  receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[{label:'Non lus',value:'2',accent:true}],rows:[{title:'A',meta:'x',id:'msg1'},{title:'B',meta:'y',id:'msg2'}]});
  post.mockClear();
  demanderDetail('gmail_non_lus','gmail_resumer_mail','msg1');
  expect(post).toHaveBeenCalledWith({type:'raccourci',id:expect.any(String),action:'gmail_resumer_mail',item:'msg1',panel:'gmail_non_lus'});
  expect(get(model).integrationData['gmail_non_lus'].rows?.[0].detailStatus).toBe('loading');
  expect(get(model).integrationData['gmail_non_lus'].rows?.[1].detailStatus).toBeUndefined();
  receive({type:'raccourci_resultat',action:'gmail_resumer_mail',item:'msg1',panel:'gmail_non_lus',text:'**Résumé** du mail A.'});
  const rows=get(model).integrationData['gmail_non_lus'].rows!;
  expect(rows[0]).toMatchObject({detail:'**Résumé** du mail A.',detailStatus:'ok'});
  expect(rows[1].detail).toBeUndefined();
  // le panneau lui-même reste "ok" avec ses stats intactes — un détail de
  // ligne ne doit jamais faire régresser tout le dashboard en chargement.
  expect(get(model).integrationData['gmail_non_lus'].status).toBe('ok');
  expect(get(model).integrationData['gmail_non_lus'].stats?.[0].value).toBe('2');
 });
 it('une erreur de detail ne marque que la ligne concernée',()=>{
  receive({type:'connexion',connecte:true});
  receive({type:'raccourci_resultat',action:'jira_mes_tickets',stats:[],rows:[{title:'A',meta:'',id:'AXON-1'}]});
  demanderDetail('jira_mes_tickets','jira_detail_ticket','AXON-1');
  receive({type:'raccourci_erreur',action:'jira_detail_ticket',item:'AXON-1',panel:'jira_mes_tickets',message:'404'});
  expect(get(model).integrationData['jira_mes_tickets'].rows?.[0]).toMatchObject({detailStatus:'error',detail:'404'});
  expect(get(model).integrationData['jira_mes_tickets'].status).toBe('ok');
 });
 it('pieces_jointes remplace la liste, glisser bascule le highlight de dépôt',()=>{
  receive({type:'connexion',connecte:true});
  receive({type:'pieces_jointes',items:[{nom:'cours.pdf',statut:'chargement',est_image:false,taille:''}]});
  expect(get(model).attachments).toEqual([{nom:'cours.pdf',statut:'chargement',message:undefined,estImage:false,taille:''}]);
  receive({type:'pieces_jointes',items:[{nom:'cours.pdf',statut:'ok',est_image:false,taille:'42KB'}]});
  expect(get(model).attachments[0]).toMatchObject({statut:'ok',taille:'42KB'});
  expect(get(model).dragActif).toBe(false);
  receive({type:'glisser',actif:true});
  expect(get(model).dragActif).toBe(true);
  receive({type:'glisser',actif:false});
  expect(get(model).dragActif).toBe(false);
 });
 it('une pièce jointe en erreur porte son message, un statut inconnu retombe sur ok',()=>{
  receive({type:'connexion',connecte:true});
  receive({type:'pieces_jointes',items:[{nom:'x.docx',statut:'erreur',message:'fichier introuvable',est_image:false,taille:''},{nom:'y.png',statut:'???',est_image:true,taille:'12KB'}]});
  const items=get(model).attachments;
  expect(items[0]).toMatchObject({statut:'erreur',message:'fichier introuvable'});
  expect(items[1]).toMatchObject({statut:'ok',estImage:true});
 });
 it('déconnexion efface les pièces jointes, demanderPicker/detacherPiece postent le bon message',()=>{
  receive({type:'connexion',connecte:true});
  post.mockClear();
  demanderPicker();
  expect(post).toHaveBeenLastCalledWith({type:'demander_picker'});
  detacherPiece('cours.pdf');
  expect(post).toHaveBeenLastCalledWith({type:'detacher',nom:'cours.pdf'});
  receive({type:'pieces_jointes',items:[{nom:'cours.pdf',statut:'ok',est_image:false,taille:'1KB'}]});
  expect(get(model).attachments).toHaveLength(1);
  receive({type:'connexion',connecte:false});
  expect(get(model).attachments).toEqual([]);
 });
 it('creerSuivi poste le bon message avec un id, et rien hors connexion/démo',()=>{
  expect(creerSuivi('Machine Learning','matiere','ML')).toBeUndefined(); // pas connecté : rien
  expect(post).not.toHaveBeenCalled();
  receive({type:'connexion',connecte:true});
  post.mockClear();
  const id=creerSuivi('Machine Learning','matiere','ML');
  expect(id).toBeTruthy();
  expect(post).toHaveBeenLastCalledWith({type:'creer_suivi',id,titre:'Machine Learning',type_suivi:'matiere',matiere:'ML'});
  // §2, lot 3 : l'état "en cours" vit dans le modèle, pas seulement dans le
  // composant — une reconnexion perdue peut ainsi le débloquer (voir le test
  // de déconnexion ci-dessous).
  expect(get(model).creationSuivi).toEqual({id,statut:'en_cours'});
 });
 it('un flux accumule ses morceaux puis se termine, et une déconnexion arrête un flux en cours',()=>{
  receive({type:'connexion',connecte:true});
  const id=demanderFlux('resume_suivi','suivi_a')!;
  expect(post).toHaveBeenLastCalledWith({type:'demander_flux',id,genre:'resume_suivi',cible:'suivi_a'});
  receive({type:'flux_morceau',id,texte:'**En bref** '});
  receive({type:'flux_morceau',id,texte:'une API.'});
  expect(get(model).flux[id]).toEqual({genre:'resume_suivi',cible:'suivi_a',texte:'**En bref** une API.',statut:'en_cours'});
  receive({type:'flux_fin',id});
  expect(get(model).flux[id].statut).toBe('fini');
  const autre=demanderFlux('resume_suivi','suivi_b')!;
  receive({type:'connexion',connecte:false});
  expect(get(model).flux[autre]).toMatchObject({statut:'erreur'});
  expect(get(model).flux[id].statut).toBe('fini'); // un flux terminé reste tel quel
 });
 it('ouvrir un suivi demande sa page, et une réponse pour un AUTRE suivi est ignorée',()=>{
  receive({type:'connexion',connecte:true});
  ouvrirSuivi('suivi_a');
  expect(get(model).view).toBe('suivi');
  expect(post).toHaveBeenLastCalledWith(expect.objectContaining({type:'raccourci',action:'etudes_page_suivi',item:'suivi_a'}));
  receive({type:'raccourci_resultat',action:'etudes_page_suivi',item:'suivi_b',page:{id:'suivi_b'}});
  expect(get(model).pageSuivi?.statut).toBe('loading');
  receive({type:'raccourci_resultat',action:'etudes_page_suivi',item:'suivi_a',page:{id:'suivi_a',titre:'P'}});
  expect(get(model).pageSuivi).toMatchObject({id:'suivi_a',statut:'ok',donnees:{titre:'P'}});
 });
 it('une déconnexion pendant une création de suivi en vol la fait échouer, pas rester bloquée',()=>{
  receive({type:'connexion',connecte:true});
  const id=creerSuivi('Machine Learning','matiere','ML');
  receive({type:'connexion',connecte:false});
  expect(get(model).creationSuivi).toMatchObject({id,statut:'erreur'});
 });
 it('une déconnexion pendant une action d’échéance en vol (reporter/annuler/archiver) la fait échouer, pas rester bloquée',()=>{
  receive({type:'connexion',connecte:true});
  const id=majEcheance('suivi_abc','ech_1',{date:'2026-12-02'});
  expect(get(model).actionEtudes).toEqual({id,statut:'en_cours'});
  receive({type:'connexion',connecte:false});
  expect(get(model).actionEtudes).toMatchObject({id,statut:'erreur'});
 });
 it('un appel d’outil atterrit dans activity ET dans messages, dans l’ordre',()=>{
  receive({type:'connexion',connecte:true});
  receive({type:'message',texte:'Je commence la recherche.'});
  receive({type:'outil',nom:'web_search',detail:'exemple.com/article'});
  receive({type:'message',texte:'Voilà ce que j’ai trouvé.'});
  const m=get(model).messages;
  expect(m.map(x=>x.who)).toEqual(['axon','outil','axon']);
  expect(m[1]).toMatchObject({text:'web_search',detail:'exemple.com/article'});
  expect(get(model).activity.at(-1)).toMatchObject({name:'web_search',detail:'exemple.com/article'});
 });
 it('un raccourci qui ne reçoit jamais de réponse finit en erreur, pas bloqué en chargement indéfiniment',()=>{
  // Reproduit le bug signalé : une session Axon pas relancée depuis la mise
  // à jour de l'île ignore "raccourci" sans jamais répondre — avant ce
  // correctif, le panneau restait bloqué sur le squelette pour toujours.
  vi.useFakeTimers();
  receive({type:'connexion',connecte:true});
  demanderRaccourci('gmail_non_lus');
  expect(get(model).integrationData['gmail_non_lus'].status).toBe('loading');
  vi.advanceTimersByTime(11999);
  expect(get(model).integrationData['gmail_non_lus'].status).toBe('loading');
  vi.advanceTimersByTime(2);
  expect(get(model).integrationData['gmail_non_lus']).toMatchObject({status:'error'});
  expect(get(model).integrationData['gmail_non_lus'].message).toContain('relance');
  vi.useRealTimers();
 });
 it('une vraie réponse avant le délai annule le message "sans réponse" (pas de course)',()=>{
  vi.useFakeTimers();
  receive({type:'connexion',connecte:true});
  demanderRaccourci('gmail_non_lus');
  receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[],rows:[]});
  vi.advanceTimersByTime(20000); // largement après le délai
  expect(get(model).integrationData['gmail_non_lus'].status).toBe('ok'); // pas écrasé par le timeout
  vi.useRealTimers();
 });
 it('le détail d’une ligne qui ne répond jamais finit aussi en erreur',()=>{
  vi.useFakeTimers();
  receive({type:'connexion',connecte:true});
  receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[],rows:[{title:'A',meta:'',id:'msg1'}]});
  demanderDetail('gmail_non_lus','gmail_resumer_mail','msg1');
  vi.advanceTimersByTime(12001);
  const row=get(model).integrationData['gmail_non_lus'].rows?.[0];
  expect(row).toMatchObject({detailStatus:'error'});
  vi.useRealTimers();
 });
});
