"""
Linha editorial: o que NUNCA sai nas páginas do Tulio (@morsadigital e
@ordemsithbrasil), mesmo sendo notícia de portal grande.

Pedido dele em 12/10/2026, depois de sair um post sobre vazamento de GTA 6 com
personagem nua: "precisamos de filtros anti disseminação de coisa idiota, crime
e coisas que deixem os incels da internet felizes. O Morsa não é isso, e nem o
Ordem."

Duas camadas:
  1. HARD_RE: termos que barram na hora, sem modelo (título, resumo e legenda).
  2. juiz: um modelo lê título e resumo e decide com a política abaixo. Pega o
     que lista de palavra não pega (isca de guerra cultural, fofoca de corpo,
     vazamento de material roubado).

Se o juiz estiver fora do ar, a pauta é RECUSADA: melhor perder um post do que
publicar o que não é a cara da página. O mesmo arquivo roda nos dois repositórios.
"""
import json
import logging
import os
import re
import urllib.request

logger = logging.getLogger("editorial_guard")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
JUDGE_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

_HARD = {
    "nudez ou sexo": (
        r"\bnuas?\b|\bnus?\b(?! metal)|\bpelad[oa]s?\b|nudez|\bnudes?\b|\bnudity\b|naked|topless|"
        r"sem roupa|semi-?nu|\bsexo\b|\bsex\b|sexual|sexy|er[oó]tic|porn|nsfw|onlyfans|hentai|"
        r"striptease|stripper|\b18\+"),
    "sexualização de corpo": (
        r"\bgostos[ao]s?\b|\bsensual\w*|\bdecote\b|\bbumbum\b|\bpeit[oõ]es\b|\bbunda\b|\bboobs?\b|"
        r"\bbutt\b|\bthirst trap|\bwaifu\b|fan ?service|\bcorpo perfeito"),
    "crime ou violência real": (
        r"estupr\w+|\brape[ds]?\b|pedofil\w+|pedophil\w+|ass[eé]dio|harass\w+|abuso (sexual|infantil)|"
        r"feminic[ií]dio|su[ií]c[ií]d\w+|suicid\w+|viol[eê]ncia dom[eé]stica|domestic violence|"
        r"\bgrooming\b|mass shooting"),
    "ódio ou isca de guerra cultural": (
        r"\bwoke\b|anti-?woke|lacra\w+|\bmimimi\b|feminazi|\bincel\w*|red ?pill|\bsjw\b|"
        r"go woke|agenda (woke|gay|lgbt)|ideologia de g[eê]nero|cancel culture|cultura do cancelamento|"
        r"review bomb\w*"),
}
HARD_RE = {name: re.compile(rx, re.IGNORECASE) for name, rx in _HARD.items()}

POLICY = """Você é o editor responsável de uma página brasileira de cultura pop para fãs (filmes, séries, games, quadrinhos, anime). A página é um lugar de fã para fã: informa, celebra e puxa conversa boa. Decida se a pauta abaixo pode virar post.

RECUSE (ok=false) se a pauta, no todo ou no gancho, for:
1. Nudez, sexo ou sexualização: personagem ou pessoa nua, cena de sexo, corpo de atriz ou ator, "ficou mais gostosa", mod adulto, conteúdo +18.
2. Crime ou tragédia real: acusação, prisão, processo criminal, agressão, assédio, morte violenta, suicídio, golpe. (Violência DENTRO da ficção é normal e pode: batalha, vilão, morte de personagem.)
3. Vazamento de material roubado ou pirata: vídeo, build ou roteiro vazado por hacker ou "leaker", conteúdo falso atribuído a vazamento. (Rumor de bastidor publicado por imprensa e anúncio oficial podem.)
4. Isca de raiva e guerra cultural: "woke", "lacração", ataque a elenco por gênero, raça ou orientação, polêmica fabricada, campanha de ódio, review bombing, fã "revoltado" com diversidade.
5. Fofoca e humilhação: vida íntima, namoro, peso, aparência, idade, briga pessoal de gente famosa; deboche de pessoa real.
6. Política partidária, religião, golpe financeiro, aposta, cripto.
7. Bobagem sem valor para o fã: meme de mau gosto, desafio perigoso, boato sem fonte, clickbait que não entrega.

ACEITE (ok=true) o que é o trabalho normal da página: trailer, estreia, elenco, bastidor de produção, entrevista sobre a obra, novidade de jogabilidade, data, crítica à obra, curiosidade, homenagem, rumor de produção.

Na dúvida, recuse. Responda SÓ com JSON: {"ok": true ou false, "motivo": "até 12 palavras"}"""


