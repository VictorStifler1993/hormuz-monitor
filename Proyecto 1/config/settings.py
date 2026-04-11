"""
Configuración central del sistema. Carga valores desde variables de entorno.
"""

import os
from pathlib import Path

# --- Rutas ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_NEWS_DIR = DATA_DIR / "raw" / "news"
RAW_PRICES_DIR = DATA_DIR / "raw" / "prices"
PROCESSED_DIR = DATA_DIR / "processed"
CALIBRATION_DIR = DATA_DIR / "calibration"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "hormuz.db"
STATE_FILE = DATA_DIR / "state.json"

# --- APIs de noticias ---
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "")
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")

# --- APIs de precios ---
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

# --- Email (SMTP) ---
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO = [e.strip() for e in os.environ.get("EMAIL_TO", "").split(",") if e.strip()]

# --- Umbrales de notificación ---
RELEVANCE_THRESHOLD = float(os.environ.get("RELEVANCE_THRESHOLD", "0.85"))
ESCALATION_THRESHOLD = float(os.environ.get("ESCALATION_THRESHOLD", "0.7"))

# --- Scraping ---
SCRAPE_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
MAX_ARTICLES_PER_SOURCE = 20

# --- Símbolos de petróleo ---
OIL_SYMBOLS = {
    "WTI": "CL=F",
    "Brent": "BZ=F",
}

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
