"""
Fila de Reels: o Mac abastece, o GitHub publica.

O YouTube bloqueia o IP do GitHub, então o download só funciona em casa. Para o
Mac não precisar estar ligado todo dia, ele baixa vários vídeos de uma vez
(`fill`), sobe para uma Release do GitHub e registra em data/reel_queue.json.
O CI publica um por dia a partir das 18h BRT (`publish`).

Fonte: SÓ uploads recentes dos canais oficiais abaixo (ID conferido à mão).
Legenda sempre nossa + crédito do canal.

Uso:  python src/reel_queue.py fill | publish | due | status
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("morsa.reel_queue")

BRT = timezone(timedelta(hours=-3))
ROOT = Path(__file__).parent.parent
QUEUE_PATH = ROOT / "data" / "reel_queue.json"
RELEASE_TAG = "reel-queue"
REPO = os.environ.get("GITHUB_REPOSITORY", "tuliogama/morsa-digital-autoposter")

REEL_SLOT_BRT = int(os.environ.get("REEL_SLOT_BRT", "18"))
QUEUE_TARGET = int(os.environ.get("REEL_QUEUE_TARGET", "7"))
MAX_PER_CHANNEL = 2          # variedade: no máximo 2 pendentes do mesmo canal
MAX_AGE_DAYS = 30            # vídeo mais velho que isso não é mais novidade
MIN_SECONDS, MAX_SECONDS = 20, 210
TRIM_SECONDS = 90            # Reels até 90s entram na recomendação

# Canais oficiais conferidos em 06/10/2026 (ID + inscritos + selo). Handles
# parecidos podem ser falsos: @dcbrasil tinha 3 inscritos. Só adicionar por ID.
OFFICIAL_CHANNELS = {
    "UCItRs-h8YU1wRRfP637614w": "Marvel Brasil",
    "UCEOVI4AmQE01FDKNFunkV2w": "Warner Bros. Pictures Brasil",
    "UCR7ZwQz60rW9dK59Dirdc8w": "HBO Max Brasil",
    "UCc1l5mTmAv2GC_PXrBpqyKQ": "Netflix Brasil",
    "UC9NXpIA01HVRhYgcEbs80Nw": "Sony Pictures Brasil",
    "UCApaSzvP6jM9rfs8UbcqD1g": "Disney+ Brasil",
    "UCuNjvqjTzw9LcD9PVpTVWRA": "Prime Video Brasil",
    "UCgqD3GdUEfupsdY1kmFLIrw": "Paramount Brasil",
    "UCVc-JLY3Db6-O48y7TS4N7Q": "Crunchyroll Brasil",
    "UC6i4mzH3OPrZV0p64zoz-Ww": "PlayStation Brasil",
    "UC6VcWc1rAoWdBCM0JxrRQ3A": "Rockstar Games",
}

_WANTED_RE = re.compile(r"trailer|teaser|clipe|cena|sneak peek|primeiro olhar|first look",
                        re.IGNORECASE)
_UNWANTED_RE = re.compile(r"#shorts|ao vivo|live|podcast|entrevista|bastidores|making of|"
                          r"react|libras|audiodescrição|legendado|\bleg\b|pré-venda|"
                          r"prévia|episódio|"  # promo de episódio vence em dias
                          r"avaliações da imprensa", re.IGNORECASE)
MIN_VIEWS_GENERIC = 100_000  # fora das franquias fortes, só entra o que já provou interesse
_STRONG_CATS = {"dc", "marvel", "starwars", "anime_big", "gta", "game_big"}


# ── Estado da fila ──────────────────────────────────────────────────────────

def load_queue() -> list[dict]:
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save_queue(queue: list[dict]):
    QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


def pending(queue: list[dict]) -> list[dict]:
    return [q for q in queue if not q.get("posted")]


# ── Mac: abastecer ──────────────────────────────────────────────────────────

def _channel_uploads(channel_id: str) -> list[dict]:
    """Uploads recentes pelo RSS público do canal (não depende de yt-dlp)."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        root = ET.fromstring(r.read())
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    out = []
    for e in root.findall("a:entry", ns):
        stats = e.find("m:group/m:community/m:statistics", ns)
        out.append({
            "video_id": e.findtext("yt:videoId", "", ns),
            "title": e.findtext("a:title", "", ns),
            "published": e.findtext("a:published", "", ns),
            "description": (e.findtext("m:group/m:description", "", ns) or "")[:700],
            "views": int(stats.get("views", 0)) if stats is not None else 0,
        })
    return out


