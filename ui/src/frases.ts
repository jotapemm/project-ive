/**
 * As frases que cada voz diz ao ser testada.
 *
 * ESTE É O ARQUIVO PRA MEXER. Não precisa entender React nem procurar no
 * meio do JSX: mude o texto aqui e recarregue a página.
 *
 * O botão "ouvir uma amostra" fala exatamente o que estiver escrito aqui
 * para a voz selecionada — nada de rodízio, nada de frase surpresa.
 */

/**
 * Chave = nome do modelo.
 *
 * Voz SEM entrada aqui fala a GENERICA — e e isso que permite comparar:
 * percorrendo o seletor, todas dizem exatamente a mesma frase, e a unica
 * variavel que sobra e o timbre. Se voce quiser comparar o Faber junto,
 * comente a linha dele aqui embaixo.
 */
export const APRESENTACAO: Record<string, string> = {
  "pt_BR-faber-medium": "Faala tcheeeê! Como eu posso te ajudá?",
};

/**
 * A frase de teste padrao. Mude AQUI para trocar a que voce ouve ao
 * comparar as vozes — ela tem pergunta, numero e nasalizacao de proposito:
 * "nao" e "entao" sao justamente onde as vozes de outro idioma tropecam.
 */
export const GENERICA =
  "Oiee, como eu posso te ajudá hoje?";

/** A frase de apresentação da voz — sempre a mesma, por escolha. */
export function amostra(voz: string): string {
  return APRESENTACAO[voz] ?? GENERICA;
}
