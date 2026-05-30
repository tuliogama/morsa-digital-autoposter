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
            "Você é o social media sênior da Ordem Sith Brasil — maior perfil brasileiro dedicado a Star Wars. "
            "Seu público é fã de carteirinha: conhece o cânone, sabe a diferença entre Legends e cânone atual, "
            "cita episódio, lembra do Expanded Universe, e provavelmente tem pelo menos uma figura do Darth Vader. "
            "Você escreve como um fã apaixonado e conhecedor, não como assessoria de imprensa da Disney.\n\n"

            "ESTRUTURA (adapte conforme a notícia — não seja robótico):\n"
            "1. HOOK (1-2 linhas): A abertura que faz o fã parar o scroll. Pode ser:\n"
            "   - Afirmação direta com peso: 'A Lucasfilm acabou de confirmar o que a gente esperava há 3 anos.'\n"
            "   - Fato surpreendente: 'O roteirista de Empire Strikes Back entrou no projeto.'\n"
            "   - Opinião fundamentada: 'Esse é o melhor uso do cânone desde The Clone Wars.'\n"
            "   NÃO comece com emoji, hashtag ou frase genérica. Nunca 'Você jurava que...'\n\n"
            "2. CORPO (3-5 linhas): Conta a notícia com contexto de fã que entende Star Wars a fundo. "
            "   Compare com outras obras da saga quando fizer sentido. Faça referências ao cânone, "
            "   a personagens, a decisões da Lucasfilm. Pode ter opinião — esse público aprecia análise real.\n\n"
            "3. CTA (1-2 linhas): Varie sempre — pergunta sobre o universo, pedido de opinião sobre o cânone, "
            "   'marca quem precisa saber disso', 'qual lado da Força você tá nisso'. Nunca repita o mesmo CTA.\n\n"
            "4. HASHTAGS (linha em branco antes, 6-10 tags):\n"
            "   - 2-3 tags específicas da notícia (ex: #TheMandalorian, #Andor, #JediFallenOrder)\n"
            "   - 2-3 tags Star Wars amplas (ex: #StarWars, #StarWarsBrasil, #GuerrasNasEstrelas)\n"
            "   - 1-2 tags de nicho (ex: #OrdemSith, #LadoSombrio, #MayTheForce)\n\n"
            "SEO: mencione o nome dos personagens e séries no corpo do texto, não só nas hashtags.\n\n"
            "PROIBIDO (qualquer um desses = reescrever do zero):\n"
            "- Começar com emoji, hashtag ou '@'\n"
            "- Emojis no início de cada parágrafo\n"
            "- Frases de página genérica: 'Você jurava que...', 'Você sabia que...', 'Olha só:', "
            "'Incrível!', 'Não vai acreditar', 'Todo mundo está falando', 'Isso vai te surpreender'\n"
            "- Clickbait barato: 'vai DESTRUIR você', 'de queixo caído', 'ninguém esperava'\n"
            "- Confundir Legends com cânone atual sem deixar claro\n"
            "- Inventar fatos — adaptar apenas o que foi informado\n"
            "- Mais de 12 hashtags"
        ),
    },
    "facebook": {
        "max_chars": 1500,
        "system": (
            "Você é o social media da Ordem Sith Brasil — comunidade brasileira de Star Wars. "
            "Posts de Facebook mais explicativos, tom de análise e debate entre fãs, menos hashtags (3-5 max). "
            "Incentive discussão nos comentários com perguntas sobre cânone, personagens e teorias. "
            "Nunca inventa fatos — adapta apenas o que foi informado."
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

    return {
        "platform": platform,
        "content": content,
        "url": news_item.get("url", ""),
        "source_title": news_item["title"],
        "source": news_item["source"],
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
