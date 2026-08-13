/**
 * Voz do IVE — o lado de FALAR.
 *
 * Usa a síntese do próprio Windows via `speechSynthesis`. Zero download,
 * zero servidor, e o texto não sai da máquina: as vozes daqui reportam
 * `localService: true`, ou seja, sintetizam localmente.
 *
 * Ponto de arquitetura que vale repetir: **isto não é ferramenta.** Não
 * entra no `registry`. O cardápio é o que o MODELO pode pedir, e se
 * `falar()` virasse ferramenta o modelo passaria a decidir sozinho quando
 * abrir a caixa de som do escritório. Falar é decisão da interface.
 *
 * Fase 2 (ouvir, com Whisper local) mora noutro lugar, porque precisa de
 * servidor. Esta camada é só navegador.
 */

export type Preferencias = {
  auto: boolean;   // fala sozinho quando o IVE responde
  vozURI: string;  // qual voz do sistema
  ritmo: number;   // 0.5 a 2
};

const CHAVE = "ive-voz";

export const PADRAO: Preferencias = { auto: false, vozURI: "", ritmo: 1.05 };

export function carregar(): Preferencias {
  try {
    return { ...PADRAO, ...JSON.parse(localStorage.getItem(CHAVE) || "{}") };
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

export const suportado = (): boolean =>
  typeof window !== "undefined" && "speechSynthesis" in window;

/**
 * A lista de vozes chega assíncrona na primeira chamada — `getVoices()`
 * volta vazio e o evento `voiceschanged` avisa depois. Quem chamar uma vez
 * só e acreditar no vazio conclui que não tem voz nenhuma.
 */
export function vozes(): Promise<SpeechSynthesisVoice[]> {
  if (!suportado()) return Promise.resolve([]);
  const jaTem = speechSynthesis.getVoices();
  if (jaTem.length) return Promise.resolve(jaTem);

  return new Promise((ok) => {
    const responder = () => ok(speechSynthesis.getVoices());
    speechSynthesis.addEventListener("voiceschanged", responder, { once: true });
    setTimeout(responder, 2000); // rede de segurança: o evento pode não vir
  });
}

/** Só as de português, com as do Brasil na frente. */
export function vozesPtBr(todas: SpeechSynthesisVoice[]): SpeechSynthesisVoice[] {
  return todas
    .filter((v) => /^pt/i.test(v.lang))
    .sort((a, b) => Number(/br/i.test(b.lang)) - Number(/br/i.test(a.lang)));
}

/**
 * Quebra em frases antes de falar.
 *
 * Não é capricho: o Chrome corta a fala por volta de 15 segundos quando a
 * frase é longa demais. Enfileirar frases curtas evita isso, e de quebra
 * dá uma pausa natural na pontuação.
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

export function calar(): void {
  if (suportado()) speechSynthesis.cancel();
}

export const falando = (): boolean =>
  suportado() && (speechSynthesis.speaking || speechSynthesis.pending);

/**
 * Fala. Resolve quando termina, ou quando é interrompido por outra fala.
 * Nunca rejeita: falha de voz não deve derrubar a tela.
 */
export function falar(
  texto: string,
  pref: Preferencias,
  vozesDisponiveis: SpeechSynthesisVoice[],
): Promise<void> {
  if (!suportado()) return Promise.resolve();

  const frases = emFrases(limpar(texto));
  if (!frases.length) return Promise.resolve();

  calar(); // uma fala de cada vez

  const escolhida =
    vozesDisponiveis.find((v) => v.voiceURI === pref.vozURI) ??
    vozesPtBr(vozesDisponiveis)[0];

  return new Promise((pronto) => {
    frases.forEach((frase, i) => {
      const fala = new SpeechSynthesisUtterance(frase);
      if (escolhida) {
        fala.voice = escolhida;
        fala.lang = escolhida.lang;
      } else {
        fala.lang = "pt-BR";
      }
      fala.rate = pref.ritmo;
      if (i === frases.length - 1) {
        fala.onend = () => pronto();
        fala.onerror = () => pronto();
      }
      speechSynthesis.speak(fala);
    });
  });
}
