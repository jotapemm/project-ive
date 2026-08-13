"""
Testes da troca de motor. Não sobem modelo nenhum — nem a API da Anthropic,
nem o Ollama. Testam a costura, que é onde os erros de verdade moram.

    python -m pytest -q
"""

import pytest

from ive import motores, registry
from ive.motores import ErroDeMotor
from ive.motores.local import MotorLocal
from ive.tools import arquivos, planilha  # noqa: F401  (registra o cardápio)


def test_motor_desconhecido_falha_com_as_opcoes():
    with pytest.raises(ErroDeMotor) as e:
        motores.escolher("gpt")
    assert "anthropic" in str(e.value) and "local" in str(e.value)


def test_motor_sem_chave_explica_o_que_fazer(monkeypatch):
    monkeypatch.setattr("ive.config.API_KEY", "")
    with pytest.raises(ErroDeMotor) as e:
        motores.escolher("anthropic")
    assert ".env" in str(e.value)


def test_ollama_fora_do_ar_falha_cedo(monkeypatch):
    """Melhor falhar na largada do que no meio da tarefa."""
    monkeypatch.setattr("ive.config.OLLAMA_URL", "http://127.0.0.1:59999")
    with pytest.raises(ErroDeMotor) as e:
        motores.escolher("local")
    assert "Ollama" in str(e.value)


# --- tradução do cardápio ----------------------------------------------
# A Anthropic chama de 'input_schema'; o Ollama segue o formato da OpenAI
# e chama de 'parameters'. Se essa tradução escorregar, o modelo local
# recebe ferramenta sem schema e erra todos os argumentos.

def test_traducao_preserva_todo_o_cardapio():
    original = registry.especificacao_para_api()
    traduzido = MotorLocal._traduzir_cardapio(original)
    assert len(traduzido) == len(original)
    assert {t["function"]["name"] for t in traduzido} == \
           {o["name"] for o in original}


def test_traducao_preserva_o_schema_intacto():
    original = registry.especificacao_para_api()
    traduzido = MotorLocal._traduzir_cardapio(original)
    por_nome = {t["function"]["name"]: t["function"] for t in traduzido}

    for spec in original:
        fn = por_nome[spec["name"]]
        assert fn["parameters"] == spec["input_schema"]
        assert fn["description"] == spec["description"]
        assert fn["parameters"]["type"] == "object"


def test_traducao_usa_o_envelope_que_o_ollama_espera():
    traduzido = MotorLocal._traduzir_cardapio(registry.especificacao_para_api())
    assert all(t["type"] == "function" for t in traduzido)
    # 'input_schema' é nome da Anthropic e não pode vazar pro lado de cá.
    assert all("input_schema" not in t["function"] for t in traduzido)
