"""
Gerador de imagens para posts do Instagram/Facebook.
Formato 4:5 (1080x1350px) Full HD com logo Morsa Digital no canto inferior direito.
"""
import io
import os
import math
import logging
import urllib.request
import urllib.parse
import base64
import json
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Dimensões do post
POST_W = 1080
POST_H = 1350  # 4:5

# Cores Morsa Digital
COLOR_ORANGE = (255, 107, 0)   # #FF6B00
COLOR_BLACK  = (0, 0, 0)
COLOR_WHITE  = (255, 255, 255)
COLOR_DARK   = (15, 15, 15)    # fundo escuro

LOGO_SIZE    = 140   # px — logo redondinha
LOGO_MARGIN  = 40    # distância das bordas

ASSETS_DIR   = Path(__file__).parent.parent / "assets"
LOGO_PATH    = ASSETS_DIR / "morsa_logo.png"

HEADERS = {"User-Agent": "MorsaDigital-Autoposter/1.0"}


# ---------------------------------------------------------------------------
# Utilitários PIL
# ---------------------------------------------------------------------------

def _pil_available() -> bool:
    try:
        import PIL  # noqa
        return True
    except ImportError:
        return False


def _make_circle_mask(size: int):
    """Cria máscara circular (modo L)."""
    from PIL import Image, ImageDraw
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    return mask


def _round_logo(logo_size: int = LOGO_SIZE):
    """Retorna a logo do Morsa Digital recortada em círculo."""
    from PIL import Image

    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            mask = _make_circle_mask(logo_size)
            output = Image.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
            output.paste(logo, (0, 0), mask)
            return output
        except Exception as e:
            logger.warning(f"Erro ao processar logo: {e}")

    # Fallback: gerar logo simples com as cores da Morsa
    return _generate_fallback_logo(logo_size)


