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

CURADORIA — A LEGENDA PRECISA SE SUSTENTAR SOZINHA (regras absolutas):
- A Morsa só NOTICIA cultura pop. NUNCA vende, oferece ou anuncia serviço/produto/curso/assinatura próprio. Proibido "nosso serviço", "assine", "contrate", "chama no direct", "link na bio para comprar". Você é jornalista de fã, não vendedor.
- Se o título é uma LISTA numerada ("7 heróis que...", "5 animes que estreiam..."), o corpo OBRIGATORIAMENTE nomeia os itens, um a um (pode numerar 1, 2, 3...). Se a notícia fornecida não traz os nomes reais, NÃO escreva o post — responda apenas a palavra PULAR.
- Se o título promete ESTREIA/DATA ("ganha data", "estreia em", "quando chega"), o corpo OBRIGATORIAMENTE traz a data concreta (dia/mês ou mês/ano). Sem a data nos dados fornecidos, responda apenas PULAR.
- Toda informação que o título promete (nome do anime, qual regra mudou, quais modelos) tem que aparecer no corpo. O leitor não pode terminar a legenda com a mesma dúvida com que começou.
- Proibido encher lista com "vários", "alguns", "diversos", "entre outros", "e muito mais". Ou nomeia, ou não publica.

REGRAS DE ESPECIFICIDADE (falhas reais que já aconteceram — não repita):
- Se o título menciona "heróis que vencem X" → o corpo OBRIGATORIAMENTE cita os heróis pelo nome. Nunca "vários heróis de outras editoras" sem nomear nenhum. Se a notícia não tem os nomes, muda o título.
- Se o título diz "quebra uma regra" → o corpo OBRIGATORIAMENTE diz qual regra foi quebrada. Nunca deixar o leitor sem saber o que mudou.
- Se o título menciona um produto físico (Hot Wheels, LEGO, etc.) → o corpo descreve o produto especificamente. Sem imagem, o texto é tudo — "carrinhos inspirados em filmes" sem dizer quais modelos/personagens é inútil.
- NUNCA use o CTA para perguntar algo que o próprio post não respondeu. Se o post não disse quem vence, não pergunte "quem você acha que vence?" — a galera vai responder "fala logo!". Responda primeiro, pergunte depois.
- NUNCA termine um argumento com "poderia até derrota-lo" e em seguida pergunte "você acha que pode derrotar?". É contraditório e parece insegurança. Tome posição.

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


import re as _re

# Os TÍTULOS chegam em inglês OU português → detecção bilíngue.
# (Os checks do CORPO ficam em PT porque a legenda gerada é sempre PT.)

# Substantivos de lista: "7 HERÓIS QUE...", "5 ANIMES...", "7 Heroes Who..."
_LIST_NOUNS = (
    r"her[óo]is|heroes|vil[õo]es|villains|animes?|mang[áa]s|mangas?|filmes|movies|"
    r"jogos|games|s[ée]ries|series|shows|doramas|personagens|characters|"
    r"momentos|moments|cenas|scenes|teorias|theories|curiosidades|motivos|reasons|"
    r"raz[õo]es|vers[õo]es|versions|easter eggs|refer[êe]ncias|references|"
    r"atores|actors|diretores|directors|trailers|f[ai]ses|temporadas|seasons|"
    r"epis[óo]dios|episodes|reviravoltas|twists|mortes|deaths|things|ways"
)
# Permite até 3 palavras entre o número e o substantivo: "7 Comic Book Heroes", "5 Best Anime"
_LIST_RE = _re.compile(rf"\b(\d{{1,2}})\s+(?:[\w'&-]+\s+){{0,3}}({_LIST_NOUNS})\b", _re.IGNORECASE)

# Promessa de estreia/data/lançamento no título (EN+PT)
_DATE_PROMISE_RE = _re.compile(
    r"\b(estreia|estr[ée]ia|data de|chega em|lan[çc]a(?:mento)?|anuncia|"
    r"ganha data|j[áa] tem data|quando estreia|"
    r"release date|premiere|premieres|debuts?|launches|gets? (?:a )?release|"
    r"arrives|announces? (?:a )?date|comes out|out date|sets? (?:a )?date)\b",
    _re.IGNORECASE)

