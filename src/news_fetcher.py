"""
Busca notícias nerd/geek/pop/games de fontes brasileiras e internacionais.
"""
import json
import time
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Fontes RSS nerd/geek/pop — Brasil e internacional
NERD_RSS_FEEDS = [
    # Brasil ✅ verificados em maio/2026
    ("IGN Brasil",          "https://br.ign.com/feed.xml"),
    ("Cinema com Rapadura", "https://cinemacomrapadura.com.br/feed/"),
    # Internacional ✅ verificados em maio/2026
    ("IGN",         "https://feeds.feedburner.com/ign/all"),
    ("Kotaku",      "https://kotaku.com/rss"),
    ("ComicBook",   "https://comicbook.com/feed/"),
    ("Den of Geek", "https://www.denofgeek.com/feed/"),
    ("The Verge",   "https://www.theverge.com/rss/index.xml"),
    ("Deadline",    "https://deadline.com/feed/"),
    ("Variety",     "https://variety.com/feed/"),
    # Mortos: Omelete (404), JovemNerd (redirect), Screen Rant (timeout),
    #         Polygon (timeout), Game Informer (timeout)
]

HEADERS = {
    "User-Agent": "MorsaDigital-Autoposter/1.0 (https://instagram.com/morsadigital)"
}

# Palavras-chave para filtrar conteúdo nerd/geek/pop relevante
NERD_KEYWORDS = [
    # Games
    "game", "games", "gaming", "gta", "playstation", "xbox", "nintendo",
    "ps5", "ps4", "steam", "indie", "rpg", "fps", "esport", "esports",
    "minecraft", "fortnite", "league of legends", "valorant", "zelda",
    # Filmes/Séries
    "marvel", "dc", "star wars", "disney", "netflix", "hbo", "amazon prime",
    "anime", "manga", "série", "filme", "trailer", "season", "temporada",
    "avengers", "batman", "spider-man", "pokemon", "one piece", "naruto",
    # Tecnologia geek
    "ia", "ai", "inteligência artificial", "spacex", "nasa", "elon musk",
    "openai", "chatgpt", "robô", "robot", "hack", "hacker", "cyberpunk",
    # Pop culture / Quadrinhos
    "cosplay", "comic", "quadrinhos", "nerd", "geek", "otaku",
    "convention", "sdcc", "comic con",
]


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Falha ao buscar {url}: {e}")
        return None


def _is_nerd_content(title: str, source: str) -> bool:
    """Verifica se o conteúdo é relevante para o público nerd/geek/pop."""
    # Fontes 100% nerd — aceitar tudo
    nerd_sources = {"IGN Brasil", "Cinema com Rapadura", "IGN", "Kotaku",
                    "ComicBook", "Den of Geek", "Screen Rant", "Polygon"}
    if source in nerd_sources:
        return True

    # Para fontes mistas (Verge, Gizmodo) — filtrar por keywords
    title_lower = title.lower()
    return any(kw in title_lower for kw in NERD_KEYWORDS)


def fetch_rss(max_per_feed: int = 5) -> list[dict]:
    """Busca artigos de RSS feeds nerd/geek/pop."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)  # 3 dias

    for feed_name, feed_url in NERD_RSS_FEEDS:
        raw = _fetch_url(feed_url)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)
        count = 0

        for entry in entries:
            if count >= max_per_feed:
                break

            title = (
                _text(entry, "title")
                or _text(entry, "atom:title", ns)
                or ""
            ).strip()

            link = (
                _text(entry, "link")
                or _attr(entry, "atom:link", "href", ns)
                or ""
            ).strip()

            if not title or not link:
                continue

            # Filtrar conteúdo não-nerd de fontes mistas
            if not _is_nerd_content(title, feed_name):
                continue

            pub_raw = (
                _text(entry, "pubDate")
                or _text(entry, "atom:published", ns)
                or _text(entry, "atom:updated", ns)
                or ""
            )
            ts = _parse_date(pub_raw)
            if ts and ts < cutoff:
                continue

            # Pegar descrição/resumo se disponível
            description = (
                _text(entry, "description")
                or _text(entry, "atom:summary", ns)
                or ""
            )[:300]

            items.append({
                "source": feed_name,
                "title": title,
                "url": link,
                "description": description,
                "score": 0,
                "published_at": ts.isoformat() if ts else "",
            })
            count += 1

        time.sleep(0.2)

    return items


def fetch_hackernews_nerd(max_items: int = 10) -> list[dict]:
    """Busca histórias nerd/geek/tech do HackerNews (últimas 24h)."""
    raw = _fetch_url("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not raw:
        return []

    ids = json.loads(raw)[:60]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []

    for story_id in ids:
        if len(items) >= max_items:
            break
        raw_item = _fetch_url(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not raw_item:
            continue
        item = json.loads(raw_item)
        if item.get("type") != "story" or not item.get("url"):
            continue

        title = item.get("title", "")
        if not _is_nerd_content(title, "HackerNews"):
            continue

        ts = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)
        if ts < cutoff:
            continue

        items.append({
            "source": "HackerNews",
            "title": title,
            "url": item.get("url", ""),
            "description": "",
            "score": item.get("score", 0),
            "published_at": ts.isoformat(),
        })
        time.sleep(0.05)

    return sorted(items, key=lambda x: x["score"], reverse=True)


def _text(element, tag: str, ns: dict = None) -> Optional[str]:
    if ns:
        el = element.find(tag, ns)
    else:
        el = element.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _attr(element, tag: str, attr: str, ns: dict = None) -> Optional[str]:
    if ns:
        el = element.find(tag, ns)
    else:
        el = element.find(tag)
    if el is not None:
        return el.get(attr, "").strip() or None
    return None


def _parse_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def fetch_all_news(limit: int = 30) -> list[dict]:
    """Agrega notícias nerd/geek/pop de todas as fontes."""
    logger.info("Buscando notícias nerd dos RSS feeds (Omelete, IGN, Kotaku...)...")
    rss = fetch_rss(max_per_feed=5)

    logger.info("Buscando conteúdo nerd/geek no HackerNews...")
    hn = fetch_hackernews_nerd(max_items=10)

    all_items = rss + hn

    # Deduplicar por título similar
    seen_titles = set()
    unique = []
    for item in all_items:
        key = item["title"].lower()[:60]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(item)

    # Prioriza fontes brasileiras (mais relevantes para o público)
    br_sources = {"Omelete", "IGN Brasil", "The Enemy", "Jovem Nerd", "Pipoca Moderna"}
    br_items = [i for i in unique if i["source"] in br_sources]
    intl_items = [i for i in unique if i["source"] not in br_sources]

    # HackerNews com score alto vai na frente das internacionais
    hn_items = sorted([i for i in intl_items if i["source"] == "HackerNews"],
                      key=lambda x: x["score"], reverse=True)
    other_intl = [i for i in intl_items if i["source"] != "HackerNews"]

    combined = br_items + hn_items + other_intl
    return combined[:limit]
