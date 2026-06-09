"""
Editorial Engine — orquestra carrosseis e reels editoriais para @morsadigital.

Estratégia baseada em dados reais (jun/2026):
- ER atual de posts automáticos: 0.038%
- Spider-Noir carrossel manual: 42 likes (4x a média)
- Reels: boost algorítmico comprovado no Instagram

Cadência editorial:
  - 3-4 posts de feed/dia (notícias quentes)
  - 1 carrossel editorial/dia (conteúdo curado)
  - 1 reel/dia (slideshow de notícias com vídeo)

Tipos de carrossel:
  - "top_n"      : "Top 5 anúncios da semana" (segunda/sexta)
  - "deep_dive"  : "Tudo sobre [franquia]" (quando há novidade grande)
  - "event_recap": "Summer Game Fest em resumo" (pós-evento)
"""
import json
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from content_generator import _call_groq, CaptionGenerationError
from news_fetcher import fetch_all_news

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geração de conteúdo para carrossel via Groq
# ---------------------------------------------------------------------------

CAROUSEL_SYSTEM = """Você é o diretor editorial da Morsa Digital — canal nerd/pop para 27k seguidores brasileiros.

Você cria carrosseis editoriais de alta performance para o Instagram.

DADOS DE PERFORMANCE REAIS:
- Marvel/DC: melhor categoria (17.6 likes avg, +75% acima da média)
- Games grandes (God of War, Zelda, GTA): bom desempenho
- Anime mainstream (One Piece, JJK, Demon Slayer): forte no Brasil
- Carrosseis editoriais: 4x mais engajamento que posts automáticos

REGRAS DO CARROSSEL:
- Título da capa: impactante, direto, referencia a franquia/tema
- Cada slide: headline curto (máx 8 palavras) + corpo de 2-3 frases com contexto real
- Última slide = CTA variado (nunca "curta e siga" genérico)
- Tom: fã apaixonado que também sabe do que fala. Não robótico.
- NUNCA inventar informações — use apenas o que está nas notícias fornecidas

Responda APENAS com JSON válido, sem markdown, sem explicações."""


def generate_carousel_content(news_list: list, carousel_type: str = "top_n") -> dict:
    """
    Usa Groq para gerar o conteúdo editorial completo de um carrossel.

    Retorna dict no formato esperado por carousel_generator.generate_carousel()
    """
    if not news_list:
        raise ValueError("Lista de notícias vazia")

    n = min(len(news_list), 5)
    news_list = news_list[:n]

    # Montar contexto das notícias para o Groq
    news_context = "\n".join(
        f"{i+1}. [{item.get('source','')}] {item.get('title','')}\n   {item.get('description','')[:150]}"
        for i, item in enumerate(news_list)
    )

    if carousel_type == "top_n":
        user_msg = f"""Crie um carrossel editorial "Top {n}" com essas notícias:

{news_context}

Formato JSON:
{{
  "title": "Título da capa (ex: TOP 5 ANÚNCIOS DA SEMANA)",
  "subtitle": "Subtítulo curto explicativo",
  "category_tag": "Games|Marvel|Anime|Cinema|etc",
  "cover_image_url": "URL da imagem da notícia mais impactante",
  "items": [
    {{
      "headline": "Headline curto (máx 8 palavras, ALL CAPS opcional)",
      "body": "2-3 frases explicando o que é e por que importa para o fã",
      "image_url": "URL da imagem desta notícia (pode ser null)"
    }}
  ],
  "cta_text": "CTA do último slide (ex: Salva pra não esquecer 🔖)",
  "cta_secondary": "Pergunta ou comentário para engajamento"
}}"""

    elif carousel_type == "deep_dive":
        main_news = news_list[0]
        user_msg = f"""Crie um carrossel "deep dive" sobre esta notícia principal:

PRINCIPAL: {main_news.get('title','')}
{main_news.get('description','')}

CONTEXTO ADICIONAL:
{news_context}

Crie 4-5 slides que aprofundem o tema: contexto histórico, impacto, o que vem a seguir.

Formato JSON (mesmo schema acima)."""

    else:  # event_recap
        user_msg = f"""Crie um carrossel "resumo do evento" com os melhores anúncios:

{news_context}

Identifique o evento principal e crie slides com os destaques.
Formato JSON (mesmo schema acima)."""

    try:
        raw = _call_groq(CAROUSEL_SYSTEM, user_msg, max_tokens=1200)

        # Limpar markdown se vier
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        data = json.loads(raw)

        # Preencher image_urls ausentes com as das notícias
        for i, item in enumerate(data.get("items", [])):
            if not item.get("image_url") and i < len(news_list):
                # Tentar pegar imagem da notícia correspondente
                item["image_url"] = None  # será preenchido pelo carousel_generator

        # Cover image da primeira notícia se não especificado
        if not data.get("cover_image_url") and news_list:
            data["cover_image_url"] = None

        logger.info(f"Conteúdo de carrossel gerado: {data.get('title','?')}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido do Groq: {e}\nRaw: {raw[:200]}")
        raise CaptionGenerationError(f"Groq retornou JSON inválido para carrossel")
    except Exception as e:
        raise CaptionGenerationError(f"Falha ao gerar carrossel: {e}")


