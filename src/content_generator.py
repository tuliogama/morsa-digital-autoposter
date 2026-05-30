"""
Gera posts adaptados por plataforma usando Claude API (Haiku — baixo custo).
"""
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"

PLATFORM_PROMPTS = {
    "twitter": {
        "max_chars": 280,
        "system": (
            "Você é o social media da Morsa Digital — canal tech brasileiro descontraído, nerd e autêntico. "
            "Escreve tweets curtos (máx 280 chars) sobre tecnologia com personalidade: pode usar gírias, "
            "emojis moderados, referências geek. Sempre inclui 2-3 hashtags relevantes em português e inglês. "
            "Nunca inventa fatos — apenas comenta/adapta o que foi informado. Fim do tweet sem URL (a URL é adicionada separado)."
        ),
    },
    "instagram": {
        "max_chars": 2200,
        "system": (
            "Você é o social media sênior da Morsa Digital — perfil brasileiro de cultura geek/nerd/pop "
            "focado em filmes, séries, animes, doramas e games. Você escreve como um fã apaixonado, "
            "não como uma máquina. Cada legenda é única, humana e tem personalidade.\n\n"

            "ESTRUTURA (adapte conforme a notícia — não seja robótico):\n"
            "1. HOOK (1-2 linhas): A abertura mais importante. Pode ser:\n"
            "   - Uma afirmação ousada: 'Isso vai dividir a internet.'\n"
            "   - Uma pergunta que gera curiosidade: 'Você ainda acredita nisso?'\n"
            "   - Um dado ou fato surpreendente: '3 anos esperando e chegou assim.'\n"
            "   - Uma opinião provocadora relacionada à notícia\n"
            "   NÃO comece com emoji forçado, hashtag ou frase genérica tipo 'Novidade!'\n\n"
            "2. CORPO (3-5 linhas): Conta a notícia com contexto, como um jornalista que também é fã. "
            "   Use linguagem natural, pode ter uma ironia leve, referência da cultura pop, comparação "
            "   com algo que o público conhece. Emojis são bem-vindos no MEIO do texto quando fazem sentido, "
            "   não no começo de cada linha.\n\n"
            "3. CTA (1-2 linhas): Varie entre estilos — às vezes uma pergunta direta, às vezes 'salva pra "
            "   não esquecer', às vezes 'marca quem precisa saber disso'. Nunca repita o mesmo CTA.\n\n"
            "4. HASHTAGS (linha em branco antes, 6-10 tags): Mix estratégico:\n"
            "   - 2-3 tags de nicho específico da notícia (ex: #DemonSlayer, #PS5, #StrangerThings)\n"
            "   - 2-3 tags de categoria média (ex: #Anime, #Games, #Netflix)\n"
            "   - 1-2 tags amplas em português (ex: #CulturaPop, #MundoNerd)\n\n"
            "SEO NO INSTAGRAM: use palavras-chave relevantes naturalmente no texto (não só nas hashtags). "
            "O algoritmo indexa o texto da legenda. Se a notícia é sobre GTA 6, mencione 'GTA 6' no texto.\n\n"
            "PROIBIDO (qualquer um desses = reescrever do zero):\n"
            "- Começar com hashtag, @, emoji ou '#post'/'#instagram'\n"
            "- Emojis no início de cada parágrafo (parece bot)\n"
            "- Frases genéricas de página barata: 'Incrível notícia!', 'Que novidade!', 'Você sabia que...', "
            "'Você jurava que...', 'Você ainda acredita que...', 'Isso vai te surpreender', 'Olha só:', "
            "'Não vai acreditar', 'Todo mundo está falando sobre', 'É isso mesmo!'\n"
            "- Exagero clickbait: 'vai DESTRUIR você', 'vai te deixar de queixo caído', 'ninguém esperava'\n"
            "- Tom de fofoca ou sensacionalismo barato\n"
            "- Mesmo CTA toda legenda\n"
            "- Inventar fatos — adapta apenas o que foi informado\n"
            "- Mais de 12 hashtags"
        ),
    },
    "facebook": {
        "max_chars": 1500,
        "system": (
            "Você é o social media da Morsa Digital — canal tech brasileiro. "
            "Escreve posts de Facebook sobre tecnologia com tom acessível: mais explicativo que Instagram, "
            "menos hashtags (3-4 max), incentiva discussão nos comentários. "
            "Estrutura: título em negrito (com **) + desenvolvimento + pergunta para engajar. "
            "Nunca inventa fatos — apenas comenta/adapta o que foi informado."
        ),
    },
}


