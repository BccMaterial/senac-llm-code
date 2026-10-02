# PARALELIZAÇÃO — vários modelos trabalhando ao mesmo tempo.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# Duas formas, com propósitos diferentes:
#
#   SECTIONING — subtarefas independentes, em paralelo. Ganha TEMPO.
#                (é o que este arquivo faz)
#   VOTING     — a MESMA tarefa várias vezes, com critérios diferentes.
#                Ganha CONFIANÇA.
#
# A condição para usar: as subtarefas não podem depender uma da outra. Aqui a
# piada não precisa do conto, e o conto não precisa do poema — por isso os três
# cabem no mesmo passo. O agregador é quem espera todos.
#
#                          ┌───────┐
#                          │ START │
#                          └───┬───┘
#             ┌────────────────┼────────────────┐
#             ▼                ▼                ▼
#     ┌───────────────┐ ┌─────────────┐ ┌───────────────┐
#     │  gerar_piada  │ │ gerar_conto │ │  gerar_poema  │
#     └───────┬───────┘ └──────┬──────┘ └───────┬───────┘
#             └────────────────┼────────────────┘
#                              ▼
#                      ┌───────────────┐
#                      │    agregar    │
#                      └───────┬───────┘
#                              ▼
#                           ┌─────┐
#                           │ END │
#                           └─────┘

import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")

# -------------------------------------------------------------------- estado

class Estado(TypedDict):
    tema: str
    piada: str
    conto: str
    poema: str
    saida_combinada: str


# ----------------------------------------------------------------------- nós

def gerar_piada(estado: Estado):
    """Primeira chamada: a piada."""
    inicio = time.perf_counter()
    resposta = modelo.invoke(f"Escreva uma piada sobre {estado['tema']}")
    print(f"  [nó] gerar_piada  {time.perf_counter() - inicio:5.1f} s")
    resposta.pretty_print()
    return {"piada": resposta.text}


def gerar_conto(estado: Estado):
    """Segunda chamada: o conto."""
    inicio = time.perf_counter()
    resposta = modelo.invoke(f"Escreva um conto curto sobre {estado['tema']}")
    print(f"  [nó] gerar_conto  {time.perf_counter() - inicio:5.1f} s")
    resposta.pretty_print()
    return {"conto": resposta.text}


def gerar_poema(estado: Estado):
    """Terceira chamada: o poema."""
    inicio = time.perf_counter()
    resposta = modelo.invoke(f"Escreva um poema sobre {estado['tema']}")
    print(f"  [nó] gerar_poema  {time.perf_counter() - inicio:5.1f} s")
    resposta.pretty_print()
    return {"poema": resposta.text}


def agregar(estado: Estado):
    """Junta os três num texto só. Só roda quando os três terminam."""
    combinado = f"Um conto, uma piada e um poema sobre {estado['tema']}.\n\nCONTO:\n{estado['conto']}\n\nPIADA:\n{estado['piada']}\n\nPOEMA:\n{estado['poema']}"
    return {"saida_combinada": combinado}


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("gerar_piada", gerar_piada)
construtor.add_node("gerar_conto", gerar_conto)
construtor.add_node("gerar_poema", gerar_poema)
construtor.add_node("agregar", agregar)

# Três arestas saindo do START: é isto que põe os nós no MESMO passo.
construtor.add_edge(START, "gerar_piada")
construtor.add_edge(START, "gerar_conto")
construtor.add_edge(START, "gerar_poema")

# Três arestas chegando no agregador: ele só roda quando as três terminam.
construtor.add_edge("gerar_piada", "agregar")
construtor.add_edge("gerar_conto", "agregar")
construtor.add_edge("gerar_poema", "agregar")

construtor.add_edge("agregar", END)

paralelo = construtor.compile()


# ------------------------------------------------------------------ execução

inicio = time.perf_counter()
estado = paralelo.invoke({"tema": "gatos"})
total = time.perf_counter() - inicio

# ATENÇÃO ao comparar os tempos: o grafo despacha os três nós no mesmo passo,
# mas quem atende é o servidor do modelo. Com um Ollama local servindo um
# modelo só, as três chamadas entram numa FILA e o total vira a soma — o
# paralelismo do grafo não se converte em ganho nenhum. Contra uma API, que
# atende as três ao mesmo tempo, o total tende ao MAIOR dos três.
print(f"\n  total {total:5.1f} s")
