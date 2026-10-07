"""
Fila de Reels: o Mac abastece, o GitHub publica.

O YouTube bloqueia o IP do GitHub, então o download só funciona em casa. Para o
Mac não precisar estar ligado todo dia, ele baixa vários vídeos de uma vez
(`fill`), sobe para uma Release do GitHub e registra em data/reel_queue.json.
O CI publica um por dia a partir das 11h BRT (`publish`).

Fonte: SÓ uploads recentes dos canais oficiais abaixo (ID conferido à mão).
Legenda sempre nossa + crédito do canal.

Três tipos de item na fila:
  - fixo   (`scheduled_for`): sai naquele dia (Halloween, Natal, lançamentos).
  - fresh  (`kind: fresh`): lançamento novo achado pelo `fill`; fura a fila do acervo.
  - acervo (`kind: acervo`): trailers e cenas clássicas pré-mapeados em
    data/reel_plan.json (`premap`), na ordem do plano, para os dias sem os outros.

Uso:  python src/reel_queue.py fill | premap | audit | publish | due | status
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("morsa.reel_queue")

BRT = timezone(timedelta(hours=-3))
ROOT = Path(__file__).parent.parent
RELEASE_TAG = "reel-queue"
REPO = os.environ.get("GITHUB_REPOSITORY", "tuliogama/morsa-digital-autoposter")

# Dois fluxos, um reel por dia de cada:
#   cenas — cenas, clipes e bastidores com legenda de pergunta ao fã. É o formato
#           dos maiores reels da conta (436 mil a 1,2 milhão de alcance em 2025).
#   main  — trailers: fixos por data, lançamentos e acervo.
# Horários: em 184 reels de nov/24 a out/25, os das 11h às 13h tiveram alcance
# 1,2x a mediana do mês (27 dos 35 acima de 10 mil); os das 17h às 19h, 0,6x.
STREAMS = {
    "cenas": {"queue": "reel_queue_cenas.json", "plan": "reel_plan_cenas.json", "slot": 11},
    "main":  {"queue": "reel_queue.json",       "plan": "reel_plan.json",       "slot": 13},
}
MIN_GAP_MIN = 90             # intervalo mínimo entre dois reels


def use_stream(name: str):
    """Aponta o módulo para a fila, o plano e o horário de um fluxo."""
    global STREAM, QUEUE_PATH, PLAN_PATH, REEL_SLOT_BRT
    cfg = STREAMS[name]
    STREAM = name
    QUEUE_PATH = ROOT / "data" / cfg["queue"]
    PLAN_PATH = ROOT / "data" / cfg["plan"]
    REEL_SLOT_BRT = cfg["slot"]


use_stream(os.environ.get("REEL_STREAM") or "main")

FRESH_TARGET = int(os.environ.get("REEL_FRESH_TARGET", "3"))   # lançamentos novos em espera
PIN_GRACE_DAYS = 2           # fixo que perdeu o dia ainda sai até 2 dias depois
MAX_PER_CHANNEL = 2          # variedade: no máximo 2 pendentes do mesmo canal
MAX_AGE_DAYS = 30            # vídeo mais velho que isso não é mais novidade
MIN_SECONDS, MAX_SECONDS = 20, 210
TRIM_SECONDS = 90            # Reels até 90s entram na recomendação
PREMAP_MAX_PER_RUN = int(os.environ.get("PREMAP_MAX_PER_RUN", "10"))   # por fluxo, por execução
PREMAP_PAUSE_SECONDS = int(os.environ.get("PREMAP_PAUSE_SECONDS", "70"))

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

# Canais oficiais usados só no fluxo de cenas (conferidos em 06/10/2026: selo de
# verificado e de 1,1 a 23,8 milhões de inscritos). Ficam fora do `fill` porque
# publicam trailers em inglês. Falsos descartados: @DisneyChannelBR (2,5 mil),
# @AdultSwimBrasil (5), @SonyPicturesAnimation (11).
SCENE_CHANNELS = {
    "UCvC4D8onUfXzvjTOM-dBfEA": "Marvel Entertainment",
    "UCZGYJFUizSax-yElQaFDp5Q": "Star Wars",
    "UC_IRYSp4auq7hKLvziWVH6w": "Pixar",
    "UCq7OHvWO6Z3u-LztFdrcU-g": "Illumination",
    "UCgKkNPU2Ib7_TcyAl8M2S-w": "Warner Bros. Entertainment",
    "UC9YHyj7QSkkSg2pjQ7M8Khg": "Paramount Movies",
    "UCz97F7dMxBNOfGYu3rx8aCw": "Sony Pictures Entertainment",
    "UC2-BeLxzUBSs0uSrmzWhJuQ": "20th Century Studios",
    "UCX2M7xn-jMmq4KfX25TCTCA": "HBO Brasil",
    "UCP6nJ-Elnfnpjv6HQRsv1Cw": "Walt Disney Studios BR",
    "UCAnCxJ1Weh2pUAKJW0bro0Q": "Paramount+ Brasil",
}
ALL_OFFICIAL = {**OFFICIAL_CHANNELS, **SCENE_CHANNELS}

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
            # games são a categoria de menor retorno da conta: só GTA entra como lançamento
            if cat in ("game_niche", "game_big") or (cat not in _STRONG_CATS and v["views"] < MIN_VIEWS_GENERIC):
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


def _is_br_channel(channel: str) -> bool:
    return "Brasil" in channel or channel.endswith(" BR")


def _download(video_id: str, out_path: str) -> bool:
    """Até 1080 de LARGURA: pega o vertical 1080x1920 inteiro e o horizontal em 1080x608."""
    from reel_downloader import _ytdlp
    for attempt in range(3):          # o YouTube devolve 403 esporádico; retomar resolve
        r = _ytdlp(f"https://www.youtube.com/watch?v={video_id}",
                   "-f", "bv*[ext=mp4][width<=1080]+ba[ext=m4a]/b[ext=mp4][width<=1080]/b",
                   "--merge-output-format", "mp4", "-o", out_path)
        if "not a bot" in r.stderr:
            raise YouTubeBlocked(r.stderr.strip()[-160:])
        if r.returncode == 0 and os.path.exists(out_path):
            return True
        time.sleep(10)
    return False


def _pt_subtitles(video_id: str, workdir: str) -> str | None:
    """Legenda OFICIAL em português (nunca a automática), em .srt."""
    from reel_downloader import _ytdlp
    _ytdlp(f"https://www.youtube.com/watch?v={video_id}", "--skip-download", "--write-subs",
           "--sub-langs", "pt-BR,pt", "--convert-subs", "srt",
           "-o", os.path.join(workdir, "sub.%(ext)s"))
    found = sorted(Path(workdir).glob("sub*.srt"))
    return str(found[0]) if found else None


def _render_cues(srt_path: str, workdir: str) -> list[tuple[str, float, float]]:
    """Desenha cada fala num PNG (o ffmpeg do Homebrew não tem filtro de legenda)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 46)

    def secs(t: str) -> float:
        h, m, rest = t.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest.replace(",", "."))

    cues = []
    for block in re.split(r"\n\s*\n", Path(srt_path).read_text(encoding="utf-8", errors="replace")):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        timing = next((l for l in lines if "-->" in l), None)
        if not timing:
            continue
        start, end = (secs(x.split()[0]) for x in timing.split("-->"))
        text = re.sub(r"<[^>]+>", "", " ".join(lines[lines.index(timing) + 1:])).strip()
        if not text or start >= TRIM_SECONDS:
            continue
        words, rows, row = text.split(), [], ""
        for w in words:                                  # quebra em linhas de até 940px
            if font.getlength(f"{row} {w}".strip()) > 940 and row:
                rows.append(row)
                row = w
            else:
                row = f"{row} {w}".strip()
        rows.append(row)
        img = Image.new("RGBA", (1080, 62 * len(rows) + 24), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for i, r in enumerate(rows):
            x = (1080 - font.getlength(r)) / 2
            draw.text((x, 10 + 62 * i), r, font=font, fill="white", stroke_width=4, stroke_fill="black")
        png = os.path.join(workdir, f"cue_{len(cues):03d}.png")
        img.save(png)
        cues.append((png, start, min(end, TRIM_SECONDS)))
    return cues


def _prepare_video(video_id: str, workdir: str, burn_subs: bool = False) -> tuple[str, str]:
    """
    Baixa e deixa em 1080x1920 com logo, no máximo TRIM_SECONDS.
    Vertical nativo (Shorts) fica em tela cheia; horizontal vai no meio com fundo
    desfocado. Devolve (arquivo, "vertical" | "horizontal").
    """
    from reel_downloader import _make_round_logo, LOGO_TOP
    raw = os.path.join(workdir, f"raw_{video_id}.mp4")
    if not _download(video_id, raw):
        raise RuntimeError("download falhou")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", raw], capture_output=True, text=True)
    width, height = (int(x) for x in probe.stdout.strip().split(",")[:2])
    vertical = height > width

    cues = []
    if burn_subs:
        srt = _pt_subtitles(video_id, workdir)
        if not srt:
            raise ValueError("legenda oficial em português não baixou")
        cues = _render_cues(srt, workdir)

    if vertical:
        graph = ("[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                 "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1[base];")
        cue_y = "H-h-520"            # acima da legenda e dos botões do Instagram
    else:
        graph = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                 "boxblur=40:6[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base];")
        cue_y = "1300"               # na faixa desfocada, logo abaixo do vídeo
    graph += f"[base][1:v]overlay=W-w-20:{LOGO_TOP}[v0]"
    inputs = ["-i", raw, "-i", str(_make_round_logo())]
    for i, (png, start, end) in enumerate(cues):
        inputs += ["-i", png]
        graph += (f";[v{i}][{i + 2}:v]overlay=0:{cue_y}:enable='between(t,{start:.2f},{end:.2f})'[v{i + 1}]")
    out = os.path.join(workdir, f"{video_id}.mp4")
    r = subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", graph,
                        "-map", f"[v{len(cues)}]", "-map", "0:a?", "-t", str(TRIM_SECONDS),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr[-300:]}")
    return out, "vertical" if vertical else "horizontal"


