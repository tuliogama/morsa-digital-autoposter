"""
Stories automáticos: cada post ou reel novo da conta ganha um story com a arte
da marca chamando para ele.

A Graph API publica story de imagem e de vídeo, mas não tem figurinha de enquete,
caixinha nem link, e não faz o "compartilhar post no story" do app. Então:
  - reel novo  → teaser de 15s do próprio vídeo, com selo e chamada discretos;
  - post novo  → a arte do post inteira sobre preto, com dois rótulos pequenos.

Regras: no máximo MAX_PER_DAY por dia, MIN_GAP_MIN entre um e outro, só posts das
últimas 24h, um story por post. Estado em data/stories_log.json.

O mesmo arquivo roda no morsa-digital-autoposter e no ordem-sith-autoposter: a
cor e o logo vêm do image_generator de cada repositório.

Uso: python src/stories.py [--dry-run]
"""
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("stories")

BRT = timezone(timedelta(hours=-3))
ROOT = Path(__file__).parent.parent
LOG_PATH = ROOT / "data" / "stories_log.json"
GRAPH_URL = "https://graph.facebook.com/v21.0"

MAX_PER_DAY = int(os.environ.get("STORIES_MAX_PER_DAY", "3"))
MIN_GAP_MIN = int(os.environ.get("STORIES_MIN_GAP_MIN", "150"))
QUIET_BEFORE, QUIET_AFTER = 8, 23        # sem story de madrugada (horário de Brasília)
W, H = 1080, 1920


def _load_log() -> list[dict]:
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def recent_posts(hours: int = 24) -> list[dict]:
    """Posts e reels da própria conta nas últimas horas, do mais novo ao mais antigo."""
    token, ig = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    fields = ("id,timestamp,media_type,media_product_type,media_url,thumbnail_url,caption,"
              "children{media_type,media_url,thumbnail_url}")
    data = _get(f"{GRAPH_URL}/{ig}/media?fields={fields}&limit=15&access_token={token}").get("data", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for p in data:
        if datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z") < cutoff:
            continue
        if p.get("media_type") == "VIDEO":
            image = p.get("thumbnail_url")
        elif p.get("media_type") == "CAROUSEL_ALBUM":
            first = (p.get("children", {}).get("data") or [{}])[0]
            image = first.get("thumbnail_url") or first.get("media_url")
        else:
            image = p.get("media_url")
        if image:
            out.append({"id": p["id"], "is_reel": p.get("media_type") == "VIDEO", "image": image,
                        "video": p.get("media_url") if p.get("media_type") == "VIDEO" else None,
                        "hook": (p.get("caption") or "").strip().split("\n")[0]})
    return out


def pick(posts: list[dict], log: list[dict], now: datetime) -> tuple[dict | None, str]:
    """Qual post vira story agora (ou None e o motivo)."""
    if not QUIET_BEFORE <= now.hour < QUIET_AFTER:
        return None, f"{now:%H:%M}: fora do horário de stories"
    today = [e for e in log if e["at"][:10] == now.date().isoformat()]
    if len(today) >= MAX_PER_DAY:
        return None, f"já saíram {len(today)} stories hoje"
    if log:
        gap = (now - datetime.fromisoformat(max(e["at"] for e in log))).total_seconds() / 60
        if gap < MIN_GAP_MIN:
            return None, f"último story há {gap:.0f} min (mínimo {MIN_GAP_MIN})"
    done = {e["media_id"] for e in log}
    fresh = [p for p in posts if p["id"] not in done]
    if not fresh:
        return None, "nenhum post novo sem story"
    # reel primeiro: é o formato que mais precisa de empurrão
    fresh.sort(key=lambda p: not p["is_reel"])
    return fresh[0], "ok"


TEASER_SECONDS = 15


def _spaced(draw, xy, text, font, fill, gap=6, anchor_center=None):
    """Texto com espaçamento entre letras (rótulos pequenos ficam mais elegantes)."""
    widths = [draw.textbbox((0, 0), ch, font=font)[2] for ch in text]
    total = sum(widths) + gap * (len(text) - 1)
    x, y = xy
    if anchor_center is not None:
        x = anchor_center - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + gap
    return total


def render_feed(post: dict) -> bytes:
    """
    Story de post do feed: a arte do post (que já tem título e logo) inteira, sobre
    preto, com as bordas de cima e de baixo esfumadas. Só dois rótulos pequenos.
    """
    from PIL import Image, ImageDraw
    from image_generator import COLOR_ORANGE as BRAND, _load_font

    with urllib.request.urlopen(post["image"], timeout=30) as r:
        art = Image.open(io.BytesIO(r.read())).convert("RGB")
    art = art.resize((W, int(art.height * W / art.width)))
    if art.height > 1500:
        cut = (art.height - 1500) // 2
        art = art.crop((0, cut, W, cut + 1500))
    canvas = Image.new("RGB", (W, H), (8, 8, 10))
    top = (H - art.height) // 2
    fade = Image.new("L", art.size, 255)                      # esfuma 90px em cima e embaixo
    px = fade.load()
    for y in range(90):
        v = int(255 * y / 90)
        for x in range(W):
            px[x, y] = v
            px[x, art.height - 1 - y] = v
    canvas.paste(art, (0, top), fade)
    draw = ImageDraw.Draw(canvas)
    small = _load_font(46)
    _spaced(draw, (0, top - 110), "NOVO NO FEED", small, BRAND, gap=10, anchor_center=W / 2)
    draw.line([(W / 2 - 60, top - 44), (W / 2 + 60, top - 44)], fill=BRAND, width=4)
    _spaced(draw, (0, top + art.height + 60), "LEIA NO PERFIL", small, (235, 235, 235), gap=10,
            anchor_center=W / 2)
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _teaser_overlay(path: str):
    """Camada transparente do teaser: selo pequeno no alto e chamada no rodapé."""
    from PIL import Image, ImageDraw
    from image_generator import COLOR_ORANGE as BRAND, _load_font

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = layer.load()
    for y in range(H - 420, H):                               # degradê escuro só no rodapé
        alpha = int(190 * (y - (H - 420)) / 420)
        for x in range(W):
            px[x, y] = (0, 0, 0, alpha)
    draw = ImageDraw.Draw(layer)
    label_font = _load_font(44)
    lw = sum(draw.textbbox((0, 0), ch, font=label_font)[2] for ch in "NOVO REEL") + 8 * 8
    draw.rounded_rectangle([60, 250, 60 + lw + 56, 322], radius=36, fill=BRAND + (255,))
    _spaced(draw, (88, 262), "NOVO REEL", label_font, "white", gap=8)
    cta_font = _load_font(52)
    _spaced(draw, (0, H - 250), "ASSISTA COMPLETO NO PERFIL", cta_font, "white", gap=8, anchor_center=W / 2)
    draw.line([(W / 2 - 70, H - 178), (W / 2 + 70, H - 178)], fill=BRAND + (255,), width=5)
    layer.save(path)


def render_teaser(post: dict, workdir: str) -> str:
    """Story de reel: os primeiros segundos do próprio vídeo, com selo e chamada."""
    src = os.path.join(workdir, "src.mp4")
    urllib.request.urlretrieve(post["video"], src)
    overlay = os.path.join(workdir, "overlay.png")
    _teaser_overlay(overlay)
    out = os.path.join(workdir, f"story_{post['id']}.mp4")
    fade_at = TEASER_SECONDS - 0.6
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-i", overlay, "-filter_complex",
         f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v];"
         f"[v][1:v]overlay=0:0,fade=t=out:st={fade_at}:d=0.6[o]",
         "-map", "[o]", "-map", "0:a?", "-af", f"afade=t=out:st={fade_at}:d=0.6",
         "-t", str(TEASER_SECONDS), "-c:v", "libx264", "-preset", "fast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr[-300:]}")
    return out


