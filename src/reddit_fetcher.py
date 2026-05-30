"""
Busca trending topics do Reddit relevantes para cultura pop/nerd/geek brasileira.
Filtra NSFW, conteúdo impróprio e valida credibilidade via Claude antes de entrar no pipeline.
"""
import json
import logging
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "MorsaDigital-Autoposter/1.0 (by /u/morsadigital)"
}

# Subreddits relevantes — apenas cultura pop/nerd/geek
SUBREDDITS = [
    # Games
    "games", "gaming", "nintendo", "PS5", "xboxone", "pcgaming",
    "indiegaming", "gamedev",
    # Filmes e séries
    "movies", "television", "marvelstudios", "DC_Cinematic",
    "StarWars", "television",
    # Anime e manga
    "anime", "manga", "OnePiece", "DemonSlayer", "Naruto",
    "DragonBallZ", "attackontitan", "JujutsuKaisen",
    # Brasil
    "brasil", "gamesEcultura",
]

# Subreddits 100% seguros — sem filtro de keyword (já são nichados)
SAFE_SUBREDDITS = {
    "marvelstudios", "DC_Cinematic", "StarWars", "OnePiece",
    "DemonSlayer", "Naruto", "DragonBallZ", "attackontitan",
    "JujutsuKaisen", "nintendo", "PS5",
}

# Palavras que invalidam o post imediatamente (além do flag NSFW da API)
NSFW_KEYWORDS = [
    "nsfw", "nude", "naked", "sex", "porn", "xxx", "hentai", "lewd",
    "gore", "death", "kill", "suicide", "rape", "assault",
    "explicit", "adult content", "+18", "18+",
]

# Palavras que indicam conteúdo inadequado para o canal (fake news, ódio, etc.)
BLOCK_KEYWORDS = [
    "fake", "hoax", "conspiracy", "teoria da conspiração",
    "hate", "racist", "racism", "racismo",
    "politics", "política", "election", "eleição",
    "crypto", "bitcoin", "nft", "token", "invest",
    "scam", "fraud", "golpe",
]

# Mínimo de upvotes para considerar trending
MIN_UPVOTES = 500
# Janela de tempo: posts das últimas 24h
LOOKBACK_HOURS = 24


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Falha ao buscar {url}: {e}")
        return None


def _is_content_safe(title: str, selftext: str = "", flair: str = "") -> tuple[bool, str]:
    """
    Verifica se o conteúdo é seguro para publicação.
    Retorna (is_safe, motivo_se_bloqueado).
    """
    combined = f"{title} {selftext} {flair}".lower()

    for kw in NSFW_KEYWORDS:
        if kw in combined:
            return False, f"NSFW keyword: '{kw}'"

    for kw in BLOCK_KEYWORDS:
        if kw in combined:
            return False, f"Blocked keyword: '{kw}'"

    return True, ""


def _validate_with_claude(items: list[dict]) -> list[dict]:
    """
    Usa Claude para validar credibilidade e relevância antes de entrar no pipeline.
    Remove rumores não verificáveis, clickbait e conteúdo inadequado.
    """
    if not items:
        return []

    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from content_generator import _call_claude

    titles_block = "\n".join(
        f"{i+1}. [r/{item['subreddit']}] {item['title']} ({item['score']} upvotes)"
        for i, item in enumerate(items)
    )

    prompt = (
        f"Lista de posts trending do Reddit:\n\n{titles_block}\n\n"
        f"Analise cada item e responda APENAS com os números dos posts que:\n"
        f"1. São FATOS verificáveis (notícias reais, anúncios oficiais, trailers confirmados)\n"
        f"2. São adequados para público brasileiro nerd/geek/pop geral (sem NSFW, violência, política, finanças)\n"
        f"3. Têm potencial de engajamento para fãs de filmes, séries, animes, doramas ou games\n\n"
        f"REJEITE: rumores sem fonte, teorias não confirmadas, conteúdo sensacionalista, "
        f"notícias de IA genérica, política, finanças, celebridades sem relação com cultura pop.\n\n"
        f"Responda APENAS com números separados por vírgula. Se nenhum for adequado, responda: nenhum"
    )

    try:
        result = _call_claude(
            "Você é editor de conteúdo da Morsa Digital. Sua função é garantir que apenas "
            "conteúdo factual, seguro e relevante para cultura pop/nerd/geek entre no pipeline. "
            "Priorize qualidade sobre quantidade — é melhor não postar do que postar algo duvidoso.",
            prompt,
        )

        result = result.strip().lower()
        if result == "nenhum" or not result:
            return []

        indices = [int(x.strip()) - 1 for x in result.split(",") if x.strip().isdigit()]
        validated = [items[i] for i in indices if 0 <= i < len(items)]
        logger.info(f"Claude validou {len(validated)}/{len(items)} posts do Reddit")
        return validated

    except Exception as e:
        logger.warning(f"Validação Claude falhou: {e} — usando filtro manual apenas")
        return items