def generate_carousel_caption(carousel_data: dict) -> str:
    """
    Gera legenda do Instagram para o carrossel (aparece no feed).
    Tom editorial, resume o carrossel e convida para navegar.
    """
    title = carousel_data.get("title", "")
    items = carousel_data.get("items", [])
    items_preview = " | ".join(
        item.get("headline", "")[:30] for item in items[:3]
    )

    system = """Você é o copywriter da Morsa Digital.
Escreva a legenda para um carrossel do Instagram.
FORMATO:
- Linha 1: hook direto (sem emoji no início)
- Linha em branco
- 2-3 linhas resumindo o que está no carrossel
- Linha em branco
- CTA para arrastar os slides
- Linha em branco
- 5-7 hashtags específicas
NÃO truncar. NÃO começar com emoji."""

    user_msg = (
        f"Carrossel: {title}\n"
        f"Destaques: {items_preview}\n\n"
        "Escreva a legenda completa do Instagram."
    )

    try:
        return _call_groq(system, user_msg, max_tokens=500)
    except Exception as e:
        # Fallback simples
        return (
            f"{title}\n\n"
            f"Arrasta para ver tudo 👉\n\n"
            f"#MorsaDigital #CulturaPop #Nerd #Geek"
        )


# ---------------------------------------------------------------------------
# Geração de conteúdo para reel
# ---------------------------------------------------------------------------

REEL_CAPTION_SYSTEM = """Você é o copywriter da Morsa Digital para Reels.
Reels têm legenda curta e impactante — foco em chamar para assistir o vídeo.
FORMATO:
- Hook: 1 linha direta (sem emoji no início)
- Linha em branco
- 2 linhas de contexto
- Linha em branco
- CTA: "Assiste até o final 👇" ou similar
- Linha em branco
- 5-6 hashtags específicas + #MorsaDigital
NÃO usar mais de 200 palavras."""


def generate_reel_data(news_list: list) -> dict:
    """
    Prepara os dados para o reel: escolhe as melhores notícias com imagem
    e gera textos curtos de overlay para cada slide.

    Retorna dict no formato de publish_reel().
    """
    # Filtrar notícias com imagem disponível
    # (o reel_generator vai baixar as imagens das URLs)
    slides = []
    for news in news_list[:5]:
        title = news.get("title", "")
        # Gerar headline curto para overlay do vídeo
        try:
            headline = _call_groq(
                "Crie um headline ULTRA curto (máx 6 palavras) para overlay de vídeo. "
                "Sem pontuação excessiva. Sem reticências. Responda apenas o headline.",
                f"Notícia: {title}",
                max_tokens=25,
            ).strip().strip('"').strip("'")
        except Exception:
            headline = " ".join(title.split()[:6])

        slides.append({
            "image_url": news.get("url", ""),  # será buscado o og:image
            "text": headline,
            "news": news,
        })

    # Buscar imagens reais das notícias para os slides
    slides_with_images = _fetch_og_images(slides)

    title = news_list[0].get("title", "Destaques da semana") if news_list else "Destaques"

    return {
        "slides": slides_with_images,
        "title": title,
    }


def _fetch_og_images(slides: list) -> list:
    """
    Extrai og:image de cada URL de notícia usando a mesma lógica robusta
    do image_generator (200KB de HTML, 4 padrões, valida download).
    """
    from image_generator import _fetch_article_image, _upload_image

    result = []
    for slide in slides:
        url = slide.get("news", {}).get("url", "")
        image_url = None

        if url:
            try:
                img_bytes = _fetch_article_image(url)
                if img_bytes:
                    # Upload para CDN público (GitHub → Imgur → catbox)
                    cdn_url = _upload_image(img_bytes)
                    if cdn_url:
                        image_url = cdn_url
                        logger.info(f"Imagem do reel: {cdn_url[:60]}")
            except Exception as e:
                logger.warning(f"Falha ao buscar imagem para reel slide ({url[:50]}): {e}")

        if image_url:
            result.append({
                "image_url": image_url,
                "text": slide["text"],
            })
        # Se não achou imagem, pula — reel precisa de imagens reais

    return result