def _publish_video_story(path: str) -> str:
    """
    Envia o arquivo direto para a Meta (upload resumable) e publica como story.
    Sem link público no meio: o repositório da Ordem Sith é privado e a Meta não
    conseguia buscar o vídeo numa Release dele (erro 2207076).
    """
    from publishers.instagram import _post, _publish_container
    token, ig = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    container = _post(f"{GRAPH_URL}/{ig}/media",
                      {"media_type": "STORIES", "upload_type": "resumable", "access_token": token})
    data = Path(path).read_bytes()
    req = urllib.request.Request(
        container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v21.0/{container['id']}",
        data=data, method="POST",
        headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)),
                 "Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=300) as r:
        if not json.loads(r.read()).get("success"):
            raise RuntimeError("a Meta não confirmou o recebimento do vídeo")
    for _ in range(24):                                       # até 4 minutos de processamento
        time.sleep(10)
        status = _get(f"{GRAPH_URL}/{container['id']}?fields=status_code,status&access_token={token}")
        if status.get("status_code") == "FINISHED":
            return _publish_container(ig, token, container["id"])
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"a Meta recusou o vídeo: {status}")
    raise RuntimeError("vídeo do story não ficou pronto a tempo")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    dry = "--dry-run" in sys.argv
    now = datetime.now(BRT)
    log = _load_log()
    post, reason = pick(recent_posts(), log, now)
    if "--due" in sys.argv:                 # usado pelo workflow para não instalar ffmpeg à toa
        logger.info(reason if post is None else f"há story a publicar ({'reel' if post['is_reel'] else 'post'})")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"due={'true' if post else 'false'}\nreel={'true' if post and post['is_reel'] else 'false'}\n")
        return 0
    if post is None:
        logger.info(f"Sem story agora: {reason}")
        return 0
    logger.info(f"Story para o {'reel' if post['is_reel'] else 'post'} {post['id']}: {post['hook'][:70]}")
    preview = ROOT / "logs"
    preview.mkdir(exist_ok=True)
    if post["is_reel"] and post.get("video"):
        with tempfile.TemporaryDirectory(prefix="story_") as tmp:
            teaser = render_teaser(post, tmp)
            if dry:
                shutil.copy(teaser, preview / "story_preview.mp4")
                logger.info(f"Dry run: teaser salvo em {preview / 'story_preview.mp4'}")
                return 0
            story_id = _publish_video_story(teaser)
    else:
        image = render_feed(post)
        if dry:
            (preview / "story_preview.jpg").write_bytes(image)
            logger.info(f"Dry run: arte salva em {preview / 'story_preview.jpg'}")
            return 0
        from image_generator import _upload_image
        from publishers.instagram import _post_to_stories
        url = _upload_image(image)
        if not url:
            logger.error("Não consegui hospedar a arte do story")
            return 1
        story_id = _post_to_stories(os.environ["IG_USER_ID"], os.environ["FB_ACCESS_TOKEN"], post["id"], url)
    if not story_id:
        return 1
    log.append({"media_id": post["id"], "story_id": story_id, "at": now.isoformat(timespec="seconds")})
    LOG_PATH.write_text(json.dumps(log[-200:], indent=1, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Story publicado: {story_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
