"""
Gera posts adaptados por plataforma usando Groq API (Llama 3.3 70B — gratuito).
Fallback: templates sem IA se a API falhar.
"""
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

PLATFORM_PROMPTS = {
    "instagram": {
        "max_chars": 2200,
        "system": (
            "Você é o social media sênior da Morsa Digital — perfil brasileiro de Star Wars "
            "focado em filmes, séries, animes, doramas e games. Você escreve como um fã apaixonado, "
            "não como uma máquina. Cada legenda é única, humana e tem personalidade.\n\n"
            "ESTRUTURA:\n"
            "1. HOOK (1-2 linhas): afirmação ousada, dado surpreendente ou opinião provocadora. "
            "NÃO comece com emoji, hashtag ou frases genéricas.\n"
            "2. CORPO (3-5 linhas): conta a notícia com contexto, linguagem natural, pode ter ironia leve.\n"
            "3. CTA (1-2 linhas): variado — pergunta, 'salva pra não esquecer', 'marca quem precisa saber'.\n"
            "4. HASHTAGS (6-10 tags): mix nicho + categoria + amplas em PT.\n\n"
            "PROIBIDO: começar com emoji/hashtag, 'Você jurava', 'Incrível notícia!', 'Você sabia que', "
            "'Isso vai te surpreender', 'Olha só:', mesmo CTA toda legenda, emojis no início de cada parágrafo."
        ),
    },
    "facebook": {
        "max_chars": 2200,
        "system": (
            "Você é o social media sênior da Morsa Digital — perfil brasileiro de Star Wars. "
            "Escreva uma legenda humana e engajante para o Facebook, com tom de fã apaixonado. "
            "Use 4-8 hashtags estratégicas no final. Sem frases genéricas ou emojis no início."
        ),
    },
    "twitter": {
        "max_chars": 280,
        "system": (
            "Você é o social media da Morsa Digital — canal tech brasileiro descontraído e nerd. "
            "Escreva um tweet de no máximo 280 caracteres com personalidade. Inclua 2-3 hashtags."
        ),
    },
}


def _call_groq(system: str, user_msg: str, max_tokens: int = 600) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY não configurada")

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": 0.8,
    }).encode()

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/7.88.1",
            "Accept": "*/*",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def _template_caption(news_item: dict, platform: str) -> str:
    """Fallback sem IA quando a API não está disponível."""
    title  = news_item.get("title", "")
    source = news_item.get("source", "")
    tags   = "#MundoNerd #CulturaPop #GeekBrasil"
    return f"{title}\n\nVia {source}.\n\n{tags}"


def generate_post(news_item: dict, platform: str) -> dict:
    cfg    = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["instagram"])
    title  = news_item.get("title", "")
    url    = news_item.get("url", "")
    source = news_item.get("source", "")

    user_msg = (
        f"Crie uma legenda para o {platform.capitalize()} sobre esta notícia:\n"
        f"Título: {title}\nFonte: {source}\nURL: {url}\n\n"
        f"Escreva a legenda completa pronta para publicar."
    )

    try:
        content = _call_groq(cfg["system"], user_msg)
        logger.info(f"Legenda gerada via Groq ({len(content)} chars)")
    except Exception as e:
        logger.warning(f"Groq falhou ({e}) — usando template")
        content = _template_caption(news_item, platform)

    # Headline para a imagem: gerado pelo Groq — curto, completo, sem reticências
    try:
        image_headline = _call_groq(
            "Você cria headlines curtos para imagens de posts de Instagram no estilo IGN Brasil. "
            "Máximo 6 palavras. ALL CAPS não necessário. Sem reticências. Sem ponto final. "
            "A frase deve ser completa e fazer sentido sozinha.",
            f"Crie um headline de imagem para esta notícia: {title}",
            max_tokens=30,
        ).strip().strip('"').strip("'").rstrip(".")
    except Exception:
        # Fallback: pegar até 6 palavras que formem sentido
        words = title.split()
        image_headline = " ".join(words[:6])

    return {
        "content":        content[:cfg["max_chars"]],
        "platform":       platform,
        "news_item":      news_item,
        "image_headline": image_headline,
    }
