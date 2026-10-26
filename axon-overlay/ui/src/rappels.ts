import type { GenreRappel, Rappel } from './types';

//: Ce qu'on peut faire d'un rappel, selon ce qu'il annonce. Le démon ne fournit
//: que le genre et le suivi concerné : les libellés et l'ordre vivent ici.
export type IdAction = 'suivi' | 'point' | 'etudes' | 'conversation' | 'plus_tard' | 'compris';

export interface ActionRappel {
  id: IdAction;
  libelle: string;
  principal?: boolean;
  //: Passe par la session CLI : indisponible tant qu'Axon n'est pas connecté.
  axon?: boolean;
}

const COMPRIS: ActionRappel = { id: 'compris', libelle: 'Compris' };
const PLUS_TARD: ActionRappel = { id: 'plus_tard', libelle: 'Plus tard' };

const ACTIONS: Record<GenreRappel, (r: Rappel) => ActionRappel[]> = {
  echeance: r => [
    ...(r.suiviId ? [
      { id: 'suivi', libelle: 'Voir le suivi', principal: true, axon: true },
      { id: 'point', libelle: 'Faire le point', axon: true },
    ] as ActionRappel[] : []),
    PLUS_TARD, COMPRIS,
  ],
  recapitulatif: () => [{ id: 'etudes', libelle: 'Voir les études', principal: true, axon: true }, COMPRIS],
  tache: () => [{ id: 'conversation', libelle: 'Ouvrir dans la conversation', principal: true }, COMPRIS],
};

export function actionsDuRappel(rappel: Rappel): ActionRappel[] {
  return ACTIONS[rappel.genre](rappel);
}

const GENRES: readonly GenreRappel[] = ['echeance', 'recapitulatif', 'tache'];
const texte = (v: unknown) => (v == null ? '' : String(v));

//: Un message `rappel` reçu, validé : un genre inconnu vaut une tâche ordinaire.
export function lireRappel(m: Record<string, unknown>, repli: string): Rappel {
  const genre = GENRES.find(g => g === m.genre) ?? 'tache';
  return {
    id: texte(m.id) || repli,
    titre: texte(m.titre) || 'Rappel',
    texte: texte(m.texte),
    genre,
    suiviId: texte(m.suivi_id) || undefined,
    echeanceId: texte(m.echeance_id) || undefined,
  };
}

//: Le texte d'un rappel en lignes à dire : sans puces ni marques Markdown —
//: le démon le fait rédiger par un modèle, qui en met volontiers.
export function parolesDuRappel(texte: string): string[] {
  return texte.split('\n')
    .map(l => l.trim().replace(/^([•\-*]|\d+[.)])\s+/, '').replace(/\*\*|__|`/g, '').replace(/^#+\s*/, ''))
    .filter(Boolean);
}

//: « Axon · Rappel · Rendu du projet CDS » → « Rendu du projet CDS » : c'est
//: Axon qui parle, la bulle n'a pas à le répéter.
export function titreDuRappel(rappel: Rappel): string {
  return rappel.titre.replace(/^(Axon\s*·\s*)?(Rappel\s*·\s*)?/, '') || 'Rappel';
}
