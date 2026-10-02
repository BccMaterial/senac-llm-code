# O MODELO AUMENTADO — as duas peças sobre as quais todo o resto é montado.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# Nenhuma das duas é um agente. São dois acréscimos ao modelo, e os padrões de
# arquitetura das aulas seguintes são feitos de combinações deles:
#
#   with_structured_output  ->  a saída obedece a um schema
#   bind_tools              ->  a saída pode ser um PEDIDO de chamada

from pydantic import BaseModel, Field

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")


# ----------------------------------------------- 1. aumentado com um schema

class ConsultaDeBusca(BaseModel):
    consulta: str | None = Field(default=None, description="Consulta otimizada para busca na web.")
    justificativa: str | None = Field(default=None, description="Por que esta consulta atende ao pedido do usuário.")


# `include_raw` devolve também a mensagem crua, do jeito que ela saiu do
# modelo — é o que mostra COMO o schema foi obtido.
modelo_estruturado = modelo.with_structured_output(ConsultaDeBusca, include_raw=True)

saida = modelo_estruturado.invoke("Como o escore de cálcio na tomografia se relaciona com colesterol alto?")

print("\n--- 1. com schema")
print("resposta do modelo:")
saida["raw"].pretty_print()
print("objeto validado:", saida["parsed"])
print("erro de validação:", saida["parsing_error"])


# -------------------------------------------- 2. aumentado com ferramentas

def multiplicar(a: int, b: int) -> int:
    """Multiplique `a` por `b`."""
    return a * b


modelo_com_ferramentas = modelo.bind_tools([multiplicar])

# Repare: o modelo NÃO executa nada. Ele devolve um pedido — nome e
# argumentos —, e quem executa é o código. É essa separação que o laço do
# `04-langgraph.py` fecha.
mensagem = modelo_com_ferramentas.invoke("Quanto é 2 vezes 3?")

print("\n--- 2. com ferramentas")
print("resposta do modelo:")
mensagem.pretty_print()
print("pedidos de chamada:", mensagem.tool_calls)
