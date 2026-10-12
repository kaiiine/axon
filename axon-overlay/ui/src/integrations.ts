export interface IntegrationMeta {
 id:string; name:string; color:string; icon:string; tagline:string;
 //: Raccourci rapide (src/ui/raccourcis_overlay.py) déclenché à l'ouverture
 //: du dashboard — lecture seule, appelle le tool directement, pas de LLM.
 //: Absent (Slack) = pas encore de raccourci rapide pour ce service.
 action?:string;
 //: Raccourci de DÉTAIL, déclenché par un clic sur une ligne précise (son
 //: `id` sert d'`item`). Absent = la ligne n'est pas cliquable pour un
 //: détail à la demande (Workspace l'a déjà dans `row.detail`, pas besoin).
 detailAction?:string;
 //: Libellé du bouton par ligne (ex. "résumer", "détails").
 detailLabel?:string;
 //: Demande en langage naturel envoyée via `demanderAxon` (passe par l'agent
 //: complet, dans le chat) pour aller plus loin que le raccourci.
 ask:string;
}

// Ce qu'Axon sait vraiment utiliser (src/agents/gmail, google_*, slack, jira) —
// le compte vit dans Axon, ce plugin ne fait qu'en afficher un aperçu.
export const INTEGRATIONS:IntegrationMeta[]=[
 {id:'gmail',name:'Gmail',color:'#ea4335',icon:'mail',tagline:'Lire, trier, répondre à ta place.',action:'gmail_non_lus',detailAction:'gmail_resumer_mail',detailLabel:'résumer',ask:'Résume mes derniers mails non lus dans Gmail.'},
 {id:'workspace',name:'Google Workspace',color:'#4285f4',icon:'grid',tagline:'Agenda, Drive, Docs, Sheets, Slides.',action:'workspace_aujourdhui',ask:'Récapitule mon agenda d’aujourd’hui.'},
 {id:'slack',name:'Slack',color:'#611f69',icon:'hash',tagline:'Lire et écrire dans tes canaux.',ask:'Résume les messages récents sur Slack.'},
 {id:'jira',name:'Jira',color:'#0052cc',icon:'flag',tagline:'Suivre et faire avancer tes tickets.',action:'jira_mes_tickets',detailAction:'jira_detail_ticket',detailLabel:'détails',ask:'Fais le point sur mes tickets Jira assignés.'},
];
