"""Fachada do pacote de scraping.

Orquestra cliente HTTP + rate limiter + cache + scrapers especificos.
Exposto para `app.py` como `ScrapingService`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from services.scraping.cache import TTLCache
from services.scraping.commodity_scraper import CommodityScraper
from services.scraping.http_client import HTTPClient, HTTPClientError
from services.scraping.rate_limiter import RateLimitExceeded, RateLimiter
from services.scraping.weather_scraper import WeatherScraper


logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ok(data: dict[str, Any], source: str) -> dict[str, Any]:
    return {"status": "ok", "source": source, "fetched_at": _now_iso(), "data": data}


def _error(message: str, source: str) -> dict[str, Any]:
    return {
        "status": "error",
        "source": source,
        "fetched_at": _now_iso(),
        "message": message,
        "data": None,
    }


class ScrapingService:
    def __init__(
        self,
        weather_location: str,
        weather_ttl_seconds: int,
        commodities_ttl_seconds: int,
        request_timeout: int,
        max_requests_per_minute: int,
    ):
        self.weather_location = weather_location
        self.weather_ttl = weather_ttl_seconds
        self.commodities_ttl = commodities_ttl_seconds

        self._http = HTTPClient(timeout_seconds=request_timeout)
        self._cache = TTLCache()
        self._rate_limiter = RateLimiter(max_requests_per_minute=max_requests_per_minute)
        self._weather = WeatherScraper(self._http)
        self._commodities = CommodityScraper(self._http)

    def get_weather(self) -> dict[str, Any]:
        cache_key = f"weather::{self.weather_location}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        source = "wttr.in"
        try:
            self._rate_limiter.acquire()
            data = self._weather.fetch(self.weather_location)
        except RateLimitExceeded as exc:
            logger.warning("Rate limit no scraping de clima: %s", exc)
            return _error("Limite de requisicoes atingido. Tente em instantes.", source)
        except HTTPClientError as exc:
            logger.warning("Falha ao obter clima: %s", exc)
            return _error("Fonte de clima indisponivel no momento.", source)
        except Exception as exc:  # noqa: BLE001 - blindagem: scraping nao pode derrubar a API
            logger.exception("Erro inesperado no scraping de clima: %s", exc)
            return _error("Erro inesperado ao consultar clima.", source)

        result = _ok(data, source)
        self._cache.set(cache_key, result, self.weather_ttl)
        return result

    def get_commodities(self) -> dict[str, Any]:
        cache_key = "commodities::default"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        source = "noticiasagricolas.com.br"
        try:
            self._rate_limiter.acquire()
            data = self._commodities.fetch()
        except RateLimitExceeded as exc:
            logger.warning("Rate limit no scraping de cotacoes: %s", exc)
            return _error("Limite de requisicoes atingido. Tente em instantes.", source)
        except HTTPClientError as exc:
            logger.warning("Falha ao obter cotacoes: %s", exc)
            return _error("Fonte de cotacoes indisponivel no momento.", source)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erro inesperado no scraping de cotacoes: %s", exc)
            return _error("Erro inesperado ao consultar cotacoes.", source)

        result = _ok(data, source)
        self._cache.set(cache_key, result, self.commodities_ttl)
        return result

    def weather_snapshot_for_agent(self) -> str | None:
        """Retorna um resumo textual do clima para anexar ao prompt do LLM.

        Se o scraping nao tiver dado valido em cache (e a fonte estiver
        fora), retorna None — o agente segue sem o contexto extra.
        """
        cached = self._cache.get(f"weather::{self.weather_location}")
        if cached is None or cached.get("status") != "ok":
            return None

        current = (cached.get("data") or {}).get("current") or {}
        if not current:
            return None

        return (
            "Contexto climatico atual (scraping externo):\n"
            f"- Local: {self.weather_location}\n"
            f"- Condicao: {current.get('description', '?')}\n"
            f"- Temperatura: {current.get('temperature_c', '?')}°C "
            f"(sensacao {current.get('feels_like_c', '?')}°C)\n"
            f"- Umidade: {current.get('humidity_pct', '?')}% | Vento: {current.get('wind_kmph', '?')} km/h\n"
            f"- Precipitacao: {current.get('precip_mm', '?')} mm"
        )
