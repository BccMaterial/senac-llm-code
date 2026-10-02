# Aula 10 — MCP: conectando o agente a ferramentas de terceiros

Laboratório da aula 10. Risca o penúltimo item da lista de pendências que a
aula 03 (nota 04, §9) deixou de pé. Depois desta aula resta um: multiagente,
na aula 12.

## O caso de uso

> Dada uma ferramenta que já existe no agente, publicá-la como serviço que
> qualquer agente consome — e decidir se vale a pena.

## Dependência nova

`mcp` (SDK oficial de Python, que inclui a camada FastMCP). Está no
`requirements.txt` da raiz.

## Uma decisão de projeto desta pasta

**O servidor roda sozinho.** Ele é o `00` porque é o primeiro a subir, num
terminal só dele, por Streamable HTTP em `127.0.0.1:8000`. Os scripts `01` e
`02` são clientes: conectam-se a um servidor que já está no ar, e não o
iniciam. É a premissa do protocolo — a ferramenta é de outro dono — na forma
de executar o laboratório.

**O protocolo aparece à mão uma vez, e depois some.** O `01-sessao.py` fala
JSON-RPC sobre HTTP com a biblioteca padrão — `json` e `urllib`, nada além —,
e é a única vez em que o aluno vê as mensagens. O `02-agente-com-mcp.py` já
usa o **cliente do SDK** (`ClientSession`), que é o que se usa no trabalho; o
`00-servidor.py` usa o FastMCP do mesmo pacote.

A ordem é o conteúdo: à mão primeiro, SDK depois, e o adaptador do framework
por último, no `03-agente-langgraph-mcp.py`, que reduz tudo isto a um
dicionário de configuração e duas chamadas. O aluno será a única pessoa da
sala capaz de dizer **o que sumiu** em cada degrau — e o primeiro degrau
cobra algo visível, porque o cliente do SDK é assíncrono e o laço da aula 05
precisou virar `async`.

## Ordem sugerida

| Script | O que produz |
|---|---|
| `01-sessao.py` | A sessão MCP inteira em JSON-RPC cru: `initialize`, `tools/list`, `resources/read`, `tools/call` — com o acerto, o erro de domínio e a idempotência atravessando a fronteira do processo. **Demonstração conceitual declarada**, não caso de uso. |
| `02-agente-com-mcp.py` | O agente da aula 05 consumindo o servidor pelo **cliente do SDK**, por duas rotas: as ferramentas declaradas uma a uma, e **um executor só**, em que o agente escreve código que chama o servidor. As linhas que mudaram em relação à aula 05 estão marcadas no arquivo — inclusive a que o SDK cobrou, e que não é do protocolo. |
| `03-agente-langgraph-mcp.py` | O mesmo agente pelo **adaptador do framework** (`langchain-mcp-adapters`): a sessão e a tradução de schema somem. O que **não** some é a descrição envenenada — o adaptador confia no servidor e repassa. |
| `00-servidor.py` | O servidor. A `consultar_politica` da aula 05 publicada, mais o regulamento como **recurso** e o `registrar_parecer` como **ferramenta idempotente**. |
| `cliente.py` | O modelo, escolhido por uma variável do `.env` entre Mistral, Ollama e Groq. É o mesmo arquivo da aula 09. |

## As três coisas que esta pasta demonstra

**1. MCP não é arquitetura de agente.** O `01` mostra que o laço, o estado, o
orçamento, o motivo de término e o detector de laço da aula 05 não mudam uma
linha. Continua tudo sendo trabalho de quem escreve o agente.

**2. O protocolo cobra em ferramentas declaradas.** Todo servidor conectado
declara o conjunto inteiro do que expõe, e não só o que o agente usaria:
três servidores comuns somados às ferramentas locais passam de quarenta
declarações ativas em toda volta do laço.

**3. A confusão de ferramenta é a cegueira de entidade da aula 06.** Com
dezenas de ferramentas ativas, `search_files`, `search_issues` e
`search_pull_requests` disputam a mesma escolha, e o modelo decide por
semelhança. A defesa é a mesma de lá: desambiguar fora do modelo.

## A regra de decisão

```
MCP paga quando há MAIS DE UM DONO.
```

Operação de alta frequência e baixa complexidade: o schema domina o volume
enviado. Ferramenta de consumidor único: use uma função. Essa regra volta na
aula 12, e é ela que recusa o protocolo A2A para o trabalho da disciplina.

## O que fica para a aula 14

Nomeado aqui, tratado lá: *tool poisoning*, *rug pull* e *tool shadowing*,
que compartilham um mecanismo único — **a descrição da ferramenta entra no
contexto do modelo, e portanto é entrada não confiável vinda de terceiro**.
Mais a execução de código da segunda rota do `01`, que é ASI05.

O `00-servidor.py` traz a constante `DESCRICAO_ENVENENADA` para a demonstração
do mecanismo, ao lado das ferramentas cuja descrição ela substitui. Ela é usada **contra o servidor desta pasta, localmente** — nunca
contra sistema de terceiro.

## Custo

Só o `01` chama o modelo — duas vezes, uma por rota. O `00` e o `02` são
protocolo puro.
