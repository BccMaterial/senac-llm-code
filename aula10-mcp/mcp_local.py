# Aula 10 — O cliente MCP.
#
# DECISÃO DE PROJETO DESTE MÓDULO: o cliente é escrito com a biblioteca
# padrão — `json` e `urllib`, nada além. Não é falta de biblioteca: é
# para que o protocolo fique VISÍVEL, em vez de ficar atrás de um adaptador
# — que é como a aula 09 o apresentou, com `langchain.mcp`.
#
# Este módulo serve ao `01-sessao.py`, e só a ele. O servidor
# (`00-servidor.py`) e o agente (`02-agente-com-mcp.py`) usam o SDK oficial,
# que é o que se usa no trabalho. O servidor roda em processo e terminal
# PRÓPRIOS: nenhum script daqui o inicia.

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# Revisão da especificação que este cliente fala. Entra no CARIMBO da aula:
# uma execução com outra revisão não é comparável (nota 02, §5).
PROTOCOLO = "2025-06-18"

# ===================================================================== 1
#  A declaração de ferramenta
# ===================================================================== 1

def declaracao_openai(nome: str, descricao: str, propriedades: dict) -> dict:
    """Monta a declaração no formato que o modelo recebe.

    O ponto da aula: este formato é o MESMO da aula 03. MCP não inventou a
    declaração — padronizou de onde ela vem."""
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": v} for k, v in propriedades.items()},
                "required": list(propriedades),
            },
        },
    }


# ===================================================================== 2
#  Cliente MCP sobre Streamable HTTP, em JSON-RPC cru
# ===================================================================== 2

URL_PADRAO = "http://127.0.0.1:8000/mcp"


def _do_fluxo_sse(corpo: str) -> dict:
    """Extrai o JSON-RPC de uma resposta em `text/event-stream`.

    O Streamable HTTP permite ao servidor responder de duas formas: um JSON
    direto, ou um fluxo de eventos em que a mensagem vem nas linhas `data:`.
    O cliente precisa aceitar as duas."""
    for linha in corpo.splitlines():
        if linha.startswith("data:"):
            return json.loads(linha[len("data:"):].strip())
    raise RuntimeError("fluxo SSE sem linha `data:`")


