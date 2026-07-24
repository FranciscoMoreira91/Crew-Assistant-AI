"""
tools/websearch_tool.py
------------------------
Ferramenta CrewAI para pesquisar informação atual na Web e para "ler"
o conteúdo de uma página a partir do seu URL, para que o agente
Pesquisador deixe de responder apenas com o conhecimento interno do
modelo e passe a ter acesso a factos reais e atuais (notícias, preços,
cotações, artigos indicados pelo utilizador, etc.).

Duas operações (ver `WebSearchToolInput.operation`):

    "pesquisar"       -> pesquisa uma query na Web e devolve uma lista
                          de resultados (título, URL, resumo/snippet).
    "resumir_pagina"  -> descarrega o conteúdo de um URL e devolve o
                          texto principal da página (limpo de HTML),
                          para o agente resumir por palavras próprias.

Fornecedores de pesquisa suportados (variável de ambiente SEARCH_PROVIDER):

    "duckduckgo" (omissão) -> não precisa de nenhuma chave de API.
    "serper"                -> precisa de SERPER_API_KEY (serper.dev).
    "tavily"                -> precisa de TAVILY_API_KEY (tavily.com).

Tal como acontece em tools/image_tool.py, a configuração é lida do
ambiente a cada chamada (_current_search_config()), para que uma
alteração feita no painel de Definições ou no .env tenha efeito
imediato, sem reiniciar a app.

Dependências novas (ver requirements.txt): ddgs, beautifulsoup4
"""

import os
from typing import Callable, List, Literal, Optional, Type

import requests
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

try:
    from bs4 import BeautifulSoup
    _BS4_DISPONIVEL = True
except ImportError:  # a dependência pode ainda não estar instalada
    _BS4_DISPONIVEL = False

REQUEST_TIMEOUT = 12
USER_AGENT = (
    "Mozilla/5.0 (compatible; CrewAssistantAI/2.3; "
    "+https://crewassistant.pt) WebSearchTool"
)
MAX_RESULTADOS = 5
MAX_CARACTERES_PAGINA = 6000


def _current_search_config():
    """Lê a configuração de pesquisa diretamente do ambiente, a cada
    chamada, tal como o resto das ferramentas do projeto."""
    provider = os.getenv("SEARCH_PROVIDER", "duckduckgo").strip().lower()
    serper_key = os.getenv("SERPER_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")
    return provider, serper_key, tavily_key


class WebSearchToolInput(BaseModel):
    operation: Literal["pesquisar", "resumir_pagina"] = Field(
        default="pesquisar",
        description=(
            "pesquisar -> pesquisa a 'query' na Web e devolve os "
            "resultados mais relevantes (título, URL, resumo).\n"
            "resumir_pagina -> descarrega o conteúdo do 'url' indicado "
            "e devolve o texto principal da página, para depois seres "
            "tu a resumi-lo por palavras próprias."
        ),
    )
    query: str = Field(
        default="",
        description="Termos de pesquisa. Obrigatório quando operation='pesquisar'.",
    )
    url: str = Field(
        default="",
        description="URL da página a ler/resumir. Obrigatório quando operation='resumir_pagina'.",
    )
    max_resultados: int = Field(
        default=MAX_RESULTADOS,
        ge=1,
        le=10,
        description="Número máximo de resultados a devolver (apenas para operation='pesquisar').",
    )


