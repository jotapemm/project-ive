"""Motor de nuvem: API da Anthropic. Custa por token, mas é bem melhor."""

import json
from typing import Any

from anthropic import Anthropic

from .. import config
from .base import Chamada, ErroDeMotor, Resposta


def _contar(uso, campo: str) -> int:
    """usage traz None em vez de 0 quando o campo não se aplica."""
    return getattr(uso, campo, None) or 0


class MotorNuvem:
    nome = "anthropic"

    def __init__(self) -> None:
        if not config.API_KEY:
            raise ErroDeMotor(
                "ANTHROPIC_API_KEY não encontrada. Copie .env.example para "
                ".env e preencha a chave — ou use IVE_MOTOR=local."
            )
        self._cliente = Anthropic(api_key=config.API_KEY)
        # A API casa cache por PREFIXO, e monta na ordem
        # ferramentas -> sistema -> mensagens. Marcar o fim do sistema
        # portanto guarda o cardápio junto, que é o pedaço reenviado a
        # cada volta do loop. Leitura de cache custa ~10% do normal.
        self._sistema = [{
            "type": "text",
            "text": config.PROMPT_SISTEMA,
            "cache_control": {"type": "ephemeral"},
        }]

    @property
    def descricao(self) -> str:
        return f"anthropic · {config.MODELO}"

    def abrir(self, pedido: str) -> list:
        return [{"role": "user", "content": pedido}]

    def conversar(self, historico: list, ferramentas: list[dict]) -> Resposta:
        bruta = self._cliente.messages.create(
            model=config.MODELO,
            max_tokens=config.MAX_TOKENS,
            system=self._sistema,
            tools=ferramentas,
            messages=historico,
        )

        r = Resposta(
            bruto=bruta.content,
            # input_tokens conta só o que NÃO veio do cache. O prompt real
            # é a soma dos três campos.
            tokens_in=bruta.usage.input_tokens,
            tokens_out=bruta.usage.output_tokens,
            cache_criacao=_contar(bruta.usage, "cache_creation_input_tokens"),
            cache_leitura=_contar(bruta.usage, "cache_read_input_tokens"),
        )
        r.texto = "\n".join(
            b.text for b in bruta.content if b.type == "text"
        ).strip()

        if bruta.stop_reason == "max_tokens":
            r.parada = "truncado"
            r.detalhe = (
                f"bateu o teto de {config.MAX_TOKENS} tokens (o raciocínio "
                "interno conta junto com o texto)"
            )
        elif bruta.stop_reason == "refusal":
            r.parada = "recusado"
            categoria = getattr(bruta.stop_details, "category", None)
            r.detalhe = f"categoria: {categoria}" if categoria else ""
        elif bruta.stop_reason == "tool_use":
            r.parada = "ferramenta"
            r.chamadas = [
                Chamada(id=b.id, nome=b.name, entrada=b.input)
                for b in bruta.content if b.type == "tool_use"
            ]
        return r

    def anotar_resposta(self, historico: list, resposta: Resposta) -> None:
        # Devolve os blocos crus — inclusive os de raciocínio, que a API
        # exige de volta intactos no turno seguinte.
        historico.append({"role": "assistant", "content": resposta.bruto})

    def anotar_resultados(
        self, historico: list, resultados: list[tuple[Chamada, Any, bool]]
    ) -> None:
        # Todos os resultados vão numa ÚNICA mensagem. Espalhar em várias
        # ensina o modelo a parar de pedir ferramentas em paralelo.
        historico.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": chamada.id,
                    "content": json.dumps(saida, ensure_ascii=False, default=str),
                    "is_error": eh_erro,
                }
                for chamada, saida, eh_erro in resultados
            ],
        })
