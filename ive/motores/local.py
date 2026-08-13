"""
Motor local: modelo aberto rodando na sua máquina via Ollama.

Zero API externa, zero fatura, funciona sem internet. Os dados de cliente
não saem do PC — o que, num escritório contábil, não é detalhe.

O preço disso é honesto e vale saber antes:

  * Um modelo de 3-4B é MUITO pior que o Claude em chamar ferramenta.
    Ele inventa nome de ferramenta, erra o schema, entra em loop. O
    registry barra tudo isso (ferramenta que não existe não executa), mas
    o resultado é o agente falhando mais.
  * Sem GPU dedicada a conta roda na CPU. Espere alguns tokens por segundo,
    não dezenas.
  * Não tem cache de prompt: o cardápio é reprocessado a cada volta. Como
    não custa dinheiro, custa só tempo.
"""

import json
import uuid
from typing import Any

import httpx

from .. import config
from .base import Chamada, ErroDeMotor, Resposta


class MotorLocal:
    nome = "local"

    def __init__(self) -> None:
        self._url = config.OLLAMA_URL.rstrip("/")
        self._modelo = config.MODELO_LOCAL
        # Timeout generoso: numa CPU sem GPU uma resposta demora mesmo.
        self._http = httpx.Client(timeout=httpx.Timeout(600.0, connect=5.0))
        self._conferir()

    @property
    def descricao(self) -> str:
        return f"local · {self._modelo}"

    def _conferir(self) -> None:
        """Falha cedo e com instrução, em vez de estourar no meio da tarefa."""
        try:
            r = self._http.get(f"{self._url}/api/tags", timeout=5.0)
            r.raise_for_status()
        except Exception:
            raise ErroDeMotor(
                f"Ollama não respondeu em {self._url}. Abra o app do Ollama "
                "(ou rode 'ollama serve') e tente de novo."
            )
        instalados = [m["name"] for m in r.json().get("models", [])]
        # 'qwen3:4b' e 'qwen3:4b-instruct' contam como o mesmo pedido.
        if not any(m.split(":")[0] == self._modelo.split(":")[0] for m in instalados):
            raise ErroDeMotor(
                f"Modelo '{self._modelo}' não está baixado. "
                f"Rode: ollama pull {self._modelo}\n"
                f"Instalados: {instalados or 'nenhum'}"
            )

    def abrir(self, pedido: str) -> list:
        return [
            {"role": "system", "content": config.PROMPT_SISTEMA},
            {"role": "user", "content": pedido},
        ]

    @staticmethod
    def _traduzir_cardapio(ferramentas: list[dict]) -> list[dict]:
        """
        Mesmo JSON Schema, outra embalagem.

        A Anthropic chama de 'input_schema'; o Ollama segue o formato da
        OpenAI e chama de 'parameters'. Só isso muda.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": f["name"],
                    "description": f["description"],
                    "parameters": f["input_schema"],
                },
            }
            for f in ferramentas
        ]

    def conversar(self, historico: list, ferramentas: list[dict]) -> Resposta:
        try:
            bruta = self._http.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": historico,
                    "tools": self._traduzir_cardapio(ferramentas),
                    "stream": False,
                    # Modelos da família qwen3 vêm com raciocínio LIGADO, e
                    # na CPU é ele que domina o relógio. Ver config.
                    "think": config.PENSAR_LOCAL,
                    "options": {"num_predict": config.MAX_TOKENS},
                },
            )
            bruta.raise_for_status()
        except httpx.HTTPError as e:
            raise ErroDeMotor(f"Falha falando com o Ollama: {e}")

        dados = bruta.json()
        msg = dados.get("message", {}) or {}

        r = Resposta(
            bruto=msg,
            texto=(msg.get("content") or "").strip(),
            tokens_in=dados.get("prompt_eval_count", 0) or 0,
            tokens_out=dados.get("eval_count", 0) or 0,
        )

        # O Ollama não devolve id de chamada; o loop precisa de um pra casar
        # pedido com resultado, então geramos aqui.
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {}) or {}
            argumentos = fn.get("arguments") or {}
            if isinstance(argumentos, str):  # alguns modelos devolvem string
                try:
                    argumentos = json.loads(argumentos)
                except json.JSONDecodeError:
                    argumentos = {}
            r.chamadas.append(Chamada(
                id=f"local_{uuid.uuid4().hex[:12]}",
                nome=fn.get("name", ""),
                entrada=argumentos,
            ))

        if r.chamadas:
            r.parada = "ferramenta"
        elif dados.get("done_reason") == "length":
            r.parada = "truncado"
            r.detalhe = f"bateu o teto de {config.MAX_TOKENS} tokens"
        return r

    def anotar_resposta(self, historico: list, resposta: Resposta) -> None:
        historico.append({"role": "assistant", **resposta.bruto})

    def anotar_resultados(
        self, historico: list, resultados: list[tuple[Chamada, Any, bool]]
    ) -> None:
        # Formato OpenAI: um turno 'tool' por resultado, não um só agrupando.
        for chamada, saida, _ in resultados:
            historico.append({
                "role": "tool",
                "tool_name": chamada.nome,
                "content": json.dumps(saida, ensure_ascii=False, default=str),
            })
