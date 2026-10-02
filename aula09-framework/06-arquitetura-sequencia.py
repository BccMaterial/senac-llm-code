# PROMPT CHAINING — cada chamada processa a saída da anterior.
#
# https://docs.langchain.com/oss/python/langgraph/workflows-agents
#
# É o padrão que a Aula 05 chama de SEQUENCIAL COM PORTÃO: a cadeia é fixa,
# quem decide o caminho é código — não o modelo. Serve a tarefas bem
# definidas, que se quebram em passos verificáveis.
#
#                        ┌───────┐
#                        │ START │
#                        └───┬───┘
#                            ▼
#                   ┌─────────────────┐
#                   │   gerar_piada   │
#                   └────────┬────────┘
#                            │
#                     tem_desfecho()        <- o PORTÃO, em código puro
#                     ┌──────┴──────┐
#                  "falhou"      "passou"
#                     │             │
#                     ▼             ▼
#            ┌─────────────────┐  ┌─────┐
#            │ melhorar_piada  │  │ END │
#            └────────┬────────┘  └─────┘
#                     ▼
#            ┌─────────────────┐
#            │   polir_piada   │
#            └────────┬────────┘
#                     ▼
#                  ┌─────┐
#                  │ END │
#                  └─────┘

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from cliente import MODELO, PROVEDOR, modelo

print(f"[{PROVEDOR}:{MODELO}]")

# -------------------------------------------------------------------- estado

class Estado(TypedDict):
    tema: str
    piada: str
    piada_melhorada: str
    piada_final: str


# ----------------------------------------------------------------------- nós

def le_piada(estado: Estado):
    return {"piada": estado["piada"]}

# def gerar_piada(estado: Estado):
#     """Primeira chamada: a piada inicial."""
#     resposta = modelo.invoke(f"Escreva uma piada curta sobre {estado['tema']}")
#     return {"piada": resposta.text}


def tem_desfecho(estado: Estado):
    """O portão: a piada tem desfecho? Verificação em código, sem modelo."""
    if "?" in estado["piada"] or "!" in estado["piada"]:
        return "passou"
    return "falhou"


def melhorar_piada(estado: Estado):
    """Segunda chamada: acrescenta jogo de palavras."""
    resposta = modelo.invoke(f"Deixe esta piada mais engraçada acrescentando um jogo de palavras: {estado['piada']}")
    print("\n  [nó] melhorar_piada")
    resposta.pretty_print()
    return {"piada_melhorada": resposta.text}


def polir_piada(estado: Estado):
    """Terceira chamada: o acabamento."""
    resposta = modelo.invoke(f"Acrescente uma reviravolta surpreendente a esta piada: {estado['piada_melhorada']}")
    print("\n  [nó] polir_piada")
    resposta.pretty_print()
    return {"piada_final": resposta.text}


# -------------------------------------------------------------------- o grafo

construtor = StateGraph(Estado)
construtor.add_node("le_piada", le_piada)
#construtor.add_node("gerar_piada", gerar_piada)
construtor.add_node("melhorar_piada", melhorar_piada)
construtor.add_node("polir_piada", polir_piada)

construtor.add_edge(START, "le_piada")
construtor.add_conditional_edges("le_piada", tem_desfecho, {"falhou": "melhorar_piada", "passou": END})
construtor.add_edge("melhorar_piada", "polir_piada")
construtor.add_edge("polir_piada", END)

cadeia = construtor.compile()


# ------------------------------------------------------------------ execução

# piada pronta:
piada_pronta = "O bêbado olhou para a mulher na rua e disse: Que mulher feia!, e o mulher respondeu: Feio é você que está bêbado!, ao que o homem retrucou: Mas amanhã eu acordo curado!."
piada_malfeita = "O gato caiu do telhado"

#estado = cadeia.invoke({"tema": "gatos"})
estado = cadeia.invoke({"piada": piada_malfeita})

print("\nPiada inicial:")
print(estado["piada"])

if "piada_melhorada" not in estado:
    print("\n(passou no portão na primeira tentativa — os outros dois nós nem rodaram)")
