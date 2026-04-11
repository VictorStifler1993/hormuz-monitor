"""
Clase base abstracta para todos los scrapers.
"""

from abc import ABC, abstractmethod
from shared.models import RawArticle


class BaseScraper(ABC):
    """Interfaz que todos los scrapers deben implementar."""

    @abstractmethod
    def scrape(self) -> list[RawArticle]:
        """Ejecuta el scraping y devuelve artículos en bruto."""
        ...

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Identificador único de esta fuente."""
        ...

    @property
    def rate_limit_per_day(self) -> int:
        """Límite de requests por día. -1 = ilimitado."""
        return -1
