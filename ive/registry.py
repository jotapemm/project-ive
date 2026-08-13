"""
Registro de ferramentas do IVE.

Regra de ouro: se a ferramenta não está registrada aqui, o agente NÃO consegue
executá-la. Não importa o que o modelo alucine, o que o usuário peça ou o que
venha escrito dentro de um PDF. O cardápio é o limite físico do agente.
"""

from typing import Any, Callable, Dict, List

# nome -> {"func", "description", "input_schema", "escrita"}
_REGISTRO: Dict[str, Dict[str, Any]] = {}


class FerramentaDesconhecida(Exception):
    pass


def ferramenta(nome: str, descricao: str, schema: dict, escrita: bool = False):
    """
    Decorator que registra uma função como ferramenta disponível ao modelo.

    escrita=True marca a ferramenta como capaz de causar efeito no mundo
    (enviar e-mail, gravar arquivo, chamar API externa). Toda ferramenta de
    escrita passa obrigatoriamente por portão de aprovação humana — ver
    ive/aprovacao.py. Por enquanto o cardápio é 100% leitura, de propósito.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if nome in _REGISTRO:
            raise ValueError(f"Ferramenta '{nome}' já registrada")
        _REGISTRO[nome] = {
            "func": func,
            "description": descricao,
            "input_schema": schema,
            "escrita": escrita,
        }
        return func

    return decorator


def especificacao_para_api() -> List[dict]:
    """Formato que a API da Anthropic espera no parâmetro `tools`."""
    return [
        {
            "name": nome,
            "description": meta["description"],
            "input_schema": meta["input_schema"],
        }
        for nome, meta in _REGISTRO.items()
    ]


def eh_escrita(nome: str) -> bool:
    if nome not in _REGISTRO:
        raise FerramentaDesconhecida(nome)
    return _REGISTRO[nome]["escrita"]


def listar() -> List[str]:
    return sorted(_REGISTRO.keys())


def executar(nome: str, entrada: dict) -> Any:
    """
    Executa a ferramenta. Quem chama isso é o Python, nunca o modelo.
    O modelo apenas *pede*.
    """
    if nome not in _REGISTRO:
        raise FerramentaDesconhecida(
            f"Ferramenta '{nome}' não existe. Disponíveis: {listar()}"
        )
    return _REGISTRO[nome]["func"](**entrada)
