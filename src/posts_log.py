"""
Memória persistente de posts publicados.
Dedup em duas camadas:
  1. posts_log.json (local, persistido via git commit no workflow)
  2. Instagram API (fallback sempre disponível mesmo sem o arquivo local)
"""
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).parent.parent / "logs" / "posts_log.json"

# Cache em memória para evitar múltiplas chamadas à API na mesma run
_api_words_cache: Optional[set] = None


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
        "metrics": {},
    }
    posts.append(entry)
    _save(posts)
    # Invalidar cache para que a próxima checagem releia o estado atualizado
    global _api_words_cache
    _api_words_cache = None
    logger.info(f"Post registrado no log: {entry['title'][:60]}")


def _fetch_api_posted_words() -> set:
    """
    Fallback: busca os últimos 50 posts do Instagram via API e extrai palavras.
    Usado quando posts_log.json não está disponível (primeira run, runner efêmero).
    Resultado cacheado em memória durante a run.
    """
    global _api_words_cache
    if _api_words_cache is not None:
        return _api_words_cache

    token = os.environ.get("FB_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    if not token or not ig_user_id:
        _api_words_cache = set()
        return _api_words_cache

    try:
        url = (f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
               f"?fields=caption,timestamp&limit=50&access_token={token}")
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())

        words = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for post in data.get("data", []):
            try:
                ts = datetime.fromisoformat(post.get("timestamp", "").replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except Exception:
                pass
            cap = post.get("caption", "").lower()
            words.update(w for w in cap.split() if len(w) > 4 and w.isalpha())

        _api_words_cache = words
        logger.info(f"Dedup API: {len(words)} palavras carregadas dos últimos 50 posts")
        return words
    except Exception as e:
        logger.warning(f"Dedup API falhou: {e}")
        _api_words_cache = set()
        return _api_words_cache


def is_duplicate(title: str, platform: str = "instagram", lookback_days: int = 7) -> bool:
    """
    Verifica duplicata em duas camadas:
    1. posts_log.json — checagem por título exato (preciso, cobre posts desta run)
    2. Instagram API — checagem por sobreposição de palavras nas captions (fallback robusto)
    """
    title_words = {w.lower() for w in title.split() if len(w) > 4 and w.isalpha()}
    if not title_words:
        return False

    # Camada 1: posts_log.json (título → título)
    posts = _load()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
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
        if len(title_words & existing_words) >= 3:
            logger.info(f"Duplicata (log local): '{title[:60]}'")
            return True

    # Camada 2: Instagram API — palavras das captions publicadas
    if platform == "instagram":
        api_words = _fetch_api_posted_words()
        overlap = title_words & api_words
        if len(overlap) >= 3:
            logger.info(f"Duplicata (API Instagram): '{title[:60]}' — overlap={overlap}")
            return True

    return False


def get_recent_posts(platform: str = "instagram", limit: int = 20) -> list[dict]:
    posts = [p for p in _load() if p.get("platform") == platform]
    return sorted(posts, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]


def update_metrics(media_id: str, metrics: dict):
    posts = _load()
    for p in posts:
        if p.get("media_id") == media_id:
            p["metrics"] = metrics
            break
    _save(posts)
