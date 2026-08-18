/**
 * Voz do IVE — o lado de FALAR.
 *
 * Piper: rede neural (VITS) rodando no servidor local. O texto não sai da
 * máquina.
 *
 * Aqui já existiu um segundo motor, a síntese do próprio Windows via
 * `speechSynthesis`. Foi removida por soar robótica, e o motivo é técnico:
 * ela é **concatenativa** — pedaços de áudio gravados e costurados,
 * tecnologia dos anos 90. Não havia ajuste que resolvesse; era o método.
 *
 * O que se perdeu com isso: latência zero e funcionar sem servidor. Como
 * ouvir (Whisper) já exigia o servidor, a voz inteira já dependia dele —
 * então não é uma dependência nova, é a mesma.
 *
 * Ponto de arquitetura que vale repetir: isto NÃO é ferramenta. Não entra
 * no `registry`. O cardápio é o que o MODELO pode pedir, e se `falar()`
 * virasse ferramenta o modelo decidiria sozinho quando abrir a caixa de
 * som do escritório. Falar é decisão da interface.
 */

export type Preferencias = {
  auto: boolean;   // fala sozinho quando o IVE responde
  voz: string;     // nome do .onnx; vazio = o padrão do servidor
  ritmo: number;
};

const CHAVE = "ive-voz";

export const PADRAO: Preferencias = { auto: false, voz: "", ritmo: 1.05 };

export function carregar(): Preferencias {
  try {
    const cru = JSON.parse(localStorage.getItem(CHAVE) || "{}");
    // Quem já usava o sistema tem 'vozPiper' guardado, do tempo em que
    // havia dois motores. Aproveita em vez de resetar a escolha.
    if (!cru.voz && cru.vozPiper) cru.voz = cru.vozPiper;
    return { ...PADRAO, auto: !!cru.auto, voz: cru.voz ?? "", ritmo: cru.ritmo ?? PADRAO.ritmo };
  } catch {
    return { ...PADRAO };
  }
}

export function guardar(p: Preferencias): void {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(p));
  } catch {
    /* modo privado — não vale quebrar a tela por isso */
  }
}

/**
 * Quebra em frases antes de falar.
 *
 * É ganho de LATÊNCIA: o Piper cobra ~330 ms fixos por chamada, então ele
 * toca a primeira frase enquanto a segunda ainda está sendo gerada, em vez
 * de esperar o texto inteiro ficar pronto.
 */
function emFrases(texto: string): string[] {
  return texto
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?…:])\s+/)
    .flatMap((f) => (f.length <= 180 ? [f] : f.match(/.{1,180}(\s|$)/g) ?? [f]))
    .map((f) => f.trim())
    .filter(Boolean);
}

/**
 * Tira do texto o que não faz sentido ouvir. Ler "asterisco asterisco" ou
 * soletrar um JSON em voz alta é pior que não falar.
 */
export function limpar(texto: string): string {
  return texto
    .replace(/```[\s\S]*?```/g, " (bloco de código) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^[\s>#-]+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

/* --- reprodução ------------------------------------------------------- */

let tocando: HTMLAudioElement | null = null;

/*
 * Sobe a cada calar(). Uma fala antiga que ainda estava buscando áudio
 * compara este número e desiste — sem isso, cancelar e mandar outra coisa
 * faria as duas tocarem juntas alguns instantes depois.
 */
let geracao = 0;

async function baixarFrase(
  frase: string,
  pref: Preferencias,
  sinal: AbortSignal,
): Promise<string> {
  const r = await fetch("/api/voz/falar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      texto: frase,
      voz: pref.voz || null,
      // No Piper o ritmo é `length_scale`: MAIOR = mais devagar. Invertemos
      // aqui pra que o controle na interface signifique o de sempre —
      // deslizar pra direita acelera.
      ritmo: pref.ritmo ? 1 / pref.ritmo : null,
    }),
    signal: sinal,
  });
  if (!r.ok) throw new Error(`Piper falhou (${r.status})`);
  return URL.createObjectURL(await r.blob());
}

function tocar(url: string, sinal: AbortSignal): Promise<void> {
  return new Promise((pronto) => {
    const som = new Audio(url);
    tocando = som;
    let fechado = false;
    const fim = () => {
      if (fechado) return;
      fechado = true;
      URL.revokeObjectURL(url);
      if (tocando === som) tocando = null;
      pronto();
    };
    som.onended = fim;
    som.onerror = fim;
    sinal.addEventListener("abort", () => { som.pause(); fim(); }, { once: true });
    som.play().catch(fim);
  });
}

/* --- interface pública ------------------------------------------------ */

export function calar(): void {
  geracao++;
  if (tocando) {
    tocando.pause();
    tocando = null;
  }
}

export const falando = (): boolean => !!tocando && !tocando.paused;

/**
 * Fala. Resolve quando termina, ou quando é interrompido por outra fala.
 * Nunca rejeita: falha de voz não deve derrubar a tela.
 */
export async function falar(texto: string, pref: Preferencias): Promise<void> {
  const frases = emFrases(limpar(texto));
  if (!frases.length) return;

  calar(); // uma fala de cada vez

  const minha = geracao;
  const corte = new AbortController();
  const cancelado = () => geracao !== minha;

  // Busca a PRÓXIMA enquanto a atual toca. É isso que tira a pausa entre
  // frases — sem o adiantamento, cada uma pagaria a latência de novo.
  let proxima = baixarFrase(frases[0], pref, corte.signal);

  for (let i = 0; i < frases.length; i++) {
    if (cancelado()) { corte.abort(); return; }

    let url: string;
    try {
      url = await proxima;
    } catch {
      return; // servidor fora, voz não baixada — silêncio é melhor que erro
    }
    if (cancelado()) { URL.revokeObjectURL(url); corte.abort(); return; }

    if (i + 1 < frases.length) {
      proxima = baixarFrase(frases[i + 1], pref, corte.signal).catch(() => "");
    }
    await tocar(url, corte.signal);
  }
}
