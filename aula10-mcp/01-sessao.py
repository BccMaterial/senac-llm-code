# Aula 10 — 01: A SESSÃO MCP, SEM BIBLIOTECA.
#
# DEMONSTRAÇÃO CONCEITUAL, declarada no plano.md desta aula. Os demais
# scripts da pasta são caso de uso; este não é. A razão é que o protocolo
# desaparece atrás de uma biblioteca já no arquivo seguinte, como a aula 09
# o reduziu a uma chamada com `langchain.mcp` — e uma abstração que nunca
# foi aberta não pode ser diagnosticada quando falha.
#
# Exige o servidor no ar, em outro terminal:
#     python 00-servidor.py      # naquele terminal
#     python 01-sessao.py        # neste

import json

from mcp_local import PROTOCOLO, SessaoMCP

print("=" * 74)
print("UMA SESSÃO MCP INTEIRA, EM JSON-RPC CRU")
print("=" * 74)
print(f"""
  transporte ...... Streamable HTTP (processo à parte, em 127.0.0.1:8000)
  protocolo ....... JSON-RPC 2.0
  revisão ......... {PROTOCOLO}

  cliente                                    servidor
     |-- initialize --------------------------->|   versão e capacidades
     |<------------------- capacidades ---------|
     |-- notifications/initialized ------------>|
     |                                          |
     |-- tools/list ---------------------------->|
     |<---------- [ {{name, description,          |
     |               inputSchema}}, ... ] --------|
     |                                          |
     |-- tools/call {{name, arguments}} --------->|
     |<--------------------- content ------------|
     |                                          |
     |-- DELETE (Mcp-Session-Id) --------------->|   encerra a SESSÃO
     |                                          |   (o servidor continua)
""")

# O servidor NÃO é iniciado aqui: ele já está no ar, no terminal dele,
# e esta sessão apenas se conecta. É o transporte Streamable HTTP da
# nota 01, §2 — e a razão de o servidor ser o `00`.
with SessaoMCP(nome="despesas") as sessao:

    # ------------------------------------------------------- 1. handshake
    # Já aconteceu dentro do `with`: o __enter__ da SessaoMCP faz o
    # initialize e a notificação. O que o servidor declarou:
    print("=" * 74)
    print("1 — O QUE O SERVIDOR DECLAROU NO handshake")
    print("=" * 74)
    print(json.dumps(sessao.capacidades, indent=2, ensure_ascii=False))
    print("""
  A negociação existe porque as duas pontas evoluem separadamente. O que
  não for declarado aqui NÃO PODE ser usado depois — é contrato explícito,
  a mesma disciplina da saída estruturada da aula 03.
""")

    # ---------------------------------------------------- 2. tools/list
    print("=" * 74)
    print("2 — tools/list: DE ONDE VEM A DECLARAÇÃO")
    print("=" * 74)
    ferramentas = sessao.listar_ferramentas()
    for f in ferramentas:
        print(f"\n  {f['name']}")
        print(f"    description: {f.get('description', '').strip().splitlines()[0]}")
        props = f.get("inputSchema", {}).get("properties", {})
        print(f"    inputSchema: {list(props)}")
    print(f"""
  {len(ferramentas)} ferramentas.

  O FORMATO é name, description, inputSchema — o mesmo que a aula 03
  escrevia à mão. O protocolo não alterou a estrutura da declaração:
  padronizou a origem dela.
""")

    # ---------------------------------------------------- 3. resources
    print("=" * 74)
    print("3 — resources: O QUE A APLICAÇÃO DECIDE INCLUIR")
    print("=" * 74)
    texto = sessao.ler_recurso("regulamento://despesas/art-19")
    print(f"\n  regulamento://despesas/art-19\n")
    for linha in texto.splitlines():
        print(f"    {linha}")
    print("""
  Ninguém pediu ao modelo que lesse isto. A APLICAÇÃO decidiu incluir —
  e essa decisão é código, testável e barato.
""")

    # ---------------------------------------------------- 4. tools/call
    print("=" * 74)
    print("4 — tools/call: O ACERTO E O ERRO")
    print("=" * 74)

    print("\n  a) argumento válido")
    print("    ->", sessao.chamar("consultar_politica", {"categoria": "refeicao"}))

    print("\n  b) argumento inválido — ERRO DE DOMÍNIO")
    print("    ->", sessao.chamar("consultar_politica", {"categoria": "almoço"}))
    print("""
    O erro voltou como CONTEÚDO, não como falha de protocolo. É essa a
    diferença que decide se o modelo consegue se corrigir: erro de domínio
    devolvido como falha de transporte SOME do contexto, e o modelo repete
    o mesmo argumento até o orçamento acabar (nota 02, §4).
""")