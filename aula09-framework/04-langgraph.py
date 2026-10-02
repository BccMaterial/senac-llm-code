# O MESMO laço de agente, agora escrito como grafo — sem `create_agent`.
#
# https://docs.langchain.com/oss/python/langgraph/graph-api
#
#                        ┌───────┐
#                        │ START │
#                        └───┬───┘
#                            ▼
#                   ┌─────────────────┐
#         ┌────────►│  chamar_modelo  │
#         │         └────────┬────────┘
#         │                  │
#         │           deve_continuar()
#         │            ┌─────┴─────┐
#         │            │           │
#         │     pediu ferramenta   não pediu
#         │            │           │
#         │            ▼           ▼
#         │  ┌─────────────────┐ ┌─────┐
#         └──┤  no_ferramentas │ │ END │
#            └─────────────────┘ └─────┘
#
# A aresta de volta é o laço: enquanto o modelo pedir ferramenta, o grafo
# executa e devolve o resultado para ele decidir de novo.

import operator
from typing import Annotated, Literal, TypedDict

from langchain.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph

from cliente import MODELO, PROVEDOR, modelo


# --------------------------------------------------------------- ferramentas

@tool
def multiplicar(a: int, b: int) -> int:
    """Multiplique `a` por `b`.

    Args:
        a: primeiro inteiro
        b: segundo inteiro
    """
    return a * b


@tool
def somar(a: int, b: int) -> int:
    """Some `a` e `b`.

    Args:
        a: primeiro inteiro
        b: segundo inteiro
    """
    return a + b


@tool
def dividir(a: int, b: int) -> float:
    """Divida `a` por `b`.

    Args:
        a: primeiro inteiro
        b: segundo inteiro
    """
    return a / b


ferramentas = [somar, multiplicar, dividir]
ferramentas_por_nome = {f.name: f for f in ferramentas}
modelo_com_ferramentas = modelo.bind_tools(ferramentas)


# --------------------------------------------------------------------- estado

class Estado(TypedDict):
    # O reducer `operator.add` ACUMULA as mensagens. Sem ele, cada nó
    # SUBSTITUIRIA a lista inteira e o agente perderia a conversa.
    mensagens: Annotated[list[AnyMessage], operator.add]


# ----------------------------------------------------------------------- nós

def chamar_modelo(estado: Estado):
    """O modelo decide se chama uma ferramenta ou responde."""
    sistema = SystemMessage(content="Você é um assistente encarregado de fazer contas sobre os números que receber.")
    return {"mensagens": [modelo_com_ferramentas.invoke([sistema] + estado["mensagens"])]}


def no_ferramentas(estado: Estado):
    """Executa as ferramentas que o modelo pediu."""
    resultado = []
    for chamada in estado["mensagens"][-1].tool_calls:
        ferramenta = ferramentas_por_nome[chamada["name"]]
        observacao = ferramenta.invoke(chamada["args"])
        resultado.append(ToolMessage(content=observacao, tool_call_id=chamada["id"]))
    return {"mensagens": resultado}


def deve_continuar(estado: Estado) -> Literal["no_ferramentas", END]:
    """A aresta condicional: continuar o laço ou parar."""
    if estado["mensagens"][-1].tool_calls:
        return "no_ferramentas"
    return END


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("chamar_modelo", chamar_modelo)
construtor.add_node("no_ferramentas", no_ferramentas)

construtor.add_edge(START, "chamar_modelo")
construtor.add_conditional_edges("chamar_modelo", deve_continuar, ["no_ferramentas", END])
construtor.add_edge("no_ferramentas", "chamar_modelo")

agent = construtor.compile()


# ------------------------------------------------------------------ execução

# resultado = agent.invoke({"mensagens": [HumanMessage(content="Some 3 e 4, depois multiplique por 10.")]})

resultado = agent.invoke({"mensagens": [HumanMessage(content="Só quero dizer oi!")]})

print(f"[{PROVEDOR}:{MODELO}]")
for mensagem in resultado["mensagens"]:
    mensagem.pretty_print()
