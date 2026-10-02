# Exercício MCP — consultas à BrasilAPI.
#
# Execute este servidor em um terminal. Ele expõe duas ferramentas MCP
# por Streamable HTTP em 127.0.0.1:8001:
#   - consultar_cnpj(cnpj)
#   - consultar_cep(cep)
#
# CNPJ e CEP são normalizados antes da consulta: todos os caracteres que
# não forem dígitos são removidos (ex.: "01311-902" -> "01311902").

import re

import requests
from mcp.server.fastmcp import FastMCP

ENDERECO = "127.0.0.1"
PORTA = 8001
CAMINHO = "/mcp"
TIMEOUT = 10

BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1"
BRASILAPI_CEP = "https://brasilapi.com.br/api/cep/v2"

servidor = FastMCP(
    "consultas-brasilapi",
    host=ENDERECO,
    port=PORTA,
    streamable_http_path=CAMINHO,
)


def _normalizar_documento(valor: str) -> str:
    """Remove máscara e qualquer caractere que não seja um dígito."""
    return re.sub(r"\D", "", str(valor))


def _consultar_api(url: str) -> tuple[dict | None, dict | None]:
    """Busca JSON na BrasilAPI e devolve dados ou um erro para a ferramenta."""
    try:
        resposta = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as erro:
        return None, {"erro": "falha ao consultar a BrasilAPI", "detalhe": str(erro)}

    if resposta.status_code == 404:
        return None, {"erro": "registro não encontrado na BrasilAPI"}
    if not resposta.ok:
        return None, {
            "erro": "BrasilAPI respondeu com erro",
            "status": resposta.status_code,
        }

    try:
        return resposta.json(), None
    except ValueError:
        return None, {"erro": "BrasilAPI devolveu uma resposta inválida"}


@servidor.tool()
def consultar_cnpj(cnpj: str) -> dict:
    """Consulta os dados cadastrais de uma empresa pelo CNPJ na BrasilAPI.

    Argumento `cnpj`: string com exatamente 14 dígitos após remover máscara
    e pontuação. Aceita, por exemplo, "11222333000181" ou
    "11.222.333/0001-81". A consulta é feita com os dígitos normalizados.

    Retorna somente cnpj, razao_social, cep, logradouro, numero,
    complemento, bairro, municipio e uf. CNPJ e CEP na resposta são
    normalizados sem pontuação.

    Não retorna coordenadas geográficas, não consulta endereço por CEP e
    não pesquisa empresas por nome ou razão social.
    """
    cnpj_normalizado = _normalizar_documento(cnpj)
    if len(cnpj_normalizado) != 14:
        return {
            "erro": "CNPJ inválido: informe exatamente 14 dígitos",
            "recebido": cnpj,
            "normalizado": cnpj_normalizado,
        }

    dados, erro = _consultar_api(f"{BRASILAPI_CNPJ}/{cnpj_normalizado}")
    if erro:
        return {**erro, "cnpj": cnpj_normalizado}

    return {
        "cnpj": _normalizar_documento(dados.get("cnpj", cnpj_normalizado)),
        "razao_social": dados.get("razao_social"),
        "cep": _normalizar_documento(dados.get("cep", "")),
        "logradouro": dados.get("logradouro"),
        "numero": dados.get("numero"),
        "complemento": dados.get("complemento"),
        "bairro": dados.get("bairro"),
        "municipio": dados.get("municipio"),
        "uf": dados.get("uf"),
    }


@servidor.tool()
def consultar_cep(cep: str) -> dict:
    """Consulta endereço e coordenadas na BrasilAPI usando um CEP.

    Argumento `cep`: string com exatamente 8 dígitos após remover máscara
    e pontuação. Aceita, por exemplo, "01311902" ou "01311-902". A
    consulta é feita com os dígitos normalizados.

    Retorna somente cep, street, neighborhood, city, state e
    location.coordinates.latitude/longitude. O CEP da resposta é
    normalizado sem pontuação.

    Não busca por nome de rua, logradouro, bairro ou cidade; informe o
    CEP completo. Não consulta dados cadastrais de empresas ou CNPJ.
    """
    cep_normalizado = _normalizar_documento(cep)
    if len(cep_normalizado) != 8:
        return {
            "erro": "CEP inválido: informe exatamente 8 dígitos",
            "recebido": cep,
            "normalizado": cep_normalizado,
        }

    dados, erro = _consultar_api(f"{BRASILAPI_CEP}/{cep_normalizado}")
    if erro:
        return {**erro, "cep": cep_normalizado}

    coordenadas = (dados.get("location") or {}).get("coordinates") or {}
    return {
        "cep": _normalizar_documento(dados.get("cep", cep_normalizado)),
        "street": dados.get("street"),
        "neighborhood": dados.get("neighborhood"),
        "city": dados.get("city"),
        "state": dados.get("state"),
        "location": {
            "coordinates": {
                "latitude": coordenadas.get("latitude"),
                "longitude": coordenadas.get("longitude"),
            }
        },
    }


if __name__ == "__main__":
    print(f"servidor BrasilAPI no ar em {ENDERECO}:{PORTA}{CAMINHO}")
    print("conecte um cliente MCP neste endereço; Ctrl+C para encerrar")
    servidor.run(transport="streamable-http")
