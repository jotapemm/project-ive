"""
Voz do IVE — o lado de FALAR.

O par de ive/voz.py: aquele ouve, este fala. Os dois rodam aqui, e nenhum
manda áudio pra lugar nenhum.

Dois motores, escondidos atrás da mesma função:

  piper    VITS exportado pra ONNX. Rápido — ~6x tempo real numa CPU sem
           GPU. Quatro vozes em português, TODAS masculinas.

  kokoro   também ONNX, também local, mas ~0,7x tempo real: nove vezes
           mais lento que o Piper nesta máquina. Existe aqui por um motivo
           só: não há voz FEMININA em português no Piper, e a única do
           catálogo do Kokoro não prestava. A que usamos é MONTADA — ver
           a seção "português numa voz que não é portuguesa", lá embaixo.
           Serve pra frase curta e pra áudio gerado uma vez e guardado;
           não serve pra conversa corrida.

Os dois rodam no mesmo onnxruntime, que já estava instalado por causa do
Whisper. Por isso somar o Kokoro custou 92 MB de modelo e nada de runtime.

Como funciona por dentro: texto → fonemas (eSpeak-ng) → modelo → forma de
onda. Um modelo só, sem vocoder separado.

Ponto de arquitetura, igual ao de ouvir: isto NÃO entra no `registry`. O
cardápio é o que o modelo pode pedir; falar é decisão da interface.
"""

import io
import re
import threading
import wave
from typing import Any, Optional

from . import config


class ErroDeFala(Exception):
    """Falha ao sintetizar. A mensagem vai pro usuário."""


# Gênero por voz. O Piper não publica essa informação, então é escrita à
# mão; o Kokoro codifica no nome (p=português, f/m=gênero).
#
# É o único rótulo que sobra. O seletor mostra "Feminina" e "Masculina",
# sem nome próprio: quem escolhe voz quer escolher a voz, não decorar de
# quem é o apelido. Os arquivos em disco continuam com os nomes deles.
_GENERO = {
    "pt_BR-faber-medium": "m",
    "pt_BR-cadu-medium": "m",
    "pt_BR-jeff-medium": "m",
    "pt_BR-edresson-low": "m",
}

_KOKORO_MODELO = "kokoro-q8.onnx"
_KOKORO_PACOTE = "vozes-pt.npz"
_KOKORO_TAXA = 24000

# Carregar modelo custa segundos. Guardamos por nome — trocar de voz na
# interface não deve jogar fora a que já estava carregada.
_carregadas: dict[str, Any] = {}
_kokoro: dict[str, Any] = {}
_tranca = threading.Lock()


def _pasta_kokoro():
    return config.VOZES / "kokoro"


def disponiveis() -> list[dict]:
    """
    Todas as vozes em disco, dos dois motores.

    Devolve dicionário e não string porque a interface precisa saber mais
    que o nome: qual motor (pra avisar da lentidão) e o gênero — que no
    seletor É o rótulo, já que lá não aparece nome próprio.
    """
    achadas: list[dict] = []

    for p in sorted(config.VOZES.glob("*.onnx")):
        achadas.append({
            "nome": p.stem, "motor": "piper",
            "genero": _GENERO.get(p.stem, "?"), "rapida": True,
        })

    # Um .bin solto por voz, em vez de um pacote .npz: adicionar uma voz
    # passa a ser largar o arquivo na pasta. Candidatas ainda não escolhidas
    # ficam em kokoro/candidatas/ — em disco, mas fora do seletor.
    if (_pasta_kokoro() / _KOKORO_MODELO).is_file():
        for p in sorted(_pasta_kokoro().glob("*.bin")):
            achadas.append({
                "nome": p.stem, "motor": "kokoro",
                # 2a letra do nome: f = feminina, m = masculina
                "genero": "f" if p.stem[1:2] == "f" else "m",
                "rapida": False,
            })
    return achadas


