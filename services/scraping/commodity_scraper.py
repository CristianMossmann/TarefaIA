"""Scraping de cotacoes de commodities agricolas.

Fonte primaria: pagina publica do `noticiasagricolas.com.br` (cotacoes
em HTML). Como o layout de paginas publicas muda com frequencia, o
parser foi desenhado para ser tolerante:

- Procura blocos `<tr>` ou linhas com nomes conhecidos (soja, milho,
  boi gordo, cafe, trigo).
- Extrai a primeira sequencia numerica plausivel encontrada na linha.
- Se nada for encontrado (site mudou layout, esta fora do ar etc.), o
  scraper levanta `HTTPClientError` e o servico devolve `status="error"`
  com a fonte declarada.

Importante: este modulo NUNCA inventa valores. Se a fonte falhar, o
chamador recebe erro explicito e exibe estado de "indisponivel".
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any

from services.scraping.http_client import HTTPClient, HTTPClientError


logger = logging.getLogger(__name__)

COMMODITIES_URL = "https://www.noticiasagricolas.com.br/cotacoes/"

# Termos que buscamos no HTML. Cada chave eh o slug padronizado, valores
# sao palavras-alvo que podem aparecer no texto (case-insensitive).
COMMODITY_TARGETS: dict[str, list[str]] = {
    "soja": ["soja"],
    "milho": ["milho"],
    "boi_gordo": ["boi gordo", "boi-gordo"],
    "cafe": ["cafe", "café"],
    "trigo": ["trigo"],
}

# Preco plausivel: digitos seguidos OBRIGATORIAMENTE por separador decimal +
# 2 a 4 casas. Isso elimina datas (26, 2026) e numeros inteiros aleatorios.
NUMBER_RE = re.compile(r"\b(\d{1,6}[.,]\d{2,4})\b")


class _TextOnlyParser(HTMLParser):
    """Coleta apenas texto visivel (sem tags) preservando quebras de linha."""

    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):  # noqa: D401, ARG002
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag):  # noqa: D401
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"tr", "li", "p", "br", "div"}:
            self._chunks.append("\n")

    def handle_data(self, data):  # noqa: D401
        if self._skip:
            return
        cleaned = data.strip()
        if cleaned:
            self._chunks.append(cleaned + " ")

    def get_text(self) -> str:
        return "".join(self._chunks)


class CommodityScraper:
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client

    def fetch(self) -> dict[str, Any]:
        body = self.http_client.get_text(COMMODITIES_URL)
        parser = _TextOnlyParser()
        parser.feed(body)
        text = parser.get_text()

        prices = self._extract_prices(text)
        if not prices:
            raise HTTPClientError(
                "Nenhuma cotacao reconhecida na pagina publica (layout pode ter mudado)."
            )

        return {
            "source": COMMODITIES_URL,
            "prices": prices,
        }

    @staticmethod
    def _extract_prices(text: str) -> list[dict[str, Any]]:
        prices: list[dict[str, Any]] = []
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        seen: set[str] = set()

        for line in lines:
            lower = line.lower()
            # Pula linhas que mencionam varias commodities juntas (titulo/SEO).
            mentioned = sum(
                1 for terms in COMMODITY_TARGETS.values() if any(t in lower for t in terms)
            )
            if mentioned >= 3:
                continue

            for slug, terms in COMMODITY_TARGETS.items():
                if slug in seen:
                    continue
                if not any(term in lower for term in terms):
                    continue
                match = NUMBER_RE.search(line)
                if not match:
                    continue
                prices.append({
                    "commodity": slug,
                    "value_raw": match.group(1),
                    "currency": "BRL",
                    "context": line[:160],
                })
                seen.add(slug)

        return prices