def _fetch_carousel_images(carousel_data: dict, news_list: list) -> dict:
    """
    Substitui os image_url do carrossel (vindos do Groq, não confiáveis)
    por imagens reais buscadas dos artigos.

    Busca og:image via _fetch_article_image (200KB, 4 padrões, valida download)
    e faz upload para CDN público.

    Modifica carousel_data in-place e também retorna o dict.
    """
    from image_generator import _fetch_article_image, _upload_image

    items = carousel_data.get("items", [])

    # Cover image → primeira notícia disponível
    cover_fetched = False
    for i, news in enumerate(news_list):
        url = news.get("url", "")
        if not url:
            continue
        try:
            img_bytes = _fetch_article_image(url)
            if img_bytes:
                cdn_url = _upload_image(img_bytes)
                if cdn_url:
                    carousel_data["cover_image_url"] = cdn_url
                    cover_fetched = True
                    logger.info(f"Cover image: {cdn_url[:60]}")
                    break
        except Exception as e:
            logger.warning(f"Falha cover image ({url[:50]}): {e}")

    if not cover_fetched:
        carousel_data["cover_image_url"] = None

    # Imagens de cada slide → notícia correspondente por índice
    for i, item in enumerate(items):
        news = news_list[i] if i < len(news_list) else None
        url = news.get("url", "") if news else ""
        item["image_url"] = None  # reset — não confiar no Groq

        if not url:
            continue
        try:
            img_bytes = _fetch_article_image(url)
            if img_bytes:
                cdn_url = _upload_image(img_bytes)
                if cdn_url:
                    item["image_url"] = cdn_url
                    logger.info(f"Slide {i+1} image: {cdn_url[:60]}")
        except Exception as e:
            logger.warning(f"Falha imagem slide {i+1} ({url[:50]}): {e}")

    return carousel_data


def generate_reel_caption(news_list: list) -> str:
    """Gera legenda curta e impactante para o Reel."""
    titles = " | ".join(n.get("title", "")[:40] for n in news_list[:3])
    try:
        return _call_groq(
            REEL_CAPTION_SYSTEM,
            f"Noticias do reel: {titles}\nEscreva a legenda completa.",
            max_tokens=300,
        )
    except Exception:
        return "Os maiores anúncios da semana em 30 segundos 🎬\n\n#MorsaDigital #Nerd #CulturaPop"


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

def run_carousel(carousel_type: str = "top_n", news_count: int = 5) -> dict:
    """
    Pipeline completo: busca notícias → gera carrossel → publica.
    Chamado pelo GitHub Actions (editorial job).
    """
    from publishers.instagram import publish_carousel
    from posts_log import is_duplicate, record_post

    logger.info(f"Iniciando carrossel editorial: {carousel_type}")

    # 1. Buscar notícias do dia
    news = fetch_all_news(limit=25)
    if not news:
        raise ValueError("Sem notícias disponíveis para carrossel")

    # Filtrar por qualidade — pegar as top N
    from content_generator import select_best_news
    best = select_best_news(news, count=news_count)

    # 2. Gerar conteúdo editorial
    carousel_data = generate_carousel_content(best, carousel_type)

    # 3. Checar duplicata — evitar repetir o mesmo carrossel
    carousel_title = carousel_data.get("title", "")
    if is_duplicate(carousel_title, platform="instagram", lookback_days=1):
        raise ValueError(
            f"Carrossel duplicado (publicado nas últimas 24h): {carousel_title!r}"
        )

    # 4. Buscar imagens reais dos artigos (substitui urls do Groq, não confiáveis)
    logger.info("Buscando imagens dos slides via og:image...")
    carousel_data = _fetch_carousel_images(carousel_data, best)

    # 5. Gerar legenda
    caption = generate_carousel_caption(carousel_data)

    # 6. Publicar
    result = publish_carousel(carousel_data, caption)

    # 7. Registrar no log para evitar duplicatas futuras
    media_id = result.get("media_id", result.get("id", ""))
    cover_url = carousel_data.get("cover_image_url", "")
    record_post(
        media_id=media_id,
        platform="instagram",
        news_item={"title": carousel_title, "source": "editorial", "url": ""},
        caption=caption,
        image_url=cover_url or "",
    )

    logger.info(f"✅ Carrossel publicado: {result}")
    return result


