"""
Batch catch-up: posta as melhores notícias da janela recente evitando duplicatas.
"""
import os, sys, time, json, logging, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("catchup")

GRAPH_URL       = "https://graph.facebook.com/v19.0"
MAX_POSTS       = 8     # máximo de posts nessa sessão
DELAY_BETWEEN   = 45    # segundos entre posts
LOOKBACK_DAYS   = 3     # janela de busca


def get_posted_captions(ig_user_id: str, token: str) -> set[str]:
    url = (f"{GRAPH_URL}/{ig_user_id}/media"
           f"?fields=caption,timestamp&limit=50&access_token={token}")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        words = set()
        for post in data.get("data", []):
            cap = post.get("caption", "").lower()
            words.update(w for w in cap.split() if len(w) > 5 and w.isalpha())
        return words
    except Exception as e:
        logger.warning(f"Não conseguiu listar posts: {e}")
        return set()


def is_duplicate(title: str, posted_words: set[str]) -> bool:
    title_words = {w.lower() for w in title.split() if len(w) > 5 and w.isalpha()}
    return len(title_words & posted_words) >= 3


def main():
    ig_user_id = os.environ.get("IG_USER_ID", "17841405897887153")
    token      = os.environ.get("FB_ACCESS_TOKEN", "")

    if not token:
        logger.error("FB_ACCESS_TOKEN não definido.")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY não definido.")
        sys.exit(1)

    # 1. Posts já publicados
    logger.info("Verificando posts já publicados no Instagram...")
    posted_words = get_posted_captions(ig_user_id, token)
    logger.info(f"  {len(posted_words)} palavras de posts existentes carregadas")

    # 2. Busca notícias via fetcher já atualizado (feeds corretos)
    from news_fetcher import fetch_all_news
    # Temporariamente aumenta janela de 72h para 7 dias
    import news_fetcher as nf
    import datetime as _dt
    original_fetch = nf.fetch_rss

    def fetch_rss_extended(max_per_feed=15):
        import xml.etree.ElementTree as ET
        cutoff_extended = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=LOOKBACK_DAYS)
        items = []
        HEADERS = {"User-Agent": "MorsaDigital-Autoposter/1.0"}
        for feed_name, feed_url in nf.NERD_RSS_FEEDS:
            raw = nf._fetch_url(feed_url)
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
                title = (nf._text(entry, "title") or nf._text(entry, "atom:title", ns) or "").strip()
                link  = (nf._text(entry, "link")  or nf._attr(entry, "atom:link", "href", ns) or "").strip()
                if not title or not link:
                    continue
                if not nf._is_nerd_content(title, feed_name):
                    continue
                pub_raw = (nf._text(entry, "pubDate") or
                           nf._text(entry, "atom:published", ns) or "")
                ts = nf._parse_date(pub_raw)
                if ts and ts < cutoff_extended:
                    continue
                desc = (nf._text(entry, "description") or
                        nf._text(entry, "atom:summary", ns) or "")[:300]
                items.append({
                    "source": feed_name, "title": title, "url": link,
                    "description": desc, "score": 0,
                    "published_at": ts.isoformat() if ts else "",
                })
                count += 1
            time.sleep(0.2)

        # Deduplicar
        seen, unique = set(), []
        for item in items:
            key = item["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        br = {"IGN Brasil", "Cinema com Rapadura"}
        unique.sort(key=lambda x: (0 if x["source"] in br else 1))
        logger.info(f"Notícias encontradas ({LOOKBACK_DAYS} dias): {len(unique)}")
        return unique

    # Substitui fetch_rss temporariamente
    nf.fetch_rss = lambda max_per_feed=5: fetch_rss_extended(max_per_feed=15)

    all_news = fetch_all_news(limit=60)
    nf.fetch_rss = original_fetch  # restaura

    # 3. Filtra duplicatas
    fresh = [n for n in all_news if not is_duplicate(n["title"], posted_words)]
    logger.info(f"  {len(fresh)} notícias novas (não duplicadas)")

    if not fresh:
        logger.info("Nenhuma notícia nova. Encerrando.")
        return

    # 4. Deixa Claude selecionar as melhores
    from content_generator import select_best_news, generate_post
    logger.info(f"Pedindo ao Claude para selecionar as {MAX_POSTS} melhores de {len(fresh)} notícias...")
    best = select_best_news(fresh, count=MAX_POSTS)
    logger.info(f"Claude selecionou {len(best)} notícias:")
    for i, n in enumerate(best, 1):
        logger.info(f"  {i}. [{n['source']}] {n['title'][:80]}")

    if not best:
        logger.info("Claude não selecionou nenhuma. Encerrando.")
        return

    # 5. Gera e publica cada um
    from publishers.instagram import publish as ig_publish
    results = []
    for i, news_item in enumerate(best, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Post {i}/{len(best)}: {news_item['title'][:80]}")
        try:
            post = generate_post(news_item, "instagram")
            post["news_item"] = news_item
            result = ig_publish(post)
            logger.info(f"  ✅ Publicado: {result}")
            results.append({"status": "ok", "title": news_item["title"], **result})
        except Exception as e:
            logger.error(f"  ❌ Erro: {e}")
            results.append({"status": "error", "title": news_item["title"], "error": str(e)})

        if i < len(best):
            logger.info(f"  Aguardando {DELAY_BETWEEN}s...")
            time.sleep(DELAY_BETWEEN)

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"\n{'='*60}")
    logger.info(f"Catch-up concluído: {ok}/{len(results)} publicados")


if __name__ == "__main__":
    main()
