import { afterEach, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { mount, tick, unmount } from 'svelte';
import App from '../ui/src/App.svelte';
import { model, open, receive, reset, setPreference } from '../ui/src/model';

afterEach(() => { vi.useRealTimers(); reset(); delete window.webkit; });

async function monter() {
  reset();
  const post = vi.fn();
  window.webkit = { messageHandlers: { axon: { postMessage: post } } };
  setPreference('motion', false);                 // la parole s'affiche d'un coup
  const cible = document.createElement('div');
  document.body.append(cible);
  const app = mount(App, { target: cible });
  await tick();
  return { cible, post, fermer: async () => { await unmount(app); cible.remove(); } };
}

const rappelEcheance = {
  type: 'rappel', id: 'r1', titre: 'Axon · Rappel · Rendu du projet CDS',
  texte: '• Rendu dans 3 jours\n• be-cds : 2 fichiers non commités', genre: 'echeance', suivi_id: 'suivi_cds',
};

it('Axon dit le rappel dans sa bulle, puis propose ses actions', async () => {
  vi.useFakeTimers();
  const { cible, fermer } = await monter();
  open(false);
  receive(rappelEcheance);
  await tick(); vi.advanceTimersByTime(1); await tick();

  const bulle = cible.querySelector('.rappel .bulle') as HTMLElement;
  expect(bulle.querySelector('strong')?.textContent).toBe('Rendu du projet CDS');
  expect([...bulle.querySelectorAll('li')].map(l => l.textContent)).toEqual(
    ['Rendu dans 3 jours', 'be-cds : 2 fichiers non commités']);
  const boutons = [...bulle.querySelectorAll('.actions button')] as HTMLButtonElement[];
  expect(boutons.map(b => b.textContent)).toEqual(['Voir le suivi', 'Faire le point', 'Plus tard', 'Compris']);
  expect(boutons.filter(b => b.disabled).map(b => b.textContent)).toEqual(['Voir le suivi', 'Faire le point']);
  await fermer();
});

it('sans survol, la bulle lue se replie en pastille', async () => {
  vi.useFakeTimers();
  const { cible, fermer } = await monter();
  open(false);
  receive({ ...rappelEcheance, id: 'r2' });
  await tick(); vi.advanceTimersByTime(1); await tick();
  expect(get(model).popup?.deplie).toBe(true);
  vi.advanceTimersByTime(9001); await tick();
  expect(get(model).popup?.deplie).toBe(false);
  expect(get(model).rappels).toHaveLength(1);
  expect(cible.querySelector('.rappel')).toBeNull();
  await fermer();
});

it('avec les animations, l’arrivée de l’accueil ne masque pas le titre de la bulle', async () => {
  const { entrance } = await import('../ui/src/entrance');
  const { cible, fermer } = await monter();
  setPreference('motion', true);
  open(false);
  receive({ ...rappelEcheance, id: 'r3' });
  open(true);
  await tick();
  expect(get(entrance)).toBe('rest');
  expect(cible.querySelector('.island')?.classList.contains('introducing')).toBe(false);
  expect(cible.querySelector('.rappel .bulle strong')?.textContent).toBe('Rendu du projet CDS');
  await fermer();
});
