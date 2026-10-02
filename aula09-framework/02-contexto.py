from typing import TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.messages import HumanMessage

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


class Contexto(TypedDict):
    nome_do_usuario: str


def get_weather(city: str) -> str:
    """Pegue a temperatura em uma cidade."""
    return f"Está ensolarado em {city}!"


# O system prompt deixa de ser texto fixo e passa a ser calculado a cada
# chamada, a partir do contexto que veio no `invoke`.
@dynamic_prompt
def prompt_dinamico(request: ModelRequest) -> str:
    nome = request.runtime.context["nome_do_usuario"]
    return f"Aja como um assistente. Trate o usuário por {nome}."


agent = create_agent(
    model=modelo,
    tools=[get_weather],
    middleware=[prompt_dinamico],
    context_schema=Contexto,
)

result = agent.invoke(
    {"messages": [HumanMessage(content="Como está o tempo em São Paulo?")]},
    context=Contexto(nome_do_usuario="Celso"),
)

for msg in result["messages"]:
    msg.pretty_print()
