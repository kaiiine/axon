import type { Outbound } from './types';
export const isNative = () => Boolean(window.webkit?.messageHandlers?.axon);
export function post(message: Outbound): boolean {
  const target = window.webkit?.messageHandlers?.axon;
  if (!target) return false;
  try { target.postMessage(message); return true; } catch { return false; }
}
