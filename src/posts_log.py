"""
Memória persistente de posts publicados.
Evita duplicatas entre sessões e alimenta análise de performance.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).parent.parent / "logs" / "posts_log.json"


def _load() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(posts: list[dict]):
    LOG_PATH.parent.mkdir(exist_ok=True)
    LOG_PATH.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")


def record_post(media_id: str, platform: str, news_item: dict, caption: str):
    """Registra um post publicado no log persistente."""
    posts = _load()
    entry = {
        "media_id": media_id,
        "platform": platform,
        "title": news_item.get("title", ""),
        "source": news_item.get("source", ""),
        "url": news_item.get("url", ""),
        "caption_preview": caption[:200],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {},  # preenchido por metrics_analyzer
    }
    posts.append(entry)
    _save(posts)
    logger.info(f"Post registrado no log: {entry['title'][:60]}")


def is_duplicate(title: str, platform: str = "instagram", lookback_days: int = 7) -> bool:
    """Verifica se já publicamos algo sobre esse assunto recentemente."""
    from datetime import timedelta
    posts = _load()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    title_words = {w.lower() for w in title.split() if len(w) > 4 and w.isalpha()}

    for p in posts:
        if p.get("platform") != platform:
            continue
        try:
            pub = datetime.fromisoformat(p["published_at"])
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub < cutoff:
                continue
        except Exception:
            continue

        existing_words = {w.lower() for w in p.get("title", "").split() if len(w) > 4 and w.isalpha()}
        overlap = title_words & existing_words
        if len(overlap) >= 3:
            logger.info(f"Duplicata detectada: '{title[:60]}' — overlap={overlap}")
            return True

    return False


def get_recent_posts(platform: str = "instagram", limit: int = 20) -> list[dict]:
    """Retorna os posts mais recentes de uma plataforma."""
    posts = [p for p in _load() if p.get("platform") == platform]
    return sorted(posts, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]


def update_metrics(media_id: str, metrics: dict):
    """Atualiza métricas de um post (chamado por metrics_analyzer)."""
    posts = _load()
    for p in posts:
        if p.get("media_id") == media_id:
            p["metrics"] = metrics
            break
    _save(posts)
