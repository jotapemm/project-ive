/**
 * Cliente do servidor Python.
 *
 * Este arquivo é a costura vista do lado TypeScript — e é o pedaço que
 * o React Native vai reaproveitar inteiro depois. Por isso ele não sabe
 * nada de React: só tipos e fetch.
 *
 * A separação das duas famílias está aqui de propósito:
 *   executar()          → passa pelo modelo (intenção vaga)
 *   chamarFerramenta()  → chama a automação direto (intenção exata)
 */

const BASE = "/api";

export type Saude = {
  ok: boolean;
  motor: string;
  motor_descricao: string;
  motor_pronto: boolean;
  motor_motivo: string;
  motores: string[];
  modelo: string;
  modelo_local: string;
  tem_chave: boolean;
  pasta_dados: string;
  ferramentas: string[];
  max_iteracoes: number;
};

export type Ferramenta = {
  name: string;
  description: string;
  input_schema: { properties?: Record<string, unknown>; required?: string[] };
  escrita: boolean;
};

export type Resultado = {
  resposta: string;
  execucao_id: number;
  passos: number;
  status: string;
  motor: string;
  tokens_in: number;
  tokens_out: number;
  cache_criacao: number;
  cache_leitura: number;
  trilha: string[];
};

export type Execucao = {
  id: number;
  iniciada_em: string;
  pedido: string;
  status: string;
  tokens_in: number;
  tokens_out: number;
};

export class ErroDoServidor extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

async function pedir<T>(rota: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${rota}`, {
      headers: { "Content-Type": "application/json" },
      ...opcoes,
    });
  } catch {
    // Causa quase certa: o servidor Python não está de pé.
    throw new ErroDoServidor(0, "Servidor fora do ar. Rode: uvicorn ive.servidor:app");
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    throw new ErroDoServidor(
      resposta.status,
      corpo?.detail ?? `Erro ${resposta.status}`,
    );
  }
  return corpo as T;
}

export const saude = () => pedir<Saude>("/saude");
export const ferramentas = () => pedir<Ferramenta[]>("/ferramentas");
export const historico = () => pedir<Execucao[]>("/historico");

/** Passa pelo modelo. Custa tokens e demora. `motor` sobrescreve o padrão. */
export const executar = (texto: string, motor?: string) =>
  pedir<Resultado>("/executar", {
    method: "POST",
    body: JSON.stringify({ texto, motor: motor ?? null }),
  });

/** Não passa pelo modelo. Instantâneo e de graça. */
export const chamarFerramenta = (nome: string, entrada: Record<string, unknown>) =>
  pedir<unknown>(`/ferramentas/${nome}`, {
    method: "POST",
    body: JSON.stringify(entrada),
  });

export type Transcricao = {
  texto: string;
  idioma: string;
  duracao: number;
  confianca: number;
  segmentos: number;
  modelo: string;
};

/**
 * Áudio -> texto, com Whisper rodando no servidor local.
 *
 * Não passa pelo `pedir()` porque FormData precisa que o NAVEGADOR defina
 * o Content-Type — ele inclui o `boundary` do multipart. Definir na mão
 * quebra o upload de um jeito difícil de diagnosticar.
 */
export async function ouvir(audio: Blob): Promise<Transcricao> {
  const pacote = new FormData();
  pacote.append("audio", audio, "clipe.webm");

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}/voz/ouvir`, { method: "POST", body: pacote });
  } catch {
    throw new ErroDoServidor(0, "Servidor fora do ar.");
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    throw new ErroDoServidor(resposta.status, corpo?.detail ?? `Erro ${resposta.status}`);
  }
  return corpo as Transcricao;
}
