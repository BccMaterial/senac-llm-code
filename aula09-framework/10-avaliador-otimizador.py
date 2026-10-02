# AVALIADOR-OTIMIZADOR — um modelo produz, outro julga, e o julgamento volta.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# É o padrão para quando existe CRITÉRIO DE SUCESSO mas o primeiro resultado
# raramente o atende: tradução, redação, código que precisa compilar. O
# avaliador devolve nota e feedback, e o feedback entra no prompt da próxima
# tentativa.
#
# O que a documentação não põe, e a Aula 05 exige: um LIMITE DE VOLTAS. Sem
# ele, um avaliador exigente deixa o grafo girando e gastando para sempre —
# é o orçamento de passos, aqui como um campo no estado.
#
#                       ┌───────┐
#                       │ START │
#                       └───┬───┘
#                           ▼
#                   ┌───────────────┐
#             ┌────►│  gerar_piada  │
#             │     └───────┬───────┘
#             │             ▼
#             │     ┌───────────────┐
#             │     │ avaliar_piada │
#             │     └───────┬───────┘
#             │             │
#             │      rota_da_piada()
#             │      ┌──────┴──────┐
#             │ "rejeitada"     "aceita"  (ou acabaram as voltas)
#             └──────┘             │
#                                  ▼
#                               ┌─────┐
#                               │ END │
#                               └─────┘

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")

MAXIMO_DE_VOLTAS = 3


# ---------------------------------------------------------------- avaliação

class Avaliacao(BaseModel):
    nota: Literal["engraçada", "sem graça"] = Field(description="Decida se a piada tem graça.")
    feedback: str = Field(description="Se a piada não tem graça, diga como melhorá-la.")


avaliador = modelo.with_structured_output(Avaliacao, include_raw=True)


# -------------------------------------------------------------------- estado

class Estado(TypedDict):
    tema: str
    piada: str
    feedback: str
    veredito: str
    voltas: int


# ----------------------------------------------------------------------- nós

def gerar_piada(estado: Estado):
    """Escreve a piada. Da segunda vez em diante, com o feedback em mãos."""
    volta = estado.get("voltas", 0) + 1
    if estado.get("feedback"):
        pedido = f"Escreva uma piada sobre {estado['tema']}, levando em conta esta crítica: {estado['feedback']}"
    else:
        pedido = f"Escreva uma piada sobre {estado['tema']}"
    resposta = modelo.invoke(pedido)
    print(f"  [volta {volta}] piada gerada")
    resposta.pretty_print()
    return {"piada": resposta.text, "voltas": volta}


def avaliar_piada(estado: Estado):
    """Julga a piada e devolve nota e crítica."""
    saida = avaliador.invoke(f"Avalie esta piada: {estado['piada']}")
    avaliacao = saida["parsed"]
    print(f"  [volta {estado['voltas']}] veredito: {avaliacao.nota}")
    saida["raw"].pretty_print()
    return {"veredito": avaliacao.nota, "feedback": avaliacao.feedback}


def rota_da_piada(estado: Estado):
    """A aresta condicional: aceitar, ou devolver com a crítica."""
    if estado["veredito"] == "engraçada":
        return "aceita"
    if estado["voltas"] >= MAXIMO_DE_VOLTAS:
        print(f"  [limite] {MAXIMO_DE_VOLTAS} voltas sem aprovação — parando assim mesmo")
        return "aceita"
    return "rejeitada"


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("gerar_piada", gerar_piada)
construtor.add_node("avaliar_piada", avaliar_piada)

construtor.add_edge(START, "gerar_piada")
construtor.add_edge("gerar_piada", "avaliar_piada")
construtor.add_conditional_edges(
    "avaliar_piada",
    rota_da_piada,
    {  # valor devolvido pela função : nó a visitar
        "aceita": END,
        "rejeitada": "gerar_piada",
    },
)

otimizacao = construtor.compile()


# ------------------------------------------------------------------ execução

estado = otimizacao.invoke({"tema": "gatos"})

print(f"\n(aprovada na volta {estado['voltas']}; última crítica: {estado['feedback']})")
