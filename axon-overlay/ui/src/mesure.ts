import { ajusterNotif } from './model';

//: La fenêtre native suit la hauteur du contenu d'une notification ou d'une
//: bulle : l'élément annoncé ici, au moins la hauteur de la mascotte, plus les
//: marges de l'île. Au-delà du maximum natif, c'est le contenu qui défile.
const MARGES = 26;
export const HAUTEUR_MASCOTTE = 112;

export function hauteurNative(noeud: HTMLElement, surMesure: () => void = () => undefined) {
  if (typeof ResizeObserver === 'undefined') return {};
  const observateur = new ResizeObserver(() => {
    ajusterNotif(Math.max(HAUTEUR_MASCOTTE, noeud.scrollHeight) + MARGES);
    surMesure();
  });
  observateur.observe(noeud);
  return { destroy: () => observateur.disconnect() };
}
