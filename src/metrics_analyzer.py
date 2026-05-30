"""
Analisa métricas dos posts publicados via Instagram Insights API.
Requer: instagram_manage_insights no token (adicionar no app Meta).
"""
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"


def _get(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.warning(f"API error: {e}")
        return None


def fetch_post_insights(media_id: str, token: str) -> dict:
    """
    Busca métricas de um post via Insights API.
    Métricas disponíveis: impressions, reach, likes, comments, saved, shares
    """
    metrics = ["impressions", "reach", "saved", "video_views"]
    url = (f"{GRAPH_URL}/{media_id}/insights"
           f"?metric={','.join(metrics)}&access_token={token}")
    data = _get(url)
    result = {}
    if data and "data" in data:
        for m in data["data"]:
            result[m["name"]] = m["values"][0]["value"] if m.get("values") else m.get("value", 0)

    # Likes e comments via campo direto do media
    media = _get(f"{GRAPH_URL}/{media_id}?fields=like_count,comments_count&access_token={token}")
    if media:
        result["likes"] = media.get("like_count", 0)
        result["comments"] = media.get("comments_count", 0)

    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return result


def update_all_metrics(days_back: int = 7):
    """
    Atualiza métricas de todos os posts dos últimos N dias.
    Chama: python -m metrics_analyzer
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from posts_log import _load, update_metrics

    token = os.environ.get("FB_ACCESS_TOKEN", "")
    if not token:
        logger.error("FB_ACCESS_TOKEN não definido")
        return

    posts = _load()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    updated = 0

    for p in posts:
        if p.get("platform") != "instagram":
            continue
        try:
            pub = datetime.fromisoformat(p["published_at"])
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub < cutoff:
                continue
        except Exception:
            continue

        media_id = p.get("media_id")
        if not media_id:
            continue

        metrics = fetch_post_insights(media_id, token)
        if metrics:
            update_metrics(media_id, metrics)
            updated += 1
            logger.info(f"Métricas de {p['title'][:50]}: {metrics}")

    logger.info(f"Métricas atualizadas: {updated} posts")


def performance_report(top_n: int = 5) -> str:
    """
    Gera relatório de performance dos posts.
    Retorna texto formatado para análise.
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from posts_log import _load

    posts = [p for p in _load() if p.get("platform") == "instagram" and p.get("metrics")]
    if not posts:
        return "Nenhum post com métricas disponíveis ainda."

    # Score composto: likes*3 + comments*5 + saved*10 + reach
    def score(p):
        m = p.get("metrics", {})
        return (m.get("likes", 0) * 3 +
                m.get("comments", 0) * 5 +
                m.get("saved", 0) * 10 +
                m.get("reach", 0))

    ranked = sorted(posts, key=score, reverse=True)
    lines = ["=== TOP POSTS POR ENGAJAMENTO ===\n"]
    for i, p in enumerate(ranked[:top_n], 1):
        m = p.get("metrics", {})
        lines.append(
            f"{i}. [{p['source']}] {p['title'][:60]}\n"
            f"   Likes:{m.get('likes',0)} | Comentários:{m.get('comments',0)} "
            f"| Salvos:{m.get('saved',0)} | Alcance:{m.get('reach',0)}\n"
            f"   Publicado: {p.get('published_at','')[:10]}\n"
        )

    worst = sorted(posts, key=score)
    lines.append("\n=== POSTS COM MENOR ENGAJAMENTO ===\n")
    for p in worst[:3]:
        m = p.get("metrics", {})
        lines.append(
            f"- [{p['source']}] {p['title'][:60]}\n"
            f"  Likes:{m.get('likes',0)} | Comentários:{m.get('comments',0)}\n"
        )

    return "\n".join(lines)


# Fix missing Optional import
from typing import Optional


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    update_all_metrics()
    print(performance_report())
