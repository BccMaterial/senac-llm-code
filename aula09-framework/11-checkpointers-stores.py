# CHECKPOINTER × STORE — as duas memórias do LangGraph, e elas não são a mesma.
#
# https://docs.langchain.com/oss/python/langgraph/persistence
#
#   CHECKPOINTER  guarda o ESTADO de UMA execução, por `thread_id`.
#                 Serve para RETOMAR: a conversa continua de onde parou.
#   STORE         guarda fatos FORA da execução, por namespace.
#                 Serve para LEMBRAR: vale em qualquer thread, inclusive numa
#                 que nunca existiu antes.
#
# É a fronteira da Aula 08, agora como duas classes diferentes. A terceira
# chamada deste arquivo é a prova: ela abre uma thread NOVA — o checkpoint está
# vazio — e mesmo assim o agente sabe o nome, porque leu do store.
#
#                      ┌───────┐
#                      │ START │
#                      └───┬───┘
#                          ▼
#                  ┌───────────────┐
#                  │   conversar   │ ──► lê o store  (o que eu sei do usuário)
#                  │               │ ──► lê o estado (o que foi dito na thread)
#                  │               │ ──► escreve no store
#                  └───────┬───────┘
#                          ▼
#                       ┌─────┐
#                       │ END │
#                       └─────┘

import uuid
from typing import Annotated, TypedDict

from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


class Estado(TypedDict):
    mensagens: Annotated[list[AnyMessage], add_messages]


class Contexto(TypedDict):
    usuario_id: str


def conversar(estado: Estado, runtime: Runtime[Contexto]):
    """Lê a memória de longo prazo, responde, e grava o que foi dito."""
    espaco = ("usuario", runtime.context["usuario_id"])

    lembrancas = [item.value["texto"] for item in runtime.store.search(espaco)]
    if lembrancas:
        print(f"  [store] {len(lembrancas)} lembrança(s): {lembrancas}")
    else:
        print("  [store] vazio")

    sabido = "\n".join(f"- {t}" for t in lembrancas) or "(nada ainda)"
    sistema = SystemMessage(content=f"Você é um assistente. O que você já sabe sobre este usuário:\n{sabido}")

    resposta = modelo.invoke([sistema] + estado["mensagens"])

    # QUEM ESCREVE a memória é o código, não o modelo — a política mais barata
    # e a mais previsível das três que a Aula 08 compara.
    ultima = estado["mensagens"][-1]
    runtime.store.put(espaco, str(uuid.uuid4()), {"texto": ultima.text})

    return {"mensagens": [resposta]}


construtor = StateGraph(Estado, context_schema=Contexto)
construtor.add_node("conversar", conversar)
construtor.add_edge(START, "conversar")
construtor.add_edge("conversar", END)

# As duas memórias são passadas no `compile`, lado a lado e independentes.
grafo = construtor.compile(checkpointer=InMemorySaver(), store=InMemoryStore())


# ------------------------------------------------------------------ execução

contexto = Contexto(usuario_id="celso")
thread_1 = {"configurable": {"thread_id": "conversa-1"}}
thread_2 = {"configurable": {"thread_id": "conversa-2"}}


def falar(texto: str, config: dict):
    print(f"\n> {texto}   ({config['configurable']['thread_id']})")
    saida = grafo.invoke({"mensagens": [HumanMessage(content=texto)]}, config, context=contexto)
    saida["mensagens"][-1].pretty_print()


# 1. Primeira conversa: nada na memória ainda.
falar("Oi! Meu nome é Celso e gosto de churrasco.", thread_1)

# 2. Mesma thread: o CHECKPOINT basta — a pergunta anterior está no estado.
falar("Qual é o meu nome?", thread_1)

# 3. Thread NOVA: o checkpoint está vazio. Se ele acertar, foi o STORE.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_2)