def _motor_de(nome: str) -> str:
    for v in disponiveis():
        if v["nome"] == nome:
            return v["motor"]
    baixadas = [v["nome"] for v in disponiveis()]
    # Erro que nao diz o que fazer e so frustracao — a mensagem carrega o
    # comando pronto. Ha um teste que garante isso.
    raise ErroDeFala("\n".join([
        f"Voz '{nome}' não está baixada.",
        f"Disponíveis: {baixadas or 'nenhuma'}",
        "Para baixar uma voz do Piper:",
        f"  python -m piper.download_voices {nome} --download-dir {config.VOZES}",
    ]))


def pronta(nome: Optional[str] = None) -> bool:
    """A voz já está carregada na memória? (não força o carregamento)"""
    n = nome or config.VOZ_PIPER
    return n in _carregadas or bool(_kokoro)


# --- piper -------------------------------------------------------------

def _piper(nome: str) -> Any:
    if nome in _carregadas:
        return _carregadas[nome]
    with _tranca:
        if nome in _carregadas:
            return _carregadas[nome]
        try:
            from piper import PiperVoice
        except ImportError:
            raise ErroDeFala("piper-tts não está instalado.")
        try:
            _carregadas[nome] = PiperVoice.load(config.VOZES / f"{nome}.onnx")
        except Exception as e:  # noqa: BLE001
            raise ErroDeFala(f"Não consegui carregar a voz '{nome}': {e}")
    return _carregadas[nome]


def _falar_piper(texto: str, nome: str, ritmo: float) -> bytes:
    from piper import SynthesisConfig
    # length_scale: quanto MAIOR, mais devagar — ele estica a duração de
    # cada fonema. O nome engana, então fica registrado aqui.
    voz = _piper(nome)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        voz.synthesize_wav(texto, wav, syn_config=SynthesisConfig(length_scale=ritmo))
    return buffer.getvalue()


# --- kokoro ------------------------------------------------------------

def _sessao_kokoro() -> tuple:
    if _kokoro:
        return _kokoro["sess"], _kokoro["tk"], _kokoro["vozes"]
    with _tranca:
        if _kokoro:
            return _kokoro["sess"], _kokoro["tk"], _kokoro["vozes"]
        try:
            import numpy as np
            import onnxruntime as rt
            from kokoro_onnx.tokenizer import Tokenizer
        except ImportError as e:
            raise ErroDeFala(f"kokoro-onnx não está instalado: {e}")
        try:
            # Só o int8 puro. O 'q8f16' publicado derruba o onnxruntime
            # com segfault nesta máquina — int8 misturado com fp16 não é
            # combinação que toda build aguenta.
            _kokoro["sess"] = rt.InferenceSession(
                str(_pasta_kokoro() / _KOKORO_MODELO),
                providers=["CPUExecutionProvider"],
            )
            _kokoro["tk"] = Tokenizer()
            _kokoro["vozes"] = {}  # carregadas sob demanda, 0,5 MB cada
        except Exception as e:  # noqa: BLE001
            _kokoro.clear()
            raise ErroDeFala(f"Não consegui carregar o Kokoro: {e}")
    return _kokoro["sess"], _kokoro["tk"], _kokoro["vozes"]


def _estilo_kokoro(nome: str):
    """
    O vetor de estilo da voz — é ele que carrega o timbre.

    Cache por nome: 0,5 MB cada, e reler do disco a cada frase seria
    desperdício numa conversa.
    """
    import numpy as np
    _, _, cache = _sessao_kokoro()
    if nome not in cache:
        arq = _pasta_kokoro() / f"{nome}.bin"
        if not arq.is_file():
            raise ErroDeFala(f"Vetor de voz '{nome}.bin' não encontrado.")
        cache[nome] = np.fromfile(arq, dtype=np.float32).reshape(-1, 1, 256)
    return cache[nome]


# --- português numa voz que não é portuguesa ---------------------------

