"""
Testes das ferramentas. Rodam SEM chamar a API — as ferramentas são
Python puro, sem IA dentro. Essa é justamente a ideia.

    python -m pytest -q
"""

import pytest

from ive import registry
from ive.seguranca import CaminhoRecusado, caminho_seguro
from ive.tools import arquivos, planilha  # noqa: F401

PLANILHA = "clientes_agosto.xlsx"


# --- jaula de caminhos -------------------------------------------------

@pytest.mark.parametrize("malicioso", [
    "../../../etc/passwd",
    "../.env",
    "/etc/hosts",
    "C:/Windows/System32/config/SAM",
    "",
])
def test_caminho_fora_da_jaula_recusado(malicioso):
    with pytest.raises(CaminhoRecusado):
        caminho_seguro(malicioso)


def test_extensao_nao_permitida_recusada():
    with pytest.raises(CaminhoRecusado):
        caminho_seguro("script.exe", deve_existir=False)


def test_caminho_valido_aceito():
    assert caminho_seguro(PLANILHA).name == PLANILHA


# --- ferramentas -------------------------------------------------------

def test_ler_planilha_traz_colunas_e_total():
    r = planilha.ler_planilha(PLANILHA)
    assert r["total_linhas"] == 8
    assert "E-mail" in r["colunas"]
    assert len(r["amostra"]) == 5


def test_amostra_respeita_teto():
    assert len(planilha.ler_planilha(PLANILHA, linhas=999)["amostra"]) <= 10


def test_inspecionar_coluna_detecta_vazio_e_duplicado():
    r = planilha.inspecionar_coluna(PLANILHA, "E-mail")
    assert r["vazios"] == 1        # Epsilon Consultoria sem e-mail
    assert r["duplicados"] == 2    # Beta e Zeta com o mesmo e-mail


def test_coluna_inexistente_devolve_erro_util():
    r = planilha.inspecionar_coluna(PLANILHA, "Email")  # sem hífen
    assert "erro" in r
    assert "E-mail" in r["colunas_disponiveis"]


def test_filtrar_planilha():
    r = planilha.filtrar_planilha(PLANILHA, "Cliente", "ltda")
    assert r["encontradas"] == 2  # Alfa Comercio Ltda, Zeta Alimentos Ltda


def test_listar_arquivos_enxerga_a_planilha():
    nomes = [a["nome"] for a in arquivos.listar_arquivos()["arquivos"]]
    assert PLANILHA in nomes


# --- registro ----------------------------------------------------------
# As únicas ferramentas que mexem no mundo. Acrescentar uma aqui é uma
# DECISÃO consciente, não um detalhe de implementação: toda escrita passa
# pelo portão de aprovação, e a interface escolhe o que fica liberado sem
# perguntar (ver ESCRITAS_LIBERADAS em ui/src/api.ts).
ESCRITAS_CONHECIDAS = {"tocar_musica"}

def test_so_essas_ferramentas_escrevem():
    achadas = {n for n in registry.listar() if registry.eh_escrita(n)}
    assert achadas == ESCRITAS_CONHECIDAS


def test_ferramenta_fora_do_cardapio_e_bloqueada():
    with pytest.raises(registry.FerramentaDesconhecida):
        registry.executar("enviar_email", {"para": "alguem@exemplo.com"})


def test_toda_ferramenta_tem_schema_valido():
    for spec in registry.especificacao_para_api():
        assert spec["description"].strip()
        assert spec["input_schema"]["type"] == "object"
        assert "properties" in spec["input_schema"]
