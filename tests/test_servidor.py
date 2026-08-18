"""
Testes do servidor HTTP. Rodam SEM chamar a API da Anthropic — só tocam
as rotas diretas, que não passam pelo modelo.

A pergunta que estes testes respondem: pôr HTTP na frente abriu algum
buraco que a CLI não tinha? A resposta tem que ser não.

    python -m pytest -q
"""

import pytest
from fastapi.testclient import TestClient

from ive.servidor import app

PLANILHA = "clientes_agosto.xlsx"


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


# --- estado ------------------------------------------------------------

def test_saude_lista_o_cardapio(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert "ler_planilha" in r.json()["ferramentas"]


def test_saude_nao_vaza_a_chave(cliente):
    """tem_chave é booleano. A chave em si nunca sai por rota nenhuma."""
    corpo = r"{}".format(cliente.get("/saude").text)
    assert "sk-ant" not in corpo
    assert isinstance(cliente.get("/saude").json()["tem_chave"], bool)


# --- chamada direta de automação (sem IA no meio) ----------------------

def test_ferramenta_direta_funciona(cliente):
    r = cliente.post(f"/ferramentas/ler_planilha", json={"caminho": PLANILHA})
    assert r.status_code == 200
    assert r.json()["total_linhas"] == 8


def test_ferramenta_direta_acha_os_problemas_plantados(cliente):
    r = cliente.post("/ferramentas/inspecionar_coluna",
                     json={"caminho": PLANILHA, "coluna": "E-mail"})
    assert r.json()["vazios"] == 1
    assert r.json()["duplicados"] == 2


# --- o cardápio continua sendo o limite físico, também por HTTP --------

def test_ferramenta_fora_do_cardapio_da_404(cliente):
    r = cliente.post("/ferramentas/enviar_email",
                     json={"para": "alguem@exemplo.com"})
    assert r.status_code == 404


@pytest.mark.parametrize("malicioso", [
    "../../../etc/passwd",
    "../.env",
    "C:/Windows/System32/config/SAM",
])
def test_jaula_de_caminhos_vale_por_http(cliente, malicioso):
    r = cliente.post("/ferramentas/ler_planilha", json={"caminho": malicioso})
    assert r.status_code == 403


def test_argumento_invalido_da_400_e_nao_500(cliente):
    r = cliente.post("/ferramentas/ler_planilha", json={"coluna": "E-mail"})
    assert r.status_code == 400


# --- auditoria ---------------------------------------------------------

def test_historico_responde(cliente):
    assert cliente.get("/historico").status_code == 200


def test_execucao_inexistente_da_404(cliente):
    assert cliente.get("/execucoes/999999").status_code == 404


def test_pedido_vazio_nao_gasta_api(cliente):
    """Barrado antes de chegar no modelo — logo, antes de custar."""
    assert cliente.post("/executar", json={"texto": "   "}).status_code == 400


# --- voz ---------------------------------------------------------------
# Não carregam o Whisper: testam os PORTÕES, que é onde mora o risco de
# alguém derrubar o servidor mandando lixo. Carregar o modelo custa ~600MB
# de RAM e vários segundos — não é coisa pra suíte de teste.

def test_audio_vazio_da_400_e_nao_500(cliente):
    r = cliente.post("/voz/ouvir", files={"audio": ("v.webm", b"", "audio/webm")})
    assert r.status_code == 400


def test_audio_gigante_e_recusado_antes_de_transcrever(cliente):
    """
    Push-to-talk gera clipe curto. Um arquivo enorme aqui é engano ou
    abuso — e transcrever antes de conferir o tamanho seria um jeito
    barato de travar a máquina.
    """
    from ive import config

    demais = b"\0" * ((config.MAX_AUDIO_MB + 1) * 1024 * 1024)
    r = cliente.post(
        "/voz/ouvir", files={"audio": ("grande.webm", demais, "audio/webm")}
    )
    assert r.status_code == 413


def test_voz_aparece_na_saude(cliente):
    corpo = cliente.get("/saude").json()
    assert corpo["voz_modelo"]
    assert isinstance(corpo["voz_carregada"], bool)


# --- falar (Piper) -----------------------------------------------------
# Nao sintetizam de verdade: testam os PORTOES e o contrato da rota.
# Carregar uma voz custa segundos e ~200MB — nao e coisa pra suite.

def test_texto_vazio_da_400(cliente):
    assert cliente.post("/voz/falar", json={"texto": "   "}).status_code == 400


def test_texto_gigante_e_recusado(cliente):
    r = cliente.post("/voz/falar", json={"texto": "a" * 4001})
    assert r.status_code == 413


def test_voz_inexistente_explica_como_baixar(cliente):
    """Erro que nao diz o que fazer e so frustracao."""
    r = cliente.post("/voz/falar", json={"texto": "oi", "voz": "nao_existe"})
    assert r.status_code == 503
    assert "download_voices" in r.json()["detail"]


def test_saude_lista_as_vozes_baixadas(cliente):
    corpo = cliente.get("/saude").json()
    assert isinstance(corpo["fala_vozes"], list)
    assert corpo["fala_padrao"]
