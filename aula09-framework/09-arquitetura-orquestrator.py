# ORQUESTRADOR-TRABALHADOR — o número de trabalhadores só se sabe rodando.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# A diferença para o `07-arquitetura-paralelizacao.py` é essa: lá os três nós
# estavam escritos no grafo, um a um. Aqui o orquestrador decide QUANTAS
# subtarefas existem, e o `Send` cria um trabalhador para cada uma na hora da
# execução. O grafo tem um nó de trabalhador só; quantas cópias dele rodam é
# decisão de runtime.
#
# É o padrão para quando as subtarefas não podem ser previstas — escrever um
# relatório de N seções, alterar M arquivos, consultar K fontes.
#
#                          ┌───────┐
#                          │ START │
#                          └───┬───┘
#                              ▼
#                      ┌───────────────┐
#                      │  orquestrador │  <- planeja as seções
#                      └───────┬───────┘
#                              │
#                   distribuir_trabalhadores()
#                      Send × quantas seções
#             ┌────────────────┼────────────────┐
#             ▼                ▼                ▼
#     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
#     │ trabalhador  │ │ trabalhador  │ │ trabalhador  │   (o MESMO nó)
#     └───────┬──────┘ └──────┬───────┘ └───────┬──────┘
#             └────────────────┼────────────────┘
#                              ▼
#                      ┌───────────────┐
#                      │  sintetizador │
#                      └───────┬───────┘
#                              ▼
#                           ┌─────┐
#                           │ END │
#                           └─────┘

import operator
from typing import Annotated, TypedDict

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


# ------------------------------------------------------------------ o plano

class Secao(BaseModel):
    nome: str = Field(description="Nome desta seção do relatório.")
    descricao: str = Field(description="Resumo dos assuntos e conceitos que a seção vai cobrir.")


class Secoes(BaseModel):
    secoes: list[Secao] = Field(description="As seções do relatório.")


planejador = modelo.with_structured_output(Secoes, include_raw=True)


# -------------------------------------------------------------------- estado

class Estado(TypedDict):
    tema: str
    secoes: list[Secao]
    # `operator.add` ACUMULA: cada trabalhador devolve uma lista de um item, e
    # o reducer junta todas. Sem ele, o último a terminar apagaria os outros.
    secoes_prontas: Annotated[list, operator.add]
    relatorio_final: str


class EstadoDoTrabalhador(TypedDict):
    """O estado que cada trabalhador recebe: a SUA seção, e mais nada."""

    secao: Secao
    secoes_prontas: Annotated[list, operator.add]


# ----------------------------------------------------------------------- nós

def orquestrador(estado: Estado):
    """Planeja o relatório: decide quais seções existem."""
    saida = planejador.invoke(
        [
            SystemMessage(content="Monte o plano de um relatório, dividido em seções."),
            HumanMessage(content=f"O tema do relatório é: {estado['tema']}"),
        ]
    )
    plano = saida["parsed"]
    print(f"\n  [orquestrador] {len(plano.secoes)} seções planejadas")
    saida["raw"].pretty_print()
    return {"secoes": plano.secoes}


def trabalhador(estado: EstadoDoTrabalhador):
    """Escreve UMA seção. Roda uma vez por seção planejada."""
    secao = modelo.invoke(
        [
            SystemMessage(content="Escreva a seção do relatório seguindo o nome e a descrição recebidos. Sem preâmbulo, em markdown."),
            HumanMessage(content=f"Nome da seção: {estado['secao'].nome}. Descrição: {estado['secao'].descricao}"),
        ]
    )
    print(f"\n  [trabalhador] pronto: {estado['secao'].nome}")
    secao.pretty_print()
    return {"secoes_prontas": [secao.text]}


def sintetizador(estado: Estado):
    """Junta as seções na ordem em que chegaram."""
    return {"relatorio_final": "\n\n---\n\n".join(estado["secoes_prontas"])}


def distribuir_trabalhadores(estado: Estado):
    """A aresta condicional que CRIA um trabalhador por seção."""
    return [Send("trabalhador", {"secao": secao}) for secao in estado["secoes"]]


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("orquestrador", orquestrador)
construtor.add_node("trabalhador", trabalhador)
construtor.add_node("sintetizador", sintetizador)

construtor.add_edge(START, "orquestrador")
construtor.add_conditional_edges("orquestrador", distribuir_trabalhadores, ["trabalhador"])
construtor.add_edge("trabalhador", "sintetizador")
construtor.add_edge("sintetizador", END)

orquestracao = construtor.compile()


# ------------------------------------------------------------------ execução

estado = orquestracao.invoke({"tema": "Escalonamento de processos em sistemas operacionais"})