def _is_fresh(q: dict) -> bool:
    return q.get("kind", "fresh") == "fresh" and not q.get("scheduled_for")


def _add_item(queue: list[dict], video_id: str, meta: dict, **extra) -> dict:
    """Baixa, converte, sobe e registra um vídeo na fila (salva a cada item)."""
    # Português primeiro: canal brasileiro (dublado ou legendado na origem) ou
    # legenda oficial em PT queimada no vídeo. Sem nenhum dos dois, não entra.
    # Exceção: Rockstar, cujos trailers não têm versão em português.
    burn = False
    if not _is_br_channel(meta["channel"]):
        if meta.get("pt_subs"):
            burn = True
        elif meta["channel"] != "Rockstar Games":
            raise ValueError("sem versão em português (canal estrangeiro, sem legenda oficial PT)")
    with tempfile.TemporaryDirectory(prefix="morsa_queue_") as tmp:
        path, layout = _prepare_video(video_id, tmp, burn_subs=burn)
        asset_url = _upload_asset(path)
    extra.setdefault("layout", layout)
    extra.setdefault("lang", "pt" if _is_br_channel(meta["channel"]) else ("pt-legenda" if burn else "en"))
    item = {
        "video_id": video_id, "title": meta["title"], "channel": meta["channel"],
        "channel_id": meta["channel_id"], "category": meta["category"],
        "description": meta["description"], "published": meta["published"],
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
        "asset_url": asset_url, "added_at": datetime.now(BRT).isoformat(),
        "posted": False, **extra,
    }
    queue.append(item)
    save_queue(queue)
    return item


