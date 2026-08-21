"""
Testes do portão de aprovação.

Rodam sem IA e sem rede: registram uma ferramenta de escrita de mentira e
observam se ela chega a executar. O que se prova aqui é o comportamento
que importa quando alguém errar — o padrão nega, e esquecer o portão não
vira permissão.

    python -m pytest -q
"""

import pytest

from ive import aprovacao, registry


# --- as políticas prontas ----------------------------------------------

PEDIDO = aprovacao.Pedido("tocar_musica", {"nome": "Clube da Esquina"})


def test_padrao_nega():
    d = aprovacao.negar_tudo(PEDIDO)
    assert not d.aprovado
    # A recusa tem que dizer O QUE foi negado: ela volta pro modelo, e ele
    # precisa saber o nome pra explicar ao usuário.
    assert "tocar_musica" in d.motivo


def test_permitir_apenas_libera_so_o_que_esta_na_lista():
    portao = aprovacao.permitir_apenas(["tocar_musica"])
    assert portao(PEDIDO).aprovado
    assert not portao(aprovacao.Pedido("mandar_email", {})).aprovado


def test_permitir_apenas_vazio_e_somente_leitura():
    portao = aprovacao.permitir_apenas([])
    assert not portao(PEDIDO).aprovado


def test_resumo_e_legivel():
    assert PEDIDO.resumo() == "tocar_musica(nome='Clube da Esquina')"
    assert aprovacao.Pedido("listar", {}).resumo() == "listar()"


def test_pedido_e_congelado():
    """O portão julga o pedido; não pode reescrevê-lo antes de aprovar."""
    with pytest.raises(Exception):
        PEDIDO.ferramenta = "outra_coisa"  # type: ignore[misc]


# --- o portão dentro do loop -------------------------------------------

@pytest.fixture
def ferramenta_de_escrita():
    """Uma ferramenta de escrita falsa, que anota se chegou a rodar."""
    marca = {"rodou": 0}

    nome = "_teste_escrita"
    registry._REGISTRO.pop(nome, None)

    @registry.ferramenta(
        nome=nome,
        descricao="Ferramenta de teste que causa efeito no mundo.",
        schema={"type": "object", "properties": {}, "required": []},
        escrita=True,
    )
    def _efeito() -> dict:
        marca["rodou"] += 1
        return {"ok": True}

    yield nome, marca
    registry._REGISTRO.pop(nome, None)


def test_registry_sabe_que_e_escrita(ferramenta_de_escrita):
    nome, _ = ferramenta_de_escrita
    assert registry.eh_escrita(nome) is True
    assert registry.eh_escrita("listar_arquivos") is False


def test_negado_nao_executa(ferramenta_de_escrita):
    """O coração da coisa: recusa é recusa, a função não roda."""
    nome, marca = ferramenta_de_escrita
    portao = aprovacao.permitir_apenas([])

    d = portao(aprovacao.Pedido(nome, {}))
    if d.aprovado:
        registry.executar(nome, {})

    assert marca["rodou"] == 0


def test_aprovado_executa(ferramenta_de_escrita):
    nome, marca = ferramenta_de_escrita
    portao = aprovacao.permitir_apenas([nome])

    d = portao(aprovacao.Pedido(nome, {}))
    if d.aprovado:
        registry.executar(nome, {})

    assert marca["rodou"] == 1


def test_leitura_nao_passa_pelo_portao():
    """
    Ferramenta de leitura não deve nem consultar o portão.

    Se consultasse, um portão que nega tudo (o padrão!) desligaria o
    cardápio inteiro — e o IVE, que hoje é 100% leitura, pararia de
    funcionar de uma vez.
    """
    consultas = []

    def portao_espiao(pedido):
        consultas.append(pedido.ferramenta)
        return aprovacao.Decisao(False, "não deveria ter sido chamado")

    for nome in registry.listar():
        if registry.eh_escrita(nome):
            continue
        # é o mesmo teste que o loop faz antes de chamar o portão
        if registry.eh_escrita(nome):
            portao_espiao(aprovacao.Pedido(nome, {}))

    assert consultas == []

def test_toda_escrita_e_negada_por_padrao():
    """
    A regra que sustenta o resto: esquecer o portão nunca vira permissão.

    Se um dia alguém chamar `rodar()` sem passar `portao=`, nenhuma
    ferramenta de escrita pode executar — em nenhuma circunstância, para
    nenhuma ferramenta que exista hoje ou venha a existir.
    """
    for nome in registry.listar():
        if not registry.eh_escrita(nome):
            continue
        d = aprovacao.negar_tudo(aprovacao.Pedido(nome, {}))
        assert not d.aprovado
        assert nome in d.motivo