def _call_claude(system_prompt: str, user_message: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada")

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }).encode("utf-8")

    req = urllib.request.Request(
        CLAUDE_API_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Claude API erro {e.code}: {body}")


def generate_image_headline(news_item: dict) -> str:
    """
    Gera um headline curto e impactante para sobrepor na imagem — estilo IGN Brasil.
    ALL CAPS aplicado depois. Claude retorna em caixa normal.
    Máximo 8 palavras, sem reticências, com SEO.
    """
    title = news_item.get("title", "")
    description = news_item.get("description", "")[:300]

    try:
        result = _call_claude(
            "Você é editor de headline de um portal brasileiro de cultura pop/nerd/geek. "
            "Cria manchetes curtas, diretas e impactantes — no estilo IGN Brasil. "
            "Nunca usa reticências. Nunca usa clickbait barato. Sempre factual.",
            f"Notícia: {title}\nContexto: {description}\n\n"
            "Crie UMA manchete de impacto para sobrepor em imagem de post Instagram. "
            "Regras: máximo 8 palavras, sem reticências (...), sem ponto final, "
            "inclua o nome do personagem/jogo/série para SEO, "
            "seja direto e factual — não invente. "
            "Responda APENAS a manchete, sem aspas, sem explicação."
        )
        # Limpar e retornar
        headline = result.strip().strip('"').strip("'").strip()
        # Remover reticências se Claude ignorar a instrução
        headline = headline.replace("...", "").replace("…", "").strip()
        return headline if headline else title[:60]
    except Exception:
        # Fallback: usar título truncado de forma limpa
        words = title.split()
        fallback = " ".join(words[:7])
        return fallback


def select_best_news(news_items: list[dict], count: int = 5, brief: dict = None) -> list[dict]:
    """Usa Claude para escolher as notícias mais relevantes, guiado pelo Day Brief do CMO."""
    if not news_items:
        return []

    titles_block = "\n".join(
        f"{i+1}. [{item['source']}] {item['title']}"
        for i, item in enumerate(news_items[:50])
    )

    # Contexto do Day Brief se disponível
    brief_context = ""
    if brief:
        brief_context = (
            f"\nDIRETRIZES DO DIA (Day Brief do CMO):\n"
            f"- Estratégia: {brief.get('strategy_note', '')}\n"
            f"- Priorizar categorias: {', '.join(brief.get('prioritize_categories', []))}\n"
            f"- Priorizar fontes: {', '.join(brief.get('prioritize_sources', []))}\n"
            f"- Ângulo editorial: {brief.get('content_angle', '')}\n"
            f"- Tópicos em alta para explorar: {', '.join(brief.get('topics_to_explore', []))}\n"
            f"- EVITAR (já cobertos ou baixo engajamento): {', '.join(brief.get('avoid_topics', [])[:5])}\n"
        )

    prompt = (
        f"Lista de notícias disponíveis:\n\n{titles_block}\n"
        f"{brief_context}\n"
        f"Selecione os {count} itens com maior potencial de engajamento para o público brasileiro "
        f"que ama filmes, séries, animes, doramas, games e cultura pop/nerd/geek.\n"
        f"PRIORIZE: lançamentos, trailers, anúncios oficiais, franquias populares "
        f"(Marvel, DC, Star Wars, anime, Nintendo, PlayStation, Xbox).\n"
        f"EVITE: IA genérica, robótica, finanças, política, podcasts, "
        f"celebridades sem relação com cultura pop, listas genéricas sem novidade.\n"
        f"Responda APENAS com os números separados por vírgula, ex: 1,3,7,12,15"
    )

    try:
        result = _call_claude(
            "Você é curador sênior de conteúdo geek/nerd/pop para o público brasileiro. "
            "Toma decisões editoriais baseadas em dados de performance e tendências do dia.",
            prompt,
        )
        indices = [int(x.strip()) - 1 for x in result.split(",") if x.strip().isdigit()]
        selected = [news_items[i] for i in indices if 0 <= i < len(news_items)]
        return selected[:count]
    except Exception as e:
        logger.warning(f"Seleção automática falhou, usando top por score: {e}")
        return news_items[:count]


def generate_post(news_item: dict, platform: str, brief: dict = None) -> dict:
    """Gera um post para a plataforma especificada, orientado pelo Day Brief do CMO."""
    config = PLATFORM_PROMPTS.get(platform)
    if not config:
        raise ValueError(f"Plataforma desconhecida: {platform}")

    # Contexto do Day Brief para orientar o tom e estilo
    brief_context = ""
    if brief:
        hook = brief.get("recommended_hook_style", "")
        insight = brief.get("engagement_insight", "")
        angle = brief.get("content_angle", "")
        if hook or insight or angle:
            brief_context = (
                f"\nCONTEXTO DO DIA (use para calibrar o tom):\n"
                f"- Hook que está performando: {hook}\n"
                f"- Ângulo editorial de hoje: {angle}\n"
                f"- Insight de engajamento: {insight}\n"
            )

    user_msg = (
        f"Notícia: {news_item['title']}\n"
        f"Fonte: {news_item['source']}\n"
        f"URL: {news_item.get('url', '')}\n"
        f"{brief_context}\n"
        f"Gere um post para {platform} (máx {config['max_chars']} caracteres)."
    )

    content = _call_claude(config["system"], user_msg)

    # Gera headline curto para sobrepor na imagem (estilo IGN Brasil)
    image_headline = generate_image_headline(news_item)

    return {
        "platform": platform,
        "content": content,
        "url": news_item.get("url", ""),
        "source_title": news_item["title"],
        "source": news_item["source"],
        "image_headline": image_headline,
        "generated_at": datetime.utcnow().isoformat(),
        "news_item": news_item,
    }


def generate_all_posts(news_items: list[dict], platforms: list[str] = None) -> list[dict]:
    """Gera posts para todas as plataformas a partir das notícias selecionadas."""
    if platforms is None:
        platforms = ["twitter", "instagram", "facebook"]

    best = select_best_news(news_items, count=len(platforms) * 2)
    posts = []
    news_pool = list(best)

    for platform in platforms:
        if not news_pool:
            break
        news = news_pool.pop(0)
        try:
            post = generate_post(news, platform)
            posts.append(post)
            logger.info(f"Post gerado para {platform}: {news['title'][:60]}...")
        except Exception as e:
            logger.error(f"Erro ao gerar post para {platform}: {e}")

    return posts