@dataclass
class SessaoMCP:
    """Uma sessão MCP com um servidor que já está no ar, por HTTP.

    O ciclo é o da nota 01, §3: initialize -> initialized -> tools/list ->
    tools/call -> DELETE. Nada aqui é abstração do módulo; é o protocolo.

    O servidor NÃO é iniciado por aqui: ele roda no próprio terminal, por
    `python 00-servidor.py`, e esta sessão apenas se conecta a ele.

    A classe guarda o que a sessão TEM DE ESTADO, e é só isso que justifica
    ela existir: o identificador devolvido no handshake, que acompanha toda
    requisição seguinte, e o contador de `id` que correlaciona pedido e
    resposta."""

    url: str = URL_PADRAO
    nome: str = "servidor"
    _id: int = 0
    sessao: str | None = None
    capacidades: dict = field(default_factory=dict)

    # ------------------------------------------------------ ciclo de vida
    def __enter__(self) -> "SessaoMCP":
        self._initialize()
        return self

    def __exit__(self, *_) -> None:
        """Encerra a sessão, e não o servidor.

        A especificação define o gesto: `DELETE` no mesmo endereço, com o
        identificador da sessão no cabeçalho. O servidor pode recusar, com
        405, e aí a sessão simplesmente expira sozinha — por isso a falha
        aqui é ignorada.

        O processo do servidor continua no ar depois disto. É a diferença
        prática entre os dois transportes: em stdio, encerrar a sessão é
        matar o processo; aqui, são coisas separadas."""
        if not self.sessao:
            return
        pedido = urllib.request.Request(
            self.url, method="DELETE",
            headers={"Mcp-Session-Id": self.sessao,
                     "MCP-Protocol-Version": PROTOCOLO})
        try:
            urllib.request.urlopen(pedido, timeout=5).close()
        except urllib.error.URLError:
            pass                         # 405, ou servidor já encerrado
        self.sessao = None

    # -------------------------------------------------------- transporte
    def _proximo_id(self) -> int:
        self._id += 1
        return self._id

    def _postar(self, mensagem: dict) -> dict | None:
        corpo = json.dumps(mensagem, ensure_ascii=False).encode()
        cabecalhos = {
            "Content-Type": "application/json",
            # a resposta pode vir como JSON ou como fluxo de eventos, e o
            # cliente declara que aceita as duas
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOLO,
        }
        if self.sessao:
            # o identificador de sessão vem no handshake e acompanha todas
            # as requisições seguintes (revisão 2025-06-18)
            cabecalhos["Mcp-Session-Id"] = self.sessao
        pedido = urllib.request.Request(self.url, data=corpo,
                                        headers=cabecalhos, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                if self.sessao is None:
                    self.sessao = resposta.headers.get("Mcp-Session-Id")
                tipo = resposta.headers.get("Content-Type", "")
                bruto = resposta.read().decode()
        except urllib.error.URLError as erro:
            raise RuntimeError(f"servidor {self.nome} inacessível em {self.url}. Inicie-o antes, em outro terminal: python 00-servidor.py — ({erro})") from erro
        if not bruto.strip():
            return None                  # notificação aceita, sem corpo
        if tipo.startswith("text/event-stream"):
            return _do_fluxo_sse(bruto)
        return json.loads(bruto)

    def requisitar(self, metodo: str, params: dict | None = None) -> dict:
        """Uma requisição JSON-RPC, com resposta correlacionada pelo id."""
        pedido = {"jsonrpc": "2.0", "id": self._proximo_id(), "method": metodo}
        if params is not None:
            pedido["params"] = params
        resposta = self._postar(pedido) or {}
        if "error" in resposta:
            # ERRO DE PROTOCOLO (nota 02, §4): não volta ao modelo como
            # observação. É falha de transporte, e o código a trata.
            raise RuntimeError(f"{self.nome}: {resposta['error']}")
        return resposta.get("result", {})

    def notificar(self, metodo: str, params: dict | None = None) -> None:
        """Notificação: sem id, e portanto sem resposta."""
        msg = {"jsonrpc": "2.0", "method": metodo}
        if params is not None:
            msg["params"] = params
        self._postar(msg)

    # ----------------------------------------------------------- handshake
    def _initialize(self) -> None:
        resultado = self.requisitar("initialize", {
            "protocolVersion": PROTOCOLO,
            "capabilities": {},
            "clientInfo": {"name": "aula10", "version": "1.0"},
        })
        self.capacidades = resultado.get("capabilities", {})
        self.notificar("notifications/initialized")

    # ------------------------------------------------------------ os três
    def listar_ferramentas(self) -> list[dict]:
        return self.requisitar("tools/list").get("tools", [])

    def chamar(self, nome: str, argumentos: dict) -> str:
        """Executa uma ferramenta e devolve o conteúdo textual do retorno.

        ERRO DE DOMÍNIO chega aqui como CONTEÚDO, não como exceção — e é
        assim que ele volta ao modelo como observação (nota 02, §4)."""
        resultado = self.requisitar("tools/call",
                                    {"name": nome, "arguments": argumentos})
        partes = [p.get("text", "") for p in resultado.get("content", [])]
        return "\n".join(partes)

    def listar_recursos(self) -> list[dict]:
        try:
            return self.requisitar("resources/list").get("resources", [])
        except RuntimeError:
            return []                    # o servidor não declarou a capacidade

    def ler_recurso(self, uri: str) -> str:
        resultado = self.requisitar("resources/read", {"uri": uri})
        return "\n".join(c.get("text", "") for c in resultado.get("contents", []))

    # ------------------------------------------------- para o laço do agente
    def declaracoes_openai(self, prefixo: bool = False) -> list[dict]:
        """Converte `tools/list` no formato que o modelo consome.

        `prefixo=True` antepõe o nome do servidor — a defesa nº 2 contra a
        confusão de ferramenta (nota 03, §2)."""
        saida = []
        for f in self.listar_ferramentas():
            nome = f"{self.nome}__{f['name']}" if prefixo else f["name"]
            saida.append({
                "type": "function",
                "function": {
                    "name": nome,
                    "description": f.get("description", ""),
                    "parameters": f.get("inputSchema", {"type": "object"}),
                },
            })
        return saida

