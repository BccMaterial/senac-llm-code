# STORE — o que o agente sabe do usuário, fora de qualquer thread.
#
# https://docs.langchain.com/oss/python/langgraph/persistence
#
# O mesmo grafo do arquivo anterior, com o `store` ao lado do checkpointer no
# `compile`. O nó de ferramentas passa a gravar a preferência TAMBÉM no store,
# no namespace do usuário, e o agente monta o system prompt lendo de lá.
#
#   CHECKPOINTER  guarda o ESTADO de UMA execução, por `thread_id`.
#                 Serve para RETOMAR: a conversa continua de onde parou.
#   STORE         guarda fatos FORA da execução, por namespace.
#                 Serve para LEMBRAR: vale em qualquer thread, inclusive numa
#                 que nunca existiu antes.
#
# É a fronteira da Aula 08, agora como duas classes diferentes. A terceira
# chamada é a prova: ela abre uma thread NOVA — o checkpoint está vazio — e
# mesmo assim o agente sabe o nome, porque leu do store.
#
#                      ┌───────┐
#                      │ START │ ◄── Estado da thread, lido do checkpoint
#                      └───┬───┘
#                          ▼
#                  ┌───────────────┐
#           ┌────► │    agente     │ ──► lê o STORE (o que eu sei do usuário)
#           │      └───────┬───────┘
#           │              ▼
#           │       pediu ferramenta? ── não ──► END ──► Estado gravado
#           │              │ sim                         no checkpoint
#           │              ▼
#           │      ┌───────────────┐
#           └───── │no_ferramentas │ ──► escreve em `preferencias` E no STORE
#                  └───────────────┘

from typing import Annotated, Literal, TypedDict

from langchain.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


# -------------------------------------------------------------------- estado

def juntar(atual: dict, novo: dict) -> dict:
    """Reducer de `preferencias`: a chave nova entra, as antigas ficam."""
    return {**atual, **novo}


class Estado(TypedDict):
    mensagens: Annotated[list[AnyMessage], add_messages]
    preferencias: Annotated[dict[str, str], juntar]


class Contexto(TypedDict):
    usuario_id: str


# --------------------------------------------------------------- ferramenta

@tool
def salvar_preferencia(chave: str, valor: str) -> str:
    """Guarde uma preferência que o usuário declarou sobre si mesmo.

    Args:
        chave: o assunto da preferência, curto e em minúsculas (ex: "nome", "comida")
        valor: o que o usuário disse sobre esse assunto
    """
    # O corpo não grava nada: quem escreve no Estado é o nó de ferramentas,
    # que é o único lugar do grafo que devolve atualizações de estado.
    return f"Preferência guardada: {chave} = {valor}"


ferramentas_por_nome = {salvar_preferencia.name: salvar_preferencia}
modelo_com_ferramentas = modelo.bind_tools([salvar_preferencia])


# ----------------------------------------------------------------------- nós

def agente(estado: Estado, runtime: Runtime[Contexto]):
    """O modelo responde — ou decide guardar uma preferência."""
    espaco = ("usuario", runtime.context["usuario_id"])
    lembrancas = {item.key: item.value["valor"] for item in runtime.store.search(espaco)}
    print(f"  [store] {lembrancas or 'vazio'}")

    sabido = "\n".join(f"- {k}: {v}" for k, v in lembrancas.items()) or "(nada ainda)"
    sistema = SystemMessage(
        content=(
            "Você é um assistente. Quando o usuário contar algo sobre si mesmo, "
            "guarde com a ferramenta salvar_preferencia.\n"
            f"O que você já sabe sobre este usuário:\n{sabido}"
        )
    )
    return {"mensagens": [modelo_com_ferramentas.invoke([sistema] + estado["mensagens"])]}


def no_ferramentas(estado: Estado, runtime: Runtime[Contexto]):
    """Executa as chamadas pedidas e grava as preferências no Estado e no store."""
    espaco = ("usuario", runtime.context["usuario_id"])
    mensagens, preferencias = [], {}
    for chamada in estado["mensagens"][-1].tool_calls:
        observacao = ferramentas_por_nome[chamada["name"]].invoke(chamada["args"])
        preferencias[chamada["args"]["chave"]] = chamada["args"]["valor"]
        # A chave da preferência é a chave do item: dizer de novo SUBSTITUI.
        runtime.store.put(espaco, chamada["args"]["chave"], {"valor": chamada["args"]["valor"]})
        mensagens.append(ToolMessage(content=observacao, tool_call_id=chamada["id"]))
    return {"mensagens": mensagens, "preferencias": preferencias}


def deve_continuar(estado: Estado) -> Literal["no_ferramentas", END]:
    if estado["mensagens"][-1].tool_calls:
        return "no_ferramentas"
    return END


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado, context_schema=Contexto)
construtor.add_node("agente", agente)
construtor.add_node("no_ferramentas", no_ferramentas)
construtor.add_edge(START, "agente")
construtor.add_conditional_edges("agente", deve_continuar, ["no_ferramentas", END])
construtor.add_edge("no_ferramentas", "agente")

# As duas memórias são passadas no `compile`, lado a lado e independentes.
grafo = construtor.compile(checkpointer=InMemorySaver(), store=InMemoryStore())


# ------------------------------------------------------------------ execução

contexto = Contexto(usuario_id="celso")
thread_1 = {"configurable": {"thread_id": "conversa-1"}}
thread_2 = {"configurable": {"thread_id": "conversa-2"}}


def falar(texto: str, config: dict):
    print(f"\n> {texto}   ({config['configurable']['thread_id']})")
    saida = grafo.invoke({"mensagens": [HumanMessage(content=texto)], "preferencias": {}}, config, context=contexto)
    # Só as mensagens deste turno: as que vêm depois da última fala do usuário.
    inicio = max(i for i, m in enumerate(saida["mensagens"]) if m.type == "human")
    for mensagem in saida["mensagens"][inicio + 1:]:
        mensagem.pretty_print()
    print(f"\n  [estado] preferencias = {saida['preferencias']}")


# 1. O usuário declara a preferência: ela vai para o Estado da thread E para o
#    store, no namespace do usuário.
falar("Oi! Meu nome é Celso e gosto de churrasco.", thread_1)

# 2. Mesma thread: o CHECKPOINT basta — a pergunta anterior está no Estado.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_1)

# 3. Thread NOVA: o Estado começa vazio. Se ele acertar, foi o STORE.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_2)
