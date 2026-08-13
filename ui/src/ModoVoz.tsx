/**
 * Conversa por voz.
 *
 * A esfera é o único elemento vivo da tela, e ela pulsa conforme o estado:
 * com o seu volume enquanto você fala, com um batimento lento enquanto o
 * IVE pensa, e com o ritmo da fala enquanto ele responde. É o que diz
 * "estou te ouvindo" sem precisar escrever isso na tela.
 *
 * Push-to-talk, igual ao resto do sistema: o microfone abre só enquanto o
 * botão está pressionado. Aqui o alvo é a tela inteira — segurar em
 * qualquer lugar grava.
 */

import { useEffect, useRef, useState } from "react";
import * as api from "./api";
import { Esfera } from "./Esfera";
import { useGravacao } from "./microfone";

type Fase = "abrindo" | "ocioso" | "gravando" | "transcrevendo" | "pensando" | "falando";

export function ModoVoz({
  motor,
  aoFalar,
  aoSair,
}: {
  motor: string;
  aoFalar: (texto: string) => Promise<void>;
  aoSair: () => void;
}) {
  const [fase, setFase] = useState<Fase>("abrindo");
  const [dito, setDito] = useState("");
  const [resposta, setResposta] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const pronta = useRef(false);

  const { estado, erro: erroMic, nivel, comecar, parar, suportado } =
    useGravacao(async (texto) => {
      setDito(texto);
      setResposta("");
      setFase("pensando");
      try {
        const r = await api.executar(texto, motor || undefined);
        setResposta(r.resposta);
        setFase("falando");
        await aoFalar(r.resposta);
      } catch (e) {
        setErro((e as Error).message);
      } finally {
        setFase("ocioso");
      }
    });

  // O microfone tem seu próprio ciclo; a fase da tela segue ele, mas só
  // depois que a animação de entrada terminou.
  useEffect(() => {
    if (!pronta.current) return;
    if (estado === "gravando") setFase("gravando");
    else if (estado === "ouvindo") setFase("transcrevendo");
    else if (fase === "gravando" || fase === "transcrevendo") setFase("ocioso");
  }, [estado]); // eslint-disable-line react-hooks/exhaustive-deps

  // Espaço também segura pra falar, pra não obrigar o mouse.
  useEffect(() => {
    const desce = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && pronta.current) {
        e.preventDefault();
        comecar();
      }
      if (e.key === "Escape") aoSair();
    };
    const sobe = (e: KeyboardEvent) => {
      if (e.code === "Space") parar();
    };
    window.addEventListener("keydown", desce);
    window.addEventListener("keyup", sobe);
    return () => {
      window.removeEventListener("keydown", desce);
      window.removeEventListener("keyup", sobe);
    };
  }, [comecar, parar, aoSair]);

  const pulso =
    fase === "gravando" ? nivel
    : fase === "falando" ? 0.45
    : fase === "pensando" ? 0.22
    : 0;

  const legenda =
    fase === "abrindo" ? ""
    : fase === "gravando" ? "ouvindo…"
    : fase === "transcrevendo" ? "transcrevendo…"
    : fase === "pensando" ? "pensando…"
    : fase === "falando" ? "falando"
    : suportado ? "segure para falar" : "microfone indisponível";

  return (
    <div
      className={`modo-voz ${fase}`}
      onPointerDown={(e) => {
        if (e.button === 0 && pronta.current) comecar();
      }}
      onPointerUp={parar}
      onPointerLeave={parar}
    >
      <button className="sair-voz" onClick={aoSair} title="Voltar para o texto (Esc)">
        ✕
      </button>

      <Esfera
        intensidade={pulso}
        aoTerminarIntro={() => {
          pronta.current = true;
          setFase("ocioso");
        }}
      />

      <div className="legendas">
        {dito && <p className="dito">"{dito}"</p>}
        {resposta && <p className="resposta-voz">{resposta}</p>}
        {(erro || erroMic) && <p className="erro">{erro ?? erroMic}</p>}
      </div>

      <span className="rotulo-voz">{legenda}</span>
    </div>
  );
}
