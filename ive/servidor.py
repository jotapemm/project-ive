"""
Servidor HTTP do IVE — a costura entre o Python e a interface.

Duas famílias de rota, e a diferença entre elas é o projeto inteiro:

    POST /executar          passa pelo MODELO. Para intenção vaga:
                            "confere se tem e-mail repetido na de agosto"

    POST /ferramentas/{n}   chama a automação DIRETO, sem IA no meio.
    GET  /historico         Para intenção exata: um botão não precisa de
    GET  /execucoes/{id}    modelo pra ser entendido, e mandar isso pro
                            modelo é mais lento, mais caro e pode errar.

Regra: passa pelo modelo o que precisa de JULGAMENTO. O resto é chamada direta.

O cardápio continua sendo o limite físico — vale igual para as duas famílias.
Ferramenta que não está no registry não é alcançável por rota nenhuma.

Escuta só em 127.0.0.1. Isto NÃO é um servidor de internet: não tem
autenticação, e os dados são de cliente real.
"""

import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config, logdb, motores, registry, voz
from .loop import rodar
from .motores import ErroDeMotor
from .seguranca import CaminhoRecusado
from . import tools  # noqa: F401  (import registra as ferramentas)


@asynccontextmanager
async def _ciclo(_: FastAPI):
    logdb.inicializar()
    yield


app = FastAPI(title="IVE", version="0.2.0", lifespan=_ciclo)

# A UI roda noutra porta durante o desenvolvimento (Vite = 5173).
# Só localhost: nada de "*" aqui, mesmo sendo uso próprio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Pedido(BaseModel):
    texto: str
    usuario: str = "local"
    # Sobrescreve IVE_MOTOR nesta execução — deixa a tela comparar os dois
    # cérebros no mesmo pedido, sem reiniciar nada.
    motor: Optional[str] = None


@app.get("/saude")
def saude() -> dict:
    """
    Estado da instalação. A tela usa isto pra saber o que mostrar.

    'motor_pronto' é falso quando o motor escolhido não está utilizável —
    sem chave, ou Ollama fora do ar. Melhor a tela avisar antes do que o
    usuário descobrir clicando.
    """
    pronto, motivo = True, ""
    try:
        cerebro = motores.escolher()
        descricao = cerebro.descricao
    except ErroDeMotor as e:
        pronto, motivo, descricao = False, str(e), config.MOTOR

    return {
        "ok": True,
        "motor": config.MOTOR,
        "motor_descricao": descricao,
        "motor_pronto": pronto,
        "motor_motivo": motivo,
        "motores": list(motores.MOTORES),
        "modelo": config.MODELO,
        "modelo_local": config.MODELO_LOCAL,
        "tem_chave": bool(config.API_KEY),
        "pasta_dados": str(config.DADOS),
        "ferramentas": registry.listar(),
        "max_iteracoes": config.MAX_ITERACOES,
        # 'voz_carregada' falso só quer dizer que o modelo ainda não subiu
        # pra memória — a primeira transcrição leva alguns segundos a mais.
        "voz_modelo": config.MODELO_VOZ,
        "voz_carregada": voz.pronto(),
    }


# --- família 1: passa pelo modelo --------------------------------------

@app.post("/executar")
def executar(p: Pedido) -> dict:
    """
    O loop do agente, igualzinho ao da CLI. Mesma função, outro chamador.

    O rastro de progresso volta junto em 'trilha' — é o que a CLI imprime
    com o callback ao_vivo. Sem streaming ainda; a resposta vem no fim.
    """
    if not p.texto.strip():
        raise HTTPException(400, "Pedido vazio.")

    trilha: list[str] = []
    try:
        resultado = rodar(p.texto, usuario=p.usuario,
                          ao_vivo=trilha.append, motor=p.motor)
    except ErroDeMotor as e:
        # Motor indisponível: sem chave, ou Ollama fora do ar.
        raise HTTPException(503, str(e))
    return {**resultado, "trilha": trilha}


# --- família 2: chamada direta, sem IA ---------------------------------

@app.get("/ferramentas")
def ferramentas() -> list[dict]:
    return [
        {**spec, "escrita": registry.eh_escrita(spec["name"])}
        for spec in registry.especificacao_para_api()
    ]


@app.post("/ferramentas/{nome}")
def chamar_ferramenta(nome: str, entrada: dict[str, Any]) -> Any:
    """
    Executa uma automação sem passar pelo modelo.

    Mesma função que o agente chamaria, mesma jaula de caminhos, mesmo
    registry. A única diferença é quem escolheu os argumentos: aqui foi
    a interface, não o modelo.
    """
    try:
        return registry.executar(nome, entrada)
    except registry.FerramentaDesconhecida as e:
        raise HTTPException(404, str(e))
    except CaminhoRecusado as e:
        raise HTTPException(403, str(e))
    except TypeError as e:  # argumento faltando ou a mais
        raise HTTPException(400, f"Argumentos inválidos: {e}")


@app.post("/voz/ouvir")
def ouvir(audio: UploadFile = File(...)) -> dict:
    """
    Áudio -> texto, com Whisper rodando aqui na máquina.

    NÃO é `async def` de propósito: transcrever trava a CPU por segundos,
    e o FastAPI joga funções síncronas num pool de threads. Como `async`,
    isto congelaria o servidor inteiro a cada gravação.

    O resultado volta como TEXTO, não como ação. Quem decide o que fazer
    com ele é a interface — e o desenho é mostrar pro humano conferir antes
    de mandar pro agente. Transcrição errada vira ação errada.
    """
    dados = audio.file.read()
    limite = config.MAX_AUDIO_MB * 1024 * 1024
    if not dados:
        raise HTTPException(400, "Áudio vazio.")
    if len(dados) > limite:
        raise HTTPException(
            413, f"Áudio acima de {config.MAX_AUDIO_MB} MB."
        )

    # O Whisper lê de arquivo, então o clipe encosta no disco. Vai pra pasta
    # temporária do sistema — NUNCA pra dados/, que é a jaula do agente — e
    # é apagado no finally, dê no que der.
    sufixo = os.path.splitext(audio.filename or "")[1] or ".webm"
    caminho = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
            tmp.write(dados)
            caminho = tmp.name
        return voz.transcrever(caminho)
    except voz.ErroDeVoz as e:
        raise HTTPException(503, str(e))
    finally:
        if caminho:
            try:
                os.unlink(caminho)
            except OSError:
                pass


@app.get("/historico")
def historico(limite: int = 20) -> list[dict]:
    return logdb.historico(limite)


@app.get("/execucoes/{execucao_id}")
def execucao(execucao_id: int) -> dict:
    detalhe: Optional[dict] = logdb.detalhe(execucao_id)
    if detalhe is None:
        raise HTTPException(404, f"Execução {execucao_id} não existe.")
    return detalhe
