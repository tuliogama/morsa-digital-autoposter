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

LOGO_SIZE    = 120   # px — logo redondinha
LOGO_MARGIN  = 30    # distância das bordas

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
    """Cola a logo redondinha no canto inferior direito."""
    logo = _round_logo(logo_size)
    x = base_img.width - logo_size - margin
    y = base_img.height - logo_size - margin
    base_rgba = base_img.convert("RGBA")
    base_rgba.paste(logo, (x, y), logo)
    return base_rgba


def _create_branded_background(title: str = "") -> "Image":
    """Cria fundo branded (preto + diagonal laranja) quando não há imagem."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (POST_W, POST_H), (*COLOR_DARK, 255))
    draw = ImageDraw.Draw(img)

    # Diagonal laranja no topo direito
    draw.polygon(
        [(POST_W * 0.45, 0), (POST_W, 0), (POST_W, POST_H * 0.55)],
        fill=(*COLOR_ORANGE, 220)
    )

    # Linha laranja sutil
    draw.line([(0, POST_H - 180), (POST_W, POST_H - 180)],
              fill=(*COLOR_ORANGE, 80), width=2)

    # Título centralizado se fornecido
    if title:
        font_size = 72
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",          # Ubuntu/Linux
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",   # Ubuntu alt
            "/System/Library/Fonts/Helvetica.ttc",                            # macOS
            "/System/Library/Fonts/Arial Bold.ttf",                           # macOS alt
            "/Library/Fonts/Arial Bold.ttf",
        ]
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue

        margin_x = 80
        max_w = POST_W - margin_x * 2
        words = title.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if font:
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] > max_w and line:
                    lines.append(line)
                    line = word
                else:
                    line = test
            else:
                line = test
        if line:
            lines.append(line)

        total_h = len(lines) * (font_size + 16)
        y = (POST_H - total_h) // 2
        for ln in lines:
            if font:
                bbox = draw.textbbox((0, 0), ln, font=font)
                x = (POST_W - (bbox[2] - bbox[0])) // 2
            else:
                x = margin_x
            draw.text((x, y), ln, fill=COLOR_WHITE, font=font)
            y += font_size + 16

    return img


# ---------------------------------------------------------------------------
# Download de imagens de artigos
# ---------------------------------------------------------------------------

def _fetch_article_image(url: str) -> Optional[bytes]:
    """Tenta baixar a og:image do artigo."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # og:image
        import re
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
        if m:
            img_url = m.group(1)
            if not img_url.startswith("http"):
                img_url = urllib.parse.urljoin(url, img_url)
            req2 = urllib.request.Request(img_url, headers=HEADERS)
            with urllib.request.urlopen(req2, timeout=10) as r:
                return r.read()
    except Exception as e:
        logger.debug(f"Não conseguiu imagem de {url}: {e}")
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

IMGUR_CLIENT_ID = "546c25a59c58ad7"  # Client-ID público padrão do Imgur


def _upload_to_imgur(image_bytes: bytes) -> Optional[str]:
    """Sobe a imagem pro Imgur e retorna a URL pública."""
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
    except Exception as e:
        logger.warning(f"Falha upload Imgur: {e}")
    return None


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def generate_post_image(news_item: dict) -> Optional[str]:
    """
    Gera imagem 4:5 (1080x1350) com:
      - Imagem do artigo (ou fundo branded)
      - Gradiente escuro na parte inferior
      - Logo Morsa Digital redondinha no canto inferior direito

    Retorna URL pública da imagem ou None em caso de falha.
    """
    if not _pil_available():
        logger.warning("Pillow não instalado — imagem não gerada")
        return None

    from PIL import Image

    title = news_item.get("title", "")
    article_url = news_item.get("url", "")

    # 1. Tentar obter imagem do artigo
    base_img = None
    if article_url:
        img_bytes = _fetch_article_image(article_url)
        if img_bytes:
            base_img = _load_image_from_bytes(img_bytes)

    # 2. Se não encontrou imagem → fundo branded
    if base_img is None:
        logger.info("Sem imagem do artigo — usando fundo branded Morsa")
        base_img = _create_branded_background(title)
    else:
        # Redimensionar/recortar para 4:5
        base_img = _resize_crop_center(base_img, POST_W, POST_H)

    # 3. Gradiente escuro na parte inferior
    base_img = _add_gradient_overlay(base_img)

    # 4. Logo redondinha no canto inferior direito
    final_img = _paste_logo(base_img)

    # 5. Converter para RGB e salvar em bytes
    final_rgb = final_img.convert("RGB")
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=92, optimize=True)
    image_bytes = buf.getvalue()

    logger.info(f"Imagem gerada: {len(image_bytes) // 1024}KB")

    # 6. Upload para Imgur
    public_url = _upload_to_imgur(image_bytes)
    if public_url:
        logger.info(f"Imagem publicada: {public_url}")
    else:
        logger.warning("Falha no upload — usando IG_DEFAULT_IMAGE_URL como fallback")

    return public_url
