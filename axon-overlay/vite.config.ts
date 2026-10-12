import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { resolve } from 'node:path';

export default defineConfig({
  root: 'ui', base: './', plugins: [svelte()],
  resolve: { conditions: ['browser'] },
  build: {
    target: 'es2022', outDir: 'dist', emptyOutDir: true,
    lib: { entry: resolve('ui/src/main.ts'), name: 'AxonOverlay', formats: ['iife'], fileName: () => 'axon.js', cssFileName: 'axon' },
    sourcemap: true,
  },
  test: { environment: 'jsdom', include: ['../tests/**/*.test.ts'], restoreMocks: true },
});
