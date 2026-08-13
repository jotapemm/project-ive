/**
 * A esfera pontilhada do modo de voz — e a animação que chega até ela.
 *
 * O storyboard é o mesmo arco da logo, só que a câmera segue o ponto:
 *
 *     ▌·   o "i"
 *     ·    o I arma e lança o ponto pra cima
 *     ▌    a haste cai e sai de quadro
 *     ·    o ponto centraliza, girando rápido
 *     ●    explode em esfera pontilhada
 *
 * Tudo num canvas só. Poderia ser DOM para a primeira metade e canvas para
 * a segunda, mas aí seriam dois relógios para sincronizar no momento exato
 * da explosão — e é justamente esse instante que precisa ser perfeito.
 */

import { useEffect, useRef } from "react";

/* --- linha do tempo, em ms ------------------------------------------- */
const T = {
  hasteNasce: 0,
  hasteCresce: 280,
  pontoPousa: 520,
  armaOArco: 660,
  dispara: 780,
  pontoCentraliza: 1250,
  giraRapido: 1560,
  explode: 1560,
  esferaPronta: 2500,
};

const PARTICULAS = 2600;
/* Fração que fica FORA da bola, formando o halo esfumaçado da borda. */
const HALO = 0.22;

/* --- reação ao mouse -------------------------------------------------
 * ALCANCE: até onde o cursor mexe nos pontos, em px.
 * DESVIO:  o quanto ele empurra. Subir demais rasga a esfera; este valor
 *          dá um afastamento perceptível sem desmanchar o volume.
 * VOLTA:   força da mola que traz o ponto de volta ao lugar.
 * ATRITO:  quanto da velocidade sobra a cada quadro (1 = nunca para).   */
const ALCANCE = 120;
const DESVIO = 17;
const VOLTA = 0.055;
const ATRITO = 0.86;

type P = {
  /* posição final na esfera, em espaço 3D */
  x: number; y: number; z: number;
  /* de onde ela sai na explosão */
  ox: number; oy: number;
  brilho: number;
  atraso: number;   // 0..1 — escalona a explosão em vez de tudo de uma vez
  /* deslocamento do mouse, com mola */
  dx: number; dy: number; vx: number; vy: number;
};

const suave = (t: number) => t * t * (3 - 2 * t);
const saida = (t: number) => 1 - (1 - t) ** 3;
const faixa = (t: number, a: number, b: number) =>
  Math.max(0, Math.min(1, (t - a) / (b - a)));

function semear(raio: number): P[] {
  const ps: P[] = [];
  for (let i = 0; i < PARTICULAS; i++) {
    // Direção uniforme na esfera: sortear z e o ângulo separadamente.
    // Sortear dois ângulos concentraria pontos nos polos.
    const z = Math.random() * 2 - 1;
    const a = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - z * z);

    const halo = Math.random() < HALO;
    // cbrt distribui uniforme no VOLUME. Projetado em 2D isso já dá o
    // centro brilhante da foto, porque a corda é mais longa no meio.
    const r = halo
      ? raio * (1 + 0.75 * Math.random() ** 2)
      : raio * Math.cbrt(Math.random());

    ps.push({
      x: r * s * Math.cos(a),
      y: r * s * Math.sin(a),
      z: r * z,
      ox: 0, oy: 0,
      brilho: halo ? 0.1 + Math.random() * 0.3 : 0.45 + Math.random() * 0.55,
      atraso: Math.random() ** 2,
      dx: 0, dy: 0, vx: 0, vy: 0,
    });
  }
  return ps;
}

