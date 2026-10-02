# ESTADO + CHECKPOINTER — o que o agente aprende, e por quanto tempo dura.
#
# https://docs.langchain.com/oss/python/langgraph/graph-api#state
# https://docs.langchain.com/oss/python/langgraph/persistence
#
# O usuário conta uma preferência, o modelo decide guardá-la chamando a
# ferramenta `salvar_preferencia`, e o nó de ferramentas grava o par
# chave/valor num campo próprio do Estado: `preferencias`, ao lado das
# mensagens. A partir daí o system prompt é montado com o que está lá.
#
# Ao fim da conversa, o nó `sugerir_pratos` sugere pratos lendo SÓ o campo
# `preferencias` — ele não vê a conversa. É o Estado servindo de memória
# compartilhada entre nós: um escreve, outro lê.
#
# Sem nada mais, o Estado morre com o `invoke`. O `checkpointer` no `compile`
# o grava ao fim de cada execução, por `thread_id`, e o devolve na próxima:
#
#   CHECKPOINTER  guarda o ESTADO de UMA execução, por `thread_id`.
#                 Serve para RETOMAR: a conversa continua de onde parou.
#
# A terceira chamada é a prova do LIMITE: uma thread NOVA começa com o Estado
# vazio. O checkpoint retoma uma conversa; ele não lembra do usuário em outra.
#
#                      ┌───────┐
#                      │ START │ ◄── Estado da thread, lido do checkpoint
#                      └───┬───┘     (e gravado de volta ao fim do `invoke`)
#                          ▼
#                  ┌───────────────┐
#           ┌────► │    agente     │ ──► lê `preferencias` do Estado
#           │      └───────┬───────┘
#           │              ▼
#           │       pediu ferramenta? ── não ───────┐
#           │              │ sim                    │
#           │              ▼                        ▼
#           │      ┌───────────────┐       ┌────────────────┐
#           └───── │no_ferramentas │       │ sugerir_pratos │
#                  └───────────────┘       └────────┬───────┘
#            escreve em `preferencias`              ▼
#                                                ┌─────┐   sugerir_pratos lê
#                                                │ END │   `preferencias` e
#                                                └─────┘   escreve `sugestoes`

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
    sugestoes: str


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


def sugerir_pratos(estado: Estado):
    """Sugere pratos a partir de `preferencias` — sem olhar a conversa."""
    preferencias = estado.get("preferencias", {})
    if not preferencias:
        return {"sugestoes": "(nenhuma preferência no Estado — nada a sugerir)"}
    resposta = modelo.invoke(
        f"Sugira três pratos para alguém com estas preferências: {preferencias}. "
        "Um prato por linha, com uma frase de explicação."
    )
    return {"sugestoes": resposta.text}


def deve_continuar(estado: Estado) -> Literal["no_ferramentas", "sugerir_pratos"]:
    if estado["mensagens"][-1].tool_calls:
        return "no_ferramentas"
    return "sugerir_pratos"


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("agente", agente)
construtor.add_node("no_ferramentas", no_ferramentas)
construtor.add_node("sugerir_pratos", sugerir_pratos)
construtor.add_edge(START, "agente")
construtor.add_conditional_edges("agente", deve_continuar, ["no_ferramentas", "sugerir_pratos"])
construtor.add_edge("no_ferramentas", "agente")
construtor.add_edge("sugerir_pratos", END)

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
    print(f"\n  [estado] sugestoes:\n{saida['sugestoes']}")


# 1. O usuário declara a preferência: o modelo chama a ferramenta, ela vai
#    para o Estado da thread, e `sugerir_pratos` a usa.
falar("Oi! Meu nome é Celso e gosto de churrasco.", thread_1)

# 2. Mesma thread: o CHECKPOINT devolve o Estado — mensagens e `preferencias`.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_1)

# 3. Thread NOVA: o checkpoint dela está vazio. O agente não sabe nada, e
#    não há o que sugerir.
falar("Qual é o meu nome, e do que eu gosto de comer?", thread_2)
