"""
Clasificador de noticias mediante subagente de Claude Code.
Usa la suscripción existente de Claude Code, NO la API de pago.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone

from shared.models import RawArticle, ClassifiedArticle

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT_TEMPLATE = """Eres un analista geopolítico experto especializado en el Estrecho de Ormuz y su impacto en los mercados petroleros.

Clasifica la siguiente noticia. Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown.

Noticia:
Título: {title}
Fuente: {source_id}
Fecha: {published_at}
Contenido: {content}

Responde con este JSON exacto (sin bloques de código, solo el JSON):
{{
    "relevance_score": <float 0.0-1.0, relevancia para tensiones en el Estrecho de Ormuz>,
    "escalation_score": <float -1.0 a +1.0, donde -1=máxima desescalada, 0=neutral, +1=máxima escalada>,
    "category": "<military|diplomatic|economic|sanctions|shipping|other>",
    "key_actors": ["actor1", "actor2"],
    "key_actions": ["acción1", "acción2"],
    "summary_es": "<resumen en español de 1-2 oraciones>",
    "price_impact_prediction": "<up|down|neutral>",
    "confidence": <float 0.0-1.0>
}}"""


def classify_article(article: RawArticle) -> ClassifiedArticle | None:
    """
    Clasifica un artículo usando Claude Code como subagente.
    Ejecuta `claude -p` con el prompt de clasificación.
    """
    prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
        title=article.title,
        source_id=article.source_id,
        published_at=article.published_at.isoformat(),
        content=article.content[:2000],
    )

    try:
        import os

        # Encontrar claude.cmd en Windows
        claude_cmd = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
        if not os.path.exists(claude_cmd):
            import shutil
            claude_cmd = shutil.which("claude") or "claude"

        # Asegurar que Node.js está en el PATH (necesario en algunos entornos Windows)
        env = os.environ.copy()
        node_paths = [
            os.path.join(os.environ.get("ProgramFiles", ""), "nodejs"),
            os.path.join(os.environ.get("APPDATA", ""), "npm"),
        ]
        for p in node_paths:
            if os.path.isdir(p) and p not in env.get("PATH", ""):
                env["PATH"] = p + os.pathsep + env.get("PATH", "")

        # Pasar prompt via pipe stdin — seguro, sin límite de longitud de argumentos
        result = subprocess.run(
            [claude_cmd, "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
            shell=(os.name == "nt"),
            env=env,
        )

        if result.returncode != 0:
            logger.error(f"Claude Code falló (exit {result.returncode}): {result.stderr}")
            return None

        # Parsear respuesta de Claude Code
        response_text = result.stdout.strip()
        claude_response = json.loads(response_text)

        # El output de claude --output-format json tiene la respuesta en "result"
        if "result" in claude_response:
            content = claude_response["result"]
        else:
            content = response_text

        # Extraer el JSON de clasificación del contenido
        classification = _extract_json(content)
        if not classification:
            logger.error(f"No se pudo extraer JSON de la respuesta: {content[:200]}")
            return None

        return ClassifiedArticle(
            article_id=article.article_id,
            source_id=article.source_id,
            url=article.url,
            title=article.title,
            content_snippet=article.content[:500],
            published_at=article.published_at,
            classified_at=datetime.now(timezone.utc),
            relevance_score=float(classification.get("relevance_score", 0)),
            escalation_score=float(classification.get("escalation_score", 0)),
            category=classification.get("category", "other"),
            key_actors=classification.get("key_actors", []),
            key_actions=classification.get("key_actions", []),
            summary_es=classification.get("summary_es", ""),
            price_impact_prediction=classification.get("price_impact_prediction", "neutral"),
            confidence=float(classification.get("confidence", 0)),
            claude_raw_response=content if isinstance(content, str) else json.dumps(content),
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout clasificando artículo: {article.title[:50]}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando respuesta JSON: {e}")
        return None
    except FileNotFoundError:
        logger.error(
            "Claude Code CLI no encontrado. Asegúrate de que 'claude' está en el PATH. "
            "Instálalo con: npm install -g @anthropic-ai/claude-code"
        )
        return None
    except Exception as e:
        logger.error(f"Error inesperado clasificando: {e}")
        return None


def _extract_json(text: str) -> dict | None:
    """Intenta extraer un objeto JSON de un texto que puede tener contenido extra."""
    if isinstance(text, dict):
        return text

    # Intentar parsear directamente
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Buscar JSON dentro del texto (entre { y })
    if isinstance(text, str):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    return None


def classify_batch(articles: list[RawArticle]) -> list[ClassifiedArticle]:
    """Clasifica un lote de artículos secuencialmente."""
    classified = []
    total = len(articles)

    for i, article in enumerate(articles, 1):
        logger.info(f"Clasificando [{i}/{total}]: {article.title[:60]}...")
        result = classify_article(article)
        if result:
            classified.append(result)
            logger.info(
                f"  → relevancia={result.relevance_score:.2f}, "
                f"escalación={result.escalation_score:+.2f}, "
                f"categoría={result.category}"
            )
        else:
            logger.warning(f"  → No se pudo clasificar")

    logger.info(f"Clasificados: {len(classified)}/{total}")
    return classified
