"""
Alerta básica por keywords de urgencia (sin IA).
Se ejecuta en la nube como filtro rápido.
Para clasificación sofisticada, el componente local usa Claude Code.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.keywords import ESCALATION_ALERT_KEYWORDS, DEESCALATION_ALERT_KEYWORDS
from config.settings import SMTP_HOST, SMTP_PORT, EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO
from shared.models import RawArticle

logger = logging.getLogger(__name__)


def matches_urgent_keywords(article: RawArticle) -> dict | None:
    """
    Comprueba si un artículo contiene keywords de urgencia.
    Devuelve dict con tipo y keywords encontrados, o None si no es urgente.
    """
    text = f"{article.title} {article.content}".lower()

    esc_matches = [kw for kw in ESCALATION_ALERT_KEYWORDS if kw in text]
    deesc_matches = [kw for kw in DEESCALATION_ALERT_KEYWORDS if kw in text]

    # Solo alertar si hay al menos 2 keywords de escalada/desescalada
    if len(esc_matches) >= 2:
        return {"type": "ESCALADA", "keywords": esc_matches}
    if len(deesc_matches) >= 2:
        return {"type": "DESESCALADA", "keywords": deesc_matches}

    return None


def send_keyword_alert(article: RawArticle, alert_info: dict) -> bool:
    """Envía email de alerta por keywords de urgencia."""
    if not EMAIL_FROM or not EMAIL_TO:
        logger.warning("Email no configurado, saltando alerta")
        return False

    alert_type = alert_info["type"]
    keywords = ", ".join(alert_info["keywords"])

    subject = f"HORMUZ [{alert_type}]: {article.title[:80]}"

    body = f"""
ALERTA AUTOMÁTICA - Detección por Keywords (sin clasificación IA)
{'=' * 60}

Tipo: {alert_type}
Keywords detectados: {keywords}
Fuente: {article.source_id}

Título: {article.title}

Contenido:
{article.content[:1000]}

URL: {article.url}
Fecha publicación: {article.published_at}

{'=' * 60}
NOTA: Esta alerta se basa en detección de palabras clave, NO en análisis de IA.
La clasificación completa se realizará en el componente local.
"""

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Alerta enviada: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False


def check_alerts(articles: list[RawArticle]) -> list[dict]:
    """Comprueba todos los artículos y envía alertas si procede."""
    alerts = []
    for article in articles:
        alert_info = matches_urgent_keywords(article)
        if alert_info:
            alerts.append({"article": article, "alert_info": alert_info})
            send_keyword_alert(article, alert_info)
    return alerts