def fill() -> int:
    """Lançamentos novos dos canais oficiais (mantém FRESH_TARGET em espera)."""
    queue = load_queue()
    fresh = [q for q in pending(queue) if _is_fresh(q)]
    per_channel = {}
    for q in fresh:
        per_channel[q["channel_id"]] = per_channel.get(q["channel_id"], 0) + 1
    missing = FRESH_TARGET - len(fresh)
    logger.info(f"Fila: {len(pending(queue))} pendentes ({len(fresh)} lançamentos, alvo {FRESH_TARGET})")
    if missing <= 0:
        return 0

    added = 0
    for c in find_candidates(queue):
        if added >= missing:
            break
        if per_channel.get(c["channel_id"], 0) >= MAX_PER_CHANNEL:
            continue
        seconds = _duration(c["video_id"])
        if seconds == 0:
            logger.warning("Sem duração (YouTube pode ter bloqueado o IP) — parando o fill")
            break
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            logger.info(f"Fora da duração ({seconds}s): {c['title'][:60]}")
            continue
        try:
            _add_item(queue, c["video_id"], c, kind="fresh")
        except Exception as e:
            logger.warning(f"Pulando {c['title'][:60]}: {e}")
            continue
        per_channel[c["channel_id"]] = per_channel.get(c["channel_id"], 0) + 1
        added += 1
        logger.info(f"+ [{c['category']}] {c['channel']}: {c['title'][:70]}")
    logger.info(f"Adicionados: {added} | pendentes agora: {len(pending(queue))}")
    return added


class YouTubeBlocked(RuntimeError):
    """O YouTube pediu "confirme que você não é um robô": parar e tentar outro dia."""


