"""
Stories automáticos: cada post ou reel novo da conta ganha um story com a arte
da marca chamando para ele.

A Graph API publica story de imagem, mas não tem figurinha de enquete, caixinha
nem link, e não faz o "compartilhar post no story" do app. Então o story é uma
arte 1080x1920 com a imagem do post, o gancho da legenda e a marca.

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
import sys
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


def render(post: dict) -> bytes:
    """Arte 1080x1920: fundo desfocado do próprio post, cartão com a imagem, gancho e marca."""
    from PIL import Image, ImageDraw, ImageFilter
    from image_generator import COLOR_ORANGE as BRAND, _load_font, _round_logo, _wrap_text

    with urllib.request.urlopen(post["image"], timeout=30) as r:
        src = Image.open(io.BytesIO(r.read())).convert("RGB")

    # fundo: a própria imagem cobrindo a tela, desfocada e escurecida
    scale = max(W / src.width, H / src.height)
    bg = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1))
    left, top = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(28))
    canvas = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.6)
    draw = ImageDraw.Draw(canvas)

    # cartão com a imagem do post
    card_w = 900
    card = src.resize((card_w, int(src.height * card_w / src.width)))
    if card.height > 940:
        cut = (card.height - 940) // 2
        card = card.crop((0, cut, card_w, cut + 940))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width, card.height], radius=40, fill=255)
    card_y = 430
    canvas.paste(card, ((W - card_w) // 2, card_y), mask)

    # marca + etiqueta
    logo = _round_logo(120)
    canvas.paste(logo, (90, 230), logo)
    label = "NOVO REEL" if post["is_reel"] else "NOVO NO FEED"
    font_label = _load_font(58)
    lw = draw.textbbox((0, 0), label, font=font_label)[2]
    draw.rounded_rectangle([240, 252, 240 + lw + 60, 338], radius=43, fill=BRAND)
    draw.text((270, 262), label, font=font_label, fill="white")

    # gancho da legenda: sem emoji (a fonte não tem), no máximo 3 linhas
    hook = re.sub(r"[^\w\s.,!?:;'\"()%&/+-]", "", post["hook"]).strip()
    font_hook = _load_font(68)
    lines = _wrap_text(draw, hook[:160], font_hook, 900)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip(".,;: ") + "..."
    y = card_y + card.height + 50
    for line in lines:
        draw.text((90, y), line, font=font_hook, fill="white", stroke_width=3, stroke_fill="black")
        y += 80

    # chamada final, sempre abaixo do texto
    font_cta = _load_font(54)
    cta = "VEJA NO PERFIL"
    cw = draw.textbbox((0, 0), cta, font=font_cta)[2]
    cy = max(y + 40, 1640)
    draw.rounded_rectangle([(W - cw) // 2 - 40, cy, (W + cw) // 2 + 40, cy + 90], radius=45,
                           outline="white", width=4)
    draw.text(((W - cw) // 2, cy + 14), cta, font=font_cta, fill="white")

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    dry = "--dry-run" in sys.argv
    now = datetime.now(BRT)
    log = _load_log()
    post, reason = pick(recent_posts(), log, now)
    if post is None:
        logger.info(f"Sem story agora: {reason}")
        return 0
    logger.info(f"Story para o {'reel' if post['is_reel'] else 'post'} {post['id']}: {post['hook'][:70]}")
    image = render(post)
    if dry:
        out = ROOT / "logs" / "story_preview.jpg"
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(image)
        logger.info(f"Dry run: arte salva em {out}")
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
