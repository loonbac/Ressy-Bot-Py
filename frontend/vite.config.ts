import { defineConfig, Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function removeCssHacks(): Plugin {
  return {
    name: 'remove-css-hacks',
    enforce: 'pre',
    transform(code: string, id: string) {
      if (id.endsWith('.css')) {
        // Remove legacy IE CSS hacks like: *zoom: 1;
        return code.replace(/\*\w+\s*:\s*[^;]+;/g, '');
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), removeCssHacks()],
  build: {
    outDir: '../src/web/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Vite 8 uses rolldown — manualChunks must be a function
        manualChunks(id: string) {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'vendor';
          }
          if (id.includes('node_modules/motion/') || id.includes('node_modules/lightweight-charts/')) {
            return 'ui';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
});
