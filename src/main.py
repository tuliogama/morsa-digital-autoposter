"""
Morsa Digital Autoposter — ciclo CMO completo.
Uso: python src/main.py [--dry-run] [--platforms instagram] [--skip-brief]
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from news_fetcher import fetch_all_news
from publishers import twitter, instagram, facebook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("morsa.main")

PUBLISHERS = {
    "twitter": twitter.publish,
    "instagram": instagram.publish,
    "facebook": facebook.publish,
}


def save_run_log(posts: list[dict], results: list[dict], dry_run: bool):
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"run_{timestamp}.json"
    log_file.write_text(json.dumps({
        "timestamp": timestamp,
        "dry_run": dry_run,
        "posts_generated": len(posts),
        "results": results,
        "posts": [{k: v for k, v in p.items() if k != "news_item"} for p in posts],
    }, indent=2, ensure_ascii=False))
    logger.info(f"Log salvo em {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Morsa Digital Autoposter")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--platforms", default="instagram")
    parser.add_argument("--skip-brief", action="store_true",
                        help="Pula análise do CMO e usa brief do dia se disponível")
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").lower() == "true"
    posts_per_run = int(os.environ.get("POSTS_PER_RUN", "2"))
    delay_between = int(os.environ.get("DELAY_BETWEEN_POSTS", "90"))

    if dry_run:
        logger.info("=== MODO DRY RUN ===")

    logger.info(f"Morsa Digital Autoposter | plataformas: {platforms} | {posts_per_run} posts/run")

    # ------------------------------------------------------------------ #
    # ETAPA 1 — CMO Brain: análise diária                                 #
    # ------------------------------------------------------------------ #
    brief = None
    try:
        from cmo_brain import run_daily_analysis, load_todays_brief

        if args.skip_brief:
            brief = load_todays_brief()
            if brief:
                logger.info(f"Brief do dia carregado (gerado às {brief.get('generated_at','?')[:16]})")
            else:
                logger.info("Sem brief do dia — rodando análise completa...")
                brief = run_daily_analysis()
        else:
            brief = run_daily_analysis()

    except Exception as e:
        logger.warning(f"CMO Brain falhou — continuando sem brief: {e}")

    # ------------------------------------------------------------------ #
    # ETAPA 2 — Busca de notícias                                         #
    # ------------------------------------------------------------------ #
    logger.info("Buscando notícias...")
    news = fetch_all_news(limit=40, include_reddit=True)
    logger.info(f"{len(news)} notícias encontradas")

    if not news:
        logger.error("Nenhuma notícia. Abortando.")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # ETAPA 3 — Deduplicação contra log persistente                       #
    # ------------------------------------------------------------------ #
    try:
        from posts_log import is_duplicate
        before = len(news)
        news = [n for n in news if not is_duplicate(n["title"], platform="instagram")]
        logger.info(f"Dedup: {len(news)}/{before} notícias únicas")
    except Exception as e:
        logger.warning(f"Dedup falhou: {e}")

    if not news:
        logger.info("Todas as notícias já foram publicadas. Nada a fazer.")
        return

    # ------------------------------------------------------------------ #
    # ETAPA 4 — Curadoria orientada pelo Day Brief                        #
    # ------------------------------------------------------------------ #
    from content_generator import select_best_news, generate_post

    logger.info(f"Selecionando {posts_per_run} melhores notícias...")
    if brief:
        logger.info(f"Estratégia do dia: {brief.get('strategy_note', '')}")
    best_news = select_best_news(news, count=posts_per_run, brief=brief)

    if not best_news:
        logger.error("Claude não selecionou nenhuma notícia. Abortando.")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # ETAPA 5 — Geração de posts                                          #
    # ------------------------------------------------------------------ #
    posts = []
    for n in best_news:
        for platform in platforms:
            try:
                post = generate_post(n, platform, brief=brief)
                posts.append(post)
                logger.info(f"Post gerado [{platform}]: {n['title'][:70]}")
            except Exception as e:
                logger.error(f"Erro ao gerar post [{platform}]: {e}")

    if not posts:
        logger.error("Nenhum post gerado. Abortando.")
        sys.exit(1)

    # Preview
    for post in posts:
        logger.info(f"\n{'='*60}")
        logger.info(f"PLATAFORMA: {post['platform'].upper()}")
        logger.info(f"FONTE: {post['source_title'][:80]}")
        logger.info(f"LEGENDA:\n{post['content']}")
        logger.info(f"{'='*60}")

    if dry_run:
        save_run_log(posts, [], dry_run=True)
        logger.info("Dry run concluído. Nenhum post publicado.")
        return

    # ------------------------------------------------------------------ #
    # ETAPA 6 — Publicação com delay entre posts                          #
    # ------------------------------------------------------------------ #
    results = []
    for i, post in enumerate(posts):
        if i > 0:
            logger.info(f"Aguardando {delay_between}s antes do próximo post...")
            time.sleep(delay_between)

        platform = post["platform"]
        if platform not in PUBLISHERS:
            logger.warning(f"Publisher não encontrado: {platform}")
            continue

        try:
            result = PUBLISHERS[platform](post)
            results.append({"status": "ok", **result})
            logger.info(f"✅ Publicado [{platform}]: {result}")
        except Exception as e:
            logger.error(f"❌ Erro [{platform}]: {e}")
            results.append({"platform": platform, "status": "error", "error": str(e)})

    save_run_log(posts, results, dry_run=False)

    ok = sum(1 for r in results if r.get("status") == "ok")
    logger.info(f"\nConcluído: {ok}/{len(results)} posts publicados")


if __name__ == "__main__":
    main()
