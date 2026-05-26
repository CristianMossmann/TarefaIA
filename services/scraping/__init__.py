"""Camada de web scraping do AgroVision.

Coleta dados publicos e gratuitos (clima e cotacoes agro) para enriquecer
o contexto exposto no dashboard e injetado no prompt do agente.
"""

from services.scraping.scraping_service import ScrapingService


__all__ = ["ScrapingService"]