# A voz feminina do seletor é montada: o TIMBRE vem da `af_bella`, que é
# inglesa, e o RITMO vem da `pf_dora`. As duas metades do vetor de estilo
# fazem coisas diferentes, e por isso dá pra costurar uma na outra.
#
# Isso cobra um preço na pronúncia. O eSpeak escreve o português com
# símbolos que a Dora viu em treino e a Bella nunca — pra ela cada um
# aponta pro som INGLÊS, e som inglês em palavra portuguesa é sotaque. O
# conserto é reescrever a fonemização com símbolos cuja leitura inglesa
# cai no som certo: o `ɾ` que ela conhece do "butter" americano é o mesmo
# tap do "três".
#
# Por isso a lista é amarrada à voz e não é global. Numa voz nativa o
# mesmo conserto ESTRAGARIA a fala: a Dora aprendeu os símbolos crus, e
# trocá-los a tiraria justamente do que ela sabe.
_TIMBRE_ESTRANGEIRO = {"pf_bella"}

# A ordem importa: cada linha vê o resultado da anterior.
_CONSERTOS = tuple((re.compile(p), t) for p, t in (
    ("eɪŋ", "eŋ"),              # "então", "cliente": eɪ é o ditongo de "day"
    ("æ", "ɐ"),                 # "planilha" acabava no [æ] de "cat"
    ("y", "i"),                 # o -e final saía como o [y] francês
    ("ˌ", ""),                  # o espeak pt-br acentua quase toda sílaba
    ("lj", "ʎ"),                # "filha" virava "fi-lhi-a"
    (r"(?<=[ptkbdɡfv])r", "ɾ"),   # "três", "prazo": encontro com r é TAP
    ("ɾə", "ɾ"),                # "porta": o espeak enfia um schwa, "po-ro-ta"
    ("x", "h"),                 # "carro", "Ribeiro": [x] não existe em inglês
))


def _fonemas(tk, texto: str, voz: str) -> str:
    """Texto -> IPA, consertado se a voz precisar."""
    ipa = tk.phonemize(texto, lang="pt-br")
    if voz not in _TIMBRE_ESTRANGEIRO:
        return ipa
    for padrao, troca in _CONSERTOS:
        ipa = padrao.sub(troca, ipa)
    return ipa


def _falar_kokoro(texto: str, nome: str, ritmo: float) -> bytes:
    import numpy as np
    sess, tk, _ = _sessao_kokoro()
    estilo = _estilo_kokoro(nome)

    ids = np.array(tk.tokenize(_fonemas(tk, texto, nome)), dtype=np.int64)
    if not len(ids):
        raise ErroDeFala("Nada a sintetizar depois da fonemização.")

    # NÃO usamos Kokoro.create() do pacote: na versão 0.4.7 ele manda
    # `speed` como int32 num modelo que declara float, e a inferência
    # falha. Chamamos a sessão direto com o tipo certo.
    saida = sess.run(None, {
        "input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
        "style": estilo[len(ids)].astype(np.float32),
        # No Kokoro `speed` é multiplicador direto: MAIOR = mais rápido.
        # É o inverso do length_scale do Piper — por isso não dá pra
        # repassar o mesmo número pros dois.
        "speed": np.array([1.0 / max(ritmo, 0.01)], dtype=np.float32),
    })[0]

    amostras = np.asarray(saida, dtype=np.float32).flatten()
    pcm = (np.clip(amostras, -1.0, 1.0) * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_KOKORO_TAXA)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


# --- interface pública -------------------------------------------------

def sintetizar(texto: str, nome: Optional[str] = None,
               ritmo: Optional[float] = None) -> bytes:
    """
    Texto -> WAV, em memória.

    Devolve bytes e não caminho de arquivo de propósito: o áudio vai direto
    pra resposta HTTP e morre ali. Não há motivo pra encostar no disco, e
    disco encostado é disco que alguém esquece de limpar.
    """
    texto = (texto or "").strip()
    if not texto:
        raise ErroDeFala("Texto vazio.")

    nome = nome or config.VOZ_PIPER
    ritmo = ritmo or config.PIPER_RITMO
    motor = _motor_de(nome)

    try:
        if motor == "kokoro":
            return _falar_kokoro(texto, nome, ritmo)
        return _falar_piper(texto, nome, ritmo)
    except ErroDeFala:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErroDeFala(f"Falha ao sintetizar: {e}")
