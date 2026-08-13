"""
Log de auditoria.

O modelo não guarda nada entre execuções — isso é escolha de projeto.
Mas o SISTEMA guarda tudo. São coisas diferentes:

    memória da IA  = contexto que contamina a próxima tarefa   (não queremos)
    log de auditoria = registro de o que foi feito, por quem   (obrigatório)

Sem isso você não responde "esse boleto foi enviado pra quem?" daqui a 3 meses.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciada_em   TEXT NOT NULL,
    encerrada_em  TEXT,
    usuario       TEXT,
    pedido        TEXT NOT NULL,
    resposta      TEXT,
    modelo        TEXT,
    tokens_in     INTEGER DEFAULT 0,
    tokens_out    INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'em_andamento'
);

CREATE TABLE IF NOT EXISTS chamadas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    execucao_id  INTEGER NOT NULL REFERENCES execucoes(id),
    momento      TEXT NOT NULL,
    ferramenta   TEXT NOT NULL,
    entrada      TEXT,
    saida        TEXT,
    erro         TEXT,
    ms           INTEGER
);

CREATE INDEX IF NOT EXISTS idx_chamadas_exec ON chamadas(execucao_id);
"""


def _conectar(caminho: Optional[Path] = None) -> sqlite3.Connection:
    con = sqlite3.connect(caminho or config.BANCO)
    con.row_factory = sqlite3.Row
    return con


# Colunas que entraram depois do banco já existir. CREATE TABLE IF NOT EXISTS
# não mexe em tabela que já está lá, então a adição tem que ser explícita.
_COLUNAS_NOVAS = {
    "cache_criacao": "INTEGER DEFAULT 0",
    "cache_leitura": "INTEGER DEFAULT 0",
}


def inicializar(caminho: Optional[Path] = None) -> None:
    with _conectar(caminho) as con:
        con.executescript(_SCHEMA)
        existentes = {r["name"] for r in con.execute("PRAGMA table_info(execucoes)")}
        for nome, tipo in _COLUNAS_NOVAS.items():
            if nome not in existentes:
                con.execute(f"ALTER TABLE execucoes ADD COLUMN {nome} {tipo}")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _resumir(valor: Any, limite: int = 4000) -> str:
    """Log é pra auditoria, não pra dump. Corta o que for gigante."""
    texto = valor if isinstance(valor, str) else json.dumps(
        valor, ensure_ascii=False, default=str
    )
    if len(texto) > limite:
        return texto[:limite] + f"... [+{len(texto) - limite} chars cortados]"
    return texto


def abrir_execucao(pedido: str, usuario: str = "local",
                   modelo: Optional[str] = None) -> int:
    with _conectar() as con:
        cur = con.execute(
            "INSERT INTO execucoes (iniciada_em, usuario, pedido, modelo) "
            "VALUES (?,?,?,?)",
            (_agora(), usuario, pedido, modelo or config.MODELO),
        )
        return cur.lastrowid


def registrar_chamada(
    execucao_id: int,
    ferramenta: str,
    entrada: Any,
    saida: Any = None,
    erro: Optional[str] = None,
    ms: int = 0,
) -> None:
    with _conectar() as con:
        con.execute(
            "INSERT INTO chamadas "
            "(execucao_id, momento, ferramenta, entrada, saida, erro, ms) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                execucao_id,
                _agora(),
                ferramenta,
                _resumir(entrada),
                _resumir(saida) if saida is not None else None,
                erro,
                ms,
            ),
        )


def fechar_execucao(
    execucao_id: int,
    resposta: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    status: str = "ok",
    cache_criacao: int = 0,
    cache_leitura: int = 0,
) -> None:
    with _conectar() as con:
        con.execute(
            "UPDATE execucoes SET encerrada_em=?, resposta=?, tokens_in=?, "
            "tokens_out=?, status=?, cache_criacao=?, cache_leitura=? WHERE id=?",
            (_agora(), _resumir(resposta), tokens_in, tokens_out, status,
             cache_criacao, cache_leitura, execucao_id),
        )


def historico(limite: int = 20) -> list:
    with _conectar() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, iniciada_em, usuario, pedido, status, "
            "tokens_in, tokens_out FROM execucoes "
            "ORDER BY id DESC LIMIT ?", (limite,)
        )]


def detalhe(execucao_id: int) -> Optional[dict]:
    """
    Uma execução com todas as chamadas de ferramenta que ela fez.

    É isto que responde "esse boleto foi enviado pra quem?" três meses
    depois — o rastro completo, não só a resposta final.
    """
    with _conectar() as con:
        linha = con.execute(
            "SELECT * FROM execucoes WHERE id=?", (execucao_id,)
        ).fetchone()
        if linha is None:
            return None
        chamadas = con.execute(
            "SELECT momento, ferramenta, entrada, saida, erro, ms "
            "FROM chamadas WHERE execucao_id=? ORDER BY id", (execucao_id,)
        )
        return {**dict(linha), "chamadas": [dict(c) for c in chamadas]}
