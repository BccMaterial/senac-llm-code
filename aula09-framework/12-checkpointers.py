# CHECKPOINTER — o Estado sobrevive ao fim do `invoke`, por `thread_id`.
#
# https://docs.langchain.com/oss/python/langgraph/persistence
#
# O mesmo grafo do arquivo anterior, com UMA linha a mais: o `checkpointer`
# no `compile`. Agora cada `invoke` recebe um `thread_id` e o grafo começa do
# Estado em que aquela thread parou — mensagens E `preferencias`.
#
#   CHECKPOINTER  guarda o ESTADO de UMA execução, por `thread_id`.
#                 Serve para RETOMAR: a conversa continua de onde parou.
#
# A terceira chamada é a prova do LIMITE: uma thread NOVA começa com o Estado
# vazio. O checkpoint retoma uma conversa; ele não lembra do usuário em outra.
#
#                      ┌───────┐
#                      │ START │ ◄── Estado da thread, lido do checkpoint
#                      └───┬───┘
#                          ▼
#                  ┌───────────────┐
#           ┌────► │    agente     │ ──► lê `preferencias` do Estado
#           │      └───────┬───────┘
#           │              ▼
#           │       pediu ferramenta? ── não ──► END ──► Estado gravado
#           │              │ sim                         no checkpoint
#           │              ▼
#           │      ┌───────────────┐
#           └───── │no_ferramentas │ ──► escreve em `preferencias`
#                  └───────────────┘

from typing import Annotated, Literal, TypedDict

from langchain.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


# -------------------------------------------------------------------- estado

def juntar(atual: dict, novo: dict) -> dict:
    """Reducer de `preferencias`: a chave nova entra, as antigas ficam."""
    return {**atual, **novo}


class Estado(TypedDict):
    mensagens: Annotated[list[AnyMessage], add_messages]
    preferencias: Annotated[dict[str, str], juntar]


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

def agente(estado: Estado):
    """O modelo responde — ou decide guardar uma preferência."""
    sabido = "\n".join(f"- {k}: {v}" for k, v in estado.get("preferencias", {}).items()) or "(nada ainda)"
    sistema = SystemMessage(
        content=(
            "Você é um assistente. Quando o usuário contar algo sobre si mesmo, "
            "guarde com a ferramenta salvar_preferencia.\n"
            f"O que você já sabe sobre este usuário:\n{sabido}"
        )
    )
    return {"mensagens": [modelo_com_ferramentas.invoke([sistema] + estado["mensagens"])]}


def no_ferramentas(estado: Estado):
    """Executa as chamadas pedidas e grava as preferências no Estado."""
    mensagens, preferencias = [], {}
    for chamada in estado["mensagens"][-1].tool_calls:
        observacao = ferramentas_por_nome[chamada["name"]].invoke(chamada["args"])
        preferencias[chamada["args"]["chave"]] = chamada["args"]["valor"]
        mensagens.append(ToolMessage(content=observacao, tool_call_id=chamada["id"]))
    return {"mensagens": mensagens, "preferencias": preferencias}


def deve_continuar(estado: Estado) -> Literal["no_ferramentas", END]:
    if estado["mensagens"][-1].tool_calls:
        return "no_ferramentas"
    return END


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("agente", agente)
construtor.add_node("no_ferramentas", no_ferramentas)
construtor.add_edge(START, "agente")
construtor.add_conditional_edges("agente", deve_continuar, ["no_ferramentas", END])
construtor.add_edge("no_ferramentas", "agente")

grafo = construtor.compile(checkpointer=InMemorySaver())


# ------------------------------------------------------------------ execução

thread_1 = {"configurable": {"thread_id": "conversa-1"}}
thread_2 = {"configurable": {"thread_id": "conversa-2"}}


def falar(texto: str, config: dict):
    print(f"\n> {texto}   ({config['configurable']['thread_id']})")
    saida = grafo.invoke({"mensagens": [HumanMessage(content=texto)], "preferencias": {}}, config)
    # Só as mensagens deste turno: as que vêm depois da última fala do usuário.
    inicio = max(i for i, m in enumerate(saida["mensagens"]) if m.type == "human")
    for mensagem in saida["mensagens"][inicio + 1:]:
        mensagem.pretty_print()
    print(f"\n  [estado] preferencias = {saida['preferencias']}")


# 1. O usuário declara a preferência, e ela vai para o Estado da thread.
falar("Oi! Meu nome é Celso e gosto de churrasco.", thread_1)

# 2. Mesma thread: o CHECKPOINT devolve o Estado — mensagens e `preferencias`.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_1)

# 3. Thread NOVA: o checkpoint dela está vazio, e o agente não sabe nada.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_2)
