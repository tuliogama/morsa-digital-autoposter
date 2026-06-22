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

# Feeds RSS nerd/geek/pop — curados por performance
# Removido: Gizmodo (gerava promos de gadgets/tech off-brand), The Verge (basketball, GTA release timing)
NERD_RSS_FEEDS = [
    # Brasil — prioridade máxima
    ("IGN Brasil",          "https://br.ign.com/feed.xml"),
    ("GameBlast",           "https://www.gameblast.com.br/feeds/posts/default"),
    ("AnimeUnited",         "https://animeunited.com.br/feed/"),
    # Internacional — cultura pop/nerd pura
    ("IGN",                 "https://feeds.feedburner.com/ign/all"),
    ("Kotaku",              "https://kotaku.com/rss"),
    ("ComicBook",           "https://comicbook.com/feed/"),
    ("Den of Geek",         "https://www.denofgeek.com/feed/"),
    ("Deadline",            "https://deadline.com/feed/"),
    ("Variety",             "https://variety.com/feed/"),
    ("Anime News Network",  "https://www.animenewsnetwork.com/all/rss.xml"),
    ("Eurogamer",           "https://www.eurogamer.net/?format=rss"),
    # Anime mainstream — cobrir títulos de alto engajamento
    ("Crunchyroll News",    "https://www.crunchyroll.com/news/rss"),
]

# Fontes 100% nerd — aceitar todos os artigos sem filtro de keyword
NERD_SOURCES = {
    "IGN Brasil", "GameBlast", "AnimeUnited",
    "IGN", "Kotaku", "ComicBook", "Den of Geek",
    "Anime News Network", "Eurogamer", "Crunchyroll News",
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
    # Tech/gadgets off-brand (Gizmodo-style) — não é cultura pop
    "galaxy s", "iphone ", "pixel ", "samsung galaxy", "apple watch",
    "smartwatch", "notebook ", "laptop ", "processador", "chip ",
    "inteligência artificial", "ia generativa", "chatgpt", "openai",
    "robô de limpeza", "aspirador robô", "smart home", "casa inteligente",
    "oferta ", "cupom ", "desconto ", "promoção de", "por menos de r$",
    "review do", "análise do produto", "melhor celular",
    # Conteúdo promocional / venda de serviço — Morsa só NOTICIA, nunca vende
    "assine ", "assinatura", "plano premium", "contrate", "garanta o seu",
    "publieditorial", "publipost", "patrocinado", "em parceria com",
    "use o cupom", "frete grátis", "black friday", "pré-venda com desconto",
    # Esportes reais sem relação com cultura pop
    "copa do mundo de futebol", "nba 2k", " nfl ", "basquete real",
    # Séries/franquias de baixíssimo engajamento no Brasil
    "stargate", "battlestar", "babylon 5",
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


def fetch_article_text(url: str, max_chars: int = 1800) -> str:
    """
    Busca o corpo do artigo e extrai texto legível (sem tags).
    Usado para ENRIQUECER notícias cuja description do RSS é fina demais
    para o modelo entregar a especificidade que o título promete
    (nomes de listas, datas de estreia, qual regra mudou, etc.).
    Retorna "" se não conseguir extrair conteúdo útil.
    """
    import re
    if not url:
        return ""
    html = _fetch_url(url, timeout=12)
    if not html:
        return ""

    # Remove blocos que nunca contêm o conteúdo do artigo
    html = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form|figure)[^>]*>.*?</\1>", " ", html)

    # Preferir o conteúdo dentro de <article> quando existir
    article_match = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
    body = article_match.group(1) if article_match else html

    # Extrai parágrafos e itens de lista — onde ficam nomes, datas e enumerações
    chunks = re.findall(r"(?is)<(?:p|li|h2|h3)[^>]*>(.*?)</(?:p|li|h2|h3)>", body)
    texts = []
    for c in chunks:
        c = re.sub(r"(?is)<[^>]+>", " ", c)           # tira tags internas
        c = re.sub(r"&[a-z]+;|&#\d+;", " ", c)        # tira entidades HTML
        c = re.sub(r"\s+", " ", c).strip()
        if len(c) >= 40:                               # ignora migalhas (botões, captions)
            texts.append(c)

    full = "\n".join(texts)
    return full[:max_chars].strip()


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

            # Atom feeds (ex: Blogger): preferir rel="alternate" — evita URLs de comentários
            atom_links = entry.findall("atom:link", ns)
            alternate = next((l.get("href","") for l in atom_links if l.get("rel") == "alternate"), "")
            link = (alternate or _text(entry, "link") or _attr(entry, "atom:link", "href", ns) or "").strip()

            # Ignorar URLs que são páginas de feed/comentários, não artigos
            if "/feeds/" in link or link.endswith("/comments"):
                continue

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
