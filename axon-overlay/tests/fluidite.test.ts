import { describe, expect, it } from 'vitest';
import { RATTRAPAGE_S, revelation } from '../ui/src/fluidite';

//: Des images à 60 Hz, déroulées à la main.
function horloge() {
  let instant = 0;
  const attente: ((t: number) => void)[] = [];
  return {
    planifier: (image: (t: number) => void) => { attente.push(image); },
    maintenant: () => instant,
    images(n: number) {
      for (let i = 0; i < n && attente.length; i++) { instant += 1000 / 60; attente.shift()!(instant); }
    },
  };
}

describe('révélation fluide de la réponse en direct', () => {
  it('révèle une rafale progressivement, puis la rattrape vite', () => {
    const h = horloge(), vus: string[] = [];
    const r = revelation(t => vus.push(t), { planifier: h.planifier, maintenant: h.maintenant });
    const texte = 'Le backend avance bien sur la branche feat/userCRUD.';
    r.viser(texte, true);
    h.images(1);
    expect(vus.at(-1)!.length).toBeGreaterThan(0);
    expect(vus.at(-1)!.length).toBeLessThan(texte.length);
    h.images(Math.ceil(RATTRAPAGE_S * 60) + 30);
    expect(vus.at(-1)).toBe(texte);
    expect(vus.every((v, i) => i === 0 || v.length >= vus[i - 1].length)).toBe(true);
  });

  it('sans animation, le texte s’affiche tout de suite', () => {
    const h = horloge(), vus: string[] = [];
    revelation(t => vus.push(t), { planifier: h.planifier, maintenant: h.maintenant }).viser('Bonjour', false);
    expect(vus).toEqual(['Bonjour']);
  });

  it('un texte qui ne prolonge pas l’affiché le remplace, et le vide efface', () => {
    const h = horloge(), vus: string[] = [];
    const r = revelation(t => vus.push(t), { planifier: h.planifier, maintenant: h.maintenant });
    r.viser('Premier', true); h.images(100);
    r.viser('Autre chose', true);
    expect(vus.at(-1)).toBe('Autre chose');
    r.viser('', true);
    expect(vus.at(-1)).toBe('');
  });

  it('ne coupe jamais un emoji en deux', () => {
    const h = horloge(), vus: string[] = [];
    const r = revelation(t => vus.push(t), { planifier: h.planifier, maintenant: h.maintenant });
    r.viser('🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎', true);
    h.images(200);
    expect(vus.every(v => !/[\ud800-\udbff]$/.test(v))).toBe(true);
  });
});
