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

[CTA — 1 linha. OBRIGATÓRIO variar entre: pergunta que divide opiniões ("Você acha que vai superar o original?") / confronto de escolha ("Time Iron Man ou Team Cap?") / "marca aquele amigo que precisa ver isso" / "salva pra não esquecer". Posts com pergunta polêmica geram 5x mais comentários. Nunca o mesmo em dois posts seguidos.]

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
- NUNCA use: "Incrível!", "Você sabia que", "Isso vai te surpreender", "Olha só", "Não vai acreditar"
- NUNCA truncar — termine cada bloco de forma completa
- O HOOK deve ser uma afirmação direta ou opinião ousada — NUNCA pergunta genérica
- Mencione o nome da franquia/personagem no hook — é o que faz o fã parar o scroll
- NUNCA mencione vídeo, trailer ou conteúdo para assistir — o post é apenas imagem, não há vídeo anexado
- NUNCA use CTAs como "assista", "veja o vídeo", "confira o trailer" — direcione para comentar, salvar ou marcar alguém
- NUNCA INVENTE FATOS: não cite número de filmes ("terceiro", "quarto"), datas, bilheteria, elenco, nem qualquer dado que não esteja explícito na notícia fornecida. Se não sabe, não diz.

DADOS DE PERFORMANCE (use para calibrar o tom):
- Posts Marvel/DC com afirmação ousada sobre a franquia: +75% acima da média
- Hooks com opinião ("isso é preguiça criativa", "tem tudo para pisар") performam melhor que fatos neutros
- Fã brasileiro responde bem a: comparações entre franquias, polêmicas da indústria, spoilers controlados
"""

REEL_TRAILER_SYSTEM = """Você é o social media sênior da Morsa Digital — canal brasileiro de cultura pop/nerd/geek com 27k seguidores.

Você escreve legendas para Reels de trailers oficiais. O vídeo já está postado, a legenda deve COMPLEMENTAR — não descrever o que se vê.

ESTRUTURA OBRIGATÓRIA:

[REAÇÃO — 1 linha. Como um fã reagiria ao ver esse trailer pela primeira vez. Emoção real, sem spoilers óbvios. Sem emoji no início.]

[linha em branco]

[CONTEXTO — 2 a 3 linhas. O que torna esse filme/série especial. Por que a galera BR tá ansiosa. Dado concreto ou fato que eleva o hype.]

[linha em branco]

[HYPE/DEBATE — 1 linha. Pergunta que DIVIDE opiniões ou gera debate real. Ex: "Vai superar o original ou vai decepcionar?" / "Você tá no hype ou ainda na dúvida?" / "Qual cena te deixou mais ansioso?"]

[linha em branco]

#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6

REGRAS:
- Nunca descreva cenas específicas do trailer (quem não assistiu ainda vai ver no Reel)
- Mencione o nome da franquia/personagem na primeira linha
- Hashtags específicas: nome do filme + franquia + atores principais + #Trailer + #Cinema
- Tom: fã que assistiu e PRECISA falar sobre isso com alguém
- NUNCA use "assista", "confira o trailer acima" — eles já estão vendo
- Máximo 2200 caracteres
- NUNCA INVENTE FATOS: não cite número de filmes ("terceiro", "quarto"), datas, bilheteria, nem qualquer dado que não esteja explícito na notícia fornecida. Se não sabe, não diz.
- NUNCA use afirmações como "promete ser o mais épico de todos" — são vazias. Prefira o que o fã SENTE.
- Hook deve soar como fã brasileiro real, não like robô: "Tô hypado", "Que trailer foi esse?", "Não tô pronto pra isso" — linguagem natural BR
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


class CaptionGenerationError(Exception):
    """Lançada quando não é possível gerar uma legenda de qualidade. Post deve ser pulado."""


def _validate_caption(content: str, source: str) -> bool:
    """
    Rejeita legendas que parecem scraping ou estão vazias.
    Retorna False se a legenda não serve para publicar.
    """
    if not content or len(content) < 120:
        return False
    # Indicadores de fallback ou scraping
    bad_patterns = [
        f"via {source.lower()}",
        f"segundo o {source.lower()}",
        f"de acordo com o {source.lower()}",
        f"o {source.lower()} informou",
        f"o {source.lower()} destacou",
        f"o {source.lower()} relatou",
        "#mundонerd #culturaрор #geekbrasil",  # template genérico
        "mundонerd",
        "#MundoNerd #CulturaPop #GeekBrasil",
    ]
    content_lower = content.lower()
    source_lower = source.lower()
    for pat in bad_patterns:
        if pat.lower() in content_lower:
            return False
    # Não pode mencionar a fonte como origem do conteúdo
    if source_lower and f"o {source_lower}" in content_lower:
        return False
    return True


