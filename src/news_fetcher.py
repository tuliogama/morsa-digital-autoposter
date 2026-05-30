"""
Busca notícias de Star Wars e cultura geek/sci-fi para @ordemsithbrasil.
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

# Feeds RSS focados em Star Wars + sci-fi/geek complementar
RSS_FEEDS = [
    # Star Wars primário
    ("StarWars.com",        "https://www.starwars.com/news/rss"),
    ("IGN Star Wars",       "https://feeds.feedburner.com/ign/all"),
    ("ComicBook",           "https://comicbook.com/feed/"),
    ("Den of Geek",         "https://www.denofgeek.com/feed/"),
    # Séries e cinema sci-fi complementar
    ("Deadline",            "https://deadline.com/feed/"),
    ("Variety",             "https://variety.com/feed/"),
    ("The Verge",           "https://www.theverge.com/rss/index.xml"),
    # Games (KOTOR, Jedi: Fallen Order, etc.)
    ("IGN",                 "https://feeds.feedburner.com/ign/all"),
    ("Kotaku",              "https://kotaku.com/rss"),
    # BR
    ("IGN Brasil",          "https://br.ign.com/feed.xml"),
]

# Palavras-chave Star Wars — aceitar qualquer artigo que mencione
STARWARS_KEYWORDS = [
    "star wars", "starwars", "jedi", "sith", "vader", "darth",
    "skywalker", "luke", "leia", "han solo", "obi-wan", "kenobi",
    "palpatine", "emperor", "yoda", "mando", "mandalorian", "grogu",
    "ahsoka", "andor", "boba fett", "clone wars", "bad batch",
    "acolyte", "skeleton crew", "the force", "lightsaber", "death star",
    "millennium falcon", "x-wing", "tie fighter", "rebel", "empire",
    "republic", "separatist", "galactic", "coruscant", "tatooine",
    "george lucas", "lucasfilm", "disney star wars",
    "kotor", "knights of the old republic", "jedi fallen order",
    "jedi survivor", "outlaws", "squadrons",
]

# Palavras-chave sci-fi/geek complementar (para fontes mistas)
SCIFI_KEYWORDS = [
    "sci-fi", "science fiction", "marvel", "dc comics", "avengers",
    "batman", "superman", "alien", "predator", "dune", "blade runner",
    "foundation", "rings of power", "house of dragon", "game of thrones",
    "witcher", "cyberpunk", "matrix", "terminator", "back to the future",
    "indiana jones", "jurassic", "avatar", "guardians", "thor",
]

# Fontes 100% relevantes — aceitar tudo sem filtro
PRIORITY_SOURCES = {"StarWars.com", "IGN Star Wars"}

# Fontes mistas — filtrar por palavras-chave
MIXED_SOURCES = {"IGN", "IGN Brasil", "Kotaku", "ComicBook", "Den of Geek",
                 "Deadline", "Variety", "The Verge"}

BLOCK_KEYWORDS = [
    "podcast", "episódio", "episode", " ep ", "ep.", "ouça", "escute",
    "top 10", "top 5", "ranking dos", "melhores de",
    "política", "eleição", "crypto", "bitcoin", "nft",
    "fake news", "hoax",
]

HEADERS = {
    "User-Agent": "OrdemSithBrasil-Autoposter/1.0 (https://instagram.com/ordemsithbrasil)"
}


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Falha ao buscar {url}: {e}")
        return None


def _is_relevant(title: str, source: str) -> bool:
    if any(kw in title.lower() for kw in BLOCK_KEYWORDS):
        return False
    if source in PRIORITY_SOURCES:
        return True
    title_lower = title.lower()
    return (
        any(kw in title_lower for kw in STARWARS_KEYWORDS) or
        any(kw in title_lower for kw in SCIFI_KEYWORDS)
    )


def _text(el, tag, ns=None):
    e = el.find(tag, ns) if ns else el.find(tag)
    return (e.text or "").strip() if e is not None and e.text else None


def _attr(el, tag, attr, ns=None):
    e = el.find(tag, ns) if ns else el.find(tag)
    return e.get(attr, "").strip() if e is not None else None


def _parse_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S+00:00"]:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def fetch_rss(max_per_feed: int = 6) -> list[dict]:
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    seen_urls = set()

    for feed_name, feed_url in RSS_FEEDS:
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

            if not title or not link or link in seen_urls:
                continue
            if not _is_relevant(title, feed_name):
                continue

            pub_raw = (_text(entry, "pubDate") or _text(entry, "atom:published", ns) or
                       _text(entry, "atom:updated", ns) or "")
            ts = _parse_date(pub_raw)
            if ts and ts < cutoff:
                continue

            description = (_text(entry, "description") or _text(entry, "atom:summary", ns) or "")[:300]

            items.append({
                "source": feed_name,
                "title": title,
                "url": link,
                "description": description,
                "score": 0,
                "published_at": ts.isoformat() if ts else "",
            })
            seen_urls.add(link)
            count += 1

        time.sleep(0.2)

    return items


def fetch_all_news(limit: int = 40) -> list[dict]:
    """
    Agrega notícias de Star Wars e sci-fi/geek dos feeds RSS.
    Reddit NÃO entra aqui — apenas sinal de tendência no CMO Brain.
    """
    logger.info("Buscando notícias de Star Wars e sci-fi/geek...")
    items = fetch_rss(max_per_feed=6)

    # Prioridade: Star Wars direto > outros
    sw   = [i for i in items if any(k in i["title"].lower() for k in STARWARS_KEYWORDS)]
    rest = [i for i in items if i not in sw]
    combined = sw + rest

    logger.info(f"RSS: {len(sw)} Star Wars direto + {len(rest)} sci-fi/geek = {len(combined)} notícias")
    return combined[:limit]
