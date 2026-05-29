"""
Entry point do Morsa Digital Autoposter.
Uso: python src/main.py [--dry-run] [--platforms twitter,instagram,facebook]
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from news_fetcher import fetch_all_news
from content_generator import generate_all_posts
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


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "settings.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


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
        "posts": posts,
    }, indent=2, ensure_ascii=False))
    logger.info(f"Log salvo em {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Morsa Digital Autoposter")
    parser.add_argument("--dry-run", action="store_true", help="Gera posts mas não publica")
    parser.add_argument(
        "--platforms",
        default="twitter,instagram,facebook",
        help="Plataformas separadas por vírgula",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").lower() == "true"

    if dry_run:
        logger.info("=== MODO DRY RUN — posts NÃO serão publicados ===")

    logger.info(f"Iniciando Morsa Digital Autoposter | plataformas: {platforms}")

    # 1. Buscar notícias
    logger.info("Buscando notícias tech recentes...")
    news = fetch_all_news(limit=30)
    logger.info(f"{len(news)} notícias encontradas")

    if not news:
        logger.error("Nenhuma notícia encontrada. Abortando.")
        sys.exit(1)

    # 2. Gerar posts com IA
    logger.info("Gerando posts com Claude AI...")
    posts = generate_all_posts(news, platforms=platforms)

    # Injetar news_item no post para geração de imagem
    news_by_title = {n["title"]: n for n in news}
    for post in posts:
        post["news_item"] = news_by_title.get(post.get("source_title", ""), {})
    logger.info(f"{len(posts)} posts gerados")

    if not posts:
        logger.error("Nenhum post gerado. Abortando.")
        sys.exit(1)

    # Exibir preview
    for post in posts:
        logger.info(f"\n{'='*60}")
        logger.info(f"PLATAFORMA: {post['platform'].upper()}")
        logger.info(f"FONTE: {post['source_title'][:80]}")
        logger.info(f"CONTEÚDO:\n{post['content']}")
        logger.info(f"{'='*60}")

    if dry_run:
        save_run_log(posts, [], dry_run=True)
        logger.info("Dry run concluído. Nenhum post foi publicado.")
        return

    # 3. Publicar
    results = []
    for post in posts:
        platform = post["platform"]
        if platform not in PUBLISHERS:
            logger.warning(f"Publisher não encontrado para: {platform}")
            continue
        try:
            result = PUBLISHERS[platform](post)
            results.append({"status": "ok", **result})
            logger.info(f"Publicado em {platform}: {result}")
        except Exception as e:
            logger.error(f"Erro ao publicar em {platform}: {e}")
            results.append({"platform": platform, "status": "error", "error": str(e)})

    save_run_log(posts, results, dry_run=False)

    ok = sum(1 for r in results if r.get("status") == "ok")
    logger.info(f"\nConcluído: {ok}/{len(results)} posts publicados com sucesso")


if __name__ == "__main__":
    main()