# Promessa de "a coisa específica" (singular): "o arco mais subestimado",
# "a cena que mudou tudo", "quebra uma regra", "mata um personagem".
# O título aponta para UMA coisa concreta sem nomeá-la — o corpo TEM que nomear.
# Substantivo de assunto único (EN+PT) — usado só para detectar a promessa no título
_SUBJECT_NOUNS = (
    r"arco|arc|cena|scene|epis[óo]dio|episode|reviravolta|twist|regra|rule|"
    r"personagem|character|morte|death|vil[ãa]o|villain|her[óo]i|hero|"
    r"momento|moment|easter egg|refer[êe]ncia|reference|teoria|theory|"
    r"detalhe|detail|segredo|secret|final|ending|revela[çc][ãa]o|reveal|"
    r"conex[ãa]o|connection|line|quote"
)
_SUBJECT_PROMISE_RE = _re.compile(
    rf"\b(?:o|a|os|as|um|uma|seu|sua|mais|melhor|pior|maior|"
    rf"the|a|an|its|most|best|worst|biggest|one)\s+(?:[\w'-]+\s+){{0,2}}"
    rf"(?:{_SUBJECT_NOUNS})\b|"
    rf"\b(?:quebra|muda|mata|revela|esconde|conecta|"
    rf"breaks?|changes?|kills?|reveals?|hides?|connects?)\b",
    _re.IGNORECASE)

# Tokens que comprovam uma data concreta no corpo
_MESES = ("janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|"
          "outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez")
_CONCRETE_DATE_RE = _re.compile(
    rf"\b(\d{{1,2}}\s+de\s+(?:{_MESES})|(?:{_MESES})\s+de\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}|"
    rf"\b20\d{{2}}\b|primeiro semestre|segundo semestre)\b", _re.IGNORECASE)

# Enchimento genérico que denuncia falta de especificidade
_FILLER_RE = _re.compile(
    r"\b(v[áa]rios|alguns|diversos|entre outros|e muito mais|uma s[ée]rie de|"
    r"v[áa]rias|in[úu]meros|muitos outros|outros tantos|e mais)\b", _re.IGNORECASE)

# Frase evasiva: o texto se refere ao assunto sem nomeá-lo (sinal de não-entrega).
# "o arco em questão", "esse personagem", "a cena que mudou", "tal reviravolta".
_EVASION_RE = _re.compile(
    rf"\b(?:em quest[ãa]o|em destaque)\b|"
    rf"\b(?:esse|este|essa|esta|aquele|aquela|tal|determinad[oa]|cert[oa]|um certo)\s+"
    rf"(?:{_SUBJECT_NOUNS})\b|"
    rf"\b(?:o|a)\s+(?:{_SUBJECT_NOUNS})\s+que\b",
    _re.IGNORECASE)

# Linguagem de venda/serviço em 1ª pessoa — Morsa só noticia
_SELLING_RE = _re.compile(
    r"\b(nosso(?:s)? (?:servi[çc]o|plano|produto|curso|pacote)|"
    r"assine|contrate|garanta o seu|fale com a gente|chama no direct|"
    r"link na bio para comprar|adquira (?:j[áa]|o seu)|compre agora)\b", _re.IGNORECASE)


def _count_named_items(body: str) -> int:
    """Conta itens nomeados: marcadores de lista OU nomes próprios distintos."""
    # Marcadores numerados/bullets em linhas separadas
    markers = _re.findall(r"(?m)^\s*(?:\d{1,2}[\.\)\-—:]|[-•★▪])\s+\S", body)
    if markers:
        return len(markers)
    # Nomes próprios (sequências capitalizadas), ignorando início de frase
    proper = _re.findall(r"(?<![\.\n]\s)\b[A-ZÀ-Ý][\wÀ-ÿ'-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'-]+)*", body)
    return len({p.strip() for p in proper if len(p) > 2})


def _cap_hashtags(content: str, max_tags: int = 8) -> str:
    """
    Mantém no máximo `max_tags` hashtags (as primeiras, mais específicas),
    removendo o excesso. O modelo às vezes despeja 15-20 — parece bot e
    prejudica alcance. As hashtags ficam no fim; reescreve só esse bloco.
    """
    tags = _re.findall(r"#\w+", content)
    if len(tags) <= max_tags:
        return content
    # Remove todas as hashtags do texto e recoloca só as primeiras no fim
    kept = tags[:max_tags]
    body = _re.sub(r"#\w+", "", content)
    body = _re.sub(r"[ \t]+\n", "\n", body)          # limpa espaços antes de quebra
    body = _re.sub(r"\n{3,}", "\n\n", body).rstrip()
    return f"{body}\n\n{' '.join(kept)}"


