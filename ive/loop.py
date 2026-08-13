"""
O loop do agente. Este é o miolo do IVE.

    1. manda pro motor: pergunta + cardápio de ferramentas
    2. motor responde texto OU pede ferramenta
    3. se pediu: NÓS executamos, devolvemos o resultado, volta ao passo 1
    4. se respondeu texto: acabou

Só isso. Não tem mais mistério.

Repare no que NÃO está aqui: nenhuma menção a Claude, Ollama, HTTP ou
chave de API. Quem pensa é o motor (ive/motores/), e ele é trocável por
variável de ambiente. É por isso que o mesmo loop serve pro modelo da
nuvem e pro modelo rodando no seu PC.
"""

import json
import time
from typing import Any, Callable, Optional

from . import config, logdb, motores, registry
from .motores import Chamada, ErroDeMotor
from .seguranca import CaminhoRecusado
from . import tools  # noqa: F401  (import registra as ferramentas)

# Nome antigo, mantido porque main.py e servidor.py importam por ele.
ErroDeConfiguracao = ErroDeMotor


def rodar(pedido: str, usuario: str = "local",
          ao_vivo: Optional[Callable[[str], None]] = None,
          motor: Optional[str] = None) -> dict:
    """
    Executa uma tarefa do começo ao fim.

    ao_vivo: callback opcional de progresso (print, lista, Streamlit, etc).
    motor:   sobrescreve IVE_MOTOR nesta execução.
    """
    aviso = ao_vivo or (lambda _: None)
    cerebro = motores.escolher(motor)
    logdb.inicializar()
    execucao_id = logdb.abrir_execucao(pedido, usuario, cerebro.descricao)

    # O contexto vive só dentro desta função. Acabou a tarefa, some.
    # Isso é a ausência de memória, e é intencional.
    historico = cerebro.abrir(pedido)
    cardapio = registry.especificacao_para_api()

    passos = 0
    contas = {"tokens_in": 0, "tokens_out": 0, "cache_criacao": 0,
              "cache_leitura": 0}

    def encerrar(texto: str, status: str = "ok") -> dict:
        logdb.fechar_execucao(execucao_id, texto, contas["tokens_in"],
                              contas["tokens_out"], status,
                              contas["cache_criacao"], contas["cache_leitura"])
        return {"resposta": texto, "execucao_id": execucao_id,
                "passos": passos, "status": status,
                "motor": cerebro.descricao, **contas}

    try:
        for _ in range(config.MAX_ITERACOES):
            r = cerebro.conversar(historico, cardapio)
            for campo in contas:
                contas[campo] += getattr(r, campo)

            # Só 'ferramenta' continua o loop. O resto encerra — mas por
            # motivos diferentes, e dois deles NÃO são resposta pronta.
            if r.parada == "truncado":
                # Devolver texto cortado como se fosse a resposta final é
                # pior que falhar: parece completo e não está.
                return encerrar(
                    f"Resposta truncada — {r.detalhe}. Aumente IVE_MAX_TOKENS "
                    f"ou quebre o pedido em partes.\n\n--- trecho recebido ---"
                    f"\n{r.texto}",
                    "truncado",
                )

            if r.parada == "recusado":
                return encerrar(
                    "O modelo recusou o pedido por política de segurança"
                    + (f" ({r.detalhe})." if r.detalhe else "."),
                    "recusado",
                )

            if r.parada != "ferramenta":
                return encerrar(r.texto)

            # O motor pediu ferramenta(s). Nós executamos.
            cerebro.anotar_resposta(historico, r)
            resultados: list[tuple[Chamada, Any, bool]] = []

            for chamada in r.chamadas:
                passos += 1
                aviso(f"  → {chamada.nome}("
                      f"{json.dumps(chamada.entrada, ensure_ascii=False)})")

                inicio = time.time()
                try:
                    saida, erro = registry.executar(chamada.nome, chamada.entrada), None
                except (CaminhoRecusado, registry.FerramentaDesconhecida) as e:
                    # Erro previsto: devolvemos ao modelo pra ele se corrigir.
                    saida, erro = {"erro": str(e)}, str(e)
                except TypeError as e:
                    # Argumento faltando ou a mais — modelo pequeno erra muito
                    # o schema, e precisa saber disso pra tentar de novo.
                    saida, erro = {"erro": f"Argumentos inválidos: {e}"}, str(e)
                except Exception as e:  # noqa: BLE001
                    saida, erro = {"erro": f"{type(e).__name__}: {e}"}, str(e)
                ms = int((time.time() - inicio) * 1000)

                logdb.registrar_chamada(execucao_id, chamada.nome,
                                        chamada.entrada, saida, erro, ms)
                if erro:
                    aviso(f"    ✗ {erro}")
                resultados.append((chamada, saida, erro is not None))

            cerebro.anotar_resultados(historico, resultados)

        return encerrar(
            f"Parei após {config.MAX_ITERACOES} idas e voltas sem concluir. "
            "Provavelmente a tarefa precisa ser quebrada em partes menores.",
            "teto_atingido",
        )

    except Exception as e:  # noqa: BLE001
        logdb.fechar_execucao(execucao_id, f"ERRO: {e}", contas["tokens_in"],
                              contas["tokens_out"], "erro",
                              contas["cache_criacao"], contas["cache_leitura"])
        raise
