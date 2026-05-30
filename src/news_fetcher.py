"""
Busca notícias nerd/geek/pop/games de fontes brasileiras e internacionais.
Reddit é usado APENAS como sinal de tendência no CMO Brain — nunca como fonte de posts.
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

# 13 feeds RSS nerd/geek/pop — sem Omelete (404) e sem Cinema com Rapadura
NERD_RSS_FEEDS = [
    # Brasil
    ("IGN Brasil",          "https://br.ign.com/feed.xml"),
    ("GameBlast",           "https://www.gameblast.com.br/feeds/posts/default"),
    ("AnimeUnited",         "https://animeunited.com.br/feed/"),
    # Internacional
    ("IGN",                 "https://feeds.feedburner.com/ign/all"),
    ("Kotaku",              "https://kotaku.com/rss"),
    ("ComicBook",           "https://comicbook.com/feed/"),
    ("Den of Geek",         "https://www.denofgeek.com/feed/"),
    ("The Verge",           "https://www.theverge.com/rss/index.xml"),
    ("Deadline",            "https://deadline.com/feed/"),
    ("Variety",             "https://variety.com/feed/"),
    ("Anime News Network",  "https://www.animenewsnetwork.com/all/rss.xml"),
    ("Eurogamer",           "https://www.eurogamer.net/?format=rss"),
    ("Gizmodo",             "https://gizmodo.com/rss"),
]

# Fontes 100% nerd — aceitar todos os artigos sem filtro de keyword
NERD_SOURCES = {
    "IGN Brasil", "GameBlast", "AnimeUnited",
    "IGN", "Kotaku", "ComicBook", "Den of Geek",
    "Anime News Network", "Eurogamer",
}

HEADERS = {
    "User-Agent": "MorsaDigital-Autoposter/1.0 (https://instagram.com/morsadigital)"
}

# Palavras-chave para filtrar fontes mistas (Verge, Deadline, Variety, Gizmodo)
# Palavras que indicam conteúdo a rejeitar independente da fonte
BLOCK_KEYWORDS = [
    # Podcasts
    "podcast", "episódio", "episode", "ep.", " ep ", "rapaduracast", "nerdcast",
    "jovemnerd", "maniacast", "ouça", "ouça agora", "escute",
    # Listas/clickbait sem novidade factual
    "melhores animes de", "melhores games de", "melhores filmes de",
    "top 10", "top 5", "top 3", "ranking dos",
    # Conteúdo proibido
    "política", "eleição", "crypto", "bitcoin", "nft", "invest",
    "fake news", "teoria da conspiração", "hoax",
]

NERD_KEYWORDS = [
    "game", "games", "gaming", "gta", "playstation", "xbox", "nintendo",
    "ps5", "steam", "indie", "rpg", "esport", "zelda", "call of duty",
    "resident evil", "final fantasy", "pokemon",
    "marvel", "dc", "star wars", "disney", "netflix", "hbo", "amazon prime",
    "anime", "manga", "série", "séries", "filme", "filmes", "trailer", "season",
    "temporada", "avengers", "batman", "spider-man", "superman", "deadpool",
    "one piece", "naruto", "demon slayer", "attack on titan", "jujutsu kaisen",
    "dragon ball", "bleach", "dorama", "k-drama",
    "cosplay", "comic", "comics", "nerd", "geek", "otaku", "comic con",
]


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Falha ao buscar {url}: {e}")
        return None


def _is_blocked(title: str) -> bool:
    """Rejeita podcasts, listas genéricas e conteúdo proibido independente da fonte."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in BLOCK_KEYWORDS)


def _is_nerd_content(title: str, source: str) -> bool:
    if _is_blocked(title):
        return False
    if source in NERD_SOURCES:
        return True
    title_lower = title.lower()
    return any(kw in title_lower for kw in NERD_KEYWORDS)


def _text(element, tag: str, ns: dict = None) -> Optional[str]:
    el = element.find(tag, ns) if ns else element.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _attr(element, tag: str, attr: str, ns: dict = None) -> Optional[str]:
    el = element.find(tag, ns) if ns else element.find(tag)
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


def fetch_rss(max_per_feed: int = 6) -> list[dict]:
    """Busca artigos de todos os feeds RSS nerd/geek/pop."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)

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

            title = (_text(entry, "title") or _text(entry, "atom:title", ns) or "").strip()
            link  = (_text(entry, "link")  or _attr(entry, "atom:link", "href", ns) or "").strip()

            if not title or not link:
                continue
            if not _is_nerd_content(title, feed_name):
                continue

            pub_raw = (
                _text(entry, "pubDate") or _text(entry, "atom:published", ns)
                or _text(entry, "atom:updated", ns) or ""
            )
            ts = _parse_date(pub_raw)
            if ts and ts < cutoff:
                continue

            description = (
                _text(entry, "description") or _text(entry, "atom:summary", ns) or ""
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


def fetch_all_news(limit: int = 40) -> list[dict]:
    """
    Agrega notícias nerd/geek/pop dos 13 feeds RSS.
    Reddit NÃO entra aqui — é usado apenas como sinal de tendência no CMO Brain.
    """
    logger.info("Buscando notícias de filmes, séries, animes, games e cultura pop...")
    items = fetch_rss(max_per_feed=6)

    # Deduplicar por título similar
    seen, unique = set(), []
    for item in items:
        key = item["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Prioridade: BR primeiro, depois internacional
    br_sources = {"IGN Brasil", "GameBlast", "AnimeUnited"}
    br    = [i for i in unique if i["source"] in br_sources]
    intl  = [i for i in unique if i["source"] not in br_sources]

    combined = br + intl
    logger.info(f"RSS: {len(br)} BR + {len(intl)} internacional = {len(combined)} notícias")
    return combined[:limit]
