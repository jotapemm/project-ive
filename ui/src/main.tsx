import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import * as tema from "./tema";
import "./estilo.css";

// ANTES do primeiro render, senão a tela pisca na cor padrão e só depois
// troca pra escolhida.
tema.aplicar(tema.carregar());

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