def _video_meta(video_id: str) -> dict:
    """Metadados reais do vídeo; recusa qualquer canal fora da lista oficial."""
    from reel_downloader import _ytdlp
    from content_generator import _categorize
    url = f"https://www.youtube.com/watch?v={video_id}"
    r = _ytdlp(url, "--skip-download", "--dump-json", "--extractor-args", "youtube:lang=pt")
    if not r.stdout.strip() and "not a bot" not in r.stderr:
        # com lang=pt o yt-dlp às vezes devolve "vídeo não está disponível" à toa
        r = _ytdlp(url, "--skip-download", "--dump-json")
    if "not a bot" in r.stderr or "confirm you" in r.stderr:
        raise YouTubeBlocked(r.stderr.strip()[-160:])
    if not r.stdout.strip():
        raise ValueError(f"sem metadados: {r.stderr.strip()[-120:]}")
    v = json.loads(r.stdout)
    if v.get("channel_id") not in ALL_OFFICIAL:
        raise ValueError(f"canal fora da lista oficial: {v.get('channel')}")
    channel = ALL_OFFICIAL[v["channel_id"]]
    up = v.get("upload_date", "")
    return {
        "title": v["title"], "channel": channel, "channel_id": v["channel_id"],
        "category": _categorize({"title": f"{v['title']} {channel}"}),
        "description": (v.get("description") or "")[:700],
        "published": f"{up[:4]}-{up[4:6]}-{up[6:8]}" if len(up) == 8 else "",
        "duration": int(v.get("duration") or 0),
        "pt_subs": any(k.lower().startswith("pt") for k in (v.get("subtitles") or {})),
    }


def premap() -> int:
    """
    Baixa e enfileira o que falta de PLAN_PATH, no máximo PREMAP_MAX_PER_RUN por
    execução e com pausa entre vídeos. Em 06/10/2026, ~35 downloads seguidos
    fizeram o YouTube bloquear o IP de casa; ao primeiro sinal de bloqueio, para.
    """
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    queue = load_queue()
    known = {q["video_id"] for q in queue}
    todo = [p for p in plan if p["video_id"] not in known]
    batch = todo[:PREMAP_MAX_PER_RUN]
    logger.info(f"[{STREAM}] plano: {len(plan)} itens, {len(todo)} faltando, {len(batch)} nesta execução")
    added = 0
    for n, p in enumerate(batch, 1):
        if n > 1:
            time.sleep(PREMAP_PAUSE_SECONDS)
        try:
            meta = _video_meta(p["video_id"])
            extra = {"kind": "cena" if STREAM == "cenas" else "acervo", "plan_order": plan.index(p)}
            if p.get("scheduled_for"):
                extra.update(scheduled_for=p["scheduled_for"], theme=p.get("theme", ""))
            _add_item(queue, p["video_id"], meta, **extra)
            added += 1
            logger.info(f"[{n}/{len(batch)}] + {p.get('scheduled_for', 'sequência')} | "
                        f"{meta['channel']}: {meta['title'][:60]}")
        except YouTubeBlocked as e:
            logger.warning(f"YouTube bloqueou o IP — parando por hoje ({e})")
            break
        except Exception as e:
            logger.warning(f"[{n}/{len(batch)}] FALHOU {p['video_id']}: {str(e)[:150]}")
    logger.info(f"[{STREAM}] pré-mapeados: {added} | ainda faltam {len(todo) - added}")
    return added


# ── CI: publicar ────────────────────────────────────────────────────────────

def _minutes_since_last_reel() -> float:
    token, ig = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{ig}/media"
           f"?fields=timestamp,media_type&limit=15&access_token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        media = json.loads(r.read()).get("data", [])
    times = [datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
             for m in media if m.get("media_type") == "VIDEO"]
    if not times:
        return 1e9
    return (datetime.now(timezone.utc) - max(times)).total_seconds() / 60


def is_due() -> tuple[bool, str]:
    """Um reel por dia por fluxo, a partir do horário do fluxo."""
    now = datetime.now(BRT)
    queue = load_queue()
    n = len(pending(queue))
    tag = f"[{STREAM}]"
    if _pick_next(queue) is None:
        return False, f"{tag} fila sem item para hoje (o Mac precisa abastecer)"
    if os.environ.get("REEL_FORCE") == "true":
        return True, f"{tag} forçado manualmente ({n} na fila)"
    if now.hour < REEL_SLOT_BRT:
        return False, f"{tag} {now:%H:%M} BRT, antes das {REEL_SLOT_BRT}h"
    if any(q.get("posted_at", "")[:10] == now.date().isoformat() for q in queue):
        return False, f"{tag} já saiu hoje"
    try:
        gap = _minutes_since_last_reel()
    except Exception as e:
        return False, f"{tag} falha ao consultar o Instagram ({e})"
    if gap < MIN_GAP_MIN:
        return False, f"{tag} último reel há {gap:.0f} min (mínimo {MIN_GAP_MIN})"
    return True, f"{tag} reel devido ({n} na fila)"


