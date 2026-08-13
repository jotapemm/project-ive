"""
Escolha do motor.

    IVE_MOTOR=anthropic   (padrão)  nuvem, paga por token, bem melhor
    IVE_MOTOR=local                 seu PC via Ollama, de graça, mais burro

Trocar isso não muda nada no resto do sistema: as ferramentas, a jaula de
caminhos, o log de auditoria e a interface continuam idênticos. É essa a
prova de que o cérebro é substituível.
"""

from .. import config
from .base import Chamada, ErroDeMotor, Motor, Resposta

__all__ = ["Chamada", "ErroDeMotor", "Motor", "Resposta", "escolher", "MOTORES"]

MOTORES = ("anthropic", "local")


def escolher(nome: str | None = None) -> Motor:
    nome = (nome or config.MOTOR).strip().lower()

    if nome == "anthropic":
        from .nuvem import MotorNuvem
        return MotorNuvem()

    if nome == "local":
        from .local import MotorLocal
        return MotorLocal()

    raise ErroDeMotor(
        f"Motor '{nome}' não existe. Use um destes: {', '.join(MOTORES)}."
    )