def generate_post(news_item: dict, platform: str, brief: dict = None) -> dict:
    import re
    cfg    = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["instagram"])
    title  = news_item.get("title", "")
    url    = news_item.get("url", "")
    source = news_item.get("source", "")

    user_msg = (
        f"Escreva a legenda completa para o {platform.capitalize()} sobre esta notícia.\n\n"
        f"Título: {title}\n\n"
        f"IMPORTANTE:\n"
        f"- Escreva como se a Morsa Digital estivesse reportando a notícia — NUNCA mencione o nome da fonte no texto\n"
        f"- Siga o formato com linha em branco entre cada bloco\n"
        f"- Não truncar — termine todas as frases\n"
        f"- Hashtags só relacionadas a esta notícia específica, nada genérico"
    )

    content = None
    last_error = None

    # Tentar até 2 vezes antes de desistir
    for attempt in range(2):
        try:
            raw = _call_groq(cfg["system"], user_msg, max_tokens=700)
            raw = re.sub(r'\n[ \t]*\n+', '\n\n', raw).strip()

            if _validate_caption(raw, source):
                content = raw
                logger.info(f"Legenda gerada via Groq ({len(content)} chars)")
                break
            else:
                logger.warning(f"Legenda rejeitada na validação (tentativa {attempt+1})")
        except Exception as e:
            last_error = e
            logger.warning(f"Groq falhou tentativa {attempt+1}: {e}")

    if not content:
        # Sem legenda válida → sinaliza para pular o post
        raise CaptionGenerationError(
            f"Não foi possível gerar legenda de qualidade para: {title[:60]}"
        )

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


def generate_trailer_caption(news_item: dict) -> str:
    """
    Gera legenda específica para Reel de trailer.
    Tom: reação de fã + contexto + pergunta que gera debate.
    Usa contexto real do filme se disponível no news_item.

    Passes data_estreia + status_calculado para o modelo saber quando
    o filme estreia e nunca inventar prazos ou ordinals errados.
    """
    import re
    from datetime import datetime

    title              = news_item.get("title", "")
    context            = news_item.get("contexto", "")
    elenco             = news_item.get("elenco", "")
    ano                = news_item.get("ano", "")
    data_estreia_str   = news_item.get("data_estreia", "")
    status_calculado   = news_item.get("_status_calculado", news_item.get("status", ""))

    # Monta bloco de fatos verificados para o modelo
    fatos = []
    if context:
        fatos.append(f"Contexto: {context}")
    if elenco:
        fatos.append(f"Elenco: {elenco}")
    if ano:
        fatos.append(f"Ano: {ano}")

    # Traduz a data para PT-BR legível e informa o status real
    if data_estreia_str:
        try:
            dt = datetime.strptime(data_estreia_str, "%Y-%m-%d")
            meses = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
            data_legivel = f"{dt.day} de {meses[dt.month-1]} de {dt.year}"
            if status_calculado == "pre_estreia":
                dias_faltam = (dt - datetime.now()).days
                fatos.append(f"Estreia: {data_legivel} (daqui {dias_faltam} dias — ainda NÃO estreou)")
            else:
                fatos.append(f"Estreia: {data_legivel} (já em cartaz)")
        except Exception:
            fatos.append(f"Data de estreia: {data_estreia_str}")

    fatos_block = "\n".join(fatos)

    user_msg = (
        f"Escreva a legenda para o Reel do trailer: {title}\n\n"
        f"FATOS VERIFICADOS — use APENAS estes, nunca invente outros:\n"
        f"{fatos_block}\n\n"
        f"PROIBIDO:\n"
        f"- Citar ordinal do filme (terceiro, quarto, etc.) a não ser que esteja explícito acima\n"
        f"- Inventar data de estreia diferente da fornecida\n"
        f"- Dizer que 'já está em cartaz' se o status indicar pre_estreia\n"
        f"- Dizer que 'estreia em breve' sem especificar o mês correto fornecido\n\n"
        f"Lembre: o trailer já está no vídeo. A legenda deve gerar reação e debate."
    )

    for attempt in range(2):
        try:
            raw = _call_groq(REEL_TRAILER_SYSTEM, user_msg, max_tokens=600)
            raw = re.sub(r'\n[ \t]*\n+', '\n\n', raw).strip()
            if len(raw) >= 100:
                logger.info(f"Legenda de trailer gerada ({len(raw)} chars)")
                return raw
        except Exception as e:
            logger.warning(f"Groq trailer legenda falhou tentativa {attempt+1}: {e}")

    return f"{title}\n\nO trailer chegou e a internet já está dividida.\n\nVocê tá no hype ou ainda na dúvida?\n\n#Trailer #Cinema #CulturaGeek"


