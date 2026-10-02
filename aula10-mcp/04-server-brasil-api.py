import httpx
from mcp.server.fastmcp import FastMCP

# A principal diferença é que uma tool executa uma ação ou processa dados, enquanto um resource é um arquivo estático que compõe o aplicativo.

mcp = FastMCP("hospitais")

USER_AGENT = "senac-agentes-llm/1.0"

async def brasil_api(
    estado: str | None = None,
    cidade: str | None = None,
    atendimento: str | None = None,
    vertical: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Consulta a BrasilAPI de hospitais.

    Args:
        estado: sigla da UF (parâmetro `uf`), ex: SP
        cidade: busca parcial pelo município (parâmetro `municipio`)
        atendimento: termo principal, ex: escorpiao, cascavel, radioterapia, 17.07
        vertical: "peconhentos", "oncologia" ou "raras"
        q: busca livre por nome ou endereço do estabelecimento
        limit: máximo de itens (1 a 500)
        offset: deslocamento para paginação
    """
    url = "https://brasilapi.com.br/api/hospitais/v1"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    params = {
        "uf": estado,
        "municipio": cidade,
        "atendimento": atendimento,
        "vertical": vertical,
        "q": q,
        "limit": max(1, min(limit, 500)),
        "offset": max(0, offset),
    }
    params = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

@mcp.tool()
async def hospitais_animais_peconhentos(
    estado: str, cidade: str, atendimento: str | None = None
) -> str:
    """Procura hospitais habilitados para lidar com animais peçonhentos

    Args:
        estado: unidade federativa com 2 letras em minúsculo: sp, rj, df...
        cidade: nome da cidade em minusculo sem acentos
        atendimento: opcional, nome do animal ou soro (escorpiao, cascavel, jararaca, crotalico...)
    """
    data = await brasil_api(
        estado=estado.upper(),
        cidade=cidade,
        atendimento=atendimento,
        vertical="peconhentos",
    )

    if not data or "items" not in data:
        return "Não foi possível consultar os hospitais."

    aviso = data.get("emergencia", {}).get(
        "aviso", "Em emergência, ligue 192 (SAMU)."
    )

    if not data["items"]:
        return f"Nenhum hospital encontrado para {cidade}/{estado.upper()}.\n\n{aviso}"

    hospitais = [
        f"""
Nome: {h.get("name", "Desconhecido")}
Endereço: {h.get("address", "Não informado")} - {h.get("city", "")}/{h.get("state_code", "")}
Telefone: {h.get("phones", "Não informado")}
Soros: {", ".join(h.get("treatments", [])) or "Não informado"}
"""
        for h in data["items"]
    ]
    return "\n---\n".join(hospitais) + f"\n\n{aviso}"

if __name__ == "__main__":
    mcp.run(transport="stdio")

