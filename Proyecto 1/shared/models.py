"""
Modelos de datos compartidos entre componentes cloud y local.
Estos dataclasses son la "lengua común" de todo el sistema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib
import json


@dataclass
class RawArticle:
    """Artículo en bruto tal como sale del scraper."""
    source_id: str          # ej: "rss_reuters", "gnews", "newsapi"
    url: str
    title: str
    content: str            # texto completo o snippet
    published_at: datetime
    scraped_at: datetime
    language: str = "en"
    raw_metadata: dict = field(default_factory=dict)

    @property
    def article_id(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "published_at": self.published_at.isoformat(),
            "scraped_at": self.scraped_at.isoformat(),
            "language": self.language,
            "raw_metadata": self.raw_metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RawArticle":
        return cls(
            source_id=d["source_id"],
            url=d["url"],
            title=d["title"],
            content=d["content"],
            published_at=datetime.fromisoformat(d["published_at"]),
            scraped_at=datetime.fromisoformat(d["scraped_at"]),
            language=d.get("language", "en"),
            raw_metadata=d.get("raw_metadata", {}),
        )


@dataclass
class ClassifiedArticle:
    """Artículo clasificado por el subagente Claude Code."""
    article_id: str
    source_id: str
    url: str
    title: str
    content_snippet: str        # primeros 500 chars
    published_at: datetime
    classified_at: datetime
    relevance_score: float      # 0.0 a 1.0
    escalation_score: float     # -1.0 (desescalada) a +1.0 (escalada)
    category: str               # military|diplomatic|economic|sanctions|shipping|other
    key_actors: list[str] = field(default_factory=list)
    key_actions: list[str] = field(default_factory=list)
    summary_es: str = ""
    price_impact_prediction: str = "neutral"  # up|down|neutral
    confidence: float = 0.0
    claude_raw_response: str = ""
    notified: bool = False

    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "content_snippet": self.content_snippet,
            "published_at": self.published_at.isoformat(),
            "classified_at": self.classified_at.isoformat(),
            "relevance_score": self.relevance_score,
            "escalation_score": self.escalation_score,
            "category": self.category,
            "key_actors": self.key_actors,
            "key_actions": self.key_actions,
            "summary_es": self.summary_es,
            "price_impact_prediction": self.price_impact_prediction,
            "confidence": self.confidence,
            "claude_raw_response": self.claude_raw_response,
            "notified": self.notified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClassifiedArticle":
        return cls(
            article_id=d["article_id"],
            source_id=d["source_id"],
            url=d["url"],
            title=d["title"],
            content_snippet=d["content_snippet"],
            published_at=datetime.fromisoformat(d["published_at"]),
            classified_at=datetime.fromisoformat(d["classified_at"]),
            relevance_score=d["relevance_score"],
            escalation_score=d["escalation_score"],
            category=d["category"],
            key_actors=d.get("key_actors", []),
            key_actions=d.get("key_actions", []),
            summary_es=d.get("summary_es", ""),
            price_impact_prediction=d.get("price_impact_prediction", "neutral"),
            confidence=d.get("confidence", 0.0),
            claude_raw_response=d.get("claude_raw_response", ""),
            notified=d.get("notified", False),
        )


@dataclass
class OilPrice:
    """Precio del petróleo en un momento dado."""
    timestamp: datetime
    symbol: str             # "CL=F" (WTI) o "BZ=F" (Brent)
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str             # "yfinance" o "alphavantage"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OilPrice":
        return cls(
            timestamp=datetime.fromisoformat(d["timestamp"]),
            symbol=d["symbol"],
            open=d["open"],
            high=d["high"],
            low=d["low"],
            close=d["close"],
            volume=d["volume"],
            source=d["source"],
        )


@dataclass
class CorrelationResult:
    """Resultado de un análisis de correlación."""
    analysis_id: str
    computed_at: datetime
    news_window_hours: int
    price_window_hours: int
    lag_minutes: int
    correlation_coefficient: float
    p_value: float
    sample_size: int
    source_id: Optional[str] = None     # None = todas las fuentes
    category: Optional[str] = None
    method: str = "spearman"            # pearson|spearman|granger
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "computed_at": self.computed_at.isoformat(),
            "news_window_hours": self.news_window_hours,
            "price_window_hours": self.price_window_hours,
            "lag_minutes": self.lag_minutes,
            "correlation_coefficient": self.correlation_coefficient,
            "p_value": self.p_value,
            "sample_size": self.sample_size,
            "source_id": self.source_id,
            "category": self.category,
            "method": self.method,
            "notes": self.notes,
        }


@dataclass
class CalibrationRecord:
    """Registro de calibración de la escala de escalación."""
    calibrated_at: datetime
    threshold_name: str         # ej: "high_escalation", "moderate_deescalation"
    old_threshold: float
    new_threshold: float
    sample_size: int
    avg_price_impact: float     # cambio medio de precio asociado
    notes: str = ""
