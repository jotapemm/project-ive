/**
 * Gravação por push-to-talk, compartilhada entre o botão da caixa de texto
 * e a tela de conversa por voz.
 *
 * Um hook e não duas cópias porque aqui mora a permissão de microfone e a
 * liberação das faixas — se as duas telas tratarem isso separado, uma vai
 * esquecer de fechar o microfone e ninguém vai perceber tão cedo.
 *
 * `nivel` é o volume ao vivo, de 0 a 1. Serve pra esfera pulsar junto com
 * a sua voz — sem isso a tela de voz fica parada e o usuário não sabe se
 * está sendo ouvido.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";

export type EstadoMic = "parado" | "gravando" | "ouvindo";

/* Menos que isso é clique sem querer — não vale acordar o Whisper. */
const MINIMO_BYTES = 1200;

export function useGravacao(aoTranscrever: (texto: string) => void) {
  const [estado, setEstado] = useState<EstadoMic>("parado");
  const [erro, setErro] = useState<string | null>(null);
  const [nivel, setNivel] = useState(0);

  const gravador = useRef<MediaRecorder | null>(null);
  const pedacos = useRef<Blob[]>([]);
  const audioCtx = useRef<AudioContext | null>(null);
  const medidor = useRef<number>(0);
  const entrega = useRef(aoTranscrever);
  entrega.current = aoTranscrever;

  const suportado =
    typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  const parar = useCallback(() => {
    if (gravador.current?.state === "recording") gravador.current.stop();
  }, []);

  const comecar = useCallback(async () => {
    if (!suportado) return;
    // `estado` via ref seria mais seguro contra corrida, mas o gravador já
    // é a fonte da verdade: se ele está gravando, não começamos outro.
    if (gravador.current?.state === "recording") return;

    setErro(null);
    try {
      const fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Medidor de volume. Só leitura — não toca nem grava nada por aqui.
      try {
        const ac = new AudioContext();
        const analisador = ac.createAnalyser();
        analisador.fftSize = 512;
        ac.createMediaStreamSource(fluxo).connect(analisador);
        const buffer = new Uint8Array(analisador.frequencyBinCount);
        audioCtx.current = ac;

        const medir = () => {
          analisador.getByteTimeDomainData(buffer);
          let soma = 0;
          for (const v of buffer) {
            const d = (v - 128) / 128;
            soma += d * d;
          }
          const rms = Math.sqrt(soma / buffer.length);
          // Sobe rápido, desce devagar: pulso que acompanha a fala sem tremer.
          setNivel((n) => Math.max(Math.min(1, rms * 4.5), n * 0.88));
          medidor.current = requestAnimationFrame(medir);
        };
        medidor.current = requestAnimationFrame(medir);
      } catch {
        /* sem medidor a gravação continua funcionando */
      }

      const rec = new MediaRecorder(fluxo);
      pedacos.current = [];
      rec.ondataavailable = (e) => e.data.size && pedacos.current.push(e.data);

      rec.onstop = async () => {
        // Solta o microfone NA HORA. Sem isto o navegador segue com o
        // indicador de gravação aceso e o dispositivo reservado.
        fluxo.getTracks().forEach((t) => t.stop());
        cancelAnimationFrame(medidor.current);
        audioCtx.current?.close().catch(() => {});
        audioCtx.current = null;
        setNivel(0);

        const clipe = new Blob(pedacos.current, { type: rec.mimeType });
        if (clipe.size < MINIMO_BYTES) {
          setEstado("parado");
          return;
        }
        setEstado("ouvindo");
        try {
          const r = await api.ouvir(clipe);
          if (r.texto.trim()) entrega.current(r.texto.trim());
          else setErro("Não entendi nada no áudio.");
        } catch (e) {
          setErro((e as Error).message);
        } finally {
          setEstado("parado");
        }
      };

      rec.start();
      gravador.current = rec;
      setEstado("gravando");
    } catch {
      setErro("Sem acesso ao microfone.");
      setEstado("parado");
    }
  }, [suportado]);

  // Se o componente sair no meio da gravação, o microfone fecha junto.
  useEffect(() => () => {
    parar();
    cancelAnimationFrame(medidor.current);
    audioCtx.current?.close().catch(() => {});
  }, [parar]);

  return { estado, erro, nivel, comecar, parar, suportado };
}