def _pick_next(queue: list[dict], today=None) -> dict | None:
    """Fixo do dia → lançamento novo → acervo na ordem do plano."""
    today = today or datetime.now(BRT).date()
    todo = pending(queue)

    def days_late(q):
        return (today - datetime.strptime(q["scheduled_for"], "%Y-%m-%d").date()).days

    pinned = [q for q in todo if q.get("scheduled_for") and 0 <= days_late(q) <= PIN_GRACE_DAYS]
    if pinned:
        return min(pinned, key=days_late)
    fresh = [q for q in todo if _is_fresh(q)]
    if fresh:
        posted = sorted((q for q in queue if q.get("posted")), key=lambda q: q.get("posted_at", ""))
        last_cat = posted[-1]["category"] if posted else None
        return next((q for q in fresh if q["category"] != last_cat), fresh[0])
    acervo = sorted((q for q in todo if not q.get("scheduled_for")),
                    key=lambda q: q.get("plan_order", 0))
    return acervo[0] if acervo else None


_THEME_NOTES = {
    "halloween": "Este Reel faz parte do especial de Halloween da Morsa.",
    "natal": "Este Reel faz parte do especial de Natal da Morsa.",
    "ano_novo": "Este Reel é da virada de ano da Morsa.",
    "vingadores": "Este Reel faz parte do aquecimento da Morsa para o novo filme dos Vingadores.",
    "gta": "Este Reel faz parte da contagem da Morsa para GTA VI.",
    "criancas": "Este Reel é do especial de Dia das Crianças da Morsa (12 de outubro).",
    "animacao": "Este Reel é do Dia Internacional da Animação (28 de outubro).",
}


def _age_note(item: dict) -> str:
    """Vídeo antigo é relembrança, nunca notícia."""
    try:
        published = datetime.fromisoformat(item["published"][:10]).date()
    except ValueError:
        return ""
    days = (datetime.now(BRT).date() - published).days
    if days <= 60:
        return ""
    return (f"ATENÇÃO: o vídeo foi publicado pelo canal em {published:%m/%Y}. NÃO é novidade: "
            "escreva como relembrança (\"relembre\", \"vale rever\"), nunca como lançamento, "
            "e não diga que algo \"chegou\", \"saiu\" ou \"estreia em breve\". A obra já foi "
            "lançada: não especule sobre o que \"vai\" acontecer nela; pergunte ao fã o que "
            "achou ou qual a lembrança dele.\n")


# Molde tirado dos maiores reels da conta: pergunta ao fã na 1ª linha, contexto
# curto em voz de fã, chamada para comentar.
HOOK_SYSTEM = """Você é o social media da Morsa Digital, canal brasileiro de cultura pop/nerd.
Escreve legendas para Reels de CENAS, clipes e bastidores de filmes, séries e animações.
O objetivo é fazer o fã comentar.

ESTRUTURA OBRIGATÓRIA:

[LINHA 1: uma pergunta direta ao fã, até 90 caracteres, com o nome da obra ou do personagem. Sem emoji no início. Exemplos do tom: "Você lembrava dessa cena ou tá descobrindo agora?", "Concorda? Ou vai defender outro Aranha?", "Tem como isso perder a graça?"]

[linha em branco]

[2 ou 3 linhas de contexto em voz de fã: por que essa cena marcou, o que ela tem de especial.]

[linha em branco]

[1 linha chamando para comentar. Varie: "Comenta aí...", "Qual é a sua...", "Marca aquele amigo que..."]

[linha em branco]

#hashtags (5 a 7, específicas da obra e dos personagens, terminando em #MorsaDigital)

REGRAS:
- Português do Brasil, informal, como um fã escreve. Nada de tom de release.
- Use só o que está nos fatos fornecidos e no título. Não invente elenco, datas, bilheteria, bastidores ou curiosidades.
- No contexto, fale de sentimento e memória do fã, não de fatos da obra: nada de lugares, episódios, números, anos, objetos ou acontecimentos que não estejam escritos nos fatos fornecidos. Detalhe "de cabeça" sai errado.
- Você NÃO assistiu ao vídeo. Não afirme o que acontece na cena: quem enfrenta quem, quem vence, quem aparece além dos nomes que estão no título, falas ou golpes. Fale da obra e dos personagens citados no título, e deixe a cena para quem assiste.
- Nunca use travessão.
- Sem hashtag genérica (#Cinema, #Filmes, #Trailer).
- Nomes de filmes e personagens como o público brasileiro conhece (Homem de Ferro, Doutor Estranho, Homem-Aranha: Através do Aranhaverso), mesmo que o título do vídeo esteja em inglês.
- A pergunta da linha 1 tem que dividir opiniões ou puxar memória: melhor ou pior, quem ganha, lembra ou não lembra, concorda ou não. Pergunta morna ("quem mais gostou?") não serve.
- Nada de frase de enchimento como "vale dar o play", "vale a pena rever", "arrepia qualquer fã"."""


