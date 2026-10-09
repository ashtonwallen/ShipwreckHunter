import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: {port: 5173, proxy: {'/api':'http://127.0.0.1:8787','/data':'http://127.0.0.1:8787'}},
  build: {rollupOptions: {output: {manualChunks: {
    map: ['maplibre-gl'], terrain: ['three'], react: ['react','react-dom'], markdown: ['react-markdown']
  }}}}
});