def _verify_specificity(caption: str, title: str) -> tuple[bool, str]:
    """
    Garante que a legenda ENTREGA o que o título promete.
    Retorna (ok, motivo). Se ok=False, o post deve ser pulado.
    """
    # Corpo = legenda sem as hashtags finais
    body = _re.sub(r"(?m)^\s*#.*$", "", caption).strip()

    # 1) Nunca vender serviço/produto da Morsa
    if _SELLING_RE.search(caption):
        return False, "linguagem de venda/serviço (Morsa só noticia, não vende)"

    # 2) Título é lista numerada → corpo precisa nomear os itens
    m = _LIST_RE.search(title)
    if m:
        n = int(m.group(1))
        required = min(n, 3)
        named = _count_named_items(body)
        if named < required:
            return False, f"título promete {n} {m.group(2)} mas o corpo nomeia só {named}"
        if _FILLER_RE.search(body):
            return False, "lista preenchida com termos genéricos ('vários', 'entre outros')"

    # 3) Título promete data/estreia → corpo precisa de data concreta OU nome específico
    if _DATE_PROMISE_RE.search(title):
        if not _CONCRETE_DATE_RE.search(body):
            return False, "título promete estreia/data mas o corpo não traz data concreta"

    # 4) Título aponta para UMA coisa específica (o arco, a cena, qual regra) →
    #    o corpo não pode escapar com frase evasiva sem nomear a coisa
    if _SUBJECT_PROMISE_RE.search(title):
        if _EVASION_RE.search(body):
            return False, "título promete algo específico mas o corpo escapa sem nomear ('em questão', 'esse arco', etc.)"

    return True, ""


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

    description = news_item.get("description", "").strip()

    # ENRIQUECIMENTO: se a descrição é fina OU o título promete especificidade
    # (lista numerada, estreia/data), busca o corpo do artigo para dar dados reais
    # ao modelo. Sem isso o modelo preenche com genérico.
    promises_specificity = bool(
        _LIST_RE.search(title)
        or _DATE_PROMISE_RE.search(title)
        or _SUBJECT_PROMISE_RE.search(title)
    )
    if url and (len(description) < 400 or promises_specificity):
        try:
            from news_fetcher import fetch_article_text
            article = fetch_article_text(url)
            if article and len(article) > len(description):
                description = article
                logger.info(f"Notícia enriquecida com corpo do artigo ({len(article)} chars)")
        except Exception as e:
            logger.warning(f"Falha ao enriquecer notícia: {e}")

    user_msg = (
        f"Escreva a legenda completa para o {platform.capitalize()} sobre esta notícia.\n\n"
        f"Título: {title}\n"
        + (f"Resumo/descrição: {description}\n" if description else "")
        + f"\nIMPORTANTE:\n"
        f"- Escreva como se a Morsa Digital estivesse reportando a notícia — NUNCA mencione o nome da fonte no texto\n"
        f"- Siga o formato com linha em branco entre cada bloco\n"
        f"- Não truncar — termine todas as frases\n"
        f"- Hashtags só relacionadas a esta notícia específica, nada genérico\n"
        f"- Se o título promete especificidade (nomes, qual regra, quais modelos), o corpo DEVE entregar essa especificidade. Se a descrição não tiver os dados, adapte o título para não prometer o que não pode cumprir."
    )

    content = None
    last_error = None

    # Tentar até 2 vezes antes de desistir
    for attempt in range(2):
        try:
            raw = _call_groq(cfg["system"], user_msg, max_tokens=700)
            raw = re.sub(r'\n[ \t]*\n+', '\n\n', raw).strip()

            # Modelo sinalizou que a notícia não tem dados para um post de qualidade
            if raw.strip().upper().rstrip(".!") == "PULAR" or len(raw) < 60:
                logger.info(f"Modelo pediu PULAR para '{title[:50]}' — notícia sem dados suficientes")
                raise CaptionGenerationError(f"Notícia sem dados para post de qualidade: {title[:60]}")

            if not _validate_caption(raw, source):
                logger.warning(f"Legenda rejeitada na validação (tentativa {attempt+1})")
                continue

            ok, motivo = _verify_specificity(raw, title)
            if not ok:
                logger.warning(f"Legenda sem especificidade (tentativa {attempt+1}): {motivo}")
                continue

            content = raw
            logger.info(f"Legenda gerada via Groq ({len(content)} chars)")
            break
        except CaptionGenerationError:
            raise  # notícia sem dados — pular já, não adianta tentar de novo
        except Exception as e:
            last_error = e
            logger.warning(f"Groq falhou tentativa {attempt+1}: {e}")

    if not content:
        # Sem legenda válida → sinaliza para pular o post
        raise CaptionGenerationError(
            f"Não foi possível gerar legenda de qualidade para: {title[:60]}"
        )

    # Corta excesso de hashtags — regra é 6-8, o modelo às vezes despeja 20
    content = _cap_hashtags(content, max_tags=8)

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