class CaptionUnavailable(RuntimeError):
    """O modelo não respondeu (limite da Groq: 1.000 chamadas/dia, 8 mil tokens/min)."""


def _caption(item: dict) -> str:
    from content_generator import REEL_TRAILER_SYSTEM, _call_groq, _strip_ai_tells, _cap_hashtags
    from editorial import _with_credit
    system = HOOK_SYSTEM if STREAM == "cenas" else REEL_TRAILER_SYSTEM
    user_msg = (
        f"Escreva a legenda para o Reel: {item['title']}\n\n"
        f"{_age_note(item)}{_THEME_NOTES.get(item.get('theme', ''), '')}\n"
        f"FATOS VERIFICADOS (descrição oficial do canal {item['channel']}) — use APENAS estes, "
        f"nunca invente elenco, data ou enredo:\n{item['description']}\n\n"
        "Não copie frases da descrição oficial: escreva com a voz da Morsa.\n"
        "PROIBIDO afirmar qualquer coisa que não esteja nos fatos acima: data de estreia, "
        "elenco, enredo, se é final de série, se terá continuação, opinião sobre a obra "
        "completa (ninguém assistiu ainda). Na dúvida, fale do que o título promete e "
        "faça a pergunta ao fã. Termine com 5 a 6 hashtags específicas da franquia "
        "(nada genérico como #Cinema, #Trailer ou #Filmes)."
    )
    text, last_error = "", None
    for attempt in range(3):
        try:
            text = re.sub(r"\n[ \t]*\n+", "\n\n", _call_groq(system, user_msg, 600)).strip()
            if len(text) >= 100:
                break
        except Exception as e:
            last_error = e
            logger.warning(f"Groq falhou na legenda: {e}")
            time.sleep(20 * (attempt + 1))     # limite da conta: 8 mil tokens por minuto
    if len(text) < 100:
        raise CaptionUnavailable(f"sem legenda para {item['video_id']}: {last_error}")
    return _with_credit(_cap_hashtags(_strip_ai_tells(text)), item["channel"])


# ── Auditoria: legendas prontas e arquivos conferidos antes do dia ───────────

_NEWS_WORDS_RE = re.compile(r"\b(chegou|acabou de sair|acaba de sair|estreia em breve|em breve|"
                            r"novo trailer|saiu o trailer)\b", re.IGNORECASE)


def lint_caption(item: dict, caption: str) -> list[str]:
    """Regras fixas que toda legenda tem que cumprir."""
    problems = []
    lines = [l for l in caption.splitlines() if l.strip()]
    tags = re.findall(r"#\w+", caption)
    if f"Vídeo: {item['channel']}" not in caption:
        problems.append("sem crédito do canal")
    if "—" in caption or "–" in caption:
        problems.append("tem travessão")
    if not 4 <= len(tags) <= 8:
        problems.append(f"{len(tags)} hashtags (esperado 4 a 8)")
    if any(t.lower() in ("#cinema", "#filmes", "#trailer", "#série", "#series") for t in tags):
        problems.append("hashtag genérica")
    if len(caption) < 150 or len(caption) > 1200:
        problems.append(f"tamanho {len(caption)}")
    if lines and not lines[0][0].isalnum() and lines[0][0] not in '"“¿':
        problems.append("começa com emoji ou símbolo")
    if STREAM == "cenas" and lines and "?" not in lines[0]:
        problems.append("1ª linha não é pergunta")
    if _age_note(item) and _NEWS_WORDS_RE.search(caption):
        problems.append("trata vídeo antigo como novidade")
    return problems