def find_candidates(queue: list[dict]) -> list[dict]:
    from content_generator import _categorize, _CATEGORY_TIER
    known = {q["video_id"] for q in queue}
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    found, seen_titles = [], set()
    for channel_id, channel in OFFICIAL_CHANNELS.items():
        try:
            uploads = _channel_uploads(channel_id)
        except Exception as e:
            logger.warning(f"RSS de {channel} falhou: {e}")
            continue
        for v in uploads:
            if v["video_id"] in known or not _WANTED_RE.search(v["title"]) \
                    or _UNWANTED_RE.search(v["title"]):
                continue
            if datetime.fromisoformat(v["published"]) < cutoff:
                continue
            cat = _categorize({"title": f"{v['title']} {channel}"})
            if cat == "game_niche" or (cat not in _STRONG_CATS and v["views"] < MIN_VIEWS_GENERIC):
                continue
            key = re.sub(r"\W+", "", v["title"].lower().split("|")[0])
            if key in seen_titles:
                continue
            seen_titles.add(key)
            found.append({**v, "channel": channel, "channel_id": channel_id,
                          "category": cat, "tier": _CATEGORY_TIER.get(cat, 4)})
    # Público mais engajado primeiro; dentro do tier, o mais visto
    found.sort(key=lambda v: (v["tier"], -v["views"]))
    return found


def _duration(video_id: str) -> int:
    from reel_downloader import _ytdlp
    r = _ytdlp(f"https://www.youtube.com/watch?v={video_id}", "--skip-download",
               "--print", "%(duration)s")
    try:
        return int(float(r.stdout.strip().splitlines()[-1]))
    except (ValueError, IndexError):
        return 0


def _upload_asset(path: str) -> str:
    if subprocess.run(["gh", "release", "view", RELEASE_TAG, "--repo", REPO],
                      capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", RELEASE_TAG, "--repo", REPO,
                        "--title", "Fila de Reels", "--notes",
                        "Vídeos de canais oficiais aguardando publicação."],
                       capture_output=True, check=True)
    r = subprocess.run(["gh", "release", "upload", RELEASE_TAG, path, "--repo", REPO, "--clobber"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"upload falhou: {r.stderr[-200:]}")
    return f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{os.path.basename(path)}"


def _prepare_video(video_id: str, workdir: str) -> str:
    """Baixa e converte para 9:16 (fundo desfocado + logo), no máximo TRIM_SECONDS."""
    from reel_downloader import _download_video, _make_round_logo, _make_vertical_blur
    raw = os.path.join(workdir, f"raw_{video_id}.mp4")
    if not _download_video(video_id, raw):
        raise RuntimeError("download falhou")
    trimmed = os.path.join(workdir, f"trim_{video_id}.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", raw, "-t", str(TRIM_SECONDS), "-c", "copy", trimmed],
                   capture_output=True, check=True)
    out = os.path.join(workdir, f"{video_id}.mp4")
    _make_vertical_blur(trimmed, out, str(_make_round_logo()))
    return out


def fill() -> int:
    queue = load_queue()
    per_channel = {}
    for q in pending(queue):
        per_channel[q["channel_id"]] = per_channel.get(q["channel_id"], 0) + 1
    missing = QUEUE_TARGET - len(pending(queue))
    logger.info(f"Fila: {len(pending(queue))} pendentes, alvo {QUEUE_TARGET}")
    if missing <= 0:
        return 0

    added = 0
    for c in find_candidates(queue):
        if added >= missing:
            break
        if per_channel.get(c["channel_id"], 0) >= MAX_PER_CHANNEL:
            continue
        seconds = _duration(c["video_id"])
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            logger.info(f"Fora da duração ({seconds}s): {c['title'][:60]}")
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="morsa_queue_") as tmp:
                asset_url = _upload_asset(_prepare_video(c["video_id"], tmp))
        except Exception as e:
            logger.warning(f"Pulando {c['title'][:60]}: {e}")
            continue
        queue.append({
            "video_id": c["video_id"], "title": c["title"], "channel": c["channel"],
            "channel_id": c["channel_id"], "category": c["category"],
            "description": c["description"], "published": c["published"],
            "youtube_url": f"https://www.youtube.com/watch?v={c['video_id']}",
            "asset_url": asset_url, "added_at": datetime.now(BRT).isoformat(),
            "posted": False,
        })
        save_queue(queue)   # salva a cada item: queda no meio não perde o que subiu
        per_channel[c["channel_id"]] = per_channel.get(c["channel_id"], 0) + 1
        added += 1
        logger.info(f"+ [{c['category']}] {c['channel']}: {c['title'][:70]}")
    logger.info(f"Adicionados: {added} | pendentes agora: {len(pending(queue))}")
    return added


