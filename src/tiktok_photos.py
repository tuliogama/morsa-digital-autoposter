"""
Acervo do feed no TikTok: as notícias estáticas que o Morsa publicou no Instagram
desde que a automação foi ligada (29/05/2026) entram no TikTok como post de FOTO,
3 por dia, das que mais engajaram no Instagram para as que menos (desde 22/10/2026;
antes eram 10 por dia em ordem cronológica).

Pedido do Tulio em 14/10/2026: os vídeos repostados caíram em "conteúdo não
original" e o TikTok passou a recomendar foto para a conta; a meta é chegar aos
1.000 seguidores do nicho (porta do Marketplace) e depois às 100 mil views.

  build     monta data/tiktok_photo_backlog.json a partir do Instagram (uma vez;
            rodar de novo só acrescenta o que faltar)
  schedule  agenda na Zernio os próximos 2 dias de slots (roda toda noite)
  status    mostra quanto falta

As imagens do Instagram vêm de URL que expira, então cada uma é baixada e sobe na
Release `tiktok-fotos` (repositório público, URL estável) só na hora de agendar.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("tiktok_photos")

BRT = timezone(timedelta(hours=-3))
ROOT = Path(__file__).parent.parent
BACKLOG_PATH = ROOT / "data" / "tiktok_photo_backlog.json"
START = "2026-05-29"
REPO = os.environ.get("GITHUB_REPOSITORY", "tuliogama/morsa-digital-autoposter")
RELEASE_TAG = "tiktok-fotos"
# 10 por dia, fora dos minutos dos vídeos (11h, 13h, 13h30, 15h, 16h30, 17h15, 18h,
# 19h30, 21h, 22h30) e longe das notícias do dia (9h, 16h, 21h)
PHOTO_SLOTS_BRT = ["12:00", "14:00", "18:30"]
# 22/10/2026: de 10 para 3 por dia (com as 3 notícias do dia, 6 fotos). Com 23 posts por
# dia a conta não ganhou seguidor (105 → 106 em 8 dias) e a mediana por foto caiu de 64
# para 18; foto a 30-60 min do post anterior rendeu 58, a menos de 30 min, 35. Os
# horários ficam a mais de 1h das notícias (9h, 16h, 21h).

# Notícia velha que fala em "hoje", "amanhã", "esta semana" vira informação errada
_STALE_RE = re.compile(r"\b(hoje|amanh[aã]|ontem|esta semana|nesta semana|neste fim de semana|"
                       r"agora mesmo|daqui a pouco|em instantes|ao vivo)\b", re.IGNORECASE)


# Acervo de junho/2026 tem post da fase ruim: promoção, preço, tecnologia, empresa.
_WEAK_RE = re.compile(r"R\$|promo[cç]|desconto|oferta|cupom|black friday|pre[cç]o|por menos de|"
                      r"de gra[cç]a|gr[aá]tis|amazon|mercado livre|loja|compre|\bceo\b|a[cç][oõ]es|"
                      r"investidor|democratizar|rob[oô]s?\b|intelig[eê]ncia artificial|\bia\b|"
                      r"celular|smartphone|notebook|gadget", re.IGNORECASE)
_WEAK_CATS = {"game_niche"}


def _weak(caption: str) -> str | None:
    """Motivo para deixar fora do TikTok, ou None."""
    from news_fetcher import _is_blocked
    from content_generator import _categorize
    first = caption.split("\n")[0]
    if first.lstrip().startswith("#"):
        return "molde antigo"
    if _is_blocked(first) or _WEAK_RE.search(first):
        return "fraco"
    if _categorize({"title": first}) in _WEAK_CATS:
        return "fraco"
    return None


def clean_caption(caption: str) -> str:
    """Legenda antiga no padrão de hoje: sem travessão, sem markdown, sem emoji abrindo."""
    text = re.sub(r"\s*[—–]\s*", ", ", caption or "")
    text = re.sub(r"(?m)^#+\s+(?=\w)", "", text)                 # "# Título" de markdown
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^[^\w\"'(]+", "", text.strip())             # emoji ou símbolo no começo
    return text


_DATED_RE = re.compile(r"vem a[ií]|est[aá] vindo|vai chegar|chega (em|dia|no|na|ao)|estreia|estreou|"
                       r"lan[cç]a(mento|do|r)?\b|anunci|confirm|data de|revelad|primeiro trailer|"
                       r"\bem breve\b|nesta (sexta|semana)|\b20[0-9]{2}\b", re.IGNORECASE)


def rank() -> int:
    """Guarda em cada item o engajamento que o post teve no Instagram (curtidas + 3x comentários)."""
    token, user = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{user}/media?fields=id,like_count,comments_count,timestamp"
           f"&limit=100&access_token={token}")
    score = {}
    while url:
        data = _graph(url)
        for p in data.get("data", []):
            score[p["id"]] = p.get("like_count", 0) + 3 * p.get("comments_count", 0)
        if data.get("data") and data["data"][-1]["timestamp"][:10] < START:
            break
        url = data.get("paging", {}).get("next")
    backlog = _load()
    for b in backlog:
        b["ig_score"] = score.get(b["media_id"], 0)
    _save(backlog)
    return len(score)


def _graph(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _load() -> list[dict]:
    try:
        return json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]):
    BACKLOG_PATH.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def build() -> int:
    """Lê o feed do Instagram desde START e guarda a fila em ordem cronológica."""
    from editorial_guard import hard_block
    from posts_log import _key_words
    token, user = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{user}/media?fields=id,timestamp,media_type,caption"
           f"&limit=100&access_token={token}")
    posts = []
    while url:
        data = _graph(url)
        batch = data.get("data", [])
        posts += batch
        if batch and batch[-1]["timestamp"][:10] < START:
            break
        url = data.get("paging", {}).get("next")
    backlog = _load()
    known = {b["media_id"] for b in backlog}
    seen_words = [set(b["words"]) for b in backlog]
    skipped = {"apagado do registro": 0, "linha editorial": 0, "data relativa": 0, "repetido": 0}
    added = 0
    for p in sorted(posts, key=lambda p: p["timestamp"]):
        if p["timestamp"][:10] < START or p["media_type"] not in ("CAROUSEL_ALBUM", "IMAGE"):
            continue
        if p["id"] in known:
            continue
        caption = p.get("caption") or ""
        first = caption.split("\n")[0]
        if hard_block(caption):
            skipped["linha editorial"] += 1
            continue
        if _weak(caption):
            skipped["fraco"] = skipped.get("fraco", 0) + 1
            continue
        if _STALE_RE.search(first):
            skipped["data relativa"] += 1
            continue
        words = _key_words(first)
        if any(len(words & w) >= 3 for w in seen_words):
            skipped["repetido"] += 1
            continue
        seen_words.append(words)
        backlog.append({"media_id": p["id"], "posted_ig": p["timestamp"], "title": first[:120],
                        "words": sorted(words), "tiktok_id": None, "scheduled_for": None})
        added += 1
    _save(backlog)
    logger.info(f"Acervo: +{added} (total {len(backlog)}) | fora: {skipped}")
    return added


def _images(media_id: str) -> list[str]:
    """URLs atuais das imagens do post (expiram em poucos dias)."""
    token = os.environ["FB_ACCESS_TOKEN"]
    d = _graph(f"https://graph.facebook.com/v19.0/{media_id}?fields=media_type,media_url,caption,"
               f"children{{media_url,media_type}}&access_token={token}")
    if d.get("media_type") == "CAROUSEL_ALBUM":
        return [c["media_url"] for c in d.get("children", {}).get("data", [])
                if c.get("media_type") == "IMAGE"][:35], d.get("caption", "")
    return [d["media_url"]], d.get("caption", "")


def _host(urls: list[str], media_id: str) -> list[str]:
    """Baixa e sobe na Release pública: a Zernio só busca a imagem na hora de publicar."""
    if subprocess.run(["gh", "release", "view", RELEASE_TAG, "--repo", REPO],
                      capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", RELEASE_TAG, "--repo", REPO, "--title",
                        "Fotos do TikTok", "--notes", "Artes do feed aguardando o TikTok."],
                       capture_output=True, check=True)
    out = []
    with tempfile.TemporaryDirectory(prefix="tk_foto_") as tmp:
        for i, u in enumerate(urls):
            path = os.path.join(tmp, f"{media_id}_{i}.jpg")
            urllib.request.urlretrieve(u, path)
            r = subprocess.run(["gh", "release", "upload", RELEASE_TAG, path, "--repo", REPO,
                                "--clobber"], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"upload falhou: {r.stderr[-200:]}")
            out.append(f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{os.path.basename(path)}")
    return out


def schedule(days_ahead: int = 2, max_new: int = 25) -> int:
    from publishers import tiktok
    if not tiktok.enabled():
        logger.info("sem ZERNIO_API_KEY — nada a agendar")
        return 0
    backlog = _load()
    taken = {b["scheduled_for"] for b in backlog if b.get("scheduled_for")}
    # Melhores primeiro (engajamento do post no Instagram), e notícia com cara de
    # novidade datada ("vem aí", "estreia", "anuncia") vai para o fim: envelhece mal.
    todo = sorted((b for b in backlog if not b.get("tiktok_id")),
                  key=lambda b: (bool(_DATED_RE.search(b["title"])), -b.get("ig_score", 0)))
    now = datetime.now(BRT)
    created = 0
    for offset in range(days_ahead + 1):
        day = (now + timedelta(days=offset)).date()
        for hhmm in PHOTO_SLOTS_BRT:
            when = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
            stamp = when.strftime("%Y-%m-%dT%H:%M:00")
            if stamp in taken or when < now + timedelta(minutes=20) or created >= max_new or not todo:
                continue
            item = todo.pop(0)
            try:
                urls, caption = _images(item["media_id"])
                tk = tiktok.post_photos(_host(urls, item["media_id"]), clean_caption(caption),
                                        scheduled_for=stamp)
            except Exception as e:
                logger.warning(f"{item['media_id']} falhou: {str(e)[:160]}")
                item["tiktok_id"] = f"erro: {str(e)[:120]}"     # não trava a fila; fica anotado
                _save(backlog)
                continue
            item.update(tiktok_id=tk["id"], scheduled_for=stamp)
            taken.add(stamp)
            created += 1
            _save(backlog)
            logger.info(f"{stamp[5:16]} | {item['posted_ig'][:10]} | {item['title'][:70]}")
    return created


def status() -> str:
    backlog = _load()
    done = [b for b in backlog if b.get("tiktok_id") and not str(b["tiktok_id"]).startswith("erro")]
    left = len(backlog) - len(done)
    end = (datetime.now(BRT) + timedelta(days=left / len(PHOTO_SLOTS_BRT))).strftime("%d/%m/%Y")
    return (f"acervo: {len(backlog)} | agendados ou publicados: {len(done)} | faltam {left} "
            f"(a {len(PHOTO_SLOTS_BRT)} por dia, termina por volta de {end})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "build":
        build()
    elif cmd == "refilter":
        # passa o filtro de qualidade no que já está na fila (e cancela agendado que caiu)
        from publishers import tiktok
        keep, out = [], 0
        for b in _load():
            try:
                _, cap = _images(b["media_id"])
            except Exception:
                cap = b["title"]
            if _weak(cap) and not (b.get("tiktok_id") or "").startswith("erro"):
                if b.get("tiktok_id"):
                    try:
                        tiktok._api("DELETE", f"/posts/{b['tiktok_id']}")
                    except Exception as e:
                        logger.warning(f"não cancelou {b['tiktok_id']}: {e}")
                        keep.append(b); continue
                out += 1
                continue
            keep.append(b)
        _save(keep)
        logger.info(f"fora pelo filtro de qualidade: {out}")
    elif cmd == "reset":
        # cancela todos os agendados que ainda não saíram e devolve à fila
        from publishers import tiktok
        items = _load()
        for b in items:
            if b.get("tiktok_id") and not b["tiktok_id"].startswith("erro") and b.get("scheduled_for") \
                    and b["scheduled_for"] > datetime.now(BRT).strftime("%Y-%m-%dT%H:%M:00"):
                tiktok._api("DELETE", f"/posts/{b['tiktok_id']}")
                b.update(tiktok_id=None, scheduled_for=None)
        _save(items)
    elif cmd == "rank":
        logger.info(f"engajamento lido de {rank()} posts")
    elif cmd == "schedule":
        logger.info(f"novos agendamentos: {schedule()}")
    print(status())
