/**
 * Logo I.V.E.
 *
 *   <LogoIVE />                    marca principal, animando em loop
 *   <LogoIVE modo="uma-vez" />     inicialização: anima e congela montada
 *   <LogoIVE modo="parada" />      estática, pro cabeçalho
 *   <LogoMarca />                  marca simples: só o "i"
 *
 * A animação em si mora no logo.css e é o desenho original, intacto.
 * O que este arquivo acrescenta é a MEDIÇÃO: em vez de chumbar "barra de
 * 18px", ele mede o glifo "I" da fonte de verdade e escreve as variáveis
 * CSS. Assim a barra tem exatamente a espessura do I em qualquer tamanho,
 * e nada quebra se a fonte demorar a carregar ou for trocada.
 */

import { useEffect, useRef, useState } from "react";
import "./logo.css";

/* O E termina de entrar aos 52% de um ciclo de 6s. É aí que congelamos. */
const MONTAGEM_MS = 3_200;
const PAUSA_MS = 700;
const SAIDA_MS = 450;
/* Rede de segurança: nada pode prender o usuário na tela de abertura. */
const TETO_MS = 9_000;

type Modo = "anima" | "uma-vez" | "parada";

/**
 * Quanto vão entre os elementos, como fração da espessura da barra.
 * Único número a mexer se quiser o conjunto mais apertado ou mais solto.
 */
const VAO = 0.3;

/** Mede a fonte real e escreve as medidas no elemento. */
function medir(lock: HTMLDivElement): boolean {
  const cs = getComputedStyle(lock);
  const ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return false;

  // O peso entra na conta: uma fonte pedida em 700 mede diferente da 400.
  ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const m = ctx.measureText("I");
  const alturaCaixa = Math.round(m.actualBoundingBoxAscent);
  const largura = Math.round(
    Math.abs(m.actualBoundingBoxRight - m.actualBoundingBoxLeft),
  );

  // Fonte ainda não chegou: a métrica vem degenerada. Tenta de novo depois.
  if (!alturaCaixa || !largura || largura < 6) return false;

  const vao = Math.max(2, Math.round(largura * VAO));

  lock.querySelectorAll<HTMLElement>(".tira, .pingo").forEach((b) => {
    b.style.width = `${largura}px`;
    b.style.height = `${largura}px`;
  });
  const haste = lock.querySelector<HTMLElement>(".haste");
  if (haste) haste.style.height = `${alturaCaixa}px`;

  /*
   * Por que o I.V.E parecia irregular:
   *
   * A barra e o quadrado são divs — ocupam exatamente a tinta, sem sobra.
   * O V e o E são glifos, e toda fonte embute uma lateral vazia em cada
   * um. Com `gap` uniforme, o vão VISÍVEL ao redor das letras ficava
   * maior que ao redor dos quadrados, e o conjunto perdia o ritmo.
   *
   * A correção é medir essa lateral vazia e cancelar com margem negativa.
   * Aí o gap passa a valer tinta-a-tinta, e o espaçamento fica parelho de
   * ponta a ponta — sem chumbar número nenhum na mão.
   */
  const enxugar = (el: HTMLElement | null, letra: string) => {
    if (!el) return;
    const g = ctx.measureText(letra);
    el.style.marginLeft = `${Math.round(g.actualBoundingBoxLeft)}px`;
    el.style.marginRight = `${Math.round(g.actualBoundingBoxRight - g.width)}px`;
  };
  enxugar(lock.querySelector<HTMLElement>(".g-v"), "V");
  enxugar(lock.querySelector<HTMLElement>(".g-e"), "E");

  lock.style.gap = `${vao}px`;
  lock.style.setProperty("--dx", `${-(largura + vao)}px`);
  lock.style.setProperty("--dy", `${-(alturaCaixa + Math.round(alturaCaixa * 0.3))}px`);
  lock.style.setProperty("--draw", `${Math.round(alturaCaixa * 0.4)}px`);
  // Depois das margens e do gap — senão offsetWidth vem da largura antiga.
  lock.style.setProperty("--cx", `${Math.round((lock.offsetWidth - largura) / 2)}px`);
  return true;
}