# Franquias de games com fandom BR consolidado — o resto é nichê (3-4 likes, evitar)
_BIG_GAME_FRANCHISES = (
    "gta", "grand theft auto", "god of war", "zelda", "elden ring", "dark souls",
    "call of duty", "final fantasy", "resident evil", "the last of us", "spider-man",
    "valorant", "league of legends", "counter-strike", "cs2", "fortnite", "minecraft",
    "pokemon", "pokémon", "mario", "sonic", "hollow knight", "silksong", "witcher",
    "cyberpunk", "diablo", "overwatch", "ea fc", "ea sports fc", "fifa", "death stranding",
    "metroid", "metal gear", "kingdom hearts", "tekken", "mortal kombat", "street fighter",
)
_GAME_SIGNALS = ("game", "jogo", "gameplay", "dlc", "rpg", "mmorpg", "fps", "console",
                 "playstation", "xbox", "nintendo", "steam", "ps5", "esport", "patch",
                 "update", "atualiza", "expansão", "expansion")


def _categorize(news_item: dict) -> str:
    """Classifica a notícia para garantir variedade e rebaixar games nichê."""
    t = f"{news_item.get('title','')} {news_item.get('description','')}".lower()
    if any(k in t for k in ("batman", "superman", "flash", "aquaman", "wonder woman",
                            "james gunn", " dcu", "the batman", "lanterna verde")):
        return "dc"
    if any(k in t for k in ("marvel", "avengers", "vingadores", "spider-man", "homem-aranha",
                            "x-men", "deadpool", "thor", "loki", "mcu", "wandavision")):
        return "marvel"
    if "star wars" in t or "mandalorian" in t or "jedi" in t or "skywalker" in t:
        return "starwars"
    if any(k in t for k in ("anime", "mangá", "manga", "one piece", "jujutsu", "demon slayer",
                            "dragon ball", "naruto", "bleach", "chainsaw")):
        return "anime"
    # Nome de franquia grande já basta (ex.: "GTA VI ganha data" não tem palavra "game")
    if any(f in t for f in _BIG_GAME_FRANCHISES):
        return "game_big"
    if any(k in t for k in _GAME_SIGNALS):
        return "game_niche"
    if any(k in t for k in ("filme", "movie", "trailer", "cinema", "pixar", "disney")):
        return "movie"
    if any(k in t for k in ("série", "series", "temporada", "season", "netflix", "hbo")):
        return "series"
    return "other"


def _rerank_for_diversity(selected: list) -> list:
    """
    Reordena para: (1) empurrar games nichê para o fim (baixo engajamento) e
    (2) nunca deixar 3 posts da mesma categoria em sequência.
    """
    if len(selected) <= 2:
        return selected
    tagged = [(_categorize(n), n) for n in selected]
    # Games nichê vão para o fim, preservando a ordem relativa do resto
    non_niche = [x for x in tagged if x[0] != "game_niche"]
    niche     = [x for x in tagged if x[0] == "game_niche"]
    ordered = non_niche + niche

    # Espalha categorias: evita 3 iguais seguidas
    result, pending = [], list(ordered)
    while pending:
        idx = 0
        if len(result) >= 2 and result[-1][0] == result[-2][0]:
            # últimas duas são da mesma categoria → busca a próxima diferente
            for j, (cat, _) in enumerate(pending):
                if cat != result[-1][0]:
                    idx = j
                    break
        result.append(pending.pop(idx))
    return [n for _, n in result]


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
            "5. Variedade no conjunto — NUNCA 2+ games seguidos, alterne categorias\n"
            "6. Game nichê (MMORPG indie, sim de fábrica, jogo sem fandom BR massivo) → NÃO selecione, mesmo que seja novidade\n"
            "7. NUNCA selecione a MESMA notícia/evento de duas fontes diferentes — escolha só uma\n\n"
            "Responda APENAS com os números separados por vírgula. Ex: 3,1,7,2",
            f"Estratégia do dia: {strategy}\n\nNotícias disponíveis:\n{titles}\n\n"
            f"Selecione os {count} melhores índices em ordem de prioridade (do mais ao menos impactante):",
            max_tokens=60,
        )
        indices = [int(x.strip()) - 1 for x in result.split(',') if x.strip().isdigit()]
        selected = [news_list[i] for i in indices if 0 <= i < len(news_list)]
        if selected:
            return _rerank_for_diversity(selected[:count])
    except Exception as e:
        logger.warning(f"select_best_news Groq falhou ({e}) — usando ordem original")

    return _rerank_for_diversity(news_list[:count])
