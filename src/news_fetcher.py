"""
Busca notícias tech de fontes gratuitas: HackerNews, Reddit e RSS feeds.
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

TECH_RSS_FEEDS = [
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
]

DEVTO_TAGS = ["webdev", "ai", "programming", "python", "javascript", "opensource"]

HEADERS = {
    "User-Agent": "MorsaDigital-Autoposter/1.0 (https://github.com/morsadigital)"
}


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Falha ao buscar {url}: {e}")
        return None


def fetch_hackernews(max_items: int = 15) -> list[dict]:
    """Busca top stories do HackerNews das últimas 24h."""
    raw = _fetch_url("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not raw:
        return []

    ids = json.loads(raw)[:50]
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
        ts = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)
        if ts < cutoff:
            continue
        items.append({
            "source": "HackerNews",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0),
            "published_at": ts.isoformat(),
        })
        time.sleep(0.05)

    return sorted(items, key=lambda x: x["score"], reverse=True)


def fetch_devto(max_per_tag: int = 5) -> list[dict]:
    """Busca artigos populares do Dev.to por tag (API pública, sem auth)."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    for tag in DEVTO_TAGS:
        url = f"https://dev.to/api/articles?tag={tag}&top=1&per_page={max_per_tag}"
        raw = _fetch_url(url)
        if not raw:
            continue
        try:
            articles = json.loads(raw)
        except Exception:
            continue

        for article in articles:
            pub_raw = article.get("published_at", "")
            ts = _parse_date(pub_raw)
            items.append({
                "source": f"Dev.to #{tag}",
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "score": article.get("positive_reactions_count", 0),
                "published_at": ts.isoformat() if ts else "",
            })
        time.sleep(0.3)

    return sorted(items, key=lambda x: x["score"], reverse=True)


def fetch_rss(max_per_feed: int = 5) -> list[dict]:
    """Busca artigos de RSS feeds tech."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    for feed_name, feed_url in TECH_RSS_FEEDS:
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
            )
            link = (
                _text(entry, "link")
                or entry.findtext("atom:link", namespaces=ns)
                or ""
            )
            if not title or not link:
                continue

            pub_raw = _text(entry, "pubDate") or _text(entry, "atom:published", ns) or ""
            ts = _parse_date(pub_raw)
            if ts and ts < cutoff:
                continue

            items.append({
                "source": feed_name,
                "title": title.strip(),
                "url": link.strip(),
                "score": 0,
                "published_at": ts.isoformat() if ts else "",
            })
            count += 1

    return items


def _text(element, tag: str, ns: dict = None) -> Optional[str]:
    if ns:
        el = element.find(tag, ns)
    else:
        el = element.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _parse_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_all_news(limit: int = 30) -> list[dict]:
    """Agrega notícias de todas as fontes e retorna as mais relevantes."""
    logger.info("Buscando notícias do HackerNews...")
    hn = fetch_hackernews(max_items=15)

    logger.info("Buscando artigos do Dev.to...")
    reddit = fetch_devto(max_per_tag=5)

    logger.info("Buscando RSS feeds...")
    rss = fetch_rss(max_per_feed=5)

    all_items = hn + reddit + rss

    # Deduplicar por título similar
    seen_titles = set()
    unique = []
    for item in all_items:
        key = item["title"].lower()[:60]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(item)

    # Prioriza HackerNews e Reddit por score, RSS por recência
    hn_reddit = [i for i in unique if i["source"] != "RSS"]
    rss_only = [i for i in unique if i["source"] == "RSS"]

    combined = sorted(hn_reddit, key=lambda x: x["score"], reverse=True) + rss_only
    return combined[:limit]
