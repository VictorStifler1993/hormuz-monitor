"""
Términos de búsqueda para scraping y filtrado de noticias.
"""

# Términos principales sobre el Estrecho de Ormuz y tensiones en la zona
HORMUZ_KEYWORDS = [
    # Geografía
    "Strait of Hormuz",
    "Estrecho de Ormuz",
    "Persian Gulf",
    "Golfo Pérsico",
    "Gulf of Oman",

    # Actores militares
    "IRGC",
    "Iran navy",
    "Iran military",
    "US Navy Gulf",
    "Fifth Fleet",
    "CENTCOM",
    "Revolutionary Guard",

    # Eventos típicos
    "tanker seizure",
    "oil tanker Iran",
    "Iran drone",
    "Iran missile",
    "Houthi ship",
    "Houthi Red Sea",
    "Yemen shipping",
]

# Términos sobre petróleo y energía
OIL_KEYWORDS = [
    "oil tanker",
    "crude oil",
    "oil price",
    "OPEC",
    "Iran sanctions oil",
    "oil supply disruption",
    "pipeline attack",
    "oil embargo",
    "petroleum export",
    "energy crisis Middle East",
]

# Indicadores de escalada (para alertas por keywords en cloud, sin IA)
ESCALATION_ALERT_KEYWORDS = [
    "attack",
    "strike",
    "missile",
    "blockade",
    "seizure",
    "captured",
    "explosion",
    "military operation",
    "war",
    "retaliation",
    "bombing",
    "naval clash",
    "shoot down",
    "sunk",
    "destroyed",
]

# Indicadores de desescalada (para alertas por keywords en cloud, sin IA)
DEESCALATION_ALERT_KEYWORDS = [
    "peace deal",
    "ceasefire",
    "agreement",
    "diplomatic",
    "negotiations",
    "withdraw",
    "de-escalation",
    "truce",
    "released",
    "sanctions lifted",
    "normalization",
]

# Queries combinadas para APIs de noticias (máximo eficiencia por request)
SEARCH_QUERIES = [
    "Strait of Hormuz",
    "Iran oil tanker",
    "Persian Gulf military",
    "Houthi shipping attack",
    "Iran sanctions oil",
]

# Feeds RSS a monitorear
RSS_FEEDS = {
    "google_news_hormuz": "https://news.google.com/rss/search?q=strait+of+hormuz&hl=en&gl=US&ceid=US:en",
    "google_news_iran_oil": "https://news.google.com/rss/search?q=iran+oil+tanker&hl=en&gl=US&ceid=US:en",
    "google_news_persian_gulf": "https://news.google.com/rss/search?q=persian+gulf+military&hl=en&gl=US&ceid=US:en",
    "google_news_houthi": "https://news.google.com/rss/search?q=houthi+shipping&hl=en&gl=US&ceid=US:en",
    "bbc_middleeast": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
}