def _generate_fallback_logo(size: int):
    """Logo de fallback: círculo com diagonal laranja/preto + 'M'."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fundo preto circular
    mask = _make_circle_mask(size)
    bg = Image.new("RGBA", (size, size), (*COLOR_BLACK, 255))
    img.paste(bg, (0, 0), mask)

    # Triângulo laranja (metade superior direita)
    draw.polygon([(size, 0), (size, size), (0, 0)], fill=(*COLOR_ORANGE, 255))
    # Re-aplicar máscara circular
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    # Letra "M" centralizada em branco
    draw2 = ImageDraw.Draw(result)
    font_size = int(size * 0.45)
    font = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/System/Library/Fonts/Helvetica.ttc"]:
        try:
            from PIL import ImageFont
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    text = "M"
    if font:
        bbox = draw2.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw2.text(((size - tw) // 2, (size - th) // 2 - int(size * 0.05)),
                   text, fill=(*COLOR_WHITE, 255), font=font)
    return result


def _add_gradient_overlay(img):
    """Gradiente escuro na parte inferior — cobertura maior para suportar texto."""
    from PIL import Image, ImageDraw

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    grad_h = int(img.height * 0.52)   # 52% para o texto respirar bem
    y_start = img.height - grad_h

    for y in range(grad_h):
        # Curva mais suave no início, mais densa no final
        t = y / grad_h
        alpha = int(210 * (t ** 0.7))
        draw.line([(0, y_start + y), (img.width, y_start + y)],
                  fill=(0, 0, 0, alpha))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _add_text_overlay(img, title: str, source: str = "") -> "Image":
    """
    Headline estilo IGN Brasil: ALL CAPS, branco com borda preta,
    centralizado na parte inferior da imagem. Sem painel, sem badge.
    """
    from PIL import Image, ImageDraw

    if not title:
        return img

    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)

    W, H = img.size
    MARGIN_X     = 52
    MAX_W        = W - MARGIN_X * 2
    LINE_GAP     = 8
    BLOCK_BOTTOM = H - LOGO_MARGIN - LOGO_SIZE - 28

    # ALL CAPS
    text = title.upper()
    font = _load_font(72)

    # ── Quebrar em linhas (max 3) ─────────────────────────────────────────────
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        try:
            w = draw.textbbox((0, 0), test, font=font)[2]
            if w > MAX_W and line:
                lines.append(line)
                line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        lines.append(line)
    lines = lines[:3]

    # ── Altura do bloco ───────────────────────────────────────────────────────
    try:
        bb = draw.textbbox((0, 0), "AG", font=font)
        line_h = bb[3] - bb[1]
    except Exception:
        line_h = 80

    block_h = len(lines) * line_h + (len(lines) - 1) * LINE_GAP
    y_start = BLOCK_BOTTOM - block_h

    # ── Renderizar: borda preta + texto branco ────────────────────────────────
    STROKE = 3  # espessura da borda preta
    for i, ln in enumerate(lines):
        y = y_start + i * (line_h + LINE_GAP)
        try:
            tw = draw.textbbox((0, 0), ln, font=font)[2]
        except Exception:
            tw = MAX_W
        x = (W - tw) // 2  # centralizado

        # Borda preta (stroke simulado por offsets)
        for dx in range(-STROKE, STROKE + 1):
            for dy in range(-STROKE, STROKE + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), ln,
                              fill=(0, 0, 0, 220), font=font)

        # Texto branco por cima
        draw.text((x, y), ln, fill=COLOR_WHITE, font=font)

    return img


def _paste_logo(base_img, logo_size: int = LOGO_SIZE, margin: int = LOGO_MARGIN):
    """Cola a logo redondinha no canto inferior direito com halo para contraste."""
    from PIL import Image, ImageDraw

    logo = _round_logo(logo_size)

    # Halo semitransparente por baixo da logo (garante visibilidade em qualquer fundo)
    halo_size = logo_size + 16
    halo = Image.new("RGBA", (halo_size, halo_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(halo)
    draw.ellipse((0, 0, halo_size - 1, halo_size - 1), fill=(0, 0, 0, 120))

    base_rgba = base_img.convert("RGBA")

    # Posição: canto inferior direito, margem consistente
    x = base_rgba.width - logo_size - margin
    y = base_rgba.height - logo_size - margin

    # Cola halo centrado sob a logo
    halo_x = x - (halo_size - logo_size) // 2
    halo_y = y - (halo_size - logo_size) // 2
    base_rgba.paste(halo, (halo_x, halo_y), halo)

    # Cola logo sobre o halo
    base_rgba.paste(logo, (x, y), logo)
    return base_rgba


def _load_font(size: int):
    """Carrega fonte — prioriza Bebas Neue (condensada bold, estilo IGN Brasil)."""
    from PIL import ImageFont

    # Bebas Neue no repositório — funciona local e no GitHub Actions
    bebas = ASSETS_DIR / "fonts" / "BebasNeue.ttf"
    if bebas.exists():
        try:
            return ImageFont.truetype(str(bebas), size)
        except Exception:
            pass

    # Fallback: fontes bold do sistema
    paths = [
        "/Library/Fonts/Impact.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in paths:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    """Quebra texto em linhas que cabem em max_w pixels."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        try:
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > max_w and line:
                lines.append(line)
                line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        lines.append(line)
    return lines


