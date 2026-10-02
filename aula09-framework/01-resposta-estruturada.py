# https://docs.langchain.com/oss/python/langchain/structured-output

from langchain.agents import create_agent
from pydantic import BaseModel, Field

from cliente import MODELO, PROVEDOR, modelo


class Contato(BaseModel):
    """Dados de contato de uma pessoa."""

    nome: str = Field(description="O nome da pessoa")
    email: str = Field(description="O endereço de e-mail da pessoa")
    telefone: str = Field(description="O número de telefone da pessoa")


# `response_format` escolhe sozinho a estratégia: decodificação restrita no
# provedor, quando ele oferece, ou uma chamada de ferramenta quando não.
agent = create_agent(model=modelo, response_format=Contato)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Extraia os dados de contato de: João da Silva, joao@exemplo.com.br, (11) 98765-4321"}]}
)

print(f"[{PROVEDOR}:{MODELO}]")
print(result["structured_response"])
# Contato(nome='João da Silva', email='joao@exemplo.com.br', telefone='(11) 98765-4321')
