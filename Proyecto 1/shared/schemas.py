"""
Esquemas SQL para la base de datos SQLite.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_articles (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT,
    published_at TIMESTAMP,
    scraped_at TIMESTAMP NOT NULL,
    language TEXT DEFAULT 'en',
    raw_metadata TEXT
);

CREATE TABLE IF NOT EXISTS classified_articles (
    article_id TEXT PRIMARY KEY REFERENCES raw_articles(id),
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    content_snippet TEXT,
    published_at TIMESTAMP,
    classified_at TIMESTAMP NOT NULL,
    relevance_score REAL NOT NULL,
    escalation_score REAL NOT NULL,
    category TEXT NOT NULL,
    key_actors TEXT,
    key_actions TEXT,
    summary_es TEXT,
    price_impact_prediction TEXT DEFAULT 'neutral',
    confidence REAL DEFAULT 0.0,
    claude_raw_response TEXT,
    notified INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oil_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT NOT NULL,
    UNIQUE(timestamp, symbol)
);

CREATE TABLE IF NOT EXISTS correlation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    news_window_hours INTEGER,
    price_window_hours INTEGER,
    lag_minutes INTEGER,
    correlation_coefficient REAL,
    p_value REAL,
    sample_size INTEGER,
    source_id TEXT,
    category TEXT,
    method TEXT DEFAULT 'spearman',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS calibration_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calibrated_at TIMESTAMP NOT NULL,
    threshold_name TEXT NOT NULL,
    old_threshold REAL,
    new_threshold REAL,
    sample_size INTEGER,
    avg_price_impact REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS data_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP NOT NULL,
    gap_start TIMESTAMP NOT NULL,
    gap_end TIMESTAMP NOT NULL,
    gap_type TEXT NOT NULL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_published ON raw_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_articles(source_id);
CREATE INDEX IF NOT EXISTS idx_classified_escalation ON classified_articles(escalation_score);
CREATE INDEX IF NOT EXISTS idx_classified_published ON classified_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_classified_category ON classified_articles(category);
CREATE INDEX IF NOT EXISTS idx_oil_timestamp ON oil_prices(timestamp, symbol);
CREATE INDEX IF NOT EXISTS idx_correlation_computed ON correlation_results(computed_at);
"""
