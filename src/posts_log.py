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


def record_post(media_id: str, platform: str, news_item: dict, caption: str, image_url: str = ""):
    """Registra um post publicado no log persistente."""
    posts = _load()
    entry = {
        "media_id": media_id,
        "platform": platform,
        "title": news_item.get("title", ""),
        "source": news_item.get("source", ""),
        "url": news_item.get("url", ""),
        "image_url": image_url,
        "caption_preview": caption[:200],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {},
    }
    posts.append(entry)
    _save(posts)
    # Invalidar cache para que a próxima checagem releia o estado atualizado
    global _api_titles_cache
    _api_titles_cache = None
    logger.info(f"Post registrado no log: {entry['title'][:60]}")


def _key_words(text: str) -> set:
    """
    Extrai palavras-chave de um texto para comparação de duplicatas.
    Inclui palavras com >3 letras (pega nomes como 'lucas', 'wars', 'jedi').
    """
    return {w.lower() for w in text.split() if len(w) > 3 and w.isalpha()}


# Cache: {media_id: first_line_of_caption}
_api_titles_cache: Optional[dict] = None


def _fetch_api_recent(limit: int = 20) -> dict:
    """
    Busca os últimos N posts do Instagram via API.
    Retorna {media_id: first_line_of_caption} dos últimos 3 dias.
    Cacheado em memória durante a run.
    """
    global _api_titles_cache
    if _api_titles_cache is not None:
        return _api_titles_cache

    token = os.environ.get("FB_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    if not token or not ig_user_id:
        _api_titles_cache = {}
        return _api_titles_cache

    try:
        url = (f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
               f"?fields=id,caption,timestamp&limit={limit}&access_token={token}")
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())

        result = {}
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        for post in data.get("data", []):
            try:
                ts = datetime.fromisoformat(post.get("timestamp", "").replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except Exception:
                pass
            cap = post.get("caption", "")
            first_line = cap.split("\n")[0][:120] if cap else ""
            result[post["id"]] = first_line

        _api_titles_cache = result
        logger.info(f"Dedup API: {len(result)} posts recentes carregados (últimos 3 dias)")
        return result
    except Exception as e:
        logger.warning(f"Dedup API falhou: {e}")
        _api_titles_cache = {}
        return _api_titles_cache


def is_duplicate(title: str, platform: str = "instagram", lookback_days: int = 7,
                 url: str = "") -> bool:
    """
    Verifica duplicata em três camadas:
    0. URL exata — se a mesma URL foi publicada nos últimos 7 dias, é duplicata certa
    1. posts_log.json — overlap de palavras-chave no título (threshold: 2)
    2. Instagram API — overlap com primeiras linhas das últimas 20 captions (threshold: 2)
    """
    posts = _load()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    def within_cutoff(pub_str: str) -> bool:
        try:
            pub = datetime.fromisoformat(pub_str)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            return pub >= cutoff
        except Exception:
            return True  # se não conseguir parsear, assume recente

    # Camada 0: URL exata (mais confiável — bypassa problema de idioma)
    if url:
        for p in posts:
            if p.get("platform") != platform:
                continue
            if not within_cutoff(p.get("published_at", "")):
                continue
            if p.get("url", "") == url:
                logger.info(f"Duplicata (URL): '{title[:60]}'")
                return True

    title_words = _key_words(title)
    if not title_words:
        return False

    THRESHOLD = 2

    # Camada 1: posts_log.json (título → título)
    for p in posts:
        if p.get("platform") != platform:
            continue
        if not within_cutoff(p.get("published_at", "")):
            continue
        existing_words = _key_words(p.get("title", ""))
        overlap = title_words & existing_words
        if len(overlap) >= THRESHOLD:
            logger.info(f"Duplicata (log local): '{title[:60]}' — overlap={overlap}")
            return True

    # Camada 2: Instagram API — primeiras linhas das últimas 20 captions
    if platform == "instagram":
        recent = _fetch_api_recent(limit=20)
        for mid, first_line in recent.items():
            api_words = _key_words(first_line)
            overlap = title_words & api_words
            if len(overlap) >= THRESHOLD:
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
