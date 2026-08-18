"""Configuração central do IVE."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# --- Motor -------------------------------------------------------------
# Quem pensa. Ver ive/motores/. Trocar isto não muda mais nada no sistema.
#   anthropic = nuvem, paga por token, bem melhor
#   local     = seu PC via Ollama, de graça, mais burro
MOTOR = os.getenv("IVE_MOTOR", "anthropic")

# --- API (motor 'anthropic') -------------------------------------------
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODELO = os.getenv("IVE_MODELO", "claude-sonnet-5")

# --- Ollama (motor 'local') --------------------------------------------
OLLAMA_URL = os.getenv("IVE_OLLAMA_URL", "http://127.0.0.1:11434")
MODELO_LOCAL = os.getenv("IVE_MODELO_LOCAL", "qwen3:4b")

# Raciocínio interno do modelo local (o qwen3 vem com ele LIGADO).
# Numa CPU sem GPU isso domina o tempo: medimos 1372 tokens de saída para
# uma resposta de uma linha. Desligado por padrão — para escolher ferramenta
# num cardápio de seis, o raciocínio longo não estava pagando o custo.
PENSAR_LOCAL = os.getenv("IVE_PENSAR_LOCAL", "0").lower() in ("1", "true", "sim")

# ATENÇÃO: este teto cobre o raciocínio interno do modelo MAIS o texto da
# resposta. Nos modelos atuais o raciocínio é ligado por padrão, então um
# teto apertado corta a resposta no meio (stop_reason == "max_tokens").
# 16000 é a folga recomendada para chamadas sem streaming.
MAX_TOKENS = int(os.getenv("IVE_MAX_TOKENS", "16000"))

# Teto de idas e voltas modelo <-> ferramenta numa única tarefa.
# Protege contra loop infinito (e contra fatura infinita).
MAX_ITERACOES = int(os.getenv("IVE_MAX_ITERACOES", "12"))

# --- Voz (ouvir) -------------------------------------------------------
# Whisper local. O áudio NÃO sai da máquina — ver ive/voz.py.
#   tiny/base  rápidos e imprecisos
#   small      o padrão: português sofre mais que inglês nos modelos
#              pequenos, e transcrição errada de CNPJ custa caro
#   medium     melhor ainda, mas pesado demais pra CPU sem GPU
MODELO_VOZ = os.getenv("IVE_MODELO_VOZ", "small")
IDIOMA_VOZ = os.getenv("IVE_IDIOMA_VOZ", "pt")

# Teto de tamanho do áudio recebido. Push-to-talk gera clipes curtos;
# um arquivo grande aqui é engano ou abuso.
MAX_AUDIO_MB = int(os.getenv("IVE_MAX_AUDIO_MB", "25"))

# --- Voz (falar) -------------------------------------------------------
# Piper: rede neural (VITS) exportada para ONNX, rodando aqui. Bem mais
# natural que a voz do Windows e ainda assim rapida na CPU — o modelo e
# enxuto e o onnxruntime e otimizado.
#
# Vazio = a interface usa a sintese do navegador (voz do Windows) e o
# servidor nem carrega o Piper. E a escolha do usuario, nao do servidor:
# ver o seletor em Personalizar.
VOZ_PIPER = os.getenv("IVE_VOZ_PIPER", "pt_BR-faber-medium")

# Onde ficam os .onnx. NAO e dentro de dados/ — aquilo e a jaula do
# agente, e modelo de voz nao e dado de cliente.
VOZES = Path(os.getenv("IVE_VOZES", RAIZ / "vozes")).resolve()

# Ritmo da fala. No Piper isto e `length_scale`: quanto MAIOR, mais
# devagar (ele estica a duracao de cada fonema). 1.0 = natural.
PIPER_RITMO = float(os.getenv("IVE_PIPER_RITMO", "1.0"))

# --- Diretórios --------------------------------------------------------
# JAULA: o agente só enxerga arquivos dentro de DADOS. Ver ive/seguranca.py.
DADOS = Path(os.getenv("IVE_DADOS", RAIZ / "dados")).resolve()
LOGS = Path(os.getenv("IVE_LOGS", RAIZ / "logs")).resolve()
BANCO = LOGS / "ive.sqlite3"

DADOS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

# --- Personalidade -----------------------------------------------------
PROMPT_SISTEMA = """Você é o IVE, assistente de tarefas digitais de um escritório contábil.

Como você funciona:
- Você NÃO executa nada. Você pede ferramentas, e o sistema executa por você.
- Se a ferramenta que você precisa não está no cardápio, diga isso claramente
  em vez de inventar um jeito de contornar.
- Você não tem memória entre execuções. Cada tarefa começa do zero, de propósito.

Como você responde:
- Português do Brasil, direto, sem enrolação.
- Antes de agir em cima de dados, confira: quantas linhas, quais colunas,
  tem valor faltando? Relate o que encontrou.
- Número que você não leu de uma ferramenta, você não afirma. Nunca chute
  quantidade, valor, CNPJ ou e-mail.
- Se o pedido do usuário for ambíguo em algo que importa (qual arquivo, qual
  coluna, qual período), pergunte antes de sair executando.

Contexto: os dados aqui são de clientes reais — CNPJ, e-mail, valores.
Trate com o cuidado que isso exige."""
