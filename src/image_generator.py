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
    """Adiciona gradiente escuro na parte inferior para facilitar leitura."""
    from PIL import Image, ImageDraw

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    grad_h = int(img.height * 0.40)
    y_start = img.height - grad_h

    for y in range(grad_h):
        alpha = int(200 * (y / grad_h))
        draw.line([(0, y_start + y), (img.width, y_start + y)],
                  fill=(0, 0, 0, alpha))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


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
    """Carrega fonte bold disponível no sistema."""
    from PIL import ImageFont
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
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
    """Redimensiona e recorta mantendo proporção, centralizando."""
    from PIL import Image
    src_ratio = img.width / img.height
    tgt_ratio = target_w / target_h

    if src_ratio > tgt_ratio:
        # imagem mais larga — ajustar pela altura
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


# ---------------------------------------------------------------------------
# Upload para Imgur (gratuito, sem autenticação)
# ---------------------------------------------------------------------------

IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID", "546c25a59c58ad7")


def _upload_to_imgur(image_bytes: bytes, retries: int = 2) -> Optional[str]:
    """Sobe a imagem pro Imgur com retry. Client-ID via env var IMGUR_CLIENT_ID."""
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
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            if result.get("success"):
                return result["data"]["link"]
            logger.warning(f"Imgur retornou sucesso=false: {result}")
        except Exception as e:
            logger.warning(f"Imgur tentativa {attempt+1}/{retries+1} falhou: {e}")
            if attempt < retries:
                import time; time.sleep(2)
    return None


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def _extract_direct_image_url(article_url: str) -> Optional[str]:
    """
    Extrai a URL direta da og:image do artigo sem fazer download.
    Usada como fallback quando o upload para Imgur falha.
    """
    import re
    if not article_url or "reddit.com" in article_url:
        return None
    try:
        req = urllib.request.Request(article_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(100_000).decode("utf-8", errors="replace")
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
                if img_url.startswith("http"):
                    return img_url
    except Exception:
        pass
    return None


def generate_post_image(news_item: dict) -> Optional[str]:
    """
    Gera imagem 4:5 (1080x1350) com imagem real do artigo + logo Morsa.
    Fluxo:
      1. Busca imagem do artigo
      2. Processa (resize 4:5 + gradiente + logo) e sobe para Imgur
      3. Se Imgur falhar por rate limit → usa URL direta do og:image (sem logo)
    Retorna None apenas se não houver nenhuma imagem real disponível.
    """
    title = news_item.get("title", "")
    article_url = news_item.get("url", "")

    if not article_url:
        return None

    # YouTube: URL direta do thumbnail (sem precisar de upload)
    if "youtube.com" in article_url or "youtu.be" in article_url:
        import re
        for pat in [r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})',
                    r'youtube\.com/embed/([A-Za-z0-9_-]{11})']:
            m = re.search(pat, article_url)
            if m:
                thumb = f"https://img.youtube.com/vi/{m.group(1)}/maxresdefault.jpg"
                logger.info(f"YouTube thumbnail direto: {thumb[:60]}")
                return thumb

    if not _pil_available():
        # Sem Pillow: tenta URL direta do og:image
        direct = _extract_direct_image_url(article_url)
        if direct:
            logger.info(f"Pillow indisponível — usando og:image direta: {direct[:60]}")
        return direct

    from PIL import Image

    # 1. Buscar imagem do artigo
    img_bytes = _fetch_article_image(article_url)
    if not img_bytes:
        logger.info(f"Sem imagem real para '{title[:50]}' — post será pulado")
        return None

    base_img = _load_image_from_bytes(img_bytes)
    if not base_img:
        logger.info(f"Imagem corrompida para '{title[:50]}' — post será pulado")
        return None

    logger.info("Imagem do artigo carregada com sucesso")

    # 2. Processar: resize 4:5 + gradiente + logo
    base_img = _resize_crop_center(base_img, POST_W, POST_H)
    base_img = _add_gradient_overlay(base_img)
    final_img = _paste_logo(base_img)

    final_rgb = final_img.convert("RGB")
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=92, optimize=True)
    image_bytes = buf.getvalue()
    logger.info(f"Imagem gerada: {len(image_bytes) // 1024}KB")

    # 3. Upload para Imgur
    public_url = _upload_to_imgur(image_bytes)
    if public_url:
        logger.info(f"Imagem publicada no Imgur: {public_url}")
        return public_url

    # 4. Imgur falhou (rate limit / erro) → usar URL direta do og:image como fallback
    logger.warning("Imgur indisponível — usando URL direta do og:image como fallback")
    direct = _extract_direct_image_url(article_url)
    if direct:
        logger.info(f"Fallback og:image: {direct[:60]}")
        return direct

    logger.info(f"Sem URL de imagem disponível para '{title[:50]}' — post será pulado")
    return None
