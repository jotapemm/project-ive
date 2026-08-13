"""
O contrato entre o loop e o modelo.

O loop do agente não sabe QUEM está pensando. Ele entrega o histórico e o
cardápio, recebe de volta ou um texto ou pedidos de ferramenta. Trocar o
Claude por um modelo rodando no seu próprio PC não muda uma linha de loop.py.

Cada provedor guarda o histórico no formato que a API dele exige — por isso
'historico' é opaco aqui: quem cria e quem mexe nele é sempre o motor.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


class ErroDeMotor(Exception):
    """Motor indisponível ou mal configurado. Mensagem vai pro usuário."""


@dataclass
class Chamada:
    """Um pedido de ferramenta. O modelo PEDE; quem executa é o Python."""
    id: str
    nome: str
    entrada: dict


@dataclass
class Resposta:
    texto: str = ""
    chamadas: list[Chamada] = field(default_factory=list)

    # "ferramenta" continua o loop. Os outros três encerram, e a diferença
    # importa: 'truncado' e 'recusado' NÃO são resposta pronta.
    parada: str = "fim"          # ferramenta | fim | truncado | recusado
    detalhe: str = ""

    tokens_in: int = 0
    tokens_out: int = 0
    cache_criacao: int = 0
    cache_leitura: int = 0

    # Payload cru do provedor. Só o motor que o produziu sabe lê-lo — serve
    # pra devolver o turno do assistente ao histórico sem perder nada.
    bruto: Any = None


class Motor(Protocol):
    nome: str
    descricao: str

    def abrir(self, pedido: str) -> list:
        """Cria o histórico inicial no formato deste provedor."""

    def conversar(self, historico: list, ferramentas: list[dict]) -> Resposta:
        """Uma ida ao modelo."""

    def anotar_resposta(self, historico: list, resposta: Resposta) -> None:
        """Anexa o turno do assistente."""

    def anotar_resultados(
        self, historico: list, resultados: list[tuple[Chamada, Any, bool]]
    ) -> None:
        """Anexa os resultados das ferramentas. (chamada, saída, é_erro)"""