export function LogoIVE({
  tamanho = 84,
  modo = "anima",
  congelada = false,
}: {
  tamanho?: number;
  modo?: Modo;
  congelada?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const lock = ref.current;
    if (!lock) return;

    let vivo = true;
    let tentativas = 0;

    // A fonte pode chegar depois do primeiro paint. Tenta até a métrica
    // vir sã, em vez de desenhar uma logo torta e deixar assim.
    const tentar = () => {
      if (!vivo || medir(lock) || ++tentativas > 20) return;
      setTimeout(tentar, 150);
    };

    document.fonts?.ready.then(tentar).catch(() => tentar());
    tentar();

    return () => {
      vivo = false;
    };
  }, [tamanho]);

  const classes = [
    "ive-logo",
    modo === "parada" ? "parada" : "anima",
    congelada ? "congelada" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div ref={ref} className={classes} style={{ fontSize: `${tamanho}px` }}>
      <div className="tira haste" />
      <div className="pingo">
        <div className="pingo-y">
          <div className="pingo-r" />
        </div>
      </div>
      <span className="resto g-v">V</span>
      <div className="tira resto ponto-2" />
      <span className="resto g-e">E</span>
    </div>
  );
}

/**
 * Marca simples: só o "i" — haste com o pingo quadrado em cima.
 * É o estado de repouso da animação, congelado. Serve pra cabeçalho,
 * favicon e qualquer lugar apertado demais pro I.V.E inteiro.
 */
export function LogoMarca({ tamanho = 24 }: { tamanho?: number }) {
  // Proporções tiradas da própria animação: pingo = 0,3 da altura do I,
  // vão = 0,3, haste = 1,0. Total 1,6 alturas de caixa.
  const caixa = tamanho / 1.6;
  const barra = Math.max(2, Math.round(caixa * 0.3));
  return (
    <span
      className="ive-marca"
      style={{ width: barra, height: tamanho }}
      aria-hidden="true"
    >
      <span style={{ width: barra, height: barra }} />
      <span style={{ width: 0, height: Math.round(caixa * 0.3) }} />
      <span style={{ width: barra, height: Math.round(caixa) }} />
    </span>
  );
}

/**
 * Tela de inicialização: a logo se monta, congela, e sai.
 *
 * Clicar pula. E só aparece uma vez por aba — durante o desenvolvimento
 * o Vite recarrega a página a cada arquivo salvo, e assistir 4 segundos
 * de abertura a cada Ctrl+S deixaria qualquer um louco.
 */
export function Abertura({ aoTerminar }: { aoTerminar: () => void }) {
  const palco = useRef<HTMLDivElement>(null);
  const [congelada, setCongelada] = useState(false);
  const [saindo, setSaindo] = useState(false);
  const pulou = useRef(false);

  /*
   * O relógio é o da PRÓPRIA animação, não o de parede.
   *
   * O navegador congela o relógio das animações CSS em página oculta —
   * medimos isso: playState "running", currentTime parado em 0. Mas
   * setTimeout continua correndo. Com timers, abrir o app numa aba em
   * segundo plano fazia a abertura "terminar" sem nunca ter animado: o
   * usuário voltava pra tela e já tinha perdido.
   *
   * requestAnimationFrame para junto com a animação, então os dois
   * concordam: se a aba está escondida, a abertura espera.
   */
  useEffect(() => {
    let quadro = 0;
    let saida = 0;
    let inicioPausa = 0;
    let primeiro = 0;

    const passo = (agora: number) => {
      if (pulou.current) return;
      if (!primeiro) primeiro = agora;

      const haste = palco.current?.querySelector<HTMLElement>(".haste");
      const anim = haste?.getAnimations()[0];

      // Sem animação anexada = prefers-reduced-motion (o CSS zera tudo e
      // mostra a logo montada). Nada a esperar: segue direto.
      // O teto de tempo é rede de segurança: nenhuma condição estranha
      // pode deixar o usuário preso na tela de abertura.
      const montada =
        (haste && !anim) ||
        Number(anim?.currentTime ?? 0) >= MONTAGEM_MS ||
        agora - primeiro > TETO_MS;

      if (!montada) {
        quadro = requestAnimationFrame(passo);
        return;
      }
      setCongelada(true);

      if (!inicioPausa) inicioPausa = agora;
      if (agora - inicioPausa < PAUSA_MS) {
        quadro = requestAnimationFrame(passo);
        return;
      }
      setSaindo(true);
      saida = window.setTimeout(aoTerminar, SAIDA_MS);
    };

    quadro = requestAnimationFrame(passo);
    return () => {
      cancelAnimationFrame(quadro);
      clearTimeout(saida);
    };
  }, [aoTerminar]);

  function pular() {
    if (pulou.current) return;
    pulou.current = true;
    setSaindo(true);
    setTimeout(aoTerminar, SAIDA_MS);
  }

  return (
    <div
      ref={palco}
      className={`ive-abertura ${saindo ? "saindo" : ""}`}
      onClick={pular}
      role="button"
      tabIndex={0}
      aria-label="Inicializando o IVE. Clique para pular."
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Escape") pular();
      }}
    >
      <LogoIVE tamanho={84} modo="uma-vez" congelada={congelada} />
      <span className="pular">clique para pular</span>
    </div>
  );
}