def select_best_news(news_list: list, count: int = 6, brief: dict = None) -> list:
    """
    Usa Groq para selecionar e ordenar as melhores notícias do dia.
    Baseia-se em dados reais de performance do @morsadigital (análise jun/2026):
    - Marvel/DC: 17,6 likes avg (melhor categoria)
    - Filmes: 10,8 avg
    - Games grandes (God of War, Zelda, GTA): 10,0 avg
    - Anime mainstream: bom quando é One Piece, JJK, Demon Slayer
    - Anime niche: baixíssimo engajamento
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
            "Você é o CMO do @morsadigital — canal de cultura pop/nerd para audiência brasileira de 27k seguidores.\n\n"
            "DADOS REAIS DE PERFORMANCE (análise de 200 posts, jun/2026):\n"
            "🥇 DC (Batman, Superman, Flash): 144 avg likes — PRIORIDADE MÁXIMA\n"
            "🥇 Marvel/Avengers/Spider-Man: 46 avg likes — PRIORIDADE MÁXIMA\n"
            "🥈 Filmes/animações muito aguardados (Pixar, Disney, blockbusters): bom potencial\n"
            "🥈 Conteúdo que provoca DEBATE e OPINIÃO (versus, rankings, polêmicas): alto comentário\n"
            "🥉 Star Wars: 26 avg\n"
            "🥉 Séries com grande base BR (Stranger Things, The Boys): 19 avg\n"
            "⚠️ Games APENAS os maiores: God of War, Zelda, GTA, Elden Ring, Call of Duty, Final Fantasy\n"
            "⚠️ Anime APENAS mainstream: One Piece, Jujutsu Kaisen, Demon Slayer, Dragon Ball, Bleach\n"
            "❌ Games internacionais nichê (Thief, indie, jogos sem fandom BR): 3-4 likes — NUNCA\n"
            "❌ Tech/gadgets/IA: off-brand, engajamento zero — NUNCA\n"
            "❌ Anime desconhecido sem base no Brasil: NUNCA\n"
            "❌ Séries antigas sem hype atual (Stargate, Battlestar): NUNCA\n"
            "❌ Promoções, ofertas, produtos: JAMAIS\n\n"
            "CRITÉRIOS DE SELEÇÃO (em ordem de peso):\n"
            "1. É Marvel ou DC? → seleção quase automática\n"
            "2. Tem potencial de debate/opinião no fandom BR? (versus, polêmica, surpresa, revelação)\n"
            "3. A franquia tem base consolidada no Brasil (>500k fãs BR estimados)?\n"
            "4. É novidade real (trailer, confirmação, data, cancelamento) — não rumor vago?\n"
            "5. Variedade no conjunto (não 4 posts de games seguidos)\n\n"
            "Responda APENAS com os números separados por vírgula. Ex: 3,1,7,2",
            f"Estratégia do dia: {strategy}\n\nNotícias disponíveis:\n{titles}\n\n"
            f"Selecione os {count} melhores índices em ordem de prioridade (do mais ao menos impactante):",
            max_tokens=60,
        )
        indices = [int(x.strip()) - 1 for x in result.split(',') if x.strip().isdigit()]
        selected = [news_list[i] for i in indices if 0 <= i < len(news_list)]
        if selected:
            return selected[:count]
    except Exception as e:
        logger.warning(f"select_best_news Groq falhou ({e}) — usando ordem original")

    return news_list[:count]
