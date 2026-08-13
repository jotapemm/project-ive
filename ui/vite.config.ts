import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O proxy manda /api pro servidor Python. Assim o navegador enxerga tudo
// na mesma origem e CORS nem entra na história durante o desenvolvimento.
// (O servidor tem CORS configurado também, para quando o cliente for o
// React Native e não puder passar por proxy nenhum.)
// Porta da API. Trocar aqui + no comando do uvicorn.
// (Windows às vezes deixa socket órfão preso numa porta depois que o
// processo morre; se a API não subir, trocar este número resolve.)
const API = 8010;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${API}`,
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
});
