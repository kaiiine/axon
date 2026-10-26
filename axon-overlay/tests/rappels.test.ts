import { describe, expect, it } from 'vitest';
import { actionsDuRappel, lireRappel, parolesDuRappel, titreDuRappel } from '../ui/src/rappels';
import type { Rappel } from '../ui/src/types';

const rappel = (r: Partial<Rappel>): Rappel => ({ id: 'r', titre: 'Rappel', texte: '', genre: 'tache', ...r });
const ids = (r: Rappel) => actionsDuRappel(r).map(a => a.id);

describe('les actions d’un rappel suivent ce qu’il annonce', () => {
  it('une échéance mène à son suivi, et se reporte ou se ferme', () => {
    expect(ids(rappel({ genre: 'echeance', suiviId: 's1' }))).toEqual(['suivi', 'point', 'plus_tard', 'compris']);
  });
  it('une échéance sans suivi connu ne propose pas d’y aller', () => {
    expect(ids(rappel({ genre: 'echeance' }))).toEqual(['plus_tard', 'compris']);
  });
  it('le récapitulatif mène aux études, une tâche à la conversation', () => {
    expect(ids(rappel({ genre: 'recapitulatif' }))).toEqual(['etudes', 'compris']);
    expect(ids(rappel({ genre: 'tache' }))).toEqual(['conversation', 'compris']);
  });
  it('une seule action principale par rappel', () => {
    for (const genre of ['echeance', 'recapitulatif', 'tache'] as const) {
      expect(actionsDuRappel(rappel({ genre, suiviId: 's' })).filter(a => a.principal)).toHaveLength(1);
    }
  });
});

describe('lecture d’un message rappel', () => {
  it('reprend le suivi et l’échéance, et vaut une tâche si le genre est inconnu', () => {
    expect(lireRappel({ id: 'a', titre: 'T', texte: 'x', genre: 'echeance', suivi_id: 's', echeance_id: 'e' }, 'repli'))
      .toEqual({ id: 'a', titre: 'T', texte: 'x', genre: 'echeance', suiviId: 's', echeanceId: 'e' });
    expect(lireRappel({ genre: 'inconnu' }, 'repli')).toMatchObject({ id: 'repli', titre: 'Rappel', genre: 'tache' });
  });
  it('le titre ne répète pas « Axon · Rappel · »', () => {
    expect(titreDuRappel(rappel({ titre: 'Axon · Rappel · Rendu du projet CDS' }))).toBe('Rendu du projet CDS');
    expect(titreDuRappel(rappel({ titre: 'Axon · Études' }))).toBe('Études');
  });
});

describe('le texte d’un rappel, prêt à être dit', () => {
  it('sans puces, numéros ni marques Markdown', () => {
    expect(parolesDuRappel('## Rappel\n• **Rendu** dans `3` jours\n2. Relire le README\n\n- be-cds : __propre__'))
      .toEqual(['Rappel', 'Rendu dans 3 jours', 'Relire le README', 'be-cds : propre']);
  });
});
