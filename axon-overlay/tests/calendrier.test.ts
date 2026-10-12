import {describe,it,expect} from 'vitest';
import {casesDuMois,isoLocal} from '../ui/src/calendrier';
describe('calculs du calendrier',()=>{
 it('octobre 2026 commence un jeudi : la grille démarre le lundi 28 septembre',()=>{
  const cases=casesDuMois(2026,9);
  expect(cases).toHaveLength(42);
  expect(cases[0]).toEqual({iso:'2026-09-28',jour:28,dansLeMois:false});
  expect(cases[3]).toEqual({iso:'2026-10-01',jour:1,dansLeMois:true});
  expect(cases.filter(c=>c.dansLeMois)).toHaveLength(31);
 });
 it('un mois commençant un lundi n’a pas de case vide devant',()=>{
  expect(casesDuMois(2026,5)[0]).toEqual({iso:'2026-06-01',jour:1,dansLeMois:true});
 });
 it('isoLocal reste en heure locale, même à 23 h 59',()=>{
  expect(isoLocal(new Date(2026,9,12,23,59))).toBe('2026-10-12');
 });
});