def hard_block(*texts: str) -> str | None:
    """Nome da regra violada, ou None. Sem modelo: serve para título, resumo e legenda."""
    blob = " \n ".join(t for t in texts if t)
    for name, rx in HARD_RE.items():
        m = rx.search(blob)
        if m:
            return f"{name} ({m.group(0).lower()})"
    return None


def _ask(model: str, system: str, user: str) -> dict:
    body = {
        "model": model, "temperature": 0, "max_tokens": 900, "reasoning_effort": "low",
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        GROQ_API_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                 "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(json.loads(r.read())["choices"][0]["message"]["content"])


def _judge(model: str, title: str, description: str) -> dict:
    return _ask(model, POLICY, f"Título: {title}\nResumo: {description[:1200]}")


def check(title: str, description: str = "") -> tuple[bool, str]:
    """(pode publicar?, motivo). Recusa quando o juiz não responde."""
    reason = hard_block(title, description)
    if reason:
        return False, reason
    error = None
    for model in JUDGE_MODELS:
        try:
            out = _judge(model, title, description)
            if isinstance(out.get("ok"), bool):
                return out["ok"], str(out.get("motivo", ""))[:120] or ("ok" if out["ok"] else "recusada pelo juiz")
        except Exception as e:
            error = e
            logger.warning(f"Juiz editorial ({model}) falhou: {str(e)[:120]}")
    return False, f"juiz editorial indisponível ({str(error)[:80]})"


# ── Repetição: a mesma história não sai duas vezes ───────────────────────────
# Em 11 e 12/10/2026 as duas páginas repetiram pauta (rádio a pé no GTA 6; HQs de
# Rogue One e Boba Fett): o registro local tinha sido zerado e o modelo menor, que
# fazia a comparação, deixou passar a mesma notícia vinda de outra fonte e idioma.
# Aqui a memória é o próprio Instagram, que não se perde, e quem compara é o juiz.

SAME_STORY = """Você evita post repetido numa página de cultura pop. Recebe uma PAUTA candidata e a lista do que a página JÁ PUBLICOU nos últimos dias.

Responda repetida=true se a pauta trata do MESMO fato, anúncio, declaração ou novidade de algum item da lista, mesmo com outro título, outro idioma, outra fonte ou outro ângulo. Exemplos de repetida: "GTA 6 radio stations revealed" contra "GTA 6 permite ouvir rádio a pé"; "Novas HQs de Rogue One e Boba Fett chegam" contra "Rogue One e Boba Fett chegam em outubro".

Responda repetida=false só se for um fato diferente, ainda que da mesma franquia ou personagem. Na dúvida, repetida=true.

Responda SÓ com JSON: {"repetida": true ou false, "igual_a": "trecho do item da lista, ou vazio"}"""


def recent_published(limit: int = 40) -> list[str]:
    """Começo da legenda dos últimos posts, lido do Instagram. [] se a consulta falhar."""
    token, user = os.environ.get("FB_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not user:
        return []
    url = (f"https://graph.facebook.com/v19.0/{user}/media"
           f"?fields=caption&limit={limit}&access_token={token}")
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read()).get("data", [])
    return [" ".join((p.get("caption") or "").split())[:240] for p in data if p.get("caption")]


def same_story(title: str, description: str = "", published: list[str] = None) -> tuple[bool, str]:
    """(é repetida?, com o quê). Sem resposta do juiz ou sem memória, barra."""
    try:
        memory = list(published or []) + recent_published()
    except Exception as e:
        return True, f"não consegui ler o que já saiu ({str(e)[:60]})"
    memory = list(dict.fromkeys(m for m in memory if m))[:70]
    if not memory:
        return False, ""
    listing = "\n".join(f"- {m[:240]}" for m in memory)
    error = None
    for model in JUDGE_MODELS:
        try:
            out = _ask(model, SAME_STORY, f"PAUTA: {title}\n{description[:400]}\n\nJÁ PUBLICADO:\n{listing}")
            if isinstance(out.get("repetida"), bool):
                return out["repetida"], str(out.get("igual_a", ""))[:100]
        except Exception as e:
            error = e
            logger.warning(f"Juiz de repetição ({model}) falhou: {str(e)[:120]}")
    return True, f"juiz de repetição indisponível ({str(error)[:60]})"
