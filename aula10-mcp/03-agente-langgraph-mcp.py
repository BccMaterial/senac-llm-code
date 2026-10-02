# Aula 10 — 03: O MESMO AGENTE, PELO FRAMEWORK.
#
# https://docs.langchain.com/oss/python/langchain/mcp/index
#
# O `02-agente-com-mcp.py` fala MCP pelo SDK oficial e escreve o laço à mão.
# Este aqui não escreve laço nenhum: o `MultiServerMCPClient` descobre as
# ferramentas do servidor e as devolve já no formato que o `create_agent`
# aceita. A tradução entre o schema MCP e a declaração de ferramenta do
# modelo — que o `mcp_local.py` faz em `declaracao_openai` — some inteira.
#
# O que o aluno deve comparar entre os dois arquivos:
#
#   02  conexão + sessão + listagem + tradução + laço + despacho  = tudo à mão
#   03  um dicionário de configuração e duas chamadas
#
# E o que NÃO muda: a descrição envenenada do servidor continua chegando ao
# modelo exatamente como antes. O framework não inspeciona o que o servidor
# declara — ele confia e repassa. A superfície de ataque da aula é a mesma.
#
#     terminal 1:  python 00-servidor.py
#     terminal 2:  python 03-agente-langgraph-mcp.py

import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from cliente import MODELO, PROVEDOR, modelo

SERVIDORES = {
    "despesas": {
        "url": "http://127.0.0.1:8000/mcp",
        "transport": "streamable_http",
    },
}

PERGUNTA = "A despesa D-1042 respeita a política da categoria dela? Registre o parecer."


async def main():
    cliente_mcp = MultiServerMCPClient(SERVIDORES)

    # Uma chamada de rede: inicializa a sessão, lista as ferramentas e as
    # converte. O que volta já é uma lista de ferramentas do LangChain.
    ferramentas = await cliente_mcp.get_tools()

    print(f"[{PROVEDOR}:{MODELO}]")
    print(f"  [mcp] {len(ferramentas)} ferramentas descobertas:")
    for ferramenta in ferramentas:
        print(f"        {ferramenta.name} — {ferramenta.description.splitlines()[0][:70]}")

    agente = create_agent(model=modelo, tools=ferramentas)

    resultado = await agente.ainvoke({"messages": [{"role": "user", "content": PERGUNTA}]})

    print()
    for mensagem in resultado["messages"]:
        mensagem.pretty_print()


asyncio.run(main())

# O laço continua assíncrono, como no 02 — e pela mesma razão, que NÃO é o
# MCP: o cliente do protocolo é async, então quem o consome também é. O
# framework não resolve isso; ele só move a chamada de lugar.
