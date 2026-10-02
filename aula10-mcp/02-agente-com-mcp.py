# Aula 10 — 02: O AGENTE DA AULA 05, CONSUMINDO MCP.
#
# CASO DE USO: dado o agente de prestação de contas que já existe, fazer
# com que ele use uma ferramenta publicada por outra equipe, sem reescrever
# o laço.
#
# AQUI O CLIENTE É O DO SDK OFICIAL — `ClientSession` sobre Streamable HTTP.
# O `01-sessao.py` fala o protocolo à mão, para abri-lo; este consome o
# servidor como se consome qualquer serviço de terceiro, que é o que o aluno
# vai fazer no trabalho.
#
# O script roda o mesmo objetivo por DUAS ROTAS, contra o mesmo servidor:
#
#   A. as ferramentas do servidor declaradas uma a uma, e o laço emitindo
#      uma chamada por passo — o jeito da nota 01;
#   B. uma declaração só, um EXECUTOR, e o agente escrevendo um programa
#      que faz as chamadas — a alternativa da nota 03.
#
# O MODELO vem do `cliente.py`, o mesmo da aula 09: uma variável do .env
# escolhe entre Mistral, Ollama e Groq. O que NÃO vem dele é o laço — ele
# continua escrito à mão aqui, que é o ponto do arquivo.
#
# Exige o servidor no ar, em outro terminal:
#     python 00-servidor.py          # naquele terminal
#     python 02-agente-com-mcp.py    # neste

import asyncio
import json
from dataclasses import dataclass, field

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from cliente import MODELO, PROVEDOR, modelo
from mcp_local import declaracao_openai

URL = "http://127.0.0.1:8000/mcp"

# --------------------------------------------------- as tarefas do agente
TAREFAS = [
    "A despesa D-4612 está dentro da política? Registre o parecer.",
    "A despesa D-4613 está dentro da política? Considere que foi em Lisboa.",
    "Qual é o teto de transporte, e a despesa D-4614 o respeita?",
]


# ----------------------------------------------- do SDK para o formato do modelo
def declaracoes_do_servidor(ferramentas) -> list[dict]:
    """Converte o `list_tools` do SDK no formato que o modelo consome.

    O ponto da aula 03 continua valendo: `description` e `inputSchema` são o
    que se escrevia à mão. O protocolo padronizou de ONDE eles vêm, não o que
    eles são."""
    return [
        {
            "type": "function",
            "function": {
                "name": f.name,
                "description": f.description or "",
                "parameters": f.inputSchema or {"type": "object"},
            },
        }
        for f in ferramentas.tools
    ]


def texto_do_retorno(resultado) -> str:
    """Junta os blocos textuais de um `call_tool`.

    ERRO DE DOMÍNIO chega aqui como CONTEÚDO, não como exceção — e é assim
    que ele volta ao modelo como observação (nota 02, §4)."""
    return "\n".join(bloco.text for bloco in resultado.content
                     if getattr(bloco, "text", None))


# ------------------------------------------- o laço da aula 05, quase sem alteração
# Estado, detector de laço e motivo de término vêm da aula 05 e não mudam por
# causa de MCP. O laço mudou numa coisa só, e não por causa do protocolo: o
# cliente do SDK é assíncrono, e isso atravessa quem o chama.

@dataclass
class Estado:
    """O `EstadoAgente` da aula 05, reduzido ao necessário aqui.

    O PONTO DA AULA 10 é que esta classe não muda por causa de MCP. Nem ela,
    nem o orçamento, nem o término, nem o detector de laço."""
    objetivo: str
    historico: list[dict] = field(default_factory=list)
    passos: list[tuple] = field(default_factory=list)
    termino: str | None = None


async def laco(estado: Estado, declaracoes: list[dict], executar,
               max_passos: int = 8) -> Estado:
    """O laço ReAct da aula 05. `executar(nome, args) -> str` é o único
    ponto de variação: pode ser o despacho ao servidor ou o executor de
    código."""
    msgs = [{"role": "system",
             "content": "Você analisa despesas segundo a política vigente. Use as ferramentas disponíveis antes de concluir."},
            {"role": "user", "content": estado.objetivo}]

    for passo in range(max_passos):
        # A chamada ao modelo é síncrona e BLOQUEIA o laço de eventos. Num
        # laboratório de um agente só isso não custa nada; num serviço com
        # vários, trocar-se-ia por um cliente assíncrono.
        #
        # O modelo vem do `cliente.py`, igual ao da aula 09: a mesma interface
        # atende Mistral, Ollama e Groq. As declarações seguem no formato da
        # OpenAI, que `bind_tools` aceita e converte.
        msg = modelo.bind_tools(declaracoes, temperature=0).invoke(msgs)
        msgs.append(msg)

        if not msg.tool_calls:
            estado.termino = "respondeu"
            estado.historico.append({"role": "assistant", "content": msg.text})
            return estado

        # Os argumentos já chegam DECODIFICADOS: `tool_calls` é uma lista de
        # dicionários com `name`, `args` e `id`. Sem o `json.loads` do SDK cru.
        for chamada in msg.tool_calls:
            nome = chamada["name"]
            argumentos = chamada["args"]
            # detector de laço da aula 05 — não vem do MCP
            assinatura = (nome, json.dumps(argumentos, sort_keys=True))
            estado.passos.append(assinatura)
            if estado.passos.count(assinatura) > 2:
                estado.termino = "laco_detectado"
                return estado
            observacao = await executar(nome, argumentos)
            msgs.append({"role": "tool", "tool_call_id": chamada["id"],
                         "content": observacao})

    estado.termino = "orcamento_esgotado"
    return estado