def fetch_subreddit_trending(subreddit: str, limit: int = 10) -> list[dict]:
    """Busca posts trending via feed RSS público do subreddit."""
    import xml.etree.ElementTree as ET

    url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit={limit}"
    raw = _fetch_url(url)
    if not raw:
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
    }
    entries = root.findall("atom:entry", ns)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items = []

    for entry in entries:
        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip() if title_el is not None else ""

        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""

        updated_el = entry.find("atom:updated", ns)
        updated_raw = (updated_el.text or "").strip() if updated_el is not None else ""

        content_el = entry.find("atom:content", ns)
        content_text = (content_el.text or "")[:400] if content_el is not None else ""

        if not title or not link:
            continue

        # Data de publicação
        ts = None
        for fmt in ["%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                ts = datetime.strptime(updated_raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

        if ts and ts < cutoff:
            continue

        # Filtro NSFW via título (RSS não expõe o flag over_18 diretamente)
        safe, reason = _is_content_safe(title, content_text)
        if not safe:
            logger.debug(f"Bloqueado ({reason}): {title[:50]}")
            continue

        # Filtro: só aceitar links externos (notícias reais) em subs mistos
        is_external = "reddit.com/r/" not in link or "/comments/" not in link
        is_safe_sub = subreddit in SAFE_SUBREDDITS

        if not is_external and not is_safe_sub:
            continue

        # Score via contagem de comentários no conteúdo (aproximação)
        # RSS do Reddit não expõe upvotes — usamos como proxy a posição
        items.append({
            "source": f"Reddit r/{subreddit}",
            "subreddit": subreddit,
            "title": title,
            "url": link,
            "description": content_text[:300],
            "score": max(0, limit - len(items)) * 100,  # proxy por posição no hot
            "published_at": ts.isoformat() if ts else "",
            "flair": "",
        })

    return items


def fetch_reddit_trends(max_per_sub: int = 5, validate: bool = True) -> list[dict]:
    """
    Agrega trending posts de todos os subreddits configurados.
    Aplica filtros em cascata + validação Claude.
    """
    logger.info("Buscando trends no Reddit...")
    all_items = []

    for sub in SUBREDDITS:
        items = fetch_subreddit_trending(sub, limit=max_per_sub * 2)
        all_items.extend(items)
        time.sleep(0.5)  # respeitar rate limit Reddit

    # Deduplicar por título
    seen, unique = set(), []
    for item in all_items:
        key = item["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Ordenar por score
    unique.sort(key=lambda x: x["score"], reverse=True)
    candidates = unique[:30]  # top 30 para validar

    logger.info(f"Reddit: {len(all_items)} posts → {len(candidates)} candidatos após filtros")

    # Validação Claude (fact check + relevância)
    if validate and candidates:
        candidates = _validate_with_claude(candidates)

    return candidates[:max_per_sub * 3]