# ── CI: publicar ────────────────────────────────────────────────────────────

def _reel_posted_today() -> bool:
    token, ig = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{ig}/media"
           f"?fields=timestamp,media_type&limit=15&access_token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        media = json.loads(r.read()).get("data", [])
    today = datetime.now(BRT).date()
    return any(m.get("media_type") == "VIDEO" and
               datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(BRT).date() == today
               for m in media)


def is_due() -> tuple[bool, str]:
    now = datetime.now(BRT)
    n = len(pending(load_queue()))
    if n == 0:
        return False, "fila vazia (o Mac precisa abastecer)"
    if now.hour < REEL_SLOT_BRT:
        return False, f"{now:%H:%M} BRT, antes das {REEL_SLOT_BRT}h"
    try:
        if _reel_posted_today():
            return False, "já saiu reel hoje"
    except Exception as e:
        return False, f"falha ao consultar o Instagram ({e})"
    return True, f"reel devido ({n} na fila)"


def _pick_next(queue: list[dict]) -> dict:
    """Mais antigo da fila, evitando repetir a categoria do último publicado."""
    posted = sorted((q for q in queue if q.get("posted")), key=lambda q: q.get("posted_at", ""))
    last_cat = posted[-1]["category"] if posted else None
    todo = pending(queue)
    return next((q for q in todo if q["category"] != last_cat), todo[0])


def _caption(item: dict) -> str:
    from content_generator import REEL_TRAILER_SYSTEM, _call_groq, _strip_ai_tells, _cap_hashtags
    from editorial import _with_credit
    user_msg = (
        f"Escreva a legenda para o Reel: {item['title']}\n\n"
        f"FATOS VERIFICADOS (descrição oficial do canal {item['channel']}) — use APENAS estes, "
        f"nunca invente elenco, data ou enredo:\n{item['description']}\n\n"
        "Não copie frases da descrição oficial: escreva com a voz da Morsa.\n"
        "PROIBIDO afirmar qualquer coisa que não esteja nos fatos acima: data de estreia, "
        "elenco, enredo, se é final de série, se terá continuação, opinião sobre a obra "
        "completa (ninguém assistiu ainda). Na dúvida, fale do que o título promete e "
        "faça a pergunta ao fã. Termine com 5 a 6 hashtags específicas da franquia."
    )
    text = ""
    for _ in range(2):
        try:
            text = re.sub(r"\n[ \t]*\n+", "\n\n", _call_groq(REEL_TRAILER_SYSTEM, user_msg, 600)).strip()
            if len(text) >= 100:
                break
        except Exception as e:
            logger.warning(f"Groq falhou na legenda: {e}")
    if len(text) < 100:
        text = f"{item['title']}\n\nO que você achou?"
    return _with_credit(_cap_hashtags(_strip_ai_tells(text)), item["channel"])


def publish() -> int:
    due, reason = is_due()
    logger.info(reason)
    if not due:
        return 0
    from publishers.instagram import publish_reel_from_url
    from posts_log import record_post

    queue = load_queue()
    item = _pick_next(queue)
    caption = _caption(item)
    logger.info(f"Publicando [{item['category']}] {item['title']}\n{caption}")
    result = publish_reel_from_url(item["asset_url"], caption)

    item.update(posted=True, posted_at=datetime.now(BRT).isoformat(), media_id=result["id"])
    save_queue(queue)
    record_post(media_id=result["id"], platform="instagram_reel",
                news_item={"title": item["title"], "source": item["channel"],
                           "url": item["youtube_url"]}, caption=caption)
    # O Instagram já copiou o vídeo; o arquivo na Release não é mais necessário
    subprocess.run(["gh", "release", "delete-asset", RELEASE_TAG, f"{item['video_id']}.mp4",
                    "--repo", REPO, "--yes"], capture_output=True)
    logger.info(f"Reel publicado: {result['id']} | restam {len(pending(queue))} na fila")
    return 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "fill":
        fill()
    elif cmd == "publish":
        return publish()
    elif cmd == "due":
        due, reason = is_due()
        print(reason)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"reel_due={'true' if due else 'false'}\n")
    else:
        for q in pending(load_queue()):
            print(f"[{q['category']}] {q['channel']}: {q['title']}")
        print(f"{len(pending(load_queue()))} pendentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
