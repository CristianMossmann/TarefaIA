"""Scraping de clima atual + previsao usando wttr.in.

wttr.in eh um servico publico e gratuito (sem chave de API). O formato
`?format=j1` devolve JSON estruturado (clima atual + previsao 3 dias).

Por que clima eh util para o AgroVision:
- O sistema detecta movimentacao de pessoas, veiculos e maquinas em
  ambiente agricola. O comportamento "normal" depende fortemente do
  clima: em chuva forte, AUSENCIA de maquinas eh esperada; em dia seco,
  ausencia pode indicar paralisacao.
- O contexto climatico eh injetado no prompt do agente Ollama para
  melhor qualificar os alertas.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from services.scraping.http_client import HTTPClient, HTTPClientError


logger = logging.getLogger(__name__)

WTTR_BASE = "https://wttr.in"


class WeatherScraper:
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client

    def fetch(self, location: str) -> dict[str, Any]:
        url = f"{WTTR_BASE}/{quote(location)}?format=j1&lang=pt"
        body = self.http_client.get_text(url)

        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPClientError(f"Resposta do wttr.in nao eh JSON: {exc}") from exc

        return self._normalize(location, raw)

    @staticmethod
    def _safe_str(value: Any, max_len: int = 120) -> str:
        text = "" if value is None else str(value)
        return text.strip()[:max_len]

    def _normalize(self, location: str, raw: dict[str, Any]) -> dict[str, Any]:
        current_list = raw.get("current_condition") or []
        forecast_list = raw.get("weather") or []

        current: dict[str, Any] = {}
        if current_list:
            c = current_list[0]
            description_block = (c.get("lang_pt") or c.get("weatherDesc") or [{}])
            description = self._safe_str(description_block[0].get("value")) if description_block else ""
            current = {
                "temperature_c": self._safe_str(c.get("temp_C")),
                "feels_like_c": self._safe_str(c.get("FeelsLikeC")),
                "humidity_pct": self._safe_str(c.get("humidity")),
                "wind_kmph": self._safe_str(c.get("windspeedKmph")),
                "precip_mm": self._safe_str(c.get("precipMM")),
                "description": description,
                "observed_at": self._safe_str(c.get("localObsDateTime")),
            }

        forecast: list[dict[str, Any]] = []
        for day in forecast_list[:3]:
            forecast.append({
                "date": self._safe_str(day.get("date")),
                "max_c": self._safe_str(day.get("maxtempC")),
                "min_c": self._safe_str(day.get("mintempC")),
                "rain_chance_pct": self._safe_str(
                    (day.get("hourly") or [{}])[len(day.get("hourly") or [{}]) // 2].get("chanceofrain")
                ),
            })

        return {
            "location": location,
            "current": current,
            "forecast": forecast,
        }
