"""
Voz do IVE — o lado de OUVIR.

Whisper rodando na sua máquina, via faster-whisper. O áudio não sai do PC:
num escritório contábil isso não é preferência, é requisito — a gravação
tem nome de cliente, CNPJ e valor.

É por isso que a API de fala do Chrome está fora: ela manda o áudio pro
servidor do Google.

Como funciona por dentro: o áudio vira um espectrograma mel — uma imagem
de tempo × frequência — e um transformer lê essa imagem e escreve texto.
O modelo 'small' tem 244M de parâmetros.

Ponto de arquitetura: isto NÃO é ferramenta e não entra no `registry`.
O cardápio é o que o modelo pode pedir. Ouvir é decisão da interface, não
do agente — senão o modelo poderia decidir sozinho ligar seu microfone.
"""

import threading
from typing import Any, Optional

from . import config


class ErroDeVoz(Exception):
    """Falha ao transcrever. A mensagem vai pro usuário."""


# Carregar o modelo custa segundos e ~600 MB de RAM. Fazemos uma vez só,
# na primeira transcrição, e guardamos. O lock evita que dois pedidos
# simultâneos carreguem duas cópias.
_modelo: Any = None
_tranca = threading.Lock()


def _carregar() -> Any:
    global _modelo
    if _modelo is not None:
        return _modelo

    with _tranca:
        if _modelo is not None:  # outro pedido carregou enquanto esperávamos
            return _modelo
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ErroDeVoz(
                "faster-whisper não está instalado. "
                "Rode: pip install faster-whisper"
            )
        try:
            # int8 na CPU: cabe na memória e roda em tempo aceitável numa
            # máquina sem GPU. Em float32 ficaria 4x maior e mais lento.
            _modelo = WhisperModel(
                config.MODELO_VOZ, device="cpu", compute_type="int8"
            )
        except Exception as e:  # noqa: BLE001
            raise ErroDeVoz(f"Não consegui carregar o modelo de voz: {e}")
    return _modelo


def pronto() -> bool:
    """O modelo já está carregado na memória? (não força o carregamento)"""
    return _modelo is not None


def transcrever(caminho_audio: str, idioma: Optional[str] = None) -> dict:
    """
    Áudio -> texto.

    Devolve também 'confianca' e 'duracao' porque a interface precisa saber
    quando o resultado é ruim. Transcrição errada de comando de voz vira
    ação errada, e num escritório contábil isso custa caro — melhor mostrar
    o texto pro humano conferir do que executar direto.
    """
    modelo = _carregar()

    try:
        segmentos, info = modelo.transcribe(
            caminho_audio,
            language=idioma or config.IDIOMA_VOZ,
            # Corta silêncio antes de transcrever. Numa gravação de
            # push-to-talk sobra silêncio nas pontas, e sem isso o Whisper
            # às vezes alucina texto no vazio.
            vad_filter=True,
            beam_size=5,
        )
        # transcribe() devolve um gerador preguiçoso — nada acontece até
        # iterar. É aqui que o tempo de CPU é gasto.
        partes = list(segmentos)
    except Exception as e:  # noqa: BLE001
        raise ErroDeVoz(f"Falha ao transcrever: {e}")

    texto = " ".join(p.text.strip() for p in partes).strip()

    # avg_logprob é log-probabilidade média por segmento. Exponenciar dá
    # algo entre 0 e 1 que serve de sinal grosseiro de confiança.
    import math
    if partes:
        media = sum(p.avg_logprob for p in partes) / len(partes)
        confianca = round(math.exp(media), 3)
    else:
        confianca = 0.0

    return {
        "texto": texto,
        "idioma": info.language,
        "duracao": round(info.duration, 2),
        "confianca": confianca,
        "segmentos": len(partes),
        "modelo": config.MODELO_VOZ,
    }
