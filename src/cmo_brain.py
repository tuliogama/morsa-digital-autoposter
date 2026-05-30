"""
CMO Brain — análise diária de performance, trends e concorrentes.
Gera um Day Brief que orienta toda a curadoria e geração de conteúdo do dia.
"""
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"
BRIEF_PATH = Path(__file__).parent.parent / "logs" / "day_brief.json"


# ---------------------------------------------------------------------------
# Métricas do Instagram
# ---------------------------------------------------------------------------

def _api_get(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.warning(f"API error: {e}")
        return None


def fetch_recent_media(ig_user_id: str, token: str, limit: int = 20) -> list[dict]:
    """Busca posts recentes com métricas básicas disponíveis sem insights."""
    url = (f"{GRAPH_URL}/{ig_user_id}/media"
           f"?fields=id,caption,timestamp,like_count,comments_count"
           f"&limit={limit}&access_token={token}")
    data = _api_get(url)
    if not data:
        return []
    return data.get("data", [])


def fetch_post_insights(media_id: str, token: str) -> dict:
    """
    Busca insights de um post.
    Requer instagram_manage_insights no token — graceful fallback se não disponível.
    """
    metrics = "impressions,reach,saved"
    url = f"{GRAPH_URL}/{media_id}/insights?metric={metrics}&access_token={token}"
    data = _api_get(url)
    result = {}
    if data and "data" in data:
        for m in data["data"]:
            result[m["name"]] = m.get("value", 0)
    return result


def analyze_performance(posts: list[dict], token: str) -> dict:
    """
    Analisa posts recentes e identifica padrões de performance.
    Retorna sumário estruturado.
    """
    if not posts:
        return {"status": "sem_dados"}

    enriched = []
    for p in posts[:10]:  # top 10 mais recentes
        likes = p.get("like_count", 0)
        comments = p.get("comments_count", 0)
        caption = p.get("caption", "")

        # Tentar buscar insights (salvo, alcance)
        insights = fetch_post_insights(p["id"], token)
        saved = insights.get("saved", 0)
        reach = insights.get("reach", 0)

        # Score composto
        score = likes * 3 + comments * 5 + saved * 10 + (reach // 100)

        # Detectar tipo de hook pela primeira linha
        first_line = caption.split("\n")[0][:80] if caption else ""
        hook_type = _classify_hook(first_line)

        enriched.append({
            "id": p["id"],
            "caption_preview": first_line,
            "hook_type": hook_type,
            "likes": likes,
            "comments": comments,
            "saved": saved,
            "reach": reach,
            "score": score,
            "timestamp": p.get("timestamp", ""),
        })

    enriched.sort(key=lambda x: x["score"], reverse=True)

    # Identificar padrões dos top performers
    top3 = enriched[:3]
    bottom3 = enriched[-3:]

    top_hooks = [p["hook_type"] for p in top3]
    avg_score = sum(p["score"] for p in enriched) / len(enriched) if enriched else 0

    return {
        "total_posts_analyzed": len(enriched),
        "avg_engagement_score": round(avg_score, 1),
        "top_performers": top3,
        "low_performers": bottom3,
        "best_hook_types": top_hooks,
        "best_post_preview": top3[0]["caption_preview"] if top3 else "",
    }


def _classify_hook(first_line: str) -> str:
    line = first_line.lower()
    if "?" in first_line:
        return "pergunta"
    elif any(w in line for w in ["vai", "chegou", "confirmado", "oficial", "anunciado"]):
        return "anuncio_direto"
    elif any(w in line for w in ["anos", "meses", "semanas", "espera", "finalmente"]):
        return "expectativa_cumprida"
    elif any(w in line for w in ["nao", "nunca", "jamais", "impossivel", "absurdo"]):
        return "provocacao"
    elif first_line and first_line[0].isdigit():
        return "dado_numero"
    else:
        return "afirmacao_direta"


# ---------------------------------------------------------------------------
# Análise de concorrentes (via RSS que já temos)
# ---------------------------------------------------------------------------

def analyze_competitors() -> dict:
    """
    Verifica o que os principais portais BR estão cobrindo hoje.
    Usa os feeds RSS já disponíveis como proxy de concorrentes.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from news_fetcher import _fetch_url, _text, _parse_date
    import xml.etree.ElementTree as ET

    competitor_feeds = [
        ("IGN Brasil",          "https://br.ign.com/feed.xml"),
        ("Cinema com Rapadura", "https://cinemacomrapadura.com.br/feed/"),
        ("GameBlast",           "https://www.gameblast.com.br/feeds/posts/default"),
        ("AnimeUnited",         "https://animeunited.com.br/feed/"),
    ]

    today = datetime.now(timezone.utc).date()
    topics_today = []

    for name, feed_url in competitor_feeds:
        raw = _fetch_url(feed_url)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except Exception:
            continue

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for entry in entries[:5]:
            title = (_text(entry, "title") or _text(entry, "atom:title", ns) or "").strip()
            pub_raw = (_text(entry, "pubDate") or _text(entry, "atom:published", ns) or "")
            ts = _parse_date(pub_raw)
            if ts and ts.date() == today and title:
                topics_today.append({"source": name, "title": title})

    return {
        "topics_covered_today": topics_today,
        "sources_active": list({t["source"] for t in topics_today}),
        "total_stories": len(topics_today),
    }


# ---------------------------------------------------------------------------
# Day Brief — síntese com Claude
# ---------------------------------------------------------------------------

def generate_day_brief(
    performance: dict,
    competitor_data: dict,
    trending_topics: list[str],
    recent_post_titles: list[str],
) -> dict:
    """
    Usa Claude para sintetizar toda a análise em orientações concretas para o dia.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from content_generator import _call_claude

    perf_summary = json.dumps(performance, ensure_ascii=False, indent=2)
    competitor_summary = "\n".join(
        f"- [{t['source']}] {t['title']}" for t in competitor_data.get("topics_covered_today", [])[:10]
    ) or "Nenhuma cobertura identificada hoje"

    trends_summary = "\n".join(f"- {t}" for t in trending_topics[:10]) or "Sem trends identificadas"

    recent_titles = "\n".join(f"- {t}" for t in recent_post_titles[:15]) or "Nenhum post recente"

    prompt = f"""Você é o CMO da Morsa Digital — perfil brasileiro de cultura pop/nerd/geek no Instagram.

MÉTRICAS DOS ÚLTIMOS POSTS:
{perf_summary}

O QUE OS PORTAIS BR ESTÃO COBRINDO HOJE:
{competitor_summary}

TRENDS IDENTIFICADAS AGORA:
{trends_summary}

POSTS QUE JÁ PUBLICAMOS (NÃO REPETIR):
{recent_titles}

Com base nessa análise, gere um Day Brief em JSON com exatamente este formato:
{{
  "strategy_note": "1-2 frases sobre o direcionamento estratégico do dia",
  "prioritize_categories": ["categoria1", "categoria2", "categoria3"],
  "prioritize_sources": ["fonte1", "fonte2"],
  "avoid_topics": ["tópico já coberto 1", "tópico já coberto 2"],
  "recommended_hook_style": "estilo de hook que está performando melhor hoje",
  "content_angle": "ângulo editorial para se diferenciar dos concorrentes hoje",
  "topics_to_explore": ["assunto em alta 1", "assunto em alta 2", "assunto em alta 3"],
  "engagement_insight": "o que está gerando mais engajamento baseado nos dados"
}}

Responda APENAS o JSON, sem texto adicional."""

    try:
        result = _call_claude(
            "Você é um CMO experiente de mídia digital brasileira, especializado em cultura pop e engajamento no Instagram.",
            prompt,
        )
        # Extrair JSON da resposta
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        brief = json.loads(result.strip())
        brief["generated_at"] = datetime.now(timezone.utc).isoformat()
        brief["date"] = datetime.now(timezone.utc).date().isoformat()
        return brief
    except Exception as e:
        logger.warning(f"Falha ao gerar Day Brief com Claude: {e}")
        return {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "strategy_note": "Análise automática indisponível — usando critérios padrão.",
            "prioritize_categories": ["anime", "games", "filmes", "series"],
            "prioritize_sources": ["IGN Brasil", "Cinema com Rapadura"],
            "avoid_topics": recent_post_titles[:5],
            "recommended_hook_style": "afirmacao_direta",
            "content_angle": "Cobertura ampla de cultura pop",
            "topics_to_explore": [],
            "engagement_insight": "Dados insuficientes para análise.",
        }


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def run_daily_analysis() -> dict:
    """
    Executa análise completa do CMO e retorna o Day Brief.
    Salva em logs/day_brief.json para uso durante o dia.
    """
    token = os.environ.get("FB_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")

    logger.info("=== CMO Brain — Análise diária iniciada ===")

    # 1. Métricas de performance dos posts recentes
    logger.info("Buscando métricas dos posts recentes...")
    recent_media = fetch_recent_media(ig_user_id, token, limit=20) if token else []
    performance = analyze_performance(recent_media, token)
    logger.info(f"Posts analisados: {performance.get('total_posts_analyzed', 0)} | "
                f"Score médio: {performance.get('avg_engagement_score', 0)}")

    # 2. Títulos recentes para dedup contextual
    recent_titles = [p.get("caption", "").split("\n")[0][:80]
                     for p in recent_media[:15] if p.get("caption")]

    # 3. Concorrentes
    logger.info("Analisando cobertura dos concorrentes...")
    competitor_data = analyze_competitors()
    logger.info(f"Stories concorrentes hoje: {competitor_data['total_stories']}")

    # 4. Trends (Reddit)
    logger.info("Buscando trends do Reddit...")
    trending_topics = []
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from reddit_fetcher import fetch_reddit_trends
        reddit_items = fetch_reddit_trends(max_per_sub=3, validate=False)  # validate=False para ser mais rápido
        trending_topics = [f"[r/{i['subreddit']}] {i['title']}" for i in reddit_items[:10]]
    except Exception as e:
        logger.warning(f"Reddit trends indisponível: {e}")

    # 5. Day Brief via Claude
    logger.info("Gerando Day Brief com Claude...")
    brief = generate_day_brief(performance, competitor_data, trending_topics, recent_titles)

    # Salvar brief do dia
    BRIEF_PATH.parent.mkdir(exist_ok=True)
    BRIEF_PATH.write_text(json.dumps(brief, indent=2, ensure_ascii=False))
    logger.info(f"Day Brief salvo: {BRIEF_PATH}")
    logger.info(f"Estratégia do dia: {brief.get('strategy_note', '')}")
    logger.info(f"Priorizar: {brief.get('prioritize_categories', [])}")
    logger.info(f"Hook recomendado: {brief.get('recommended_hook_style', '')}")

    return brief


def load_todays_brief() -> Optional[dict]:
    """Carrega o brief do dia se já foi gerado hoje."""
    if not BRIEF_PATH.exists():
        return None
    try:
        brief = json.loads(BRIEF_PATH.read_text())
        brief_date = brief.get("date", "")
        today = datetime.now(timezone.utc).date().isoformat()
        if brief_date == today:
            return brief
    except Exception:
        pass
    return None
