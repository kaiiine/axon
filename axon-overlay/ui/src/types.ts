export type View = 'home' | 'chat' | 'code' | 'settings' | 'integrations' | 'etudes' | 'suivi';
export type AgentState = 'idle' | 'thinking' | 'working' | 'waiting' | 'finished' | 'sleeping' | 'error';
export interface Question { texte: string; choix: string[]; affirmatif?: string; libre?: boolean; si?: string }
export interface Request { id: string | number; genre: string; apercu: string; questions: Question[]; answers: string[]; legacy?: boolean; freeform?: boolean }
export interface Message { id: number; who: 'axon' | 'toi' | 'outil'; text: string; detail?: string }
export interface Activity { id: number; name: string; detail: string }
export interface FileContent { path: string; content: string; diff: boolean; start: number }
export interface Command { cmd: string; desc: string }
export interface IntegrationStat { label: string; value: string; accent?: boolean }
//: `generationFiche*`/`generationExo*` sont spécifiques à Études (§1, lot 3)
//: mais vivent sur le type partagé plutôt qu'une variante : optionnels, donc
//: sans effet pour Gmail/Jira/Calendar qui ne les remplissent jamais.
export type StatutGeneration = 'en_cours' | 'terminee' | 'echouee';
export interface IntegrationRow { title: string; meta: string; tag?: string; accent?: boolean; id?: string; detail?: string; detailStatus?: 'loading' | 'ok' | 'error'; generationFicheStatut?: StatutGeneration; generationFicheFichier?: string; generationExoStatut?: StatutGeneration; generationExoFichier?: string; suiviId?: string }
export interface IntegrationData { status: 'loading' | 'ok' | 'error'; stats?: IntegrationStat[]; rows?: IntegrationRow[]; message?: string; generationFicheStatut?: StatutGeneration; generationFicheFichier?: string; generationExoStatut?: StatutGeneration; generationExoFichier?: string }
//: Une pièce jointe en attente, côté île — miroir de `Attachment`
//: (src/ui/attachments.py), pas son contenu complet (jamais envoyé sur le
//: socket, seulement le nécessaire pour l'afficher).
export interface AttachmentItem { nom: string; statut: 'chargement' | 'ok' | 'erreur'; message?: string; estImage: boolean; taille: string }
export type Outbound = { type: 'commande'; texte: string } | { type: 'reponse_demande'; id: string | number; reponses: string[] } | { type: 'decision'; id: string | number; accord: boolean } | { type: 'demander_commandes' } | { type: 'mode'; mode: ModeNatif; hauteur?: number } | { type: 'ouvrir'; ouvert: boolean } | { type: 'pret' } | { type: 'raccourci'; id: string; action: string; item?: string; panel?: string } | { type: 'joindre'; chemin: string } | { type: 'detacher'; nom: string } | { type: 'demander_picker' } | { type: 'creer_suivi'; id: string; titre: string; type_suivi: string; matiere?: string } | { type: 'creer_echeance'; id: string; suivi_id: string; titre: string; type_echeance: string; date: string } | { type: 'maj_echeance'; id: string; suivi_id: string; echeance_id: string; date?: string; statut?: string } | { type: 'archiver_suivi'; id: string; suivi_id: string } | { type: 'lier_ressource'; id: string; suivi_id: string; mode: 'fichier' | 'dossier' } | { type: 'supprimer_suivi'; id: string; suivi_id: string } | { type: 'demander_flux'; id: string; genre: string; cible: string } | { type: 'planifier_rappels'; id: string; suivi_id: string; echeance_id: string };
//: Réponse à UNE soumission du formulaire de création de suivi, identifiée
//: par `id` (§2, lot 3) — jamais "le dernier suivi créé", pour qu'une
//: réponse tardive ne vienne pas clore un formulaire déjà réutilisé pour
//: une autre création.
export interface CreationSuivi { id: string; statut: 'en_cours' | 'ok' | 'erreur'; message?: string }
//: Même principe pour les actions d'échéance (créer/reporter/annuler) et
//: d'archivage de suivi (§3, lot 3) — UN slot partagé entre ces trois
//: actions plutôt qu'un par action : elles ont toutes la même forme
//: (ok, ou erreur avec message) et ne sont jamais deux en vol en même
//: temps pour un même composant.
export interface ActionEtudes { id: string; statut: 'en_cours' | 'ok' | 'erreur'; message?: string }
//: Texte produit en temps réel par un appel LLM (src/ui/flux_overlay.py),
//: identifié par l'id de la demande — générique, pas propre aux études.
export interface Flux { genre: string; cible: string; texte: string; statut: 'en_cours' | 'fini' | 'erreur'; message?: string }
export interface EvenementCalendrier { date: string; libelle: string; genre: string }
export interface PageSuivi {
 id: string; titre: string; type: string; description: string;
 echeances: { id: string; titre: string; type: string; date: string; dateCourte: string; restant: string; statut: string; rappels: number }[];
 taches: { id: string; titre: string; statut: string }[];
 exercices: { total: number; termines: number };
 ressources: { id: string; nom: string; type: string; chemin: string; branche?: string; age?: string; sujet?: string; modifies?: number }[];
 resultats: { fichier: string; type: string; date: string }[];
 verification: { date: string; texte: string } | null;
 resume: { texte: string; date: string } | null;
 calendrier: EvenementCalendrier[];
}
export interface EtatPageSuivi { id: string; statut: 'loading' | 'ok' | 'error'; donnees?: PageSuivi; message?: string }
//: Taille de la fenêtre native (overlay.py) : accueil, vues détaillées, ou la
//: petite notification d'une demande HITL.
export type ModeNatif = 'accueil' | 'detail' | 'notif' | 'bulle' | 'pastille';
//: Une demande HITL servie en petite notification plutôt que dans le chat.
//: `fermer` : l'île était fermée à l'arrivée de la demande, elle se referme
//: une fois répondu. `envoye` : la réponse est partie, l'animation de sortie
//: joue avant de rendre la main. `deplie` : false, seule une pastille (Axon)
//: est affichée ; le survol la déplie en notification.
export interface Popup { fermer: boolean; envoye: boolean; deplie: boolean; texte?: string }
//: Un rappel envoyé par le démon cron, qu'Axon dit dans une bulle. `genre`
//: décide des actions proposées (voir rappels.ts) ; une échéance porte son
//: suivi pour y mener.
export type GenreRappel = 'echeance' | 'recapitulatif' | 'tache';
export interface Rappel { id: string; titre: string; texte: string; genre: GenreRappel; suiviId?: string; echeanceId?: string }
//: `enDirect` : la réponse d'Axon en cours d'écriture, '' hors d'un tour.
export interface Model { popup: Popup | null; rappels: Rappel[]; enDirect: string; view: View; state: AgentState; connected: boolean; visible: boolean; demo: boolean; detail: string; draft: string; messages: Message[]; activity: Activity[]; requests: Request[]; commands: Command[]; file: FileContent | null; busy: boolean; motion: boolean; sound: boolean; notice: string; unread: number; integration: string | null; integrationData: Record<string, IntegrationData>; attachments: AttachmentItem[]; dragActif: boolean; creationSuivi: CreationSuivi | null; actionEtudes: ActionEtudes | null; pageSuivi: EtatPageSuivi | null; flux: Record<string, Flux> }
declare global { interface Window { __axonAssets?:Record<string,string>; __axonPreview?:boolean; axon?: { recevoir: (message: unknown) => void; ouvrir: (open: boolean) => void; apercu: () => void; entree: () => void; rejouer: () => void }; webkit?: { messageHandlers?: { axon?: { postMessage: (message: Outbound) => void } } } } }
