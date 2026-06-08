"""
Gerador de carrosseis editoriais para @morsadigital.

Design: IDÊNTICO ao feed normal (image_generator.py) — imagem de fundo,
gradiente escuro inferior, headline ALL CAPS branco centralizado, logo no canto.

Diferencial do carrossel:
  - Slide 1 (capa): tag de categoria + título do carrossel
  - Slides 2-N: imagem da notícia + headline específico + número discreto
  - Último slide: CTA puro com fundo escuro

Dimensões: 1080x1350 (4:5) — igual aos posts de feed.
"""
import io
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Reutiliza tudo do image_generator — mesmas dimensões, cores, fonte, logo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_PATH  = ASSETS_DIR / "morsa_logo.png"

POST_W = 1080
POST_H = 1350

COLOR_ORANGE     = (255, 107, 0)
COLOR_WHITE      = (255, 255, 255)
COLOR_BLACK      = (0, 0, 0)
COLOR_DARK       = (15, 15, 15)
COLOR_LIGHT_GRAY = (180, 180, 180)

LOGO_SIZE   = 140
LOGO_MARGIN = 40

HEADERS = {"User-Agent": "MorsaDigital-Autoposter/1.0"}


# ---------------------------------------------------------------------------
# Funções auxiliares (mesmas do image_generator)
# ---------------------------------------------------------------------------

def _load_font(size: int):
    from PIL import ImageFont
    bebas = ASSETS_DIR / "fonts" / "BebasNeue.ttf"
    if bebas.exists():
        try:
            return ImageFont.truetype(str(bebas), size)
        except Exception:
            pass
    for fp in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    return ImageFont.load_default(size=size)


def _round_logo(size: int = LOGO_SIZE):
    from PIL import Image, ImageDraw
    if not LOGO_PATH.exists():
        return None
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(logo, (0, 0), mask)
        return out
    except Exception:
        return None


