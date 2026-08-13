"""
Jaula de caminhos.

O modelo escolhe strings. String vira caminho de arquivo. Então toda
ferramenta que toca disco passa por aqui antes.

Bloqueia:
  - path traversal ("../../.ssh/id_rsa")
  - caminho absoluto pra fora da pasta de dados ("C:/Windows/System32/...")
  - symlink apontando pra fora
  - extensão fora da lista permitida
"""

from pathlib import Path

from . import config

EXTENSOES_PERMITIDAS = {".xlsx", ".xls", ".csv", ".pdf", ".txt"}


class CaminhoRecusado(Exception):
    """Erro de segurança. É devolvido ao modelo como resultado da ferramenta."""


def caminho_seguro(caminho: str, deve_existir: bool = True) -> Path:
    if not caminho or not str(caminho).strip():
        raise CaminhoRecusado("Caminho vazio.")

    alvo = (config.DADOS / caminho).resolve()

    # resolve() já segue symlink; se o destino escapou da jaula, cai aqui.
    try:
        alvo.relative_to(config.DADOS)
    except ValueError:
        raise CaminhoRecusado(
            f"Acesso negado: '{caminho}' está fora da pasta de dados. "
            f"O IVE só lê arquivos dentro de {config.DADOS.name}/."
        )

    if alvo.suffix.lower() not in EXTENSOES_PERMITIDAS:
        raise CaminhoRecusado(
            f"Extensão '{alvo.suffix}' não permitida. "
            f"Permitidas: {sorted(EXTENSOES_PERMITIDAS)}"
        )

    if deve_existir and not alvo.is_file():
        disponiveis = [p.name for p in config.DADOS.iterdir() if p.is_file()][:20]
        raise CaminhoRecusado(
            f"Arquivo '{caminho}' não encontrado. Disponíveis: {disponiveis}"
        )

    return alvo
