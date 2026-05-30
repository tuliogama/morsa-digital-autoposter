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
            "Você é o social media da Morsa Digital — perfil brasileiro de cultura geek/nerd/pop. "
            "Foco total em: filmes, séries, animes, doramas, games e cultura pop. "
            "Escreve legendas de Instagram com personalidade: tom informal, animado, cheio de referências nerds. "
            "ESTRUTURA OBRIGATÓRIA:\n"
            "1. Gancho forte com emoji (1 linha — frase de impacto, pode ser pergunta ou exclamação)\n"
            "2. Desenvolvimento (3-5 linhas — contexto da notícia de forma envolvente)\n"
            "3. CTA engajador ('Conta nos comentários!', 'O que você acha?', 'Você vai assistir?'...)\n"
            "4. Hashtags (5-8, todas no final, nunca antes do texto)\n\n"
            "REGRAS ABSOLUTAS:\n"
            "- NUNCA comece com hashtag, '#', '@' ou qualquer símbolo\n"
            "- NUNCA use '#post', '#instagram', '#repost' ou similares\n"
            "- A legenda começa SEMPRE com o emoji do gancho, nada antes\n"
            "- Hashtags SÓ no final, após uma linha em branco\n"
            "- Nunca inventa fatos — apenas comenta/adapta o que foi informado"
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


def select_best_news(news_items: list[dict], count: int = 5) -> list[dict]:
    """Usa Claude para escolher as notícias mais relevantes e engajadoras."""
    if not news_items:
        return []

    titles_block = "\n".join(
        f"{i+1}. [{item['source']}] {item['title']}"
        for i, item in enumerate(news_items[:25])
    )

    prompt = (
        f"Lista de notícias recentes:\n\n{titles_block}\n\n"
        f"Selecione os {count} itens mais relevantes para o público brasileiro que ama "
        f"filmes, séries, animes, doramas, games e cultura pop/nerd/geek. "
        f"PRIORIZE: lançamentos, trailers, notícias de franquias populares (Marvel, DC, Star Wars, anime, Nintendo, PlayStation...). "
        f"EVITE: notícias de IA genérica, robôs, finanças, política, celebridades sem relação com cultura pop. "
        f"Responda APENAS com os números separados por vírgula, ex: 1,3,7,12,15"
    )

    try:
        result = _call_claude(
            "Você é curador de conteúdo geek/nerd/pop para o público brasileiro. "
            "Prioriza filmes, séries, animes, doramas e games. Ignora tech genérico.",
            prompt,
        )
        indices = [int(x.strip()) - 1 for x in result.split(",") if x.strip().isdigit()]
        selected = [news_items[i] for i in indices if 0 <= i < len(news_items)]
        return selected[:count]
    except Exception as e:
        logger.warning(f"Seleção automática falhou, usando top por score: {e}")
        return news_items[:count]


def generate_post(news_item: dict, platform: str) -> dict:
    """Gera um post para a plataforma especificada com base na notícia."""
    config = PLATFORM_PROMPTS.get(platform)
    if not config:
        raise ValueError(f"Plataforma desconhecida: {platform}")

    user_msg = (
        f"Notícia: {news_item['title']}\n"
        f"Fonte: {news_item['source']}\n"
        f"URL: {news_item.get('url', '')}\n\n"
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