JUDGE_MODEL = "openai/gpt-oss-120b"   # modelo maior que o redator, só para checar


def _groq_json(model: str, system: str, user: str, max_tokens: int = 700) -> dict:
    payload = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": 0,
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                 "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(json.loads(r.read())["choices"][0]["message"]["content"])


def judge_caption(item: dict, caption: str) -> list[str]:
    """Um modelo maior confere se a legenda inventou algum detalhe."""
    body = caption.split("\n\nVídeo:")[0]
    try:
        found = _groq_json(
            JUDGE_MODEL,
            "Você é checador de fatos de um perfil de cultura pop. Recebe TÍTULO e DESCRIÇÃO "
            "OFICIAL de um vídeo e a LEGENDA escrita para ele. Aponte os trechos da legenda que "
            "são detalhe factual ERRADO ou INVENTADO sobre a obra: lugar, objeto, número, data, "
            "acontecimento, fala, elenco ou enredo que não está no título/descrição e que você "
            "não tem certeza de ser verdadeiro. NÃO aponte: opinião, pergunta, sentimento, nome "
            "da obra, nem personagens que realmente pertencem à obra. Na dúvida sobre um detalhe "
            'específico, aponte. Responda JSON: {"inventado": ["trecho", ...]} (lista vazia se ok).',
            f"TÍTULO: {item['title']}\nCANAL: {item['channel']}\nDESCRIÇÃO OFICIAL: "
            f"{item['description']}\n\nLEGENDA:\n{body}").get("inventado", [])
        return [f"detalhe sem base: {x}" for x in found if isinstance(x, str)][:4]
    except Exception as e:
        return [f"checagem indisponível ({str(e)[:60]})"]


def _upcoming(queue: list[dict], days: int) -> list[dict]:
    """Itens que o calendário vai publicar nos próximos `days` dias, em ordem."""
    sim = json.loads(json.dumps(queue))
    by_id = {q["video_id"]: q for q in queue}
    day, out = datetime.now(BRT).date(), []
    for _ in range(days):
        it = _pick_next(sim, day)
        if it is not None:
            it["posted"] = True
            it["posted_at"] = day.isoformat()
            out.append(by_id[it["video_id"]])
        day += timedelta(days=1)
    return out


def prepare_captions(days: int = 6, limit: int = 4) -> dict:
    """
    Gera, audita e guarda a legenda dos próximos dias (até 3 tentativas cada).
    Econômico de propósito: cada modelo da Groq tem 200 mil tokens por dia, e o
    redator é o mesmo dos posts de feed. Na madrugada de 07/10/2026 a auditoria estourou o
    limite e gravou legendas vazias; por isso para no primeiro erro e nunca
    guarda legenda que o modelo não escreveu.
    """
    queue = load_queue()
    todo = [q for q in _upcoming(queue, days) if q.get("caption_check") != "ok"][:limit]
    stats = {"ok": 0, "revisar": 0}
    for item in todo:
        best, best_problems = None, None
        try:
            for _ in range(3):
                caption = _caption(item)
                problems = lint_caption(item, caption)
                if not problems:
                    problems = judge_caption(item, caption)
                if best is None or len(problems) < len(best_problems):
                    best, best_problems = caption, problems
                if not problems:
                    break
                time.sleep(8)
        except CaptionUnavailable as e:
            logger.warning(f"[{STREAM}] parando a auditoria: {e}")
            break
        item["caption"] = best
        item["caption_check"] = "ok" if not best_problems else "revisar"
        item["caption_problems"] = best_problems
        stats[item["caption_check"]] += 1
        save_queue(queue)
        logger.info(f"[{STREAM}] legenda {item['caption_check']}: {item['title'][:50]} {best_problems or ''}")
        time.sleep(8)
    return stats


def verify_assets() -> list[str]:
    """Confere se o arquivo de cada item pendente está no ar e com tamanho plausível."""
    bad = []
    for q in pending(load_queue()):
        try:
            req = urllib.request.Request(q["asset_url"], method="HEAD")
            with urllib.request.urlopen(req, timeout=20) as r:
                size = int(r.headers.get("Content-Length", 0))
            if size < 300_000:
                bad.append(f"{q['video_id']} arquivo pequeno demais ({size} bytes): {q['title'][:50]}")
        except Exception as e:
            bad.append(f"{q['video_id']} inacessível ({str(e)[:50]}): {q['title'][:50]}")
    return bad


