import {it,expect,vi} from 'vitest';import {get} from 'svelte/store';import {mount,unmount,tick} from 'svelte';import App from '../ui/src/App.svelte';import {model,receive,navigate,reset,setDraft} from '../ui/src/model';import {lines} from '../ui/src/diff';import {entrance} from '../ui/src/entrance';
it('cliquer une intégration ouvre son aperçu, retour revient à la liste',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 const gmail=[...target.querySelectorAll('.pill')].find(b=>b.textContent?.includes('Gmail')) as HTMLButtonElement;
 gmail.click();await tick();
 expect(target.querySelector('.dash-glass')?.textContent).toContain('Gmail');
 expect(target.querySelectorAll('.row.link')).toHaveLength(0);
 (target.querySelector('.back') as HTMLButtonElement).click();await tick();
 expect(target.querySelector('.dash-glass')).toBeNull();
 expect(target.querySelectorAll('.row.link')).toHaveLength(4);
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('ouvrir Gmail connecté charge, puis affiche les vraies données reçues',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 const gmail=[...target.querySelectorAll('.pill')].find(b=>b.textContent?.includes('Gmail')) as HTMLButtonElement;
 gmail.click();await tick();
 expect(target.querySelector('.badge')?.textContent).toBe('Chargement');
 expect(target.querySelector('.bar')).not.toBeNull(); // squelette de chargement
 receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[{label:'Non lus',value:'2',accent:true}],rows:[{title:'Objet réel',meta:'Quelqu’un · maintenant'}]});
 await tick();
 expect(target.querySelector('.badge')?.textContent).toBe('En direct');
 expect(target.querySelector('.bar')).toBeNull();
 expect(target.querySelector('.dash-glass')?.textContent).toContain('Objet réel');
 expect(target.querySelector('.dash-glass')?.textContent).not.toContain('Point hebdo équipe'); // plus le mock
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('cliquer sur une ligne Gmail déclenche son résumé et l’affiche en markdown',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 const gmail=[...target.querySelectorAll('.pill')].find(b=>b.textContent?.includes('Gmail')) as HTMLButtonElement;
 gmail.click();await tick();
 receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[{label:'Non lus',value:'1',accent:true}],rows:[{title:'Objet réel',meta:'Quelqu’un · maintenant',id:'msg1'}]});
 await tick();
 const trigger=target.querySelector('.expand-toggle') as HTMLButtonElement;
 expect(trigger).not.toBeNull();
 trigger.click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'raccourci',action:'gmail_resumer_mail',item:'msg1',panel:'gmail_non_lus'}));
 expect(target.querySelector('.expand')?.textContent).toContain('chargement');
 receive({type:'raccourci_resultat',action:'gmail_resumer_mail',item:'msg1',panel:'gmail_non_lus',text:'**Camille** a écrit ceci.'});
 await tick();
 expect(target.querySelector('.expand .md strong')?.textContent).toBe('Camille');
 // replier puis redéplier ne redemande rien : le détail est en cache.
 post.mockClear();
 trigger.click();await tick();
 trigger.click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='raccourci')).toHaveLength(0);
 expect(target.querySelector('.expand .md strong')?.textContent).toBe('Camille');
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('« Générer une réponse » sur un mail au survol envoie le contexte réel au chat, pas un texte figé',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 const gmail=[...target.querySelectorAll('.pill')].find(b=>b.textContent?.includes('Gmail')) as HTMLButtonElement;
 gmail.click();await tick();
 receive({type:'raccourci_resultat',action:'gmail_non_lus',stats:[{label:'Non lus',value:'1',accent:true}],rows:[{title:'Objet réel',meta:'Quelqu’un · maintenant',id:'msg1'}]});
 await tick();
 const reply=target.querySelector('.row-action[aria-label="Générer une réponse"]') as HTMLButtonElement;
 expect(reply).not.toBeNull();
 post.mockClear();
 reply.click();await tick();
 expect(get(model).view).toBe('chat');
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'commande',texte:expect.stringContaining('msg1')}));
 const sent=post.mock.calls.find(c=>c[0].type==='commande')?.[0].texte as string;
 expect(sent).toContain('Objet réel');
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('une erreur de raccourci affiche un état d’erreur avec reprise',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 const jira=[...target.querySelectorAll('.pill')].find(b=>b.textContent?.includes('Jira')) as HTMLButtonElement;
 jira.click();await tick();
 receive({type:'raccourci_erreur',action:'jira_mes_tickets',message:'401 non autorisé'});
 await tick();
 expect(target.querySelector('.badge')?.textContent).toBe('Erreur');
 expect(target.querySelector('.error')?.textContent).toContain('401 non autorisé');
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('« Autre (préciser) » révèle un champ juste à sa place et y met le focus',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('chat');receive({type:'demande',id:1,questions:[{texte:'Quel format ?',choix:['JSON','CSV']}]});await tick();
 const buttons=[...target.querySelectorAll('.choices button')].map(b=>b.textContent);
 expect(buttons).toEqual(['JSON','CSV','Autre (préciser)']);
 const autre=[...target.querySelectorAll('.choices button')].find(b=>b.textContent==='Autre (préciser)') as HTMLButtonElement;
 autre.click();await tick();await tick();
 expect(target.querySelector('.choices')).toBeNull();
 const input=target.querySelector('#freeform-input') as HTMLInputElement;
 expect(input).not.toBeNull();
 expect(document.activeElement).toBe(input); // le focus reste là, pas sur le champ principal du chat
 input.value='PDF';input.dispatchEvent(new Event('input',{bubbles:true}));await tick();
 (target.querySelector('.freeform-send') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenLastCalledWith({type:'reponse_demande',id:1,reponses:['PDF']});
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('un picker à choix fermé (libre:false) ne propose pas « Autre »',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('chat');receive({type:'demande',id:1,questions:[{texte:'backend LLM',choix:['groq','ollama'],libre:false}]});await tick();
 const buttons=[...target.querySelectorAll('.choices button')].map(b=>b.textContent);
 expect(buttons).toEqual(['groq','ollama']);
 expect(target.querySelector('#freeform-input')).toBeNull();
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('garde les mêmes vues et les mêmes images pendant une rafale d’événements',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 const root=target.querySelector('.island'),mascot=target.querySelector('[data-mascot]');const images=[...target.querySelectorAll('[data-mascot] img')];const sources=images.map(i=>i.getAttribute('src'));const views=[...target.querySelectorAll('.view')];
 for(let i=0;i<20;i++){receive({type:'etat',etat:i%2?'working':'thinking'});receive({type:'outil',nom:'read_file',detail:'file'+i});setDraft('draft'+i);navigate(i%2?'chat':'home');await tick();expect(target.querySelector('.island')).toBe(root);expect(target.querySelector('[data-mascot]')).toBe(mascot);expect([...target.querySelectorAll('[data-mascot] img')]).toEqual(images);expect(images.map(i=>i.getAttribute('src'))).toEqual(sources);expect([...target.querySelectorAll('.view')]).toEqual(views);expect(images.filter(i=>i.classList.contains('shown'))).toHaveLength(1);}
 receive({type:'message',texte:'<img src=x onerror=attack()>'});await tick();expect(target.querySelector('.log img')).toBeNull();await unmount(app);target.remove();delete window.webkit;reset();
});
it('un appel d’outil s’affiche en ligne compacte dans la conversation, pas en bulle de message',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 receive({type:'outil',nom:'web_search',detail:'exemple.com/article'});
 receive({type:'outil',nom:'read_file',detail:'ui/src/App.svelte'});
 await tick();
 const events=[...target.querySelectorAll('.tool-event')];
 expect(events).toHaveLength(2);
 expect(events[0].textContent).toContain('web_search');
 expect(events[0].textContent).toContain('exemple.com/article');
 expect(events[0].querySelector('.tool-mark svg path')?.getAttribute('d')).not.toBe(events[1].querySelector('.tool-mark svg path')?.getAttribute('d')); // icônes distinctes (globe vs file)
 expect(target.querySelectorAll('article.mine, article:not(.mine)')).toHaveLength(0); // pas de bulle pour un outil
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('numérote les ajouts/retraits du diff selon les deux fichiers',()=>{expect(lines({path:'a',diff:true,start:1,content:'@@ -12 +12 @@\n-old\n+new'})).toEqual([{text:'old',kind:'remove',number:12},{text:'new',kind:'add',number:12}]);});
//: Trois sections de l'île partagent le composant `Row` générique — on les
//: retrouve par leur titre plutôt que par ordre dans le DOM, pour ne pas
//: dépendre d'un ordre de rendu qui pourrait changer sans casser la vraie UI.
function sectionÉtudes(target:HTMLElement,titre:string){
 return [...target.querySelectorAll('.etudes section')].find(s=>s.querySelector('.section-head')?.textContent?.includes(titre)) as HTMLElement;
}

it('la vue Études charge suivis/échéances/récents à l’ouverture, et « ouvrir » redemande le bon raccourci',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 post.mockClear();
 (target.querySelector('[aria-label="Études"]') as HTMLButtonElement).click();await tick();
 const actions=post.mock.calls.map(c=>c[0]).filter(m=>m.type==='raccourci').map(m=>m.action);
 expect(actions).toEqual(['etudes_fiches_recentes','etudes_suivis','etudes_echeances']);
 expect(target.querySelector('.etudes-actions')).toBeNull(); // pas de document attaché → pas de boutons

 receive({type:'raccourci_resultat',action:'etudes_fiches_recentes',stats:[{label:'Récents',value:'1',accent:true}],rows:[{title:'fiche_bio',meta:'10/10 10:00',tag:'fiche',id:'fiche_bio.html'}]});
 await tick();
 const recents=sectionÉtudes(target,'Récents');
 expect(recents.querySelector('.row')?.textContent).toContain('fiche_bio');
 post.mockClear();
 (recents.querySelector('.row-action') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'raccourci',action:'etudes_ouvrir_fiche',item:'fiche_bio.html',panel:'etudes_fiches_recentes'}));

 receive({type:'pieces_jointes',items:[{nom:'cours.pdf',statut:'ok',est_image:false,taille:'10KB'}]});
 await tick();
 expect(target.querySelectorAll('.etudes-actions .action')).toHaveLength(2);
 post.mockClear();
 (target.querySelectorAll('.etudes-actions .action')[0] as HTMLButtonElement).click();await tick();
 expect(get(model).view).toBe('chat');
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'commande',texte:'/fiche'}));
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('un suivi affiché propose « créer une fiche »/« générer des exercices » qui passent son ID, et une échéance s’affiche dans sa propre section',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});
 (target.querySelector('[aria-label="Études"]') as HTMLButtonElement).click();await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Machine Learning',meta:'matiere · Partiel (2026-11-25)',tag:'matiere',id:'suivi_abc123'}]});
 receive({type:'raccourci_resultat',action:'etudes_echeances',stats:[{label:'À venir',value:'1',accent:true}],rows:[{title:'Partiel',meta:'Machine Learning · 2026-11-25',tag:'partiel',id:'ech_xyz789'}]});
 await tick();

 const suivis=sectionÉtudes(target,'Suivis');
 expect(suivis.querySelector('.row')?.textContent).toContain('Machine Learning');
 const boutons=[...suivis.querySelectorAll('.row-action')].map(b=>b.getAttribute('aria-label'));
 expect(boutons).toEqual(expect.arrayContaining(['Créer une fiche','Générer des exercices']));

 post.mockClear();
 const creerFiche=[...suivis.querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')==='Créer une fiche') as HTMLButtonElement;
 creerFiche.click();await tick();
 expect(get(model).view).toBe('chat');
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'commande',texte:'/fiche suivi_abc123'}));

 const echeances=sectionÉtudes(target,'Échéances');
 expect(echeances.querySelector('.echeance')?.textContent).toContain('Partiel');
 expect(echeances.querySelector('.echeance')?.textContent).toContain('Machine Learning');
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('glisser-déposer : le highlight de la zone de dépôt suit `dragActif`',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 expect(target.querySelector('.drop')?.classList.contains('actif')).toBe(false);
 receive({type:'glisser',actif:true});await tick();
 expect(target.querySelector('.drop')?.classList.contains('actif')).toBe(true);
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('une pièce jointe apparaît en chip dans le chat, le trombone demande le sélecteur, retirer poste bien le nom',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('chat');await tick();
 expect(target.querySelector('.attachments')).toBeNull(); // rien tant qu'aucune pièce jointe
 post.mockClear();
 (target.querySelector('.attach') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledWith({type:'demander_picker'});
 receive({type:'pieces_jointes',items:[{nom:'cours.pdf',statut:'ok',est_image:false,taille:'12KB'}]});
 await tick();
 const chip=target.querySelector('.attachments .chip');
 expect(chip?.textContent).toContain('cours.pdf');
 expect(chip?.textContent).toContain('12KB');
 post.mockClear();
 (target.querySelector('.attachments .remove') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledWith({type:'detacher',nom:'cours.pdf'});
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('une pièce jointe en erreur affiche le message au lieu de la taille',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('chat');
 receive({type:'pieces_jointes',items:[{nom:'x.docx',statut:'erreur',message:'fichier introuvable',est_image:false,taille:''}]});
 await tick();
 const chip=target.querySelector('.attachments .chip');
 expect(chip?.classList.contains('erreur')).toBe(true);
 expect(chip?.textContent).toContain('fichier introuvable');
 expect(target.querySelector('.attachments .remove')).not.toBeNull(); // une erreur reste retirable, contrairement au chargement
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('une pièce jointe en cours de lecture n’a pas de bouton retirer',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('chat');
 receive({type:'pieces_jointes',items:[{nom:'gros.pdf',statut:'chargement',est_image:false,taille:''}]});
 await tick();
 expect(target.querySelector('.attachments .chip')?.textContent).toContain('lecture');
 expect(target.querySelector('.attachments .remove')).toBeNull();
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('un bouton « passer » n’existe que pendant l’arrivée, pour pouvoir la sauter au clic',async()=>{
 reset();window.webkit={messageHandlers:{axon:{postMessage:vi.fn()}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 expect(target.querySelector('.skip-entree')).toBeNull(); // rien hors arrivée
 await unmount(app);target.remove();delete window.webkit;reset();entrance.set('rest');
});
it('créer un suivi depuis Études ne referme le formulaire qu’après confirmation du backend',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();

 expect(target.querySelector('[aria-label="Titre du suivi"]')).toBeNull(); // formulaire fermé par défaut
 (target.querySelector('[aria-label="Nouveau suivi"]') as HTMLButtonElement).click();await tick();await tick();
 const titreInput=target.querySelector('[aria-label="Titre du suivi"]') as HTMLInputElement;
 expect(titreInput).not.toBeNull();
 expect(document.activeElement).toBe(titreInput); // focus automatique, même patron que FreeformAnswer

 titreInput.value='Machine Learning';titreInput.dispatchEvent(new Event('input',{bubbles:true}));
 await tick();
 post.mockClear();
 (target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledTimes(1);
 const message=post.mock.calls[0][0];
 expect(message).toMatchObject({type:'creer_suivi',titre:'Machine Learning',type_suivi:'matiere',matiere:''});
 expect(typeof message.id).toBe('string');
 // §2, lot 3 : plus de fermeture optimiste — le formulaire reste ouvert et
 // désactivé tant que le backend n'a pas confirmé.
 expect(target.querySelector('[aria-label="Titre du suivi"]')).not.toBeNull();
 expect((target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).disabled).toBe(true);

 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc'}]});
 receive({type:'creer_suivi_resultat',id:message.id});
 await tick();
 expect(sectionÉtudes(target,'Suivis').textContent).toContain('Machine Learning');
 expect(target.querySelector('[aria-label="Titre du suivi"]')).toBeNull(); // refermé après confirmation
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('un échec de création garde les champs et affiche l’erreur, sans refermer le formulaire',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();

 (target.querySelector('[aria-label="Nouveau suivi"]') as HTMLButtonElement).click();await tick();await tick();
 const titreInput=target.querySelector('[aria-label="Titre du suivi"]') as HTMLInputElement;
 titreInput.value='Machine Learning';titreInput.dispatchEvent(new Event('input',{bubbles:true}));
 await tick();
 (target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).click();await tick();
 const id=post.mock.calls[post.mock.calls.length-1][0].id;

 receive({type:'creer_suivi_erreur',id,message:'titre manquant'});
 await tick();
 // Toujours ouvert, titre CONSERVÉ (pas réinitialisé), erreur affichée.
 expect((target.querySelector('[aria-label="Titre du suivi"]') as HTMLInputElement).value).toBe('Machine Learning');
 expect(target.textContent).toContain('titre manquant');
 expect((target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).disabled).toBe(false); // réessayable
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('un titre vide ne crée rien, Échap referme le formulaire sans rien poster',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 (target.querySelector('[aria-label="Nouveau suivi"]') as HTMLButtonElement).click();await tick();
 expect((target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).disabled).toBe(true);
 post.mockClear();
 (target.querySelector('[aria-label="Créer"]') as HTMLButtonElement).click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='creer_suivi')).toHaveLength(0);
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('le bouton de génération se désactive dès que le backend signale une génération en cours',async()=>{
 // §1, lot 3 : le verrou anti-doublon vit désormais côté backend
 // (`generation_active`, voir tests/test_streaming_generation_lock.py côté
 // Python), pas dans un délai local côté île. Ce test vérifie le CONTRAT
 // frontend : une fois que le statut "en_cours" arrive sur la ligne, le
 // bouton se désactive et un clic supplémentaire ne poste plus rien.
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc'}]});
 await tick();
 const bouton=(label:string)=>[...sectionÉtudes(target,'Suivis').querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')===label) as HTMLButtonElement|undefined;

 post.mockClear();
 bouton('Créer une fiche')!.click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='commande'&&c[0].texte==='/fiche suivi_abc')).toHaveLength(1);

 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],
          rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc',generationFicheStatut:'en_cours'}]});
 await tick();
 const enCours=bouton('Génération en cours');
 expect(enCours).not.toBeUndefined();
 expect(enCours!.disabled).toBe(true);
 expect(bouton('Créer une fiche')).toBeUndefined(); // le libellé de départ a disparu, pas juste masqué

 post.mockClear();
 enCours!.click();await tick(); // un bouton disabled ne déclenche pas onclick en DOM
 expect(post.mock.calls.filter(c=>c[0].type==='commande')).toHaveLength(0);
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('une génération échouée propose « Réessayer », une terminée « Ouvrir le résultat »',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],
          rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc',generationFicheStatut:'echouee',generationExoStatut:'terminee',generationExoFichier:'exo_ml.html'}]});
 await tick();
 const bouton=(label:string)=>[...sectionÉtudes(target,'Suivis').querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')===label) as HTMLButtonElement|undefined;

 const reessayer=bouton('Réessayer');
 expect(reessayer).not.toBeUndefined();
 expect(reessayer!.disabled).toBeFalsy(); // réessayable, pas bloqué comme "en_cours"
 post.mockClear();
 reessayer!.click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='commande'&&c[0].texte==='/fiche suivi_abc')).toHaveLength(1);

 const ouvrir=bouton('Ouvrir le résultat');
 expect(ouvrir).not.toBeUndefined();
 post.mockClear();
 ouvrir!.click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='raccourci'&&(c[0] as {action?:string}).action==='etudes_ouvrir_fiche')).toHaveLength(1);
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('créer une échéance depuis Études poste le bon message avec le suivi choisi, et ne referme qu’après confirmation',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc'}]});
 await tick();

 const echeances=sectionÉtudes(target,'Échéances');
 (echeances.querySelector('[aria-label="Nouvelle échéance"]') as HTMLButtonElement).click();await tick();
 const titreInput=echeances.querySelector('[aria-label="Titre de l’échéance"]') as HTMLInputElement;
 titreInput.value='Partiel';titreInput.dispatchEvent(new Event('input',{bubbles:true}));
 const dateInput=echeances.querySelector('[aria-label="Date de l’échéance"]') as HTMLInputElement;
 dateInput.value='2026-11-25';dateInput.dispatchEvent(new Event('input',{bubbles:true}));
 await tick();
 post.mockClear();
 (echeances.querySelector('[aria-label="Créer"]') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledTimes(1);
 const message=post.mock.calls[0][0];
 expect(message).toMatchObject({type:'creer_echeance',suivi_id:'suivi_abc',titre:'Partiel',type_echeance:'devoir',date:'2026-11-25'});
 expect(typeof message.id).toBe('string');
 expect(echeances.querySelector('[aria-label="Titre de l’échéance"]')).not.toBeNull(); // pas refermé avant confirmation

 receive({type:'etudes_action_resultat',id:message.id});
 await tick();
 expect(echeances.querySelector('[aria-label="Titre de l’échéance"]')).toBeNull();
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('reporter une échéance révèle un champ date et poste maj_echeance avec son suivi_id',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_echeances',stats:[{label:'À venir',value:'1',accent:true}],
          rows:[{title:'Partiel',meta:'Machine Learning · 2026-11-25',tag:'partiel',id:'ech_1',suiviId:'suivi_abc'}]});
 await tick();

 const echeances=sectionÉtudes(target,'Échéances');
 (echeances.querySelector('[aria-label="Reporter"]') as HTMLButtonElement).click();await tick();
 const dateInput=echeances.querySelector('[aria-label="Nouvelle date"]') as HTMLInputElement;
 expect(dateInput).not.toBeNull();
 dateInput.value='2026-12-02';dateInput.dispatchEvent(new Event('input',{bubbles:true}));
 await tick();
 post.mockClear();
 (echeances.querySelector('[aria-label="Confirmer le report"]') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'maj_echeance',suivi_id:'suivi_abc',echeance_id:'ech_1',date:'2026-12-02'}));

 receive({type:'etudes_action_resultat',id:(post.mock.calls[0][0] as {id:string}).id});
 await tick();
 expect(echeances.querySelector('[aria-label="Nouvelle date"]')).toBeNull(); // refermé après confirmation
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('annuler une échéance poste maj_echeance avec statut annulee, sans ouvrir le report',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_echeances',stats:[{label:'À venir',value:'1',accent:true}],
          rows:[{title:'Partiel',meta:'Machine Learning · 2026-11-25',tag:'partiel',id:'ech_1',suiviId:'suivi_abc'}]});
 await tick();

 const echeances=sectionÉtudes(target,'Échéances');
 post.mockClear();
 (echeances.querySelector('[aria-label="Annuler l’échéance"]') as HTMLButtonElement).click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'maj_echeance',suivi_id:'suivi_abc',echeance_id:'ech_1',statut:'annulee'}));
 expect(echeances.querySelector('[aria-label="Nouvelle date"]')).toBeNull();
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('archiver un suivi poste archiver_suivi avec son id',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Machine Learning',meta:'matiere',tag:'matiere',id:'suivi_abc'}]});
 await tick();

 const suivis=sectionÉtudes(target,'Suivis');
 post.mockClear();
 const archiver=[...suivis.querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')==='Archiver') as HTMLButtonElement;
 expect(archiver).not.toBeUndefined();
 archiver.click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'archiver_suivi',suivi_id:'suivi_abc'}));
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('« Ajouter un autre dossier ou dépôt » sur un suivi demande le sélecteur en mode dossier, et un échec s’affiche',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[{label:'Suivis actifs',value:'1',accent:true}],rows:[{title:'Projet Compilateur',meta:'Aucune échéance',tag:'Projet',id:'suivi_abc'}]});
 await tick();

 const bouton=(label:string)=>[...sectionÉtudes(target,'Suivis').querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')===label) as HTMLButtonElement|undefined;
 expect(bouton('Ajouter un fichier')).not.toBeUndefined();
 post.mockClear();
 bouton('Ajouter un autre dossier ou dépôt')!.click();await tick();
 const message=post.mock.calls.find(c=>c[0].type==='lier_ressource')?.[0];
 expect(message).toMatchObject({type:'lier_ressource',suivi_id:'suivi_abc',mode:'dossier'});

 receive({type:'etudes_action_erreur',id:message.id,message:'Suivi introuvable : suivi_abc'});
 await tick();
 expect(target.querySelector('.notice')?.textContent).toContain('Suivi introuvable');
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('la zone de dépôt propose « Fichier » et « Dossier ou dépôt », ce dernier sans suivi visé',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 const boutons=[...target.querySelectorAll('.drop button')] as HTMLButtonElement[];
 expect(boutons.map(b=>b.textContent?.trim())).toEqual(['Fichier','Dossier ou dépôt']);
 post.mockClear();
 boutons[0].click();await tick();
 expect(post).toHaveBeenCalledWith({type:'demander_picker'});
 boutons[1].click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'lier_ressource',suivi_id:'',mode:'dossier'}));
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('supprimer un suivi demande un second clic de confirmation avant d’envoyer quoi que ce soit',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[],rows:[{title:'be-cds',meta:'1 ressource',tag:'Projet',id:'suivi_be'}]});
 await tick();
 const bouton=(label:string)=>[...sectionÉtudes(target,'Suivis').querySelectorAll('.row-action')].find(b=>b.getAttribute('aria-label')===label) as HTMLButtonElement|undefined;

 post.mockClear();
 bouton('Supprimer le suivi')!.click();await tick();
 expect(post.mock.calls.filter(c=>c[0].type==='supprimer_suivi')).toHaveLength(0); // juste armé
 const confirmer=bouton('Confirmer la suppression');
 expect(confirmer?.classList.contains('danger')).toBe(true);

 confirmer!.click();await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'supprimer_suivi',suivi_id:'suivi_be'}));
 expect(bouton('Supprimer le suivi')).not.toBeUndefined(); // désarmé après envoi
 await unmount(app);target.remove();delete window.webkit;reset();
});
it('cliquer un suivi ouvre sa page : données tout de suite, résumé IA en flux, puis rechargement',async()=>{
 reset();const post=vi.fn();window.webkit={messageHandlers:{axon:{postMessage:post}}};const target=document.createElement('div');document.body.append(target);const app=mount(App,{target});await tick();
 receive({type:'connexion',connecte:true});navigate('etudes');await tick();
 receive({type:'raccourci_resultat',action:'etudes_suivis',stats:[],rows:[{title:'Conseil des Sages',meta:'2 ressources',tag:'Projet',id:'suivi_cds'}]});
 await tick();
 (sectionÉtudes(target,'Suivis').querySelector('.text.ouvrir') as HTMLButtonElement).click();await tick();
 expect(get(model).view).toBe('suivi');

 post.mockClear();
 receive({type:'raccourci_resultat',action:'etudes_page_suivi',item:'suivi_cds',page:{
  id:'suivi_cds',titre:'Conseil des Sages',type:'Projet',description:'',
  echeances:[{id:'e1',titre:'Rendu final',type:'Rendu',date:'2099-12-10',dateCourte:'10 déc.',restant:'dans 59 jours',statut:'a_venir',rappels:0}],
  taches:[],exercices:{total:0,termines:0},
  ressources:[{id:'r1',nom:'be-cds',type:'depot_git',chemin:'/x',branche:'feat/user-post',age:'il y a 7 h',sujet:'adding post',modifies:0}],
  resultats:[],verification:null,resume:null,calendrier:[{date:'2099-12-10',libelle:'Rendu final',genre:'echeance'}]}});
 await tick();
 const page=target.querySelector('.page') as HTMLElement;
 expect(page.textContent).toContain('Conseil des Sages');
 expect(page.textContent).toContain('feat/user-post · il y a 7 h · adding post'); // données locales, sans attendre l'IA
 expect(page.querySelector('[aria-label="Programmer les rappels"]')).not.toBeNull(); // 0 rappel → cloche
 const demande=post.mock.calls.find(c=>c[0].type==='demander_flux')?.[0];
 expect(demande).toMatchObject({genre:'resume_suivi',cible:'suivi_cds'}); // pas de résumé en cache → demandé tout seul
 await tick(); // flux demandé pendant le rendu de la page : visible au tick suivant
 expect(page.querySelector('.attente')).not.toBeNull(); // squelette tant que rien n'arrive

 receive({type:'flux_morceau',id:demande.id,texte:'**En bref** une plateforme de débats.'});await tick();
 expect(page.querySelector('.flux .md strong')?.textContent).toBe('En bref');
 post.mockClear();
 receive({type:'flux_fin',id:demande.id});await tick();
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'raccourci',action:'etudes_page_suivi',item:'suivi_cds'})); // résumé enregistré → page rechargée
 await unmount(app);target.remove();delete window.webkit;reset();
});