class WebSearchTool(BaseTool):
    name: str = "WebSearchTool"
    description: str = (
        "Pesquisa informação atual na Internet (notícias, preços, cotações, "
        "factos recentes) e/ou lê o conteúdo de uma página a partir do seu "
        "URL para depois a resumires. Usa operation='pesquisar' com uma "
        "'query' objetiva, ou operation='resumir_pagina' com o 'url' "
        "indicado pelo humano. Devolve sempre os URLs reais das fontes "
        "usadas — nunca inventes fontes."
    )
    args_schema: Type[BaseModel] = WebSearchToolInput

    # Callback opcional, chamado com cada URL assim que é encontrado/aberto,
    # para o frontend poder mostrar em tempo real (via SSE) os sites que o
    # agente está a pesquisar, enquanto o utilizador espera a resposta
    # final. Excluído da serialização do modelo Pydantic (não é um campo
    # de dados da ferramenta, é só um "gancho" de progresso).
    progress_callback: Optional[Callable[[str], None]] = Field(default=None, exclude=True)

    def _notificar(self, url: str) -> None:
        if not self.progress_callback or not url:
            return
        try:
            self.progress_callback(url)
        except Exception:  # noqa: BLE001
            pass  # nunca deixar o progresso visual quebrar a pesquisa real

    # ------------------------------------------------------------------ #
    # Execução principal (chamada pelo agente CrewAI)
    # ------------------------------------------------------------------ #
    def _run(
        self,
        operation: str = "pesquisar",
        query: str = "",
        url: str = "",
        max_resultados: int = MAX_RESULTADOS,
    ) -> str:
        if operation == "resumir_pagina":
            if not url.strip():
                return "É obrigatório indicar o 'url' da página a resumir."
            return self._ler_pagina(url.strip())

        if not query.strip():
            return "É obrigatório indicar a 'query' a pesquisar."
        return self._pesquisar(query.strip(), max_resultados)

    # ------------------------------------------------------------------ #
    # Pesquisa na Web
    # ------------------------------------------------------------------ #
    def _pesquisar(self, query: str, max_resultados: int) -> str:
        provider, serper_key, tavily_key = _current_search_config()

        try:
            if provider == "serper":
                if not serper_key:
                    return (
                        "SEARCH_PROVIDER='serper' mas falta a variável "
                        "SERPER_API_KEY no .env (obtém uma chave gratuita "
                        "em serper.dev)."
                    )
                resultados = self._pesquisar_serper(query, max_resultados, serper_key)
            elif provider == "tavily":
                if not tavily_key:
                    return (
                        "SEARCH_PROVIDER='tavily' mas falta a variável "
                        "TAVILY_API_KEY no .env (obtém uma chave gratuita "
                        "em tavily.com)."
                    )
                resultados = self._pesquisar_tavily(query, max_resultados, tavily_key)
            else:
                resultados = self._pesquisar_duckduckgo(query, max_resultados)
        except Exception as exc:  # noqa: BLE001
            return f"Não consegui pesquisar na Web agora. Detalhe: {exc}"

        return self._formatar_resultados(query, resultados)

    def _pesquisar_duckduckgo(self, query: str, max_resultados: int) -> List[dict]:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # nome antigo do pacote

        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_resultados):
                site_url = r.get("href") or r.get("link", "")
                self._notificar(site_url)
                resultados.append(
                    {
                        "titulo": r.get("title", ""),
                        "url": site_url,
                        "resumo": r.get("body", ""),
                    }
                )
        return resultados

    def _pesquisar_serper(self, query: str, max_resultados: int, api_key: str) -> List[dict]:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_resultados},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
        resultados = []
        for item in dados.get("organic", [])[:max_resultados]:
            site_url = item.get("link", "")
            self._notificar(site_url)
            resultados.append(
                {
                    "titulo": item.get("title", ""),
                    "url": site_url,
                    "resumo": item.get("snippet", ""),
                }
            )
        return resultados

    def _pesquisar_tavily(self, query: str, max_resultados: int, api_key: str) -> List[dict]:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_resultados,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
        resultados = []
        for item in dados.get("results", [])[:max_resultados]:
            site_url = item.get("url", "")
            self._notificar(site_url)
            resultados.append(
                {
                    "titulo": item.get("title", ""),
                    "url": site_url,
                    "resumo": item.get("content", ""),
                }
            )
        return resultados

    def _formatar_resultados(self, query: str, resultados: List[dict]) -> str:
        if not resultados:
            return f"Não encontrei resultados na Web para: '{query}'."

        linhas = [f"Resultados da pesquisa na Web para '{query}':"]
        for i, r in enumerate(resultados, 1):
            linhas.append(
                f"{i}. {r['titulo']}\n   URL: {r['url']}\n   Resumo: {r['resumo']}"
            )
        return "\n".join(linhas)

    # ------------------------------------------------------------------ #
    # Leitura/resumo de uma página a partir do URL
    # ------------------------------------------------------------------ #
    def _ler_pagina(self, url: str) -> str:
        if not _BS4_DISPONIVEL:
            return (
                "A leitura de páginas requer a biblioteca 'beautifulsoup4' "
                "(adiciona 'beautifulsoup4' ao requirements.txt e corre "
                "'pip install beautifulsoup4')."
            )

        self._notificar(url)

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return f"Não consegui aceder a {url}. Detalhe: {exc}"

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        titulo = soup.title.string.strip() if soup.title and soup.title.string else ""
        texto = " ".join(soup.get_text(separator=" ").split())

        if not texto:
            return f"Não consegui extrair texto legível de {url}."

        texto_cortado = texto[:MAX_CARACTERES_PAGINA]
        if len(texto) > MAX_CARACTERES_PAGINA:
            texto_cortado += " [...texto cortado...]"

        cabecalho = f"Conteúdo de {url}"
        if titulo:
            cabecalho += f" (título: {titulo})"

        return f"{cabecalho}\n\n{texto_cortado}"
