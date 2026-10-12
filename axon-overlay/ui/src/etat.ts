import type {AgentState} from './types';

//: Un libellé par état, partagé par le rail des vues détaillées et l'accueil.
export const LIBELLES_ETAT:Record<AgentState,string>={
 idle:'Disponible',
 thinking:'Réfléchit',
 working:'Au travail',
 waiting:'Attend ta réponse',
 finished:'Terminé',
 sleeping:'Hors ligne',
 error:'Erreur',
};
