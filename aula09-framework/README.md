# Aula 09 — Frameworks e orquestração

Catorze arquivos, e **cada um acrescenta uma coisa ao anterior**. O `diff` entre
dois arquivos consecutivos é o conteúdo do passo: rode um, converse com ele,
passe para o próximo e repare no que entrou.

Nada aqui é novo como ideia. O laço, o estado, o orçamento, o roteador e as
memórias você já escreveu à mão nas Aulas 05 a 08. O que muda é que deixam de
ser **escritos** e passam a ser **declarados**.

## Antes de rodar

```
cp .env.example .env     # na raiz do repositório
```

Uma linha decide com qual modelo tudo roda:

```
LLM_PROVEDOR=groq        # ou: mistral, ollama
```

Só a chave do provedor escolhido precisa ser preenchida. **A Groq é a
recomendada**: responde em segundos e tem cota gratuita. Com Ollama local, os
arquivos `07` e `09` levam minutos.

O `cliente.py` é o único arquivo que sabe qual provedor está em uso. Todos os
outros importam `modelo` dele e não fazem ideia do que há do outro lado.

## A ordem

| Script | O que entra |
|---|---|
| `00-tools.py` | o agente pronto, com uma ferramenta — e o `@tool` |
| `01-resposta-estruturada.py` | saída validada contra um schema Pydantic |
| `02-contexto.py` | contexto de execução, e o *system prompt* calculado a cada chamada |
| `03-memoria-sessao.py` | `checkpointer` e `thread_id`: a segunda pergunta lembra da primeira |
| `04-langgraph.py` | o mesmo laço, agora como **grafo** — sem `create_agent` |
| `05-arquitetura-tools.py` | o modelo aumentado: schema e ferramentas, as duas peças de base |
| `06-arquitetura-sequencia.py` | sequencial com portão — e o portão é **código puro** |
| `07-arquitetura-paralelizacao.py` | paralelização, **com os tempos medidos** |
| `08-arquitetura-routing.py` | *router* — agora quem decide é o modelo |
| `09-arquitetura-orquestrator.py` | `Send`: um trabalhador por item, decidido em runtime |
| `10-avaliador-otimizador.py` | a aresta de volta, com **limite de voltas** |
| `11-estado-checkpointers.py` | o agente guarda a preferência num campo do **Estado**, outro nó sugere pratos lendo só esse campo, e o `checkpointer` devolve o Estado na mesma thread — não numa nova |
| `12-stores.py` | `store`: a preferência vale em qualquer thread — retomar não é lembrar |
| `13-human-in-the-loop.py` | `interrupt`: o grafo para e espera uma pessoa |

Cada arquivo a partir do `04` traz **o grafo desenhado em ASCII no cabeçalho**.
Vale ler o desenho antes de ler o código.

## Quatro coisas para reparar

**O modelo não executa nada** (`05`). Ele devolve o nome da ferramenta e os
argumentos; quem executa é o seu código. A mensagem com o corpo vazio e os
`Tool Calls` preenchidos é a prova.

**O schema garante a forma, não o conteúdo** (`08`). Com modelo pequeno, o
pedido *"me escreva uma piada"* vai parar na rota `conto`. A resposta é uma das
três rotas válidas, e está errada mesmo assim.

**Sem reducer, o campo é substituído** (`09`). Num grafo com nós paralelos, o
último nó a terminar sobrescreve os outros — sem exceção, sem log, sem erro.
Tire o `operator.add` de `secoes_prontas` e rode de novo.

**O paralelismo pode não acontecer** (`07`). O grafo despacha os três nós no
mesmo passo; se o servidor do modelo atende uma requisição por vez, o total
vira a **soma** e não o maior. Os tempos impressos dizem qual dos dois você
tem.

## O que o framework não dá

Nenhum destes vem pronto, e todos continuam sendo seus:

- o **motivo** de término — o nó terminal diz que acabou, não diz por quê;
- o **detector de laço** — `recursion_limit` limita o dano, não detecta;
- três dos quatro **tetos** da Aula 05 — ele cobre o de passos;
- a classificação **erro recuperável × fatal**.
