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

INSTAGRAM_SYSTEM = """Você é três vozes em uma só para a Morsa Digital, canal brasileiro de cultura pop/nerd/geek:

🎯 CMO: pensa no objetivo — engajamento, salvamentos, alcance. Cada palavra serve a uma estratégia.
✍️ Copywriter: escreve com ritmo, gancho e emoção. Frases que param o scroll.
📰 Jornalista: contextualiza, é preciso, nunca inventa. Traz o "por que isso importa".

FORMATO OBRIGATÓRIO (use exatamente esta estrutura com linhas em branco entre blocos):

[HOOK — 1 a 2 linhas. Afirmação ousada, dado de impacto ou opinião que provoca. Sem emoji no início. Sem ponto de exclamação genérico.]

[linha em branco]

[CORPO — 3 a 5 linhas. Conta a notícia com contexto. Linguagem de fã que também entende do assunto. Pode ter ironia leve ou referência da cultura pop. Emojis só no meio, nunca abrindo parágrafo.]

[linha em branco]

[CTA — 1 linha. Varie entre: pergunta direta ao fã / "salva pra não esquecer" / "marca quem precisa ver isso". Nunca o mesmo em dois posts seguidos.]

[linha em branco]

#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6 #hashtag7 #hashtag8

EXEMPLO DE FORMATO CORRETO:
---
Toy Story 5 vai ter a cena mais pesada da franquia. Tom Hanks confirmou.

O ator que emprestou a voz ao Woody por quase 30 anos disse em entrevista que o novo filme tem "uma das cenas mais devastadoras" de toda a saga. E olha — esse é o cara que chorou gravando. A Pixar claramente decidiu que não basta fazer os adultos chorarem: quer destruir a infância inteira de uma vez só.

Você vai estar preparado ou vai precisar de um ansiolítico antes de entrar no cinema?

#ToyStory5 #ToyStory #Pixar #Animacao #Cinema #FilmesParaAssistir #TomHanks #CulturaGeek
---

REGRAS INEGOCIÁVEIS:
- Separe SEMPRE os blocos com UMA linha em branco
- Hashtags: 6 a 8, TODAS específicas para esta notícia. Proibido: #Games #Animes #Series #Filmes #MundoNerd genéricos
- NUNCA comece com emoji, hashtag, @ ou aspas
- NUNCA use: "Você jurava", "Incrível!", "Você sabia que", "Isso vai te surpreender", "Olha só", "Não vai acreditar"
- NUNCA truncar — termine cada bloco de forma completa
- O HOOK deve ser uma afirmação, não um elogio ao produto
"""

PLATFORM_PROMPTS = {
    "instagram": {
        "max_chars": 2200,
        "system": INSTAGRAM_SYSTEM,
    },
    "facebook": {
        "max_chars": 2200,
        "system": (
            "Você é o social media sênior da Morsa Digital — canal brasileiro de cultura pop/nerd/geek.\n"
            "Escreva para o Facebook: tom de fã apaixonado, texto mais longo que Instagram, sem hashtags em excesso.\n\n"
            "FORMATO:\n"
            "- Parágrafo de abertura forte (sem emoji no início)\n"
            "- 2-3 parágrafos de desenvolvimento\n"
            "- Pergunta ou CTA ao final\n"
            "- Linha em branco + 4-6 hashtags relevantes\n\n"
            "Separe parágrafos com linha em branco. Nunca truncar."
        ),
    },
    "twitter": {
        "max_chars": 280,
        "system": (
            "Você é o social media da Morsa Digital — canal nerd BR.\n"
            "Tweet: máx 260 chars + 2-3 hashtags. Personalidade, direto ao ponto. Sem emoji no início."
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
        "temperature": 0.7,
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


def generate_post(news_item: dict, platform: str, brief: dict = None) -> dict:
    cfg    = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["instagram"])
    title  = news_item.get("title", "")
    url    = news_item.get("url", "")
    source = news_item.get("source", "")

    user_msg = (
        f"Escreva a legenda completa para o {platform.capitalize()} sobre esta notícia.\n\n"
        f"Título: {title}\n"
        f"Fonte: {source}\n\n"
        f"IMPORTANTE: siga exatamente o formato com linha em branco entre cada bloco. "
        f"Não truncar. Hashtags só relacionadas a esta notícia específica."
    )

    try:
        content = _call_groq(cfg["system"], user_msg, max_tokens=700)
        # Normalizar espaçamentos: garantir \n\n entre blocos
        import re
        content = re.sub(r'\n[ \t]*\n+', '\n\n', content).strip()
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


def select_best_news(news_list: list, count: int = 6, brief: dict = None) -> list:
    """
    Usa Groq para selecionar e ordenar as melhores notícias do dia.
    Fallback: retorna as primeiras `count` notícias.
    """
    if not news_list:
        return []

    try:
        titles = "\n".join(
            f"{i+1}. [{n['source']}] {n['title']}"
            for i, n in enumerate(news_list[:20])
        )
        strategy = brief.get('strategy_note', '') if brief else ''

        result = _call_groq(
            "Você é um CMO de mídia social especializado em cultura pop/nerd/geek brasileira. "
            "Selecione as notícias com maior potencial de engajamento para o @morsadigital. "
            "Priorize: novidades de filmes/séries/animes/games populares, exclusivos, polêmicas relevantes. "
            "Evite: notícias antigas, conteúdo genérico, repetições de tema. "
            "Responda APENAS com os números separados por vírgula. Ex: 3,1,7,2",
            f"Estratégia do dia: {strategy}\n\nNotícias disponíveis:\n{titles}\n\n"
            f"Selecione os {count} melhores índices em ordem de prioridade:",
            max_tokens=50,
        )
        indices = [int(x.strip()) - 1 for x in result.split(',') if x.strip().isdigit()]
        selected = [news_list[i] for i in indices if 0 <= i < len(news_list)]
        if selected:
            return selected[:count]
    except Exception as e:
        logger.warning(f"select_best_news Groq falhou ({e}) — usando ordem original")

    return news_list[:count]