def _paste_logo(img):
    """Cola logo no canto inferior direito com halo — idêntico ao feed."""
    from PIL import Image, ImageDraw
    logo = _round_logo(LOGO_SIZE)
    if not logo:
        return img
    halo_size = LOGO_SIZE + 16
    halo = Image.new("RGBA", (halo_size, halo_size), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((0, 0, halo_size - 1, halo_size - 1), fill=(0, 0, 0, 120))
    base = img.convert("RGBA")
    x = base.width  - LOGO_SIZE   - LOGO_MARGIN
    y = base.height - LOGO_SIZE   - LOGO_MARGIN
    base.paste(halo, (x - 8, y - 8), halo)
    base.paste(logo, (x, y), logo)
    return base


def _add_gradient(img):
    """Gradiente escuro inferior — idêntico ao feed."""
    from PIL import Image, ImageDraw
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    grad_h  = int(img.height * 0.55)
    y_start = img.height - grad_h
    for y in range(grad_h):
        t     = y / grad_h
        alpha = int(220 * (t ** 0.65))
        draw.line([(0, y_start + y), (img.width, y_start + y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _fetch_bg(url: str) -> Optional[object]:
    """Baixa imagem e retorna PIL Image 1080x1350 com crop central."""
    from PIL import Image
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        iw, ih = img.size
        scale = max(POST_W / iw, POST_H / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - POST_W) // 2
        y = int((nh - POST_H) * 0.35)
        return img.crop((x, y, x + POST_W, y + POST_H))
    except Exception as e:
        logger.warning(f"Falha ao baixar imagem de fundo: {e}")
        return None


def _draw_headline(img, text: str, font_size: int = 72,
                   bottom_offset: int = 0) -> object:
    """
    Headline ALL CAPS centralizado na parte inferior — idêntico ao feed.
    Stroke preto + texto branco.
    """
    from PIL import ImageDraw
    if not text:
        return img

    draw   = ImageDraw.Draw(img)
    font   = _load_font(font_size)
    W, H   = img.size
    MARGIN = 52
    MAX_W  = W - MARGIN * 2
    STROKE = 3
    LINE_GAP = 8
    BLOCK_BOTTOM = H - LOGO_MARGIN - LOGO_SIZE - 28 - bottom_offset

    # Quebrar em linhas
    words = text.upper().split()
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

    try:
        bb     = draw.textbbox((0, 0), "AG", font=font)
        line_h = bb[3] - bb[1]
    except Exception:
        line_h = 80

    block_h = len(lines) * line_h + (len(lines) - 1) * LINE_GAP
    y_start = BLOCK_BOTTOM - block_h

    for i, ln in enumerate(lines):
        y = y_start + i * (line_h + LINE_GAP)
        try:
            tw = draw.textbbox((0, 0), ln, font=font)[2]
        except Exception:
            tw = MAX_W
        x = (W - tw) // 2

        for dx in range(-STROKE, STROKE + 1):
            for dy in range(-STROKE, STROKE + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), ln, fill=(0, 0, 0, 220), font=font)
        draw.text((x, y), ln, fill=COLOR_WHITE, font=font)

    return img


def _draw_tag(img, tag_text: str, slide_num: int = None, total: int = None):
    """
    Tag de categoria laranja no canto superior esquerdo.
    Número de slide discreto no canto superior direito (slides de conteúdo).
    """
    from PIL import ImageDraw
    draw  = ImageDraw.Draw(img)
    font  = _load_font(28)
    W, H  = img.size
    pad   = 12

    # Tag laranja
    tag = f"  {tag_text.upper()}  "
    try:
        bb  = draw.textbbox((0, 0), tag, font=font)
        tw  = bb[2] - bb[0]
        th  = bb[3] - bb[1]
    except Exception:
        tw, th = 120, 30

    tx, ty = 40, 40
    draw.rectangle([tx, ty, tx + tw, ty + th + pad], fill=COLOR_ORANGE)
    draw.text((tx, ty + pad // 2), tag, font=font, fill=COLOR_WHITE)

    # Número do slide (discreto, canto direito)
    if slide_num is not None and total is not None:
        num_font = _load_font(26)
        num_text = f"{slide_num}/{total}"
        try:
            nb = draw.textbbox((0, 0), num_text, font=num_font)
            nw = nb[2] - nb[0]
        except Exception:
            nw = 60
        draw.text((W - nw - 44, 50), num_text, font=num_font,
                  fill=(255, 255, 255, 180))

    return img


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------

def make_cover_slide(title: str, subtitle: str, category_tag: str,
                     image_url: str = None) -> object:
    """
    Capa: igual ao post de feed com imagem de fundo (ou fundo escuro sólido),
    tag laranja no topo e título grande embaixo.
    """
    from PIL import Image

    # Fundo
    if image_url:
        bg = _fetch_bg(image_url)
    else:
        bg = None

    if bg:
        img = bg
    else:
        img = Image.new("RGB", (POST_W, POST_H), COLOR_DARK)

    # Gradiente
    img = _add_gradient(img)

    # Tag categoria + sem número (é a capa)
    img = _draw_tag(img, category_tag)

    # Título grande (fonte 80)
    img = _draw_headline(img, title, font_size=80)

    # Subtítulo menor acima do título (se houver)
    if subtitle:
        from PIL import ImageDraw
        draw     = ImageDraw.Draw(img)
        sub_font = _load_font(34)
        W, H     = img.size
        MAX_W    = W - 104
        words    = subtitle.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            try:
                w = draw.textbbox((0, 0), test, font=sub_font)[2]
                if w > MAX_W and line:
                    lines.append(line)
                    line = word
                else:
                    line = test
            except Exception:
                line = test
        if line:
            lines.append(line)

        # Posicionar acima do título principal (aprox 180px a mais de espaço)
        BLOCK_BOTTOM = H - LOGO_MARGIN - LOGO_SIZE - 28 - 180
        y_cur = BLOCK_BOTTOM - len(lines) * 42
        for ln in lines[:2]:
            try:
                tw = draw.textbbox((0, 0), ln, font=sub_font)[2]
            except Exception:
                tw = MAX_W
            x = (W - tw) // 2
            draw.text((x, y_cur), ln, fill=COLOR_LIGHT_GRAY, font=sub_font)
            y_cur += 42

    # Logo
    img = _paste_logo(img)

    return img.convert("RGB")


def make_content_slide(number: int, total: int, headline: str,
                       body: str = "", image_url: str = None,
                       category_tag: str = "") -> object:
    """
    Slide de conteúdo: igual ao post de feed.
    Imagem de fundo + gradiente + headline ALL CAPS + número discreto.
    """
    from PIL import Image

    if image_url:
        bg = _fetch_bg(image_url)
    else:
        bg = None

    if bg:
        img = bg
    else:
        img = Image.new("RGB", (POST_W, POST_H), COLOR_DARK)

    img = _add_gradient(img)

    # Tag + número
    tag = category_tag or "Editorial"
    img = _draw_tag(img, tag, slide_num=number, total=total)

    # Calcular posição do bloco inteiro (headline + body) ancorado no rodapé
    from PIL import ImageDraw
    draw      = ImageDraw.Draw(img)
    W, H      = img.size
    MAX_W     = W - 104
    ANCHOR    = H - LOGO_MARGIN - LOGO_SIZE - 28  # rodapé, acima da logo

    head_font = _load_font(72)
    sub_font  = _load_font(32)

    # Calcular altura do headline
    head_words = headline.upper().split()
    head_lines, line = [], ""
    for word in head_words:
        test = (line + " " + word).strip()
        try:
            w = draw.textbbox((0, 0), test, font=head_font)[2]
            if w > MAX_W and line:
                head_lines.append(line)
                line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        head_lines.append(line)
    head_lines = head_lines[:3]
    try:
        hh = draw.textbbox((0, 0), "AG", font=head_font)[3] - draw.textbbox((0, 0), "AG", font=head_font)[1]
    except Exception:
        hh = 80
    head_block_h = len(head_lines) * hh + (len(head_lines) - 1) * 8

    # Calcular altura do body
    body_lines = []
    if body:
        words, line = body.split(), ""
        for word in words:
            test = (line + " " + word).strip()
            try:
                w = draw.textbbox((0, 0), test, font=sub_font)[2]
                if w > MAX_W and line:
                    body_lines.append(line)
                    line = word
                else:
                    line = test
            except Exception:
                line = test
        if line:
            body_lines.append(line)
        body_lines = body_lines[:3]
    body_block_h = len(body_lines) * 40 + (8 if body_lines else 0)

    # Posicionar: body acima do headline, tudo ancorado no ANCHOR
    GAP = 16
    total_h = head_block_h + (GAP + body_block_h if body_lines else 0)
    y_head  = ANCHOR - head_block_h

    # Renderizar headline
    STROKE = 3
    for i, ln in enumerate(head_lines):
        y = y_head + i * (hh + 8)
        try:
            tw = draw.textbbox((0, 0), ln, font=head_font)[2]
        except Exception:
            tw = MAX_W
        x = (W - tw) // 2
        for dx in range(-STROKE, STROKE + 1):
            for dy in range(-STROKE, STROKE + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), ln, fill=(0, 0, 0, 220), font=head_font)
        draw.text((x, y), ln, fill=COLOR_WHITE, font=head_font)

    # Renderizar body acima do headline
    if body_lines:
        y_body = y_head - body_block_h - GAP
        for ln in body_lines:
            try:
                tw = draw.textbbox((0, 0), ln, font=sub_font)[2]
            except Exception:
                tw = MAX_W
            x = (W - tw) // 2
            draw.text((x + 2, y_body + 2), ln, fill=(0, 0, 0, 200), font=sub_font)
            draw.text((x, y_body), ln, fill=COLOR_LIGHT_GRAY, font=sub_font)
            y_body += 40

    img = _paste_logo(img)
    return img.convert("RGB")


def make_cta_slide(cta_text: str = "Salva pra não esquecer 🔖",
                   secondary: str = "Qual foi o melhor? Comenta aí") -> object:
    """
    Último slide: fundo escuro sólido + logo grande centralizada + CTA.
    """
    from PIL import Image, ImageDraw

    img  = Image.new("RGB", (POST_W, POST_H), COLOR_DARK)
    draw = ImageDraw.Draw(img)
    W, H = POST_W, POST_H

    # Barra laranja no topo
    draw.rectangle([0, 0, W, 8], fill=COLOR_ORANGE)

    # Logo centralizada grande
    logo = _round_logo(180)
    if logo:
        lx = (W - 180) // 2
        ly = int(H * 0.22)
        img.paste(logo, (lx, ly), logo)

    # Handle laranja
    handle_font = _load_font(48)
    handle      = "@morsadigital"
    try:
        hb = draw.textbbox((0, 0), handle, font=handle_font)
        hx = (W - (hb[2] - hb[0])) // 2
    except Exception:
        hx = W // 4
    draw.text((hx, int(H * 0.22) + 200), handle, font=handle_font, fill=COLOR_ORANGE)

    # CTA principal
    cta_font = _load_font(66)
    cta_lines = []
    words = cta_text.split()
    line  = ""
    MAX_W = W - 120
    for word in words:
        test = (line + " " + word).strip()
        try:
            w = draw.textbbox((0, 0), test, font=cta_font)[2]
            if w > MAX_W and line:
                cta_lines.append(line)
                line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        cta_lines.append(line)

    y_cur = int(H * 0.55)
    for ln in cta_lines[:2]:
        try:
            tw = draw.textbbox((0, 0), ln, font=cta_font)[2]
        except Exception:
            tw = MAX_W
        x = (W - tw) // 2
        draw.text((x, y_cur), ln, font=cta_font, fill=COLOR_WHITE)
        y_cur += 76

    # Secundário
    sec_font  = _load_font(36)
    sec_lines = []
    line = ""
    for word in secondary.split():
        test = (line + " " + word).strip()
        try:
            w = draw.textbbox((0, 0), test, font=sec_font)[2]
            if w > MAX_W and line:
                sec_lines.append(line)
                line = word
            else:
                line = test
        except Exception:
            line = test
    if line:
        sec_lines.append(line)

    y_cur += 16
    for ln in sec_lines[:2]:
        try:
            tw = draw.textbbox((0, 0), ln, font=sec_font)[2]
        except Exception:
            tw = MAX_W
        x = (W - tw) // 2
        draw.text((x, y_cur), ln, font=sec_font, fill=COLOR_LIGHT_GRAY)
        y_cur += 46

    # Barra laranja no rodapé
    draw.rectangle([0, H - 8, W, H], fill=COLOR_ORANGE)

    return img


# ---------------------------------------------------------------------------
# Slide de logo (usado nos posts de feed como segundo slide)
# ---------------------------------------------------------------------------

def make_logo_slide() -> object:
    """
    Slide de encerramento para posts de feed.
    Fundo escuro sólido + logo no canto inferior direito (mesma posição do feed).
    Sem texto — identidade visual limpa.
    """
    from PIL import Image
    img = Image.new("RGB", (POST_W, POST_H), COLOR_DARK)
    img = _paste_logo(img)
    return img.convert("RGB")


def make_logo_slide_bytes() -> bytes:
    """Retorna o slide de logo como bytes JPEG, pronto para upload."""
    img = make_logo_slide()
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Geração completa
# ---------------------------------------------------------------------------

def generate_carousel(carousel_data: dict) -> list:
    """
    Gera todos os slides como bytes JPEG.

    carousel_data = {
        "title": "Top 5 Anúncios da Semana",
        "subtitle": "Do Final Fantasy 7 ao Monster Hunter",
        "category_tag": "Games",
        "cover_image_url": "https://...",
        "items": [
            {"headline": "Final Fantasy 7 Revelation", "body": "...", "image_url": "..."},
            ...
        ],
        "cta_text": "Salva pra não esquecer 🔖",
        "cta_secondary": "Qual foi o melhor? Comenta aí"
    }
    """
    slides_imgs = []
    items       = carousel_data.get("items", [])
    total       = len(items)
    tag         = carousel_data.get("category_tag", "Editorial")

    # Capa
    cover = make_cover_slide(
        title        = carousel_data.get("title", ""),
        subtitle     = carousel_data.get("subtitle", ""),
        category_tag = tag,
        image_url    = carousel_data.get("cover_image_url"),
    )
    slides_imgs.append(cover)

    # Conteúdo
    for i, item in enumerate(items, 1):
        slide = make_content_slide(
            number       = i,
            total        = total,
            headline     = item.get("headline", ""),
            body         = item.get("body", ""),
            image_url    = item.get("image_url"),
            category_tag = tag,
        )
        slides_imgs.append(slide)

    # CTA
    cta = make_cta_slide(
        cta_text  = carousel_data.get("cta_text", "Salva pra não esquecer 🔖"),
        secondary = carousel_data.get("cta_secondary", "Qual foi o melhor? Comenta aí"),
    )
    slides_imgs.append(cta)

    # Converter para bytes JPEG
    result = []
    for img in slides_imgs:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        result.append(buf.getvalue())

    logger.info(f"Carrossel gerado: {len(result)} slides")
    return result
