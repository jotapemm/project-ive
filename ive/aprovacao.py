"""
Portão de aprovação das ferramentas de escrita.

O `registry` já separa leitura de escrita: `escrita=True` marca a
ferramenta capaz de causar efeito no mundo — tocar música, mandar e-mail,
gravar arquivo. Este arquivo é o que faltava do outro lado da promessa:
quem decide se aquele efeito acontece.

O portão é uma FUNÇÃO INJETADA por quem chama o loop, e não estado
guardado aqui. O motivo é o desenho do resto do sistema: `loop.rodar()` é
síncrono e não guarda contexto entre execuções — "acabou a tarefa, some",
de propósito. Não existe onde parar uma tarefa no meio e esperar alguém
clicar. Então quem sabe como perguntar é quem chamou:

    CLI        pergunta no terminal e espera o enter
    HTTP       não tem humano na frente; exige autorização ANTES, no
               próprio pedido, e nega o que não estiver na lista
    testes     permitem ou negam à vontade, sem nada de verdade rodando

O padrão é `negar_tudo`, e isso não é excesso de zelo: é o que garante
que ESQUECER de passar um portão nunca vire permissão. Um sistema que
falha aberto só avisa que falhou depois que o estrago aconteceu.

O que este portão NÃO é: ele não valida o conteúdo do pedido. Se a
ferramenta recebe um caminho, quem confere o caminho é `seguranca.py`; se
recebe uma URL, quem confere é a ferramenta. Aqui se decide só uma coisa
— isto pode acontecer, sim ou não.
"""

from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True)
class Pedido:
    """O que o modelo quer fazer. Congelado: o portão julga, não altera."""

    ferramenta: str
    entrada: dict = field(default_factory=dict)

    def resumo(self) -> str:
        """Uma linha legível, do jeito que um humano decide olhando."""
        if not self.entrada:
            return self.ferramenta + "()"
        partes = ", ".join(f"{k}={v!r}" for k, v in self.entrada.items())
        return f"{self.ferramenta}({partes})"


@dataclass(frozen=True)
class Decisao:
    aprovado: bool
    motivo: str = ""


#: Assinatura de qualquer portão.
Portao = Callable[[Pedido], Decisao]


def negar_tudo(pedido: Pedido) -> Decisao:
    """O padrão. Nega e explica — a mensagem volta pro modelo."""
    return Decisao(
        False,
        f"'{pedido.ferramenta}' altera o mundo e não foi autorizada nesta "
        "execução. Explique ao usuário o que você faria e peça a ele que "
        "autorize.",
    )


def permitir_tudo(pedido: Pedido) -> Decisao:
    """
    Libera geral.

    Existe para teste e para uso consciente em execução automatizada. Não
    é padrão em lugar nenhum, e não deveria virar: com ele, o cardápio de
    escrita fica do tamanho da imaginação do modelo.
    """
    return Decisao(True)


def permitir_apenas(nomes: Iterable[str]) -> Portao:
    """
    Autorização dada ANTES, por nome de ferramenta.

    É o formato que serve a um cliente sem humano na frente — HTTP, fila,
    agendador: o pedido chega dizendo o que já está autorizado, e o que
    não estiver na lista é negado. A autorização vale para ESTA execução
    e morre com ela, igual ao resto do contexto.
    """
    liberadas = set(nomes)

    def portao(pedido: Pedido) -> Decisao:
        if pedido.ferramenta in liberadas:
            return Decisao(True, "autorizada no pedido")
        return Decisao(
            False,
            f"'{pedido.ferramenta}' altera o mundo e não estava na lista de "
            f"ferramentas autorizadas neste pedido "
            f"({sorted(liberadas) or 'nenhuma'}).",
        )

    return portao


def perguntar_no_terminal(pedido: Pedido) -> Decisao:
    """
    Pergunta e espera. Só serve onde existe um humano no stdin.

    Duas escolhas pequenas que mudam o resultado:

    · A resposta padrão é NÃO. Quem aperta enter distraído está negando,
      não aprovando — o caminho de menor esforço tem que ser o seguro.
    · Sem stdin (rodando em serviço, cron, pipe), a pergunta não trava
      esperando alguém que não existe: nega e diz por quê.
    """
    import sys

    if not sys.stdin or not sys.stdin.isatty():
        return Decisao(False, "Sem terminal interativo para pedir aprovação.")

    print(f"\n  ⚠ O IVE quer executar: {pedido.resumo()}")
    try:
        resposta = input("    Autorizar? [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return Decisao(False, "Aprovação interrompida pelo usuário.")

    if resposta in ("s", "sim", "y", "yes"):
        return Decisao(True, "aprovada no terminal")
    return Decisao(False, "Recusada pelo usuário.")
