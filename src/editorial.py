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
    """Tenta extrair og:image de cada URL de notícia."""
    import urllib.request
    import re

    result = []
    for slide in slides:
        url = slide.get("news", {}).get("url", "")
        og_image = None

        if url:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "MorsaDigital-Autoposter/1.0"},
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    html = r.read(50000).decode("utf-8", errors="replace")

                # Buscar og:image
                match = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    html, re.IGNORECASE
                ) or re.search(
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                    html, re.IGNORECASE
                )
                if match:
                    og_image = match.group(1)
            except Exception:
                pass

        if og_image:
            result.append({
                "image_url": og_image,
                "text": slide["text"],
            })
        # Se não achou imagem, pula — reel precisa de imagens reais

    return result


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

    # 3. Gerar legenda
    caption = generate_carousel_caption(carousel_data)

    # 4. Publicar
    result = publish_carousel(carousel_data, caption)

    logger.info(f"✅ Carrossel publicado: {result}")
    return result


def run_reel(news_count: int = 4) -> dict:
    """
    Pipeline completo: busca notícias → gera reel → publica.
    Chamado pelo GitHub Actions (reel job).
    """
    from publishers.instagram import publish_reel

    logger.info("Iniciando reel editorial")

    # 1. Buscar notícias
    news = fetch_all_news(limit=20)
    if not news:
        raise ValueError("Sem notícias para reel")

    from content_generator import select_best_news
    best = select_best_news(news, count=news_count)

    # 2. Preparar dados do reel (inclui busca de og:images)
    reel_data = generate_reel_data(best)

    if len(reel_data.get("slides", [])) < 3:
        raise ValueError("Não foi possível obter imagens suficientes para o reel")

    # 3. Gerar legenda
    caption = generate_reel_caption(best)

    # 4. Publicar
    result = publish_reel(reel_data, caption)

    logger.info(f"✅ Reel publicado: {result}")
    return result


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