def resumo(estado: Estado) -> str:
    return (f"término={estado.termino} | passos={len(estado.passos)}")


async def main() -> None:
    print("=" * 74)
    print(f"O AGENTE DA AULA 05, COM A FERRAMENTA VINDA DE OUTRO PROCESSO  [{PROVEDOR}:{MODELO}]")
    print("=" * 74)

    # O servidor NÃO é iniciado aqui: ele já está no ar, no terminal dele, e
    # o cliente do SDK apenas se conecta. As três linhas abaixo substituem
    # todo o `SessaoMCP` do `01-sessao.py` — é o que a biblioteca pronta faz,
    # e é por isso que o `01` vem antes.
    async with streamable_http_client(URL) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()

            # --------------------------------------------------------------
            # A PRIMEIRA DAS DUAS MUDANÇAS. Na aula 05, a lista de declarações
            # era montada de um dicionário local. Aqui ela vem de `tools/list`,
            # de outro processo.
            # --------------------------------------------------------------
            declaracoes_mcp = declaracoes_do_servidor(await sessao.list_tools())

            # A SEGUNDA: em vez de despachar num dicionário local, o executar
            # delega ao servidor.
            async def executar_mcp(nome: str, argumentos: dict) -> str:
                return texto_do_retorno(
                    await sessao.call_tool(nome, arguments=argumentos))

            estado_a = await laco(Estado(objetivo=TAREFAS[0]),
                                  declaracoes_mcp, executar_mcp)
            print(f"\n  {resumo(estado_a)}")
            for m in estado_a.historico:
                print(f"\n  resposta: {m['content'][:400]}")

            print("\n" + "=" * 74)
            print("O MESMO TRABALHO, COM UMA FERRAMENTA SÓ: UM EXECUTOR")
            print("=" * 74)

            # A alternativa descrita pela Anthropic (2025): em vez de declarar
            # uma ferramenta por operação, declara-se UMA — um executor —, e o
            # que existe do outro lado vai na descrição dela. O agente escreve
            # código que chama o servidor, e o dado intermediário fica no
            # ambiente de execução, sem voltar ao modelo.
            api = "\n".join(
                f'  await chamar("{d["function"]["name"]}", {d["function"]["parameters"].get("properties", {})})  # {d["function"]["description"].splitlines()[0]}'
                for d in declaracoes_mcp)

            declaracao_executor = [declaracao_openai(
                "executar_codigo",
                "Executa código Python assíncrono que consulta o servidor de despesas e atribui a variável `resultado`. Funções disponíveis no ambiente (todas precisam de `await`):\n" + api,
                {"codigo": "string"},
            )]

            async def executar_codigo(nome: str, argumentos: dict) -> str:
                """O preço desta rota, dito na mesma frase que o ganho: o
                agente passa a EXECUTAR CÓDIGO. É a categoria ASI05 do catálogo
                OWASP para aplicações agênticas, e a aula 14 trata do
                isolamento e da permissão que essa capacidade exige. Aqui roda
                no próprio processo porque é laboratório; em produção, não."""
                async def chamar(ferramenta: str, args: dict) -> str:
                    return texto_do_retorno(
                        await sessao.call_tool(ferramenta, arguments=args))

                ambiente: dict = {"chamar": chamar}
                # o código do modelo é assíncrono, e por isso roda dentro de
                # uma corrotina montada na hora
                fonte = "async def _programa():\n" + "\n".join(
                    "    " + linha for linha in argumentos["codigo"].splitlines())
                fonte += "\n    return locals().get('resultado')"
                try:
                    exec(fonte, ambiente)
                    resultado = await ambiente["_programa"]()
                except Exception as erro:
                    return f"ERRO ao executar: {type(erro).__name__}: {erro}"
                if resultado is None:
                    return "ERRO: o código precisa atribuir a variável `resultado`."
                return str(resultado)

            estado_b = await laco(Estado(objetivo=TAREFAS[0]),
                                  declaracao_executor, executar_codigo)
            print(f"\n  {resumo(estado_b)}")
            for m in estado_b.historico:
                print(f"\n  resposta: {m['content'][:400]}")

            print(f"""
  declaradas ao modelo:  rota A {len(declaracoes_mcp)} ferramentas | rota B 1 executor
  passos do laço:        rota A {len(estado_a.passos)} | rota B {len(estado_b.passos)}
""")


asyncio.run(main())


# ------------------------------------------- o que mudou, em relação à aula 05
#
#   Estado ................. não mudou
#   detector de laço ....... não mudou      <- não vem do MCP
#   orçamento .............. não mudou      <- não vem do MCP
#   motivo de término ...... não mudou      <- não vem do MCP
#
#   origem das declarações . MUDOU          <- a primeira linha
#   despacho da execução ... MUDOU          <- a segunda linha
#   o laço virou assíncrono  MUDOU          <- e esta NÃO é culpa do MCP
#
# A terceira linha é o preço da biblioteca pronta, e vale dizê-lo em voz
# alta: o cliente do SDK é assíncrono, e concorrência atravessa quem chama.
# O protocolo não pediu isso — a dependência pediu. O `01-sessao.py`, que
# fala o mesmo protocolo à mão, é síncrono.
#
# Para o modelo, a ferramenta local da aula 05 e a ferramenta MCP são
# indistinguíveis: ambas chegam a ele como declaração no mesmo formato, e é
# por isso que as duas primeiras linhas bastam. É também por isso que a frase
# da nota 01 vale literalmente:
#
#     MCP não é arquitetura de agente. É transporte de ferramenta.
#
# Tudo o que faz um agente ser CONFIÁVEL continua sendo responsabilidade de
# quem escreve o agente. Quem adota MCP esperando confiabilidade adotou a
# coisa certa pelo motivo errado.
