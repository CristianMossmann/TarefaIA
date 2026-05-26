"""Cliente HTTP minimo usado pelos scrapers.

- Usa apenas stdlib (`urllib`).
- Define User-Agent identificavel (boa pratica de scraping etico).
- Aplica timeout fixo.
- Limita o tamanho da resposta para evitar fonte hostil estourar memoria.
"""

from __future__ import annotations

import urllib.error
import urllib.request


DEFAULT_USER_AGENT = "AgroVisionBot/1.0 (+monitoring; contato=ops@example.local)"
MAX_RESPONSE_BYTES = 1_048_576  # 1 MB


class HTTPClientError(RuntimeError):
    """Erro generico ao consumir um recurso externo."""


class HTTPClient:
    def __init__(self, timeout_seconds: int = 8, user_agent: str = DEFAULT_USER_AGENT):
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def get(self, url: str, extra_headers: dict[str, str] | None = None) -> bytes:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
        }
        if extra_headers:
            headers.update(extra_headers)

        request = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise HTTPClientError(f"HTTP {exc.code} ao acessar {url}") from exc
        except urllib.error.URLError as exc:
            raise HTTPClientError(f"Falha de rede ao acessar {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise HTTPClientError(f"Timeout ao acessar {url}") from exc

    def get_text(self, url: str, extra_headers: dict[str, str] | None = None) -> str:
        body = self.get(url, extra_headers)
        if len(body) > MAX_RESPONSE_BYTES:
            raise HTTPClientError(f"Resposta de {url} excede {MAX_RESPONSE_BYTES} bytes")
        return body.decode("utf-8", errors="replace")