def write_report():
    """Relatório legível dos dois fluxos: calendário, formato, idioma e legenda de cada reel."""
    out = [f"# Fila de reels @morsadigital — {datetime.now(BRT):%d/%m/%Y %H:%M} BRT", ""]
    for name in STREAMS:
        use_stream(name)
        queue = load_queue()
        sim = json.loads(json.dumps(queue))
        day = datetime.now(BRT).date()
        if any(q.get("posted_at", "")[:10] == day.isoformat() for q in queue):
            day += timedelta(days=1)
        rows, empty = [], 0
        while pending(sim) and empty < 20 and len(rows) < 120:
            it = _pick_next(sim, day)
            if it is None:
                empty += 1
                rows.append((day, None))
            else:
                empty = 0
                it["posted"] = True
                it["posted_at"] = day.isoformat()
                rows.append((day, it))
            day += timedelta(days=1)
        while rows and rows[-1][1] is None:
            rows.pop()
        todo = pending(queue)
        out += [f"## {name} — a partir das {REEL_SLOT_BRT}h", "",
                f"{len(todo)} na fila | legendas ok: {sum(1 for q in todo if q.get('caption_check') == 'ok')} | "
                f"a revisar: {sum(1 for q in todo if q.get('caption_check') == 'revisar')} | "
                f"dias sem reel no calendário: {sum(1 for _, it in rows if it is None)}", ""]
        for d, it in rows:
            if it is None:
                out += [f"### {d:%d/%m} — sem reel (fila ainda não cobre este dia)", ""]
                continue
            out += [f"### {d:%d/%m} — {it['title'][:80]}",
                    f"{it['channel']} · {it.get('layout', '?')} · {it.get('lang', '?')} · "
                    f"legenda: {it.get('caption_check', 'ainda não gerada')}"
                    + (f" ({'; '.join(it.get('caption_problems') or [])})" if it.get("caption_problems") else ""),
                    "", "```", it.get("caption", "(gerada na hora da publicação)"), "```", ""]
    path = ROOT / "data" / "reel_report.md"
    path.write_text("\n".join(out), encoding="utf-8")
    return path


def publish() -> int:
    due, reason = is_due()
    logger.info(reason)
    if not due:
        return 0
    from publishers.instagram import publish_reel_from_url
    from posts_log import record_post

    queue = load_queue()
    item = _pick_next(queue)
    try:
        caption = item.get("caption") or _caption(item)
    except CaptionUnavailable as e:
        logger.error(f"Sem legenda, não publica agora (o próximo gatilho tenta de novo): {e}")
        return 1
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
    # publish/due/status olham os dois fluxos, a não ser que REEL_STREAM escolha um
    streams = [os.environ["REEL_STREAM"]] if os.environ.get("REEL_STREAM") else list(STREAMS)
    if cmd == "fill":
        use_stream("main")
        fill()
    elif cmd == "premap":
        for name in streams:
            use_stream(name)
            if PLAN_PATH.exists():
                premap()
    elif cmd == "publish":
        for name in streams:
            use_stream(name)
            publish()
    elif cmd == "audit":
        problems = []
        for name in streams:
            use_stream(name)
            problems += verify_assets()
            logger.info(f"[{name}] legendas: {prepare_captions()}")
        for line in problems:
            logger.warning(f"ARQUIVO: {line}")
        logger.info(f"Relatório: {write_report()}")
    elif cmd == "due":
        any_due = False
        for name in streams:
            use_stream(name)
            due, reason = is_due()
            any_due = any_due or due
            print(reason)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"reel_due={'true' if any_due else 'false'}\n")
    else:
        for name in streams:
            use_stream(name)
            todo = pending(load_queue())
            print(f"== {name} (a partir das {REEL_SLOT_BRT}h) ==")
            for q in sorted((q for q in todo if q.get("scheduled_for")), key=lambda q: q["scheduled_for"]):
                print(f"{q['scheduled_for']} [{q.get('theme', '')}] {q['channel']}: {q['title'][:70]}")
            for q in todo:
                if _is_fresh(q):
                    print(f"lançamento  [{q['category']}] {q['channel']}: {q['title'][:70]}")
            rest = [q for q in todo if not q.get("scheduled_for") and not _is_fresh(q)]
            print(f"{len(todo)} pendentes: {sum(1 for q in todo if q.get('scheduled_for'))} fixos, "
                  f"{sum(1 for q in todo if _is_fresh(q))} lançamentos, {len(rest)} em sequência")
    return 0


if __name__ == "__main__":
    sys.exit(main())
