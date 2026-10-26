import { invoke, isTauri } from '@tauri-apps/api/core';
import type { Outbound } from './types';

//: Deux hôtes natifs, une même page : l'île GTK (WebKitGTK, Linux) et
//: l'enveloppe Tauri (macOS, Windows). Hors des deux, c'est l'aperçu navigateur.
const gtk = () => window.webkit?.messageHandlers?.axon;

export const isNative = () => Boolean(gtk()) || isTauri();

export function post(message: Outbound): boolean {
  const cible = gtk();
  try {
    if (cible) { cible.postMessage(message); return true; }
    if (isTauri()) { void invoke('depuis_page', { message }).catch(() => undefined); return true; }
  } catch { /* hôte indisponible : l'appelant garde son état */ }
  return false;
}
