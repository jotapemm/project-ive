/**
 * Tema.
 *
 * Você escolhe UMA cor — o fundo. Todo o resto se deriva dela.
 *
 * A cor do texto não é uma segunda escolha: ela é calculada pela
 * luminância do fundo, então é impossível acabar com texto ilegível.
 * Escolheu um fundo claro, o texto vira escuro sozinho.
 *
 * Painel, borda e tons apagados também não moram aqui — saem no CSS por
 * `color-mix()` entre o fundo e o texto. Por isso este arquivo só precisa
 * escrever duas variáveis, e não uma paleta inteira.
 */

export type Tema = { nome: string; fundo: string };

export const TEMAS: Tema[] = [
  { nome: "Meia-noite", fundo: "#0d0d13" },
  { nome: "Grafite", fundo: "#17171a" },
  { nome: "Índigo", fundo: "#0e1128" },
  { nome: "Musgo", fundo: "#0d1a15" },
  { nome: "Vinho", fundo: "#1a0d12" },
  { nome: "Ardósia", fundo: "#1c2530" },
  { nome: "Areia", fundo: "#f2efe6" },
  { nome: "Papel", fundo: "#ffffff" },
];

const CHAVE = "ive-fundo";

/** Luminância relativa (WCAG 2). 0 = preto, 1 = branco. */
export function luminancia(hex: string): number {
  const n = hex.replace("#", "");
  const largo = n.length === 3 ? n.split("").map((c) => c + c).join("") : n;
  const canal = (i: number) => {
    const c = parseInt(largo.slice(i * 2, i * 2 + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(0) + 0.7152 * canal(1) + 0.0722 * canal(2);
}

/*
 * 0.179 é o ponto exato onde o contraste com branco iguala o contraste
 * com preto — sai de resolver (L+0.05)² = 1.05 × 0.05. Abaixo disso o
 * texto claro ganha; acima, o escuro. Não é chute.
 */
const VIRADA = 0.179;

export function textoPara(fundo: string): string {
  return luminancia(fundo) > VIRADA ? "#15151c" : "#f2f2f7";
}

export function aplicar(fundo: string): void {
  const raiz = document.documentElement;
  const claro = luminancia(fundo) > VIRADA;

  raiz.style.setProperty("--fundo", fundo);
  raiz.style.setProperty("--texto", textoPara(fundo));

  /*
   * As proporções de mistura precisam ser DIFERENTES nos dois lados.
   *
   * Luminância não é linear: misturar branco na direção de um fundo
   * branco perde contraste muito mais rápido do que preto na direção de
   * preto. Com a mesma proporção nos dois, os tons secundários caíam pra
   * 2,3:1 nos temas claros — ilegível. Medido, não estimado.
   *
   * Estes valores põem os dois níveis acima de 4,5:1 (WCAG AA) em fundo
   * claro E escuro, mantendo a hierarquia entre eles.
   */
  raiz.style.setProperty("--mix-fraco", claro ? "75%" : "68%");
  raiz.style.setProperty("--mix-apagado", claro ? "62%" : "52%");

  // Deixa o navegador ajustar scrollbar e controles nativos junto.
  raiz.style.colorScheme = claro ? "light" : "dark";
  try {
    localStorage.setItem(CHAVE, fundo);
  } catch {
    /* modo privado, ou storage cheio — não vale quebrar a tela por isso */
  }
}

export function carregar(): string {
  try {
    return localStorage.getItem(CHAVE) || TEMAS[0].fundo;
  } catch {
    return TEMAS[0].fundo;
  }
}
