"""
Ferramentas do Spotify.

Duas, e elas ficam em lados opostos do portão de aprovação:

    buscar_musica   leitura — só consulta o catálogo público
    tocar_musica    ESCRITA — faz som sair da caixa de som

A divisão não é burocracia. `tocar_musica` recebe URI e não nome de
propósito: se ela buscasse sozinha, o portão perguntaria "autoriza tocar
'The Beach'?" e a busca aconteceria DEPOIS da aprovação — teria sido
autorizado um nome, não uma música. Buscando antes, o que se aprova é uma
faixa que já apareceu na tela.

E os dois passos não custam nada a quem pede: o MODELO encadeia as duas
chamadas no mesmo turno. Quem fala diz "toca The Beach do The
Neighbourhood" uma vez só.

Quem toca não é a API do Spotify, é o app instalado: o Windows tem o
protocolo `spotify:` registrado, e entregar uma URI a ele abre o programa
(mesmo fechado) e já começa a tocar. Por isso aqui não há login de
usuário nem Premium exigido pela API — o crachá é do APLICATIVO, e serve
apenas para buscar. Nada nesta ferramenta toca a conta de ninguém.

Sobre a ordenação da busca, que engana: o resultado NÃO é personalizado.
Com crachá de aplicativo não existe usuário na conversa, então o Spotify
não sabe quem perguntou. A primeira faixa vem por popularidade global —
bom padrão, mas é o gosto do mundo, não o seu.
"""

import base64
import os
import time

import httpx

from .. import config
from ..registry import ferramenta
from ..seguranca import uri_segura

_PORTA_TOKEN = "https://accounts.spotify.com/api/token"
_PORTA_BUSCA = "https://api.spotify.com/v1/search"

# Sem isto o Spotify devolve faixas que não tocam no Brasil por direito
# autoral: a busca acha, o play falha, e o erro não explica nada.
_MERCADO = "BR"

# Crachá guardado. Pedir um por busca custaria uma viagem extra à internet,
# faria o segredo trafegar toda hora e bateria no limite de requisições.
_cache = {"token": "", "vence": 0.0}


class ErroSpotify(Exception):
    """Falha ao falar com o Spotify. A mensagem vai pro modelo."""


def _token() -> str:
    """
    O crachá do aplicativo, reaproveitado até 60s antes de vencer.

    A margem existe por um bug que só aparece em produção: usando o token
    até o último segundo, uma hora ele expira NO MEIO da viagem até o
    servidor e volta um 401 numa chamada que "deveria" funcionar. Jogar
    fora 1 minuto de um crachá de 60 compra o problema inteiro.
    """
    if _cache["token"] and time.time() < _cache["vence"]:
        return _cache["token"]

    if not config.SPOTIFY_ID or not config.SPOTIFY_SEGREDO:
        raise ErroSpotify(
            "Spotify não configurado. Crie um app em "
            "developer.spotify.com/dashboard e ponha SPOTIFY_CLIENT_ID e "
            "SPOTIFY_CLIENT_SECRET no arquivo .env."
        )

    # base64 NÃO é criptografia: é só um alfabeto seguro para cabeçalho
    # HTTP. Quem protege esta viagem é o https da URL.
    cru = f"{config.SPOTIFY_ID}:{config.SPOTIFY_SEGREDO}"
    cracha = base64.b64encode(cru.encode()).decode()

    try:
        r = httpx.post(
            _PORTA_TOKEN,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {cracha}"},
            timeout=10,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ErroSpotify(f"Não consegui autenticar no Spotify: {e}")

    d = r.json()
    _cache["token"] = d["access_token"]
    _cache["vence"] = time.time() + d["expires_in"] - 60
    return _cache["token"]


@ferramenta(
    nome="buscar_musica",
    descricao=(
        "Procura músicas no catálogo do Spotify por nome, artista ou os "
        "dois juntos. Devolve até 10 candidatas com nome, artista, álbum e "
        "a URI de cada uma. Use SEMPRE antes de tocar_musica: é daqui que "
        "sai a URI. Se o usuário disse só o nome da música, inclua o "
        "artista no termo quando ele mencionar — a busca fica bem melhor."
    ),
    schema={
        "type": "object",
        "properties": {
            "termo": {
                "type": "string",
                "description": "O que procurar, ex: 'The Beach The Neighbourhood'",
            },
            "quantos": {
                "type": "integer",
                "description": "Quantos resultados, de 1 a 10. Padrão 5.",
            },
        },
        "required": ["termo"],
    },
)
def buscar_musica(termo: str, quantos: int = 5) -> dict:
    termo = (termo or "").strip()
    if not termo:
        raise ErroSpotify("Termo de busca vazio.")

    try:
        r = httpx.get(
            _PORTA_BUSCA,
            params={
                "q": termo,
                "type": "track",
                "limit": max(1, min(10, quantos)),
                "market": _MERCADO,
            },
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=10,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ErroSpotify(f"Busca falhou: {e}")

    achadas = [
        {
            "nome": t["name"],
            "artista": ", ".join(a["name"] for a in t["artists"]),
            "album": t["album"]["name"],
            "uri": t["uri"],
        }
        for t in r.json()["tracks"]["items"]
    ]
    return {"termo": termo, "quantidade": len(achadas), "musicas": achadas}


@ferramenta(
    nome="tocar_musica",
    descricao=(
        "Toca uma música no aplicativo do Spotify instalado neste "
        "computador, abrindo o programa se estiver fechado. Recebe a URI "
        "vinda de buscar_musica — NÃO aceita nome de música. O 'rotulo' é "
        "obrigatório e deve ser 'Música — Artista' exatamente como veio da "
        "busca: é ele que a pessoa lê na hora de autorizar."
    ),
    schema={
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "URI no formato spotify:track:<22 caracteres>",
            },
            "rotulo": {
                "type": "string",
                "description": "Nome legível, ex: 'The Beach — The Neighbourhood'",
            },
        },
        "required": ["uri", "rotulo"],
    },
    escrita=True,
)
def tocar_musica(uri: str, rotulo: str = "") -> dict:
    """
    O `rotulo` não é usado para tocar nada — ele existe só para o portão
    conseguir perguntar em português.

    Sem ele a aprovação seria "autoriza tocar_musica(uri='spotify:track:
    2u0CelO5c81XS7z3dGpHbS')?", que são 22 caracteres aleatórios. Portão
    que pergunta em código não protege: ele só treina o usuário a apertar
    "sim" sem ler.

    A limitação, dita na cara: nada garante que o rótulo corresponda à
    URI — o modelo escreve os dois. Para tocar música o pior caso é sair a
    faixa errada, o que custa um "não, a outra". Para uma ferramenta que
    apagasse arquivo, esse desenho não serviria.
    """
    # A jaula ANTES de tudo: os.startfile abre o que receber — .exe, .bat,
    # link — e quem escolheu essa string foi o modelo.
    uri = uri_segura(uri)

    abrir = getattr(os, "startfile", None)
    if abrir is None:
        raise ErroSpotify(
            "tocar_musica só funciona no Windows — os.startfile não existe "
            "neste sistema."
        )

    abrir(uri)

    # Honestidade sobre o que sabemos: pedimos ao Windows que entregasse a
    # URI ao Spotify. Esse caminho não devolve nada — não há como confirmar
    # daqui que saiu som.
    return {
        "pedido": uri,
        "rotulo": rotulo,
        "situacao": "entregue ao aplicativo do Spotify",
    }
