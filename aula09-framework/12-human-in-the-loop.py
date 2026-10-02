# HUMAN-IN-THE-LOOP — o grafo para no meio e espera uma pessoa.
#
# https://docs.langchain.com/oss/python/langgraph/interrupts
#
# `interrupt()` suspende a execução DENTRO de um nó, devolve um valor a quem
# chamou e espera. A retomada é um novo `invoke`, com `Command(resume=...)`, e
# o valor passado vira o retorno do `interrupt()` lá dentro — a função continua
# da linha seguinte, como se nunca tivesse parado.
#
# O que torna isso possível é o CHECKPOINTER: a pausa é um checkpoint gravado.
# Por isso aqui ele é `SqliteSaver`, com arquivo em disco — o programa pode
# morrer entre a pergunta e a resposta que a aprovação continua pendente.
#
# A ferramenta escolhida não é por acaso: mandar e-mail é a primeira ação com
# EFEITO COLATERAL do laboratório. Até aqui tudo era leitura.
#
#                      ┌───────┐
#                      │ START │
#                      └───┬───┘
#                          ▼
#                  ┌───────────────┐
#            ┌────►│    agente     │
#            │     └───────┬───────┘
#            │      deve_continuar()
#            │      ┌──────┴──────┐
#            │   pediu          não pediu
#            │   ferramenta     ferramenta
#            │      │               │
#            │      ▼               ▼
#            │ ┌───────────────┐ ┌─────┐
#            └─┤ no_ferramentas│ │ END │
#              │  interrupt()  │ └─────┘
#              └───────────────┘

import operator
import sqlite3
from typing import Annotated, Literal, TypedDict

from langchain.messages import AnyMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from cliente import MODELO, PROVEDOR, modelo


class Estado(TypedDict):
    mensagens: Annotated[list[AnyMessage], operator.add]


@tool
def enviar_email(para: str, assunto: str, corpo: str) -> str:
    """Envie um e-mail para um destinatário.

    Args:
        para: endereço do destinatário
        assunto: assunto do e-mail
        corpo: texto do e-mail
    """
    # A execução PARA aqui. O dicionário abaixo é o que chega a quem chamou.
    decisao = interrupt(
        {
            "acao": "enviar_email",
            "para": para,
            "assunto": assunto,
            "corpo": corpo,
            "pergunta": "Aprova o envio deste e-mail?",
        }
    )

    # Daqui para baixo só roda DEPOIS do Command(resume=...).
    if decisao.get("acao") != "aprovar":
        return "Envio cancelado pelo usuário."

    # A aprovação pode vir com correções — é a diferença entre aprovar e
    # aprovar-editando.
    para = decisao.get("para", para)
    assunto = decisao.get("assunto", assunto)
    corpo = decisao.get("corpo", corpo)

    print(f"  [enviado] para={para} assunto={assunto!r}")
    return f"E-mail enviado para {para}."


ferramentas = [enviar_email]
ferramentas_por_nome = {f.name: f for f in ferramentas}
modelo_com_ferramentas = modelo.bind_tools(ferramentas)


def agente(estado: Estado):
    """O modelo decide se chama a ferramenta ou responde."""
    return {"mensagens": [modelo_com_ferramentas.invoke(estado["mensagens"])]}


def no_ferramentas(estado: Estado):
    """Executa as ferramentas pedidas — e é aqui que o interrupt acontece."""
    resultado = []
    for chamada in estado["mensagens"][-1].tool_calls:
        ferramenta = ferramentas_por_nome[chamada["name"]]
        observacao = ferramenta.invoke(chamada["args"])
        resultado.append(ToolMessage(content=observacao, tool_call_id=chamada["id"]))
    return {"mensagens": resultado}


def deve_continuar(estado: Estado) -> Literal["no_ferramentas", END]:
    if estado["mensagens"][-1].tool_calls:
        return "no_ferramentas"
    return END


construtor = StateGraph(Estado)
construtor.add_node("agente", agente)
construtor.add_node("no_ferramentas", no_ferramentas)
construtor.add_edge(START, "agente")
construtor.add_conditional_edges("agente", deve_continuar, ["no_ferramentas", END])
construtor.add_edge("no_ferramentas", "agente")

# Checkpointer em ARQUIVO: a aprovação pendente sobrevive ao fim do processo.
checkpointer = SqliteSaver(sqlite3.connect("aprovacao-de-email.db", check_same_thread=False))
grafo = construtor.compile(checkpointer=checkpointer)


# ------------------------------------------------------------------ execução

print(f"[{PROVEDOR}:{MODELO}]")

config = {"configurable": {"thread_id": "email-01"}}

# 1. Primeira chamada: o grafo roda até o interrupt e devolve o pedido.
saida = grafo.invoke(
    {"mensagens": [{"role": "user", "content": "Mande um e-mail para alice@exemplo.com.br sobre a reunião de amanhã."}]},
    config,
)

pendente = saida["__interrupt__"][0].value
print("\n  APROVAÇÃO NECESSÁRIA")
for chave, valor in pendente.items():
    print(f"    {chave}: {valor}")

# 2. Retomada: o valor abaixo vira o retorno do `interrupt()` dentro da
#    ferramenta, que continua de onde parou. Aqui a pessoa aprova E corrige o
#    assunto — trocar por {"acao": "cancelar"} mostra o outro caminho.
saida = grafo.invoke(
    Command(resume={"acao": "aprovar", "assunto": "Reunião de amanhã — confirmando"}),
    config,
)

print(f"\n{saida['mensagens'][-1].text}")
