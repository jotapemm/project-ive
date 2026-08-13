"""
IVE — interface de linha de comando.

Uso:
    python main.py                          # modo conversa
    python main.py "quantas linhas tem a planilha clientes_agosto?"
    python main.py --ferramentas            # mostra o cardápio
    python main.py --historico              # últimas execuções
"""

import sys

from ive import config, logdb, registry
from ive.loop import ErroDeConfiguracao, rodar

BANNER = r"""
  ___ __     __ ___
 |_ _|\ \   / /| __|   assistente de tarefas digitais
  | |  \ \ / / | _|    v0.1 — cardápio somente leitura
 |___|  \_V_/  |___|
"""


def mostrar_ferramentas() -> None:
    print("\nCardápio de ferramentas:\n")
    for spec in registry.especificacao_para_api():
        marca = "ESCRITA" if registry.eh_escrita(spec["name"]) else "leitura"
        print(f"  [{marca}] {spec['name']}")
        print(f"      {spec['description'].splitlines()[0]}\n")
    print("Se não está nesta lista, o agente não consegue fazer. Por construção.\n")


def mostrar_historico() -> None:
    logdb.inicializar()
    linhas = logdb.historico()
    if not linhas:
        print("\nNenhuma execução registrada ainda.\n")
        return
    print(f"\n{'id':>4}  {'quando':<20} {'status':<14} pedido")
    print("-" * 78)
    for r in linhas:
        print(f"{r['id']:>4}  {r['iniciada_em']:<20} {r['status']:<14} "
              f"{r['pedido'][:34]}")
    print()


def executar(pedido: str) -> None:
    try:
        r = rodar(pedido, ao_vivo=print)
    except ErroDeConfiguracao as e:
        print(f"\n[config] {e}\n")
        sys.exit(1)
    print(f"\n{r['resposta']}\n")
    # cache_leitura alto = o cardápio e o prompt de sistema vieram do cache,
    # a 10% do preço. Se ficar sempre em 0, o cache não está pegando.
    cache = ""
    if r["cache_criacao"] or r["cache_leitura"]:
        cache = f" · cache {r['cache_criacao']}w/{r['cache_leitura']}r"
    print(f"[execução #{r['execucao_id']} · {r['status']} · "
          f"{r['passos']} chamada(s) · "
          f"{r['tokens_in']}↑ {r['tokens_out']}↓ tokens{cache}]\n")


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in ("--ferramentas", "-f"):
        mostrar_ferramentas()
        return
    if args and args[0] in ("--historico", "-h"):
        mostrar_historico()
        return
    if args:
        executar(" ".join(args))
        return

    print(BANNER)
    print(f"Pasta de dados: {config.DADOS}")
    print(f"Ferramentas:    {', '.join(registry.listar())}")
    print("Digite 'sair' para encerrar.\n")

    while True:
        try:
            pedido = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais.")
            return
        if pedido.lower() in ("sair", "exit", "quit"):
            print("Até mais.")
            return
        if not pedido:
            continue
        executar(pedido)


if __name__ == "__main__":
    main()
