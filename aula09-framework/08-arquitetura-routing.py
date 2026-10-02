# ROUTING — uma entrada, vários caminhos, e o MODELO escolhe qual.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# A diferença para o `06-arquitetura-sequencia.py` está em quem decide. Lá o
# portão era código — um `if` procurando "?" ou "!". Aqui a decisão é uma
# chamada ao modelo com saída estruturada, e o schema é o que impede a rota de
# ser texto livre: `Literal` restringe a resposta a três valores, e qualquer
# outro vira erro de validação em vez de nó inexistente.
#
# É o Router da Aula 05. A regra de lá continua valendo: use o degrau mais
# barato que resolve — regra, depois embedding, e só então modelo.
#
#                          ┌───────┐
#                          │ START │
#                          └───┬───┘
#                              ▼
#                      ┌───────────────┐
#                      │   roteador    │  <- o modelo decide
#                      └───────┬───────┘
#                              │
#                       rota_escolhida()
#             ┌────────────────┼────────────────┐
#          "conto"          "piada"          "poema"
#             ▼                ▼                ▼
#   ┌─────────────────┐ ┌──────────────┐ ┌───────────────┐
#   │ escrever_conto  │ │escrever_piada│ │escrever_poema │
#   └────────┬────────┘ └──────┬───────┘ └───────┬───────┘
#            └─────────────────┼─────────────────┘
#                              ▼
#                           ┌─────┐
#                           │ END │
#                           └─────┘

from typing import Literal, TypedDict

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from cliente import MODELO, PROVEDOR, modelo


# ------------------------------------------------------------------- a rota

class Rota(BaseModel):
    passo: Literal["conto", "piada", "poema"] = Field(description="O próximo passo do roteamento.")


roteador_do_modelo = modelo.with_structured_output(Rota)


# -------------------------------------------------------------------- estado

class Estado(TypedDict):
    entrada: str
    decisao: str
    saida: str


# ----------------------------------------------------------------------- nós

def roteador(estado: Estado):
    """Decide para onde a entrada vai."""
    decisao = roteador_do_modelo.invoke(
        [
            SystemMessage(content="Classifique o pedido do usuário em conto, piada ou poema."),
            HumanMessage(content=estado["entrada"]),
        ]
    )
    return {"decisao": decisao.passo}


def escrever_conto(estado: Estado):
    """Escreve um conto."""
    resposta = modelo.invoke(f"Escreva um conto curto atendendo a este pedido: {estado['entrada']}")
    return {"saida": resposta.text}


def escrever_piada(estado: Estado):
    """Escreve uma piada."""
    resposta = modelo.invoke(f"Escreva uma piada atendendo a este pedido: {estado['entrada']}")
    return {"saida": resposta.text}


def escrever_poema(estado: Estado):
    """Escreve um poema."""
    resposta = modelo.invoke(f"Escreva um poema atendendo a este pedido: {estado['entrada']}")
    return {"saida": resposta.text}


def rota_escolhida(estado: Estado):
    """A aresta condicional: devolve a chave do caminho a seguir."""
    return estado["decisao"]


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("roteador", roteador)
construtor.add_node("escrever_conto", escrever_conto)
construtor.add_node("escrever_piada", escrever_piada)
construtor.add_node("escrever_poema", escrever_poema)

construtor.add_edge(START, "roteador")
construtor.add_conditional_edges(
    "roteador",
    rota_escolhida,
    {  # valor devolvido pela função : nó a visitar
        "conto": "escrever_conto",
        "piada": "escrever_piada",
        "poema": "escrever_poema",
    },
)
construtor.add_edge("escrever_conto", END)
construtor.add_edge("escrever_piada", END)
construtor.add_edge("escrever_poema", END)

roteamento = construtor.compile()


# ------------------------------------------------------------------ execução

print(f"[{PROVEDOR}:{MODELO}]")

estado = roteamento.invoke({"entrada": "Me escreva uma piada sobre gatos"})

print(f"  [rota] {estado['decisao']}\n")
print(estado["saida"])
