from langchain.agents import create_agent
from langchain.tools import tool

from cliente import MODELO, PROVEDOR, modelo


@tool
def get_weather(cidade: str) -> str:
    """Pegue a temperatura em uma cidade.

    Args:
        cidade: O nome da cidade
    """
    return f"Está ensolarado em {cidade}!"


agent = create_agent(
    model=modelo,
    tools=[get_weather],
    system_prompt="Aja como um assistente",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Como está o tempo na cidade de São Paulo?"}]}
)

print(f"[{PROVEDOR}:{MODELO}]")
print(result["messages"][-1].text)
