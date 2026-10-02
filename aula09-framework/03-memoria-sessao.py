from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")

# https://docs.langchain.com/oss/python/langchain/short-term-memory#customizing-agent-memory

def get_user_info() -> str:
    """Consulte informações sobre o usuário atual."""
    return "Nenhum perfil de usuário cadastrado."


agent = create_agent(
    model=modelo,
    tools=[get_user_info],
    checkpointer=InMemorySaver(),
)

# O `thread_id` é o que liga uma chamada à outra: as duas abaixo são a mesma
# conversa. Com outro identificador, o agente começa do zero.
thread_config = {"configurable": {"thread_id": "1"}}

resultado = agent.invoke(
    {"messages": [HumanMessage(content="Oi! Meu nome é Celso.")]},
    thread_config,
)
resultado["messages"][-1].pretty_print()
# "Olá, Celso! Prazer em conhecer você. Como posso ajudar?"

resultado = agent.invoke(
    {"messages": [HumanMessage(content="Qual é o meu nome?")]},
    thread_config,
)
resultado["messages"][-1].pretty_print()
# "Seu nome é Celso!"