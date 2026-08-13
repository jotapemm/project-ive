"""Ferramentas de leitura de planilha. Somente leitura."""

import pandas as pd

from ..registry import ferramenta
from ..seguranca import caminho_seguro

LIMITE_LINHAS_AMOSTRA = 10


def _carregar(caminho: str) -> pd.DataFrame:
    alvo = caminho_seguro(caminho)
    if alvo.suffix.lower() == ".csv":
        return pd.read_csv(alvo, dtype=str, keep_default_na=False)
    return pd.read_excel(alvo, dtype=str, keep_default_na=False)


@ferramenta(
    nome="ler_planilha",
    descricao=(
        "Lê uma planilha (.xlsx ou .csv) da pasta de dados e devolve as colunas, "
        "a quantidade de linhas e uma amostra das primeiras linhas. "
        "Use SEMPRE isto antes de responder qualquer coisa sobre uma planilha — "
        "nunca suponha nomes de coluna."
    ),
    schema={
        "type": "object",
        "properties": {
            "caminho": {
                "type": "string",
                "description": "Nome do arquivo dentro da pasta de dados, ex: 'clientes_agosto.xlsx'",
            },
            "linhas": {
                "type": "integer",
                "description": f"Quantas linhas de amostra retornar (máx {LIMITE_LINHAS_AMOSTRA})",
            },
        },
        "required": ["caminho"],
    },
)
def ler_planilha(caminho: str, linhas: int = 5) -> dict:
    df = _carregar(caminho)
    linhas = max(1, min(int(linhas), LIMITE_LINHAS_AMOSTRA))
    return {
        "arquivo": caminho,
        "total_linhas": int(len(df)),
        "colunas": list(df.columns),
        "amostra": df.head(linhas).to_dict(orient="records"),
    }


@ferramenta(
    nome="inspecionar_coluna",
    descricao=(
        "Analisa uma coluna específica de uma planilha: quantos valores vazios, "
        "quantos duplicados, quantos únicos e alguns exemplos. "
        "Use para conferir integridade antes de qualquer rotina que dependa "
        "daquela coluna (e-mail, CNPJ, valor)."
    ),
    schema={
        "type": "object",
        "properties": {
            "caminho": {"type": "string", "description": "Nome do arquivo"},
            "coluna": {"type": "string", "description": "Nome exato da coluna"},
        },
        "required": ["caminho", "coluna"],
    },
)
def inspecionar_coluna(caminho: str, coluna: str) -> dict:
    df = _carregar(caminho)
    if coluna not in df.columns:
        return {
            "erro": f"Coluna '{coluna}' não existe.",
            "colunas_disponiveis": list(df.columns),
        }
    serie = df[coluna].astype(str).str.strip()
    vazios = int((serie == "").sum())
    preenchidos = serie[serie != ""]
    duplicados = preenchidos[preenchidos.duplicated(keep=False)]
    return {
        "coluna": coluna,
        "total": int(len(serie)),
        "vazios": vazios,
        "unicos": int(preenchidos.nunique()),
        "duplicados": int(len(duplicados)),
        "exemplos_duplicados": sorted(set(duplicados.tolist()))[:5],
        "exemplos": preenchidos.head(5).tolist(),
    }


@ferramenta(
    nome="filtrar_planilha",
    descricao=(
        "Filtra linhas de uma planilha onde uma coluna contém um texto. "
        "Devolve no máximo 50 linhas. Não altera o arquivo original."
    ),
    schema={
        "type": "object",
        "properties": {
            "caminho": {"type": "string", "description": "Nome do arquivo"},
            "coluna": {"type": "string", "description": "Coluna a filtrar"},
            "contem": {
                "type": "string",
                "description": "Texto procurado (não diferencia maiúscula/minúscula)",
            },
        },
        "required": ["caminho", "coluna", "contem"],
    },
)
def filtrar_planilha(caminho: str, coluna: str, contem: str) -> dict:
    df = _carregar(caminho)
    if coluna not in df.columns:
        return {
            "erro": f"Coluna '{coluna}' não existe.",
            "colunas_disponiveis": list(df.columns),
        }
    mascara = df[coluna].astype(str).str.contains(contem, case=False, na=False)
    achados = df[mascara]
    return {
        "encontradas": int(len(achados)),
        "truncado": bool(len(achados) > 50),
        "linhas": achados.head(50).to_dict(orient="records"),
    }
