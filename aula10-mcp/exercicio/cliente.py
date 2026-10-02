# Cliente LangGraph para o servidor BrasilAPI do exercício MCP.
#
# Execute primeiro, em outro terminal:
#     python exercicio/exercicio-mcp.py
# Depois, a partir da pasta aula10-mcp:
#     python 04-cliente-exercicio-mcp.py

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from cliente import MODELO, PROVEDOR, modelo

URL = "http://127.0.0.1:8001/mcp"


def declaracoes_do_servidor(resposta) -> list[dict]:
    """Converte as ferramentas MCP para o schema aceito por bind_tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": ferramenta.name,
                "description": ferramenta.description or "",
                "parameters": ferramenta.inputSchema or {"type": "object"},
            },
        }
        for ferramenta in resposta.tools
    ]


def texto_do_retorno(resultado) -> str:
    """Extrai os blocos de texto devolvidos pela ferramenta MCP."""
    return "\n".join(
        bloco.text for bloco in resultado.content
        if getattr(bloco, "text", None)
    )


async def consultar(sessao: ClientSession, declaracao: dict,
                    titulo: str, prompt: str) -> None:
    """Executa um prompt com apenas a ferramenta adequada disponível."""
    print(f"\n{'=' * 12} {titulo} {'=' * 12}")
    mensagens = [
        {
            "role": "system",
            "content": (
                "Responda em português e use a ferramenta disponível para "
                "consultar os dados. Não invente valores; se houver erro, "
                "explique o erro retornado pela ferramenta."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    for _ in range(5):
        resposta = modelo.bind_tools([declaracao], temperature=0).invoke(mensagens)
        mensagens.append(resposta)
        if not resposta.tool_calls:
            resposta.pretty_print()
            return

        for chamada in resposta.tool_calls:
            resultado = await sessao.call_tool(
                chamada["name"], arguments=chamada["args"]
            )
            mensagens.append({
                "role": "tool",
                "tool_call_id": chamada["id"],
                "content": texto_do_retorno(resultado),
            })

    print("O limite de chamadas da ferramenta foi atingido sem resposta final.")


async def main() -> None:
    print(f"[{PROVEDOR}:{MODELO}]")
    cnpj = input("CNPJ para consultar (14 dígitos, com ou sem máscara): ").strip()
    cep = input("CEP para consultar (8 dígitos, com ou sem máscara): ").strip()
    async with streamable_http_client(URL) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            declaracoes = declaracoes_do_servidor(await sessao.list_tools())
            por_nome = {
                declaracao["function"]["name"]: declaracao
                for declaracao in declaracoes
            }

            for nome in ("consultar_cnpj", "consultar_cep"):
                if nome not in por_nome:
                    raise RuntimeError(
                        f"O servidor não publicou a ferramenta {nome!r}."
                    )

            await consultar(
                sessao,
                por_nome["consultar_cnpj"],
                "CONSULTA DE CNPJ",
                "Consulte este CNPJ e apresente os dados cadastrais retornados: "
                f"{cnpj}. Não tente obter coordenadas.",
            )
            await consultar(
                sessao,
                por_nome["consultar_cep"],
                "CONSULTA DE CEP",
                "Consulte este CEP e apresente o endereço e as coordenadas "
                f"retornados: {cep}. A consulta é pelo CEP, não pelo nome da rua.",
            )


if __name__ == "__main__":
    asyncio.run(main())
