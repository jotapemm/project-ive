"""Ferramentas de arquivo e PDF. Somente leitura."""

import re

from .. import config
from ..registry import ferramenta
from ..seguranca import EXTENSOES_PERMITIDAS, caminho_seguro

# CNPJ com ou sem máscara: 12.345.678/0001-90 ou 12345678000190
RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")


@ferramenta(
    nome="listar_arquivos",
    descricao=(
        "Lista os arquivos disponíveis na pasta de dados, com tamanho em KB. "
        "Use quando o usuário mencionar um arquivo sem dar o nome exato."
    ),
    schema={
        "type": "object",
        "properties": {
            "extensao": {
                "type": "string",
                "description": "Filtro opcional, ex: '.xlsx' ou '.pdf'",
            }
        },
        "required": [],
    },
)
def listar_arquivos(extensao: str = "") -> dict:
    arquivos = []
    for p in sorted(config.DADOS.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in EXTENSOES_PERMITIDAS:
            continue
        if extensao and p.suffix.lower() != extensao.lower():
            continue
        arquivos.append(
            {
                "nome": str(p.relative_to(config.DADOS)),
                "kb": round(p.stat().st_size / 1024, 1),
            }
        )
    return {"pasta": config.DADOS.name, "total": len(arquivos), "arquivos": arquivos}


@ferramenta(
    nome="extrair_texto_pdf",
    descricao=(
        "Extrai o texto de um PDF. Devolve o texto por página (limitado). "
        "Serve para conferir conteúdo de boleto, nota ou guia."
    ),
    schema={
        "type": "object",
        "properties": {
            "caminho": {"type": "string", "description": "Nome do PDF"},
            "max_paginas": {
                "type": "integer",
                "description": "Máximo de páginas a extrair (padrão 3)",
            },
        },
        "required": ["caminho"],
    },
)
def extrair_texto_pdf(caminho: str, max_paginas: int = 3) -> dict:
    import pdfplumber

    alvo = caminho_seguro(caminho)
    paginas = []
    with pdfplumber.open(alvo) as pdf:
        total = len(pdf.pages)
        for pagina in pdf.pages[: max(1, int(max_paginas))]:
            texto = (pagina.extract_text() or "").strip()
            paginas.append(texto[:3000])
    return {"arquivo": caminho, "total_paginas": total, "paginas": paginas}


@ferramenta(
    nome="extrair_cnpj_do_pdf",
    descricao=(
        "Procura CNPJs dentro de um PDF e devolve todos os encontrados, "
        "já normalizados (só dígitos). Esta é a chave forte para casar um PDF "
        "com a linha certa de uma planilha — NUNCA case por posição de linha "
        "ou por nome de arquivo."
    ),
    schema={
        "type": "object",
        "properties": {
            "caminho": {"type": "string", "description": "Nome do PDF"}
        },
        "required": ["caminho"],
    },
)
def extrair_cnpj_do_pdf(caminho: str) -> dict:
    import pdfplumber

    alvo = caminho_seguro(caminho)
    encontrados = []
    with pdfplumber.open(alvo) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            encontrados += [re.sub(r"\D", "", m) for m in RE_CNPJ.findall(texto)]

    unicos = sorted(set(encontrados))
    return {
        "arquivo": caminho,
        "cnpjs": unicos,
        "quantidade": len(unicos),
        # Ambiguidade é dado, não detalhe. O modelo precisa saber disso.
        "aviso": (
            "Nenhum CNPJ encontrado — não é seguro casar este PDF automaticamente."
            if not unicos
            else (
                "Mais de um CNPJ no mesmo PDF (provavelmente beneficiário + pagador). "
                "Confirme com o humano qual é o do cliente antes de casar."
                if len(unicos) > 1
                else "OK: um único CNPJ identificado."
            )
        ),
    }
