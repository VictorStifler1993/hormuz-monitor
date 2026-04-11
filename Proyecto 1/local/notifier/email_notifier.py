"""
Notificador por email para el componente local.
Se activa cuando la clasificación de Claude detecta eventos de extrema relevancia.
Notifica tanto ESCALADAS como DESESCALADAS.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import (
    SMTP_HOST, SMTP_PORT, EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO,
    RELEVANCE_THRESHOLD, ESCALATION_THRESHOLD,
)
from shared.models import ClassifiedArticle

logger = logging.getLogger(__name__)


def should_notify(article: ClassifiedArticle) -> bool:
    """
    Determina si un artículo merece notificación por email.
    Se notifica tanto escalada extrema como desescalada extrema.
    """
    return (
        article.relevance_score >= RELEVANCE_THRESHOLD
        and abs(article.escalation_score) >= ESCALATION_THRESHOLD
    )


def format_email(article: ClassifiedArticle) -> tuple[str, str]:
    """Genera asunto y cuerpo del email."""
    if article.escalation_score > 0:
        tipo = "ESCALADA"
        indicador = "+"
    else:
        tipo = "DESESCALADA"
        indicador = ""

    subject = (
        f"HORMUZ [{tipo}] "
        f"({indicador}{article.escalation_score:.2f}): "
        f"{article.title[:70]}"
    )

    actors = ", ".join(article.key_actors) if article.key_actors else "N/A"
    actions = ", ".join(article.key_actions) if article.key_actions else "N/A"

    body = f"""
ALERTA HORMUZ - Clasificación IA (Claude Code)
{'=' * 60}

TIPO: {tipo}
Score de escalación: {indicador}{article.escalation_score:.2f}
Relevancia: {article.relevance_score:.2f}
Confianza: {article.confidence:.2f}
Categoría: {article.category}

RESUMEN (ES):
{article.summary_es}

ACTORES CLAVE: {actors}
ACCIONES CLAVE: {actions}

PREDICCIÓN IMPACTO EN PRECIO: {article.price_impact_prediction.upper()}

{'=' * 60}

Título original: {article.title}
Fuente: {article.source_id}
URL: {article.url}
Fecha publicación: {article.published_at}
Fecha clasificación: {article.classified_at}

{'=' * 60}
Fragmento del artículo:
{article.content_snippet}

{'=' * 60}
Sistema de Monitoreo Geopolítico del Estrecho de Ormuz
Proyecto Antigravity
"""

    return subject, body


def send_notification(article: ClassifiedArticle) -> bool:
    """Envía email de notificación para un artículo clasificado."""
    if not EMAIL_FROM or not EMAIL_TO:
        logger.warning("Email no configurado, saltando notificación")
        return False

    subject, body = format_email(article)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Notificación enviada: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error enviando notificación: {e}")
        return False


def process_notifications(articles: list[ClassifiedArticle]) -> list[ClassifiedArticle]:
    """Procesa una lista de artículos clasificados y envía notificaciones si procede."""
    notified = []
    for article in articles:
        if should_notify(article) and not article.notified:
            if send_notification(article):
                article.notified = True
                notified.append(article)
    return notified
