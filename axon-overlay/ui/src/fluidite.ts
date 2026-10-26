//: Révèle à un rythme régulier un texte qui grandit par à-coups — le CLI envoie
//: la réponse au plus toutes les 100 ms, par paquets de mots. Afficher chaque
//: paquet d'un coup saccadait ; ici, la vitesse suit le retard : une rafale est
//: rattrapée en `RATTRAPAGE_S`, un filet de texte défile sans à-coups.

export const RATTRAPAGE_S = 0.15;
export const VITESSE_MIN = 40;      // caractères par seconde
const PAS_MAX_S = 0.1;              // un onglet en arrière-plan ne fait pas tout apparaître d'un bloc

type Planifier = (image: (instant: number) => void) => void;

export interface Rythme {
  //: Temps pour rattraper le retard : petit pour suivre un stream, grand pour « parler ».
  rattrapageS?: number;
  vitesseMin?: number;
  planifier?: Planifier;
  maintenant?: () => number;
}

//: Le débit d'Axon qui dit un rappel dans sa bulle : posé, mais jamais lent.
export const PAROLE: Rythme = { rattrapageS: 1.4, vitesseMin: 55 };

export interface Revelation {
  viser(texte: string, fluide: boolean): void;
  arreter(): void;
}

//: Ne coupe jamais au milieu d'un caractère codé sur deux unités (emoji…).
function couper(texte: string, longueur: number): string {
  const code = texte.charCodeAt(longueur - 1);
  return texte.slice(0, code >= 0xd800 && code <= 0xdbff ? longueur + 1 : longueur);
}

export function revelation(afficher: (texte: string) => void, rythme: Rythme = {}): Revelation {
  const {
    rattrapageS = RATTRAPAGE_S,
    vitesseMin = VITESSE_MIN,
    planifier = (image: (instant: number) => void) => { requestAnimationFrame(image); },
    maintenant = () => performance.now(),
  } = rythme;
  let cible = '', montre = '', reste = 0, precedent = 0, prevu = false;

  function image(instant: number) {
    prevu = false;
    const retard = cible.length - montre.length;
    if (retard <= 0) return;
    const pas = Math.min(PAS_MAX_S, Math.max(0, (instant - precedent) / 1000));
    precedent = instant;
    reste += Math.max(vitesseMin, retard / rattrapageS) * pas;
    const avance = Math.floor(reste);
    if (avance > 0) {
      reste -= avance;
      montre = couper(cible, Math.min(cible.length, montre.length + avance));
      afficher(montre);
    }
    if (montre.length < cible.length) { prevu = true; planifier(image); }
  }

  return {
    viser(texte, fluide) {
      cible = texte;
      if (!fluide || !texte.startsWith(montre)) {
        montre = texte; reste = 0;
        afficher(montre);
        return;
      }
      if (!prevu && montre.length < cible.length) {
        prevu = true;
        precedent = maintenant();
        planifier(image);
      }
    },
    arreter() { cible = montre; },
  };
}