def _load_backlog() -> list:
    """Carrega o backlog de trailers curados."""
    import json
    backlog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trailer_backlog.json")
    try:
        with open(backlog_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        return [i for i in items if not i.get("postado", False)]
    except Exception as e:
        logger.warning(f"Falha ao carregar backlog: {e}")
        return []


def _mark_backlog_posted(item_id: str):
    """Marca um item do backlog como postado."""
    import json
    backlog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trailer_backlog.json")
    try:
        with open(backlog_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            if item.get("id") == item_id:
                item["postado"] = True
        with open(backlog_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Falha ao marcar backlog: {e}")


def run_reel(news_count: int = 10) -> dict:
    """
    Pipeline completo de Reels de trailers.

    Prioridade:
      1. Backlog curado (data/trailer_backlog.json) — filmes com contexto preciso
      2. RSS feeds — trailers detectados automaticamente

    Lógica de posts:
      - Tem versão vertical nativa  → posta horizontal + vertical (2 Reels)
      - Só tem horizontal           → posta só horizontal (1 Reel)
    """
    from publishers.instagram import publish_video_reel
    from reel_downloader import download_and_process, is_trailer_news
    from content_generator import select_best_news, generate_trailer_caption
    from posts_log import is_duplicate, record_post

    logger.info("Iniciando reel de trailer")

    # Monta lista de candidatos: backlog primeiro, depois RSS
    candidates = []

    # 1. Backlog curado (prioridade 1 primeiro)
    backlog = sorted(_load_backlog(), key=lambda x: x.get("prioridade", 99))
    for item in backlog:
        candidates.append({
            "title":    item["titulo"],
            "source":   "backlog",
            "url":      "",
            "description": item.get("contexto", ""),
            # Campos extras para legenda
            "contexto": item.get("contexto", ""),
            "elenco":   item.get("elenco", ""),
            "ano":      item.get("ano", ""),
            "_backlog_id":    item["id"],
            "_query_youtube": item.get("query_youtube", item["titulo"] + " trailer dublado"),
        })

    # 2. RSS — notícias com trailer detectado automaticamente
    try:
        news = fetch_all_news(limit=40)
        best = select_best_news(news, count=news_count)
        for n in best:
            if is_trailer_news(n):
                candidates.append(n)
    except Exception as e:
        logger.warning(f"Falha ao buscar RSS: {e}")

    if not candidates:
        raise ValueError("Sem candidatos para Reel")

    logger.info(f"{len(candidates)} candidatos (backlog + RSS)")

    # 3. Processa candidatos em ordem até publicar 1
    for news_item in candidates:
        title = news_item.get("title", "")

        if is_duplicate(title, platform="instagram_reel", lookback_days=14):
            logger.info(f"Já postado recentemente: {title[:60]}")
            continue

        logger.info(f"Processando: {title[:60]}")

        # Usa query customizada do backlog se disponível
        if news_item.get("_query_youtube"):
            news_item["_search_query_override"] = news_item["_query_youtube"]

        video_paths = download_and_process(news_item)

        if not video_paths:
            logger.warning(f"Não conseguiu baixar: {title[:60]}")
            continue

        # Gera legenda com contexto real
        caption = generate_trailer_caption(news_item)
        logger.info(f"Legenda gerada ({len(caption)} chars)")

        # Publica cada versão (horizontal + vertical se existir)
        results = []
        for i, video_path in enumerate(video_paths):
            fmt = "vertical" if i > 0 else "horizontal"
            logger.info(f"Publicando Reel {fmt}: {video_path}")
            try:
                result = publish_video_reel(video_path, caption)
                results.append(result)
                record_post(
                    media_id=result.get("id", ""),
                    platform="instagram_reel",
                    news_item=news_item,
                    caption=caption,
                    image_url="",
                )
                logger.info(f"✅ Reel {fmt} publicado: {result.get('id')}")
            except Exception as e:
                logger.error(f"Erro ao publicar Reel {fmt}: {e}")

        if results:
            # Marca no backlog se veio de lá
            if news_item.get("_backlog_id"):
                _mark_backlog_posted(news_item["_backlog_id"])
            return results[0]

    raise ValueError("Não foi possível publicar nenhum Reel")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    mode = sys.argv[1] if len(sys.argv) > 1 else "carousel"

    if mode == "carousel":
        ctype = sys.argv[2] if len(sys.argv) > 2 else "top_n"
        result = run_carousel(carousel_type=ctype)
    elif mode == "reel":
        result = run_reel()
    else:
        print(f"Uso: python editorial.py [carousel|reel] [top_n|deep_dive|event_recap]")
        sys.exit(1)

    print(f"Publicado: {result}")