def _create_branded_background(title: str = "", source: str = "") -> "Image":
    """
    Fundo branded profissional quando não há imagem do artigo.
    Design: fundo escuro texturizado + bloco laranja + título em destaque + badge da fonte.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (POST_W, POST_H), (*COLOR_DARK, 255))
    draw = ImageDraw.Draw(img)

    # --- Elementos geométricos de fundo ---
    # Bloco laranja grande no topo (1/3 superior)
    draw.rectangle([(0, 0), (POST_W, int(POST_H * 0.38))], fill=(*COLOR_ORANGE, 255))

    # Círculo decorativo semitransparente no canto superior direito
    cx, cy, cr = POST_W + 80, -80, 380
    draw.ellipse([(cx - cr, cy - cr), (cx + cr, cy + cr)], fill=(0, 0, 0, 40))

    # Linha separadora
    sep_y = int(POST_H * 0.38)
    draw.line([(0, sep_y), (POST_W, sep_y)], fill=(*COLOR_ORANGE, 180), width=6)

    # Pequenos retângulos decorativos no canto inferior esquerdo
    for i in range(3):
        x0 = 60 + i * 24
        draw.rectangle([(x0, POST_H - 220), (x0 + 12, POST_H - 180)],
                       fill=(*COLOR_ORANGE, 120 - i * 30))

    # --- Texto do título ---
    if title:
        margin_x = 70
        max_w = POST_W - margin_x * 2

        # Fonte grande para o bloco laranja (parte superior)
        font_title = _load_font(68)
        lines = _wrap_text(draw, title, font_title, max_w)

        # Limitar a 4 linhas
        if len(lines) > 4:
            lines = lines[:3] + [lines[3][:30] + "..."]

        line_h = 80
        total_h = len(lines) * line_h
        # Centralizar verticalmente no bloco laranja
        y = max(40, (int(POST_H * 0.38) - total_h) // 2)

        for ln in lines:
            try:
                bbox = draw.textbbox((0, 0), ln, font=font_title)
                x = (POST_W - (bbox[2] - bbox[0])) // 2
            except Exception:
                x = margin_x
            # Sombra sutil
            draw.text((x + 2, y + 2), ln, fill=(0, 0, 0, 100), font=font_title)
            draw.text((x, y), ln, fill=COLOR_WHITE, font=font_title)
            y += line_h

    # --- Badge da fonte no canto inferior esquerdo ---
    if source:
        font_badge = _load_font(38)
        badge_text = source.upper()
        badge_x, badge_y = 70, POST_H - 230
        try:
            bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
            bw = bbox[2] - bbox[0] + 30
            bh = bbox[3] - bbox[1] + 16
            draw.rounded_rectangle([(badge_x - 10, badge_y - 8),
                                     (badge_x + bw, badge_y + bh)],
                                    radius=8, fill=(*COLOR_ORANGE, 220))
            draw.text((badge_x + 5, badge_y), badge_text,
                      fill=COLOR_WHITE, font=font_badge)
        except Exception:
            pass

    return img


# ---------------------------------------------------------------------------
# Download de imagens de artigos
# ---------------------------------------------------------------------------

def _fetch_image_bytes(img_url: str) -> Optional[bytes]:
    """Baixa bytes de uma URL de imagem."""
    try:
        req = urllib.request.Request(img_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        # Validar que é imagem real (mínimo 5KB)
        if len(data) > 5000:
            return data
    except Exception as e:
        logger.debug(f"Falha ao baixar imagem {img_url[:60]}: {e}")
    return None


def _youtube_thumbnail(url: str) -> Optional[bytes]:
    """Extrai thumbnail de URLs do YouTube."""
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})',
        r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
        r'youtube\.com/shorts/([A-Za-z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            vid = m.group(1)
            for quality in ["maxresdefault", "sddefault", "hqdefault"]:
                data = _fetch_image_bytes(f"https://img.youtube.com/vi/{vid}/{quality}.jpg")
                if data:
                    logger.info(f"YouTube thumbnail ({quality}): {vid}")
                    return data
    return None


def _reddit_external_url(url: str) -> Optional[str]:
    """Para posts do Reddit, tenta extrair a URL externa linkada via JSON API."""
    import re
    if "reddit.com/r/" not in url:
        return None
    try:
        json_url = url.rstrip("/") + ".json?limit=1"
        req = urllib.request.Request(json_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        post = data[0]["data"]["children"][0]["data"]
        ext_url = post.get("url", "")
        # Só retornar se não for reddit.com em si
        if ext_url and "reddit.com" not in ext_url:
            logger.info(f"Reddit external URL: {ext_url[:60]}")
            return ext_url
        # Tentar preview de imagem do Reddit
        preview = post.get("preview", {})
        images = preview.get("images", [])
        if images:
            img_url = images[0].get("source", {}).get("url", "").replace("&amp;", "&")
            if img_url:
                logger.info(f"Reddit preview image encontrada")
                return img_url  # URL direta de imagem
    except Exception as e:
        logger.debug(f"Reddit JSON falhou: {e}")
    return None


def _fetch_article_image(url: str) -> Optional[bytes]:
    """
    Tenta obter imagem do artigo com múltiplas estratégias:
    1. YouTube thumbnail (para links de trailer)
    2. Reddit: extrai URL externa e usa estratégia sobre ela
    3. og:image do HTML da página
    """
    import re

    if not url:
        return None

    # Estratégia 1: YouTube direto
    if "youtube.com" in url or "youtu.be" in url:
        data = _youtube_thumbnail(url)
        if data:
            return data

    # Estratégia 2: Reddit — resolver URL real
    if "reddit.com" in url:
        resolved = _reddit_external_url(url)
        if resolved:
            # Se a URL resolvida for YouTube
            if "youtube.com" in resolved or "youtu.be" in resolved:
                data = _youtube_thumbnail(resolved)
                if data:
                    return data
            # Se for URL de imagem direta
            if any(resolved.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                data = _fetch_image_bytes(resolved)
                if data:
                    return data
            # Tentar og:image da URL resolvida
            data = _fetch_article_image(resolved)
            if data:
                return data
        logger.info(f"Reddit sem imagem utilizável para: {url[:60]}")
        return None

    # Estratégia 3: og:image do HTML
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(200_000).decode("utf-8", errors="replace")

        # Múltiplos padrões de og:image
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                img_url = m.group(1).replace("&amp;", "&")
                if not img_url.startswith("http"):
                    img_url = urllib.parse.urljoin(url, img_url)
                data = _fetch_image_bytes(img_url)
                if data:
                    logger.info(f"og:image encontrada: {img_url[:60]}")
                    return data

        logger.info(f"Nenhuma og:image em: {url[:60]}")
    except Exception as e:
        logger.info(f"Falha ao buscar HTML de {url[:60]}: {e}")

    return None


def _load_image_from_bytes(data: bytes) -> Optional["Image"]:
    try:
        from PIL import Image
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def _resize_crop_center(img, target_w: int, target_h: int) -> "Image":
    """
    Redimensiona e recorta para target_w×target_h mantendo proporção.
    Horizontalmente: centraliza. Verticalmente: ancora no terço superior
    (bias 0.35) para preservar rostos e sujeitos que raramente ficam
    na metade inferior da foto.
    """
    from PIL import Image
    src_ratio = img.width / img.height
    tgt_ratio = target_w / target_h

    if src_ratio > tgt_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    # 0.35 = ancora o sujeito no terço superior; 0.5 seria centro puro
    top = int((new_h - target_h) * 0.35)
    top = max(0, min(top, new_h - target_h))
    return img.crop((left, top, left + target_w, top + target_h))


# ---------------------------------------------------------------------------
# Upload para Imgur (gratuito, sem autenticação)
# ---------------------------------------------------------------------------

IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID", "546c25a59c58ad7")


def _upload_to_imgur(image_bytes: bytes, retries: int = 1) -> Optional[str]:
    """Sobe a imagem pro Imgur."""
    for attempt in range(retries + 1):
        try:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            payload = urllib.parse.urlencode({"image": b64, "type": "base64"}).encode()
            req = urllib.request.Request(
                "https://api.imgur.com/3/image",
                data=payload,
                headers={
                    "Authorization": f"Client-ID {IMGUR_CLIENT_ID}",
                    "User-Agent": HEADERS["User-Agent"],
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            if result.get("success"):
                return result["data"]["link"]
        except Exception as e:
            logger.debug(f"Imgur tentativa {attempt+1}/{retries+1} falhou: {e}")
            if attempt < retries:
                import time; time.sleep(2)
    return None


def _upload_to_github(image_bytes: bytes) -> Optional[str]:
    """
    Upload via GitHub Contents API — usa o próprio repositório como CDN.
    Completamente confiável no GitHub Actions (usa GITHUB_TOKEN já disponível).
    Salva em images/ com nome baseado em timestamp, retorna URL raw.githubusercontent.com.
    """
    token = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "tuliogama/morsa-digital-autoposter")
    if not token:
        logger.debug("GITHUB_TOKEN não disponível — pulando upload GitHub")
        return None

    import time as _time
    filename = f"images/post_{int(_time.time())}.jpg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = json.dumps({
        "message": f"img: {filename} [skip ci]",
        "content": b64,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{filename}",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": HEADERS["User-Agent"],
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        raw_url = result.get("content", {}).get("download_url", "")
        if raw_url:
            return raw_url
        # Fallback manual da URL raw
        branch = "main"
        return f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}"
    except Exception as e:
        logger.debug(f"GitHub upload falhou: {e}")
        return None


def _upload_to_catbox(image_bytes: bytes) -> Optional[str]:
    """Fallback: catbox.moe."""
    try:
        boundary = "----MorsaBoundary7x3k"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="reqtype"\r\n\r\n'
            f"fileupload\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="fileToUpload"; filename="morsa_post.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            "https://catbox.moe/user/api.php",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": HEADERS["User-Agent"],
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            url = resp.read().decode().strip()
        if url.startswith("https://"):
            return url
    except Exception as e:
        logger.debug(f"Catbox falhou: {e}")
    return None


def _search_google_image(query: str) -> Optional[bytes]:
    """
    Busca uma imagem relevante via Google Custom Search API.
    Requer GOOGLE_CSE_KEY e GOOGLE_CSE_ID no ambiente.
    Retorna bytes da primeira imagem válida encontrada, ou None.
    """
    api_key = os.environ.get("GOOGLE_CSE_KEY", "")
    cse_id  = os.environ.get("GOOGLE_CSE_ID", "")
    if not api_key or not cse_id:
        logger.debug("GOOGLE_CSE_KEY ou GOOGLE_CSE_ID não configurados")
        return None

    try:
        params = urllib.parse.urlencode({
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "searchType": "image",
            "num": "5",
            "imgSize": "large",
            "imgType": "photo",
            "safe": "active",
        })
        url = f"https://www.googleapis.com/customsearch/v1?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "MorsaDigital/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        items = data.get("items", [])
        for item in items:
            img_url = item.get("link", "")
            if not img_url:
                continue
            img_bytes = _fetch_image_bytes(img_url)
            if img_bytes and len(img_bytes) > 30_000:
                logger.info(f"Google CSE imagem: {img_url[:70]}")
                return img_bytes

    except Exception as e:
        logger.warning(f"Google CSE falhou: {e}")

    return None


def _build_search_query(news_item: dict) -> str:
    """
    Monta query de busca de imagem a partir do título da notícia.
    Extrai o tema central (franquia, jogo, filme) para uma busca mais precisa.
    """
    title = news_item.get("title", "")
    # Remover palavras genéricas de notícia para focar no tema
    stop = ["trailer", "anuncia", "anunciado", "confirmado", "revela",
            "lança", "lançamento", "novo", "nova", "vídeo", "video",
            "screenshots", "imagens", "gameplay", "review", "análise",
            "é anunciado", "será", "xbox games showcase", "direct",
            "treehouse", "game fest"]
    words = title
    for s in stop:
        words = words.replace(s, " ").replace(s.capitalize(), " ")
    # Pegar as primeiras palavras significativas
    clean = " ".join(w for w in words.split() if len(w) > 2)[:60]
    return f"{clean} official screenshot promotional art"


def _upload_image(image_bytes: bytes) -> Optional[str]:
    """
    Upload em cascata:
    1. GitHub (repo próprio — 100% confiável no Actions)
    2. Imgur (funciona localmente)
    3. catbox.moe (fallback externo)
    """
    url = _upload_to_github(image_bytes)
    if url:
        logger.info(f"Imagem publicada (GitHub CDN): {url[:70]}")
        return url

    url = _upload_to_imgur(image_bytes)
    if url:
        logger.info(f"Imagem publicada (Imgur): {url}")
        return url

    logger.warning("Imgur indisponível — tentando catbox.moe...")
    url = _upload_to_catbox(image_bytes)
    if url:
        logger.info(f"Imagem publicada (catbox.moe): {url}")
        return url

    logger.warning("Todos os serviços de upload falharam — post será pulado")
    return None


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def _fetch_article_images(url: str, count: int = 2) -> list:
    """
    Busca até `count` imagens distintas do artigo.
    Ordem de tentativa:
      1. og:image  → slide 1
      2. twitter:image (se diferente) → slide 2
      3. <img> do corpo do artigo com src >= 400px (heurística de tamanho na URL)
    Retorna lista de bytes (pode ter 1 ou 2 elementos).
    """
    import re

    if not url:
        return []

    # YouTube: só uma thumbnail disponível
    if "youtube.com" in url or "youtu.be" in url:
        data = _youtube_thumbnail(url)
        return [data] if data else []

    # Reddit: resolver e delegar
    if "reddit.com" in url:
        resolved = _reddit_external_url(url)
        if resolved:
            return _fetch_article_images(resolved, count)
        return []

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(200_000).decode("utf-8", errors="replace")
    except Exception as e:
        logger.info(f"Falha ao buscar HTML de {url[:60]}: {e}")
        return []

    found_urls = []

    def _normalize(u):
        return u.split("?")[0].split("#")[0]

    def _add_candidate(img_url):
        img_url = img_url.replace("&amp;", "&")
        if not img_url.startswith("http"):
            img_url = urllib.parse.urljoin(url, img_url)
        if _normalize(img_url) not in [_normalize(u) for u in found_urls]:
            found_urls.append(img_url)

    # 1. Meta tags: og:image e twitter:image
    meta_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pat in meta_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            _add_candidate(m.group(1))

    # Apenas meta tags — o conteúdo de <article> mistura imagens de artigos
    # relacionados que são indistinguíveis das imagens do artigo principal

    # 3. Baixar e validar (>20KB = imagem real, não ícone)
    result = []
    for img_url in found_urls:
        if len(result) >= count:
            break
        data = _fetch_image_bytes(img_url)
        if data and len(data) > 20_000:
            result.append(data)
            logger.info(f"Imagem {len(result)} confirmada ({len(data)//1024}KB): {img_url[:60]}")

    return result


def generate_post_image_pair(news_item: dict, headline: str = "") -> tuple:
    """
    Gera par de imagens para o carrossel de feed (2 slides):
      Slide 1: imagem com gradiente + título + logo (formato padrão)
      Slide 2: mesma imagem limpa — só o crop 4:5 + logo, sem texto

    Faz apenas uma requisição para buscar a imagem do artigo.
    Retorna (slide1_url, slide2_url). slide2_url pode ser None se upload falhar.
    """
    if not _pil_available():
        logger.warning("Pillow não instalado — imagens não geradas")
        return (None, None)

    title = news_item.get("title", "")
    article_url = news_item.get("url", "")
    if not article_url:
        return (None, None)

    # 1. Buscar até 2 imagens distintas do artigo
    images = _fetch_article_images(article_url, count=2)
    if not images:
        logger.info(f"Sem imagem real para '{title[:50]}' — post será pulado")
        return (None, None)

    display_headline = headline if headline else title

    # 2. Slide 1: primeira imagem + gradiente + título + logo
    base1 = _load_image_from_bytes(images[0])
    if not base1:
        return (None, None)

    slide1 = _resize_crop_center(base1, POST_W, POST_H)
    slide1 = _add_gradient_overlay(slide1)
    slide1 = _add_text_overlay(slide1, display_headline)
    slide1 = _paste_logo(slide1)
    buf1 = io.BytesIO()
    slide1.convert("RGB").save(buf1, format="JPEG", quality=92, optimize=True)
    slide1_url = _upload_image(buf1.getvalue())

    if not slide1_url:
        return (None, None)

    # 3. Slide 2: segunda imagem via Google CSE, mesma composição do slide 1 (sem texto)
    slide2_url = None
    try:
        query = _build_search_query(news_item)
        logger.info(f"Buscando 2ª imagem: {query[:60]}")
        img2_bytes = _search_google_image(query)

        if img2_bytes:
            base2 = _load_image_from_bytes(img2_bytes)
            if base2:
                slide2 = _resize_crop_center(base2, POST_W, POST_H)
                slide2 = _paste_logo(slide2)
                buf2 = io.BytesIO()
                slide2.convert("RGB").save(buf2, format="JPEG", quality=92, optimize=True)
                slide2_url = _upload_image(buf2.getvalue())
                if slide2_url:
                    logger.info(f"Slide 2 (Google CSE): {slide2_url[:60]}")
        else:
            logger.info("Google CSE sem resultado — slide 2 não gerado")
    except Exception as e:
        logger.warning(f"Falha ao gerar slide 2: {e}")

    return (slide1_url, slide2_url)


def _make_context_slide(title: str, description: str) -> "Image":
    """
    Slide editorial — fundo escuro, texto de contexto da notícia, logo.
    Usado como segundo slide do carrossel de feed.
    """
    from PIL import Image, ImageDraw, ImageFont

    ASSETS = Path(__file__).parent.parent / "assets"

    def _font(size):
        bebas = ASSETS / "fonts" / "BebasNeue.ttf"
        if bebas.exists():
            try:
                return ImageFont.truetype(str(bebas), size)
            except Exception:
                pass
        for fp in ["/System/Library/Fonts/Helvetica.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
        return ImageFont.load_default(size=size)

    img  = Image.new("RGB", (POST_W, POST_H), (15, 15, 15))
    draw = ImageDraw.Draw(img)
    W, H = POST_W, POST_H
    MARGIN = 72
    MAX_W  = W - MARGIN * 2
    ORANGE = (255, 107, 0)
    WHITE  = (255, 255, 255)
    GRAY   = (180, 180, 180)

    # Barra laranja no topo
    draw.rectangle([0, 0, W, 10], fill=ORANGE)

    # Tag "CONTEXTO" laranja
    tag_font = _font(28)
    tag = "  CONTEXTO  "
    try:
        tb = draw.textbbox((0, 0), tag, font=tag_font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
    except Exception:
        tw, th = 160, 30
    draw.rectangle([MARGIN, 60, MARGIN + tw, 60 + th + 16], fill=ORANGE)
    draw.text((MARGIN, 68), tag, font=tag_font, fill=WHITE)

    # Título em Bebas Neue
    title_font = _font(68)
    words = title.upper().split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        try:
            if draw.textbbox((0, 0), test, font=title_font)[2] > MAX_W and line:
                lines.append(line); line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        lines.append(line)
    lines = lines[:3]

    y = 130
    for ln in lines:
        draw.text((MARGIN, y), ln, font=title_font, fill=WHITE)
        try:
            y += draw.textbbox((0, 0), "A", font=title_font)[3] + 6
        except Exception:
            y += 76

    # Separador laranja
    y += 20
    draw.rectangle([MARGIN, y, W - MARGIN, y + 3], fill=ORANGE)
    y_after_sep = y + 28

    # Descrição em texto menor — centralizada verticalmente no espaço restante
    if description:
        desc_font = _font(36)
        # Limitar a ~500 chars, cortar só em espaço
        desc = description[:500].strip()
        if len(description) > 500:
            cut = description[:500].rsplit(" ", 1)[0]
            desc = cut + "…"

        words2 = desc.split()
        dlines, dline = [], ""
        for word in words2:
            test = (dline + " " + word).strip()
            try:
                if draw.textbbox((0, 0), test, font=desc_font)[2] > MAX_W and dline:
                    dlines.append(dline); dline = word
                else:
                    dline = test
            except Exception:
                dline = test
        if dline:
            dlines.append(dline)
        dlines = dlines[:7]

        LINE_H = 48
        block_h = len(dlines) * LINE_H
        area_top = y_after_sep
        area_bot = H - LOGO_MARGIN - LOGO_SIZE - 60
        y = area_top + max(0, (area_bot - area_top - block_h) // 2)

        for ln in dlines:
            draw.text((MARGIN, y), ln, font=desc_font, fill=GRAY)
            y += LINE_H

    # Barra laranja no rodapé
    draw.rectangle([0, H - 10, W, H], fill=ORANGE)

    # Logo
    return _paste_logo(img)


def generate_post_image(news_item: dict, headline: str = "") -> Optional[str]:
    """
    Gera imagem 4:5 (1080×1350px) com imagem real do artigo + logo Morsa Digital.
    Logo e formato 4:5 são obrigatórios — sem eles o post não sai.

    Fluxo:
      1. Busca imagem real do artigo (og:image, youtube thumbnail, etc.)
      2. Processa: resize 4:5 + gradiente + logo Morsa
      3. Upload: Imgur → fallback catbox.moe
      4. Se não encontrar imagem OU upload falhar → retorna None (post pulado)
    """
    if not _pil_available():
        logger.warning("Pillow não instalado — imagem não gerada")
        return None

    title = news_item.get("title", "")
    article_url = news_item.get("url", "")

    if not article_url:
        return None

    # 1. Buscar imagem real do artigo
    img_bytes = _fetch_article_image(article_url)
    if not img_bytes:
        logger.info(f"Sem imagem real para '{title[:50]}' — post será pulado")
        return None

    base_img = _load_image_from_bytes(img_bytes)
    if not base_img:
        logger.info(f"Imagem inválida para '{title[:50]}' — post será pulado")
        return None

    logger.info("Imagem do artigo carregada com sucesso")

    # 2. Processar: resize 4:5 + gradiente + headline + logo Morsa
    display_headline = headline if headline else title
    base_img = _resize_crop_center(base_img, POST_W, POST_H)
    base_img = _add_gradient_overlay(base_img)
    base_img = _add_text_overlay(base_img, display_headline)
    final_img = _paste_logo(base_img)

    final_rgb = final_img.convert("RGB")
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=92, optimize=True)
    image_bytes = buf.getvalue()
    logger.info(f"Imagem processada: {len(image_bytes) // 1024}KB")

    # 3. Upload (Imgur → catbox.moe)
    return _upload_image(image_bytes)