export function Esfera({
  intensidade = 0,
  aoTerminarIntro,
}: {
  /** 0 a 1 — pulsa a esfera enquanto grava ou enquanto o IVE fala. */
  intensidade?: number;
  aoTerminarIntro?: () => void;
}) {
  const tela = useRef<HTMLCanvasElement>(null);
  const forca = useRef(intensidade);
  const avisou = useRef(false);
  const aviso = useRef(aoTerminarIntro);

  forca.current = intensidade;
  aviso.current = aoTerminarIntro;

  useEffect(() => {
    const cv = tela.current;
    if (!cv) return;
    const ctx = cv.getContext("2d", { alpha: true });
    if (!ctx) return;

    const parado = matchMedia("(prefers-reduced-motion: reduce)").matches;

    let larg = 0, alt = 0, raio = 0, dpr = 1;
    let ps: P[] = [];
    const mouse = { x: -9999, y: -9999, dentro: false };

    function medir() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      const r = cv!.getBoundingClientRect();
      larg = r.width; alt = r.height;
      cv!.width = Math.round(larg * dpr);
      cv!.height = Math.round(alt * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      raio = Math.min(larg, alt) * 0.19;
      ps = semear(raio);
    }
    medir();

    const aoRedimensionar = () => medir();
    window.addEventListener("resize", aoRedimensionar);

    const aoMover = (e: PointerEvent) => {
      const r = cv!.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
      mouse.dentro = true;
    };
    const aoSair = () => { mouse.dentro = false; mouse.x = mouse.y = -9999; };
    cv.addEventListener("pointermove", aoMover);
    cv.addEventListener("pointerleave", aoSair);

    /* --- desenho ------------------------------------------------------ */

    // Baldes de alpha: trocar fillStyle 2600 vezes por quadro é o que mata
    // o desempenho, não o número de pontos. Com 7 baldes são 7 trocas.
    const BALDES = 7;

    function esfera(t: number, giro: number) {
      const cx = larg / 2;
      const cy = alt * 0.42;

      const explodindo = faixa(t, T.explode, T.esferaPronta);
      const pulso = 1 + forca.current * 0.12;
      const dist = 500;

      const sen = Math.sin(giro), cos = Math.cos(giro);
      const inclina = 0.32;
      const si = Math.sin(inclina), ci = Math.cos(inclina);

      const listas: number[][] = Array.from({ length: BALDES }, () => []);

      for (const p of ps) {
        // gira em Y, depois inclina em X
        const x1 = p.x * cos - p.z * sen;
        const z1 = p.x * sen + p.z * cos;
        const y2 = p.y * ci - z1 * si;
        const z2 = p.y * si + z1 * ci;

        const escala = dist / (dist + z2 * pulso);
        let sx = cx + x1 * pulso * escala;
        let sy = cy + y2 * pulso * escala;

        // Explosão: a partícula sai do ponto central e voa até seu lugar.
        // O atraso individual faz a casca abrir em ondas, não de uma vez.
        if (explodindo < 1) {
          const inicio = p.atraso * 0.45;
          const k = saida(faixa(explodindo, inicio, inicio + 0.55));
          sx = cx + (sx - cx) * k;
          sy = cy + (sy - cy) * k;
        }

        // mola do mouse
        if (mouse.dentro) {
          const ax = sx + p.dx - mouse.x;
          const ay = sy + p.dy - mouse.y;
          const d2 = ax * ax + ay * ay;
          if (d2 < ALCANCE * ALCANCE && d2 > 0.01) {
            const d = Math.sqrt(d2);
            // Quadrático: quem está na beirada do alcance quase não sente,
            // quem está embaixo do cursor sente tudo.
            const empurra = (1 - d / ALCANCE) ** 2 * DESVIO;
            p.vx += (ax / d) * empurra * 0.12;
            p.vy += (ay / d) * empurra * 0.12;
          }
        }
        p.vx += -p.dx * VOLTA;
        p.vy += -p.dy * VOLTA;
        p.vx *= ATRITO;
        p.vy *= ATRITO;
        p.dx += p.vx;
        p.dy += p.vy;

        sx += p.dx;
        sy += p.dy;

        if (sx < -20 || sx > larg + 20 || sy < -20 || sy > alt + 20) continue;

        const prof = (escala - 0.82) / 0.36;          // 0 fundo, 1 frente
        const a = p.brilho * (0.3 + Math.max(0, Math.min(1, prof)) * 0.7)
                * (0.35 + explodindo * 0.65);
        const balde = Math.min(BALDES - 1, Math.max(0, Math.round(a * (BALDES - 1))));
        listas[balde].push(sx, sy, escala > 1.02 ? 1.9 : 1.3);
      }

      for (let b = 1; b < BALDES; b++) {
        const lista = listas[b];
        if (!lista.length) continue;
        ctx!.fillStyle = `rgba(252,252,252,${(b / (BALDES - 1)) * 0.95})`;
        for (let i = 0; i < lista.length; i += 3) {
          const s = lista[i + 2];
          ctx!.fillRect(lista[i], lista[i + 1], s, s);
        }
      }
    }

    /* A primeira metade: a haste, o arco e o voo do ponto. */
    function intro(t: number) {
      const cx = larg / 2;
      const cyEsfera = alt * 0.42;
      const chao = alt * 0.78;

      const w = Math.max(4, raio * 0.16);
      const altHaste = w * 3.4;

      // O ponto: sobe do chão até o centro da esfera, girando no fim.
      const voo = faixa(t, T.dispara, T.pontoCentraliza);
      const yRepouso = chao - altHaste - w * 1.3;
      const py = t < T.dispara ? yRepouso : yRepouso + (cyEsfera - yRepouso) * saida(voo);

      // A haste some pra baixo enquanto a câmera acompanha o ponto.
      const queda = faixa(t, T.dispara, T.dispara + 520);
      const desce = queda ** 2 * alt * 0.6;

      const nasce = suave(faixa(t, T.hasteNasce, T.hasteCresce));
      const arma = faixa(t, T.armaOArco, T.dispara);
      const solta = faixa(t, T.dispara, T.dispara + 140);
      const estica = 1 - arma * 0.42 + solta * 0.5;

      ctx!.fillStyle = `rgba(252,252,252,${1 - queda})`;
      if (nasce > 0 && queda < 1) {
        const h = altHaste * nasce * estica;
        ctx!.fillRect(cx - w / 2, chao - h + desce, w, h);
      }

      // O quadrado, girando cada vez mais rápido ao chegar no centro.
      const vis = faixa(t, T.hasteCresce, T.pontoPousa);
      if (vis > 0) {
        const giro = faixa(t, T.dispara, T.giraRapido) ** 2 * Math.PI * 5;
        const some = 1 - faixa(t, T.explode - 90, T.explode);
        ctx!.save();
        ctx!.translate(cx, py);
        ctx!.rotate(giro);
        ctx!.globalAlpha = vis * some;
        ctx!.fillStyle = "#fcfcfc";
        ctx!.fillRect(-w / 2, -w / 2, w, w);
        ctx!.restore();
      }
    }

    let quadro = 0;
    let t0 = 0;

    const passo = (agora: number) => {
      if (!t0) t0 = agora;
      // Com reduced-motion pulamos direto pra esfera pronta.
      const t = parado ? T.esferaPronta + 1 : agora - t0;

      ctx.clearRect(0, 0, larg, alt);

      if (t < T.explode) intro(t);
      if (t >= T.explode) esfera(t, parado ? 0.6 : agora * 0.00016);

      if (!avisou.current && t >= T.esferaPronta) {
        avisou.current = true;
        aviso.current?.();
      }
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);

    return () => {
      cancelAnimationFrame(quadro);
      window.removeEventListener("resize", aoRedimensionar);
      cv.removeEventListener("pointermove", aoMover);
      cv.removeEventListener("pointerleave", aoSair);
    };
  }, []);

  return <canvas ref={tela} className="esfera" />;
}
