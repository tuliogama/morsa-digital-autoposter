"""
Gerador de carrosseis editoriais para @morsadigital.

Tipos de carrossel:
  - "top_n"      : Top N itens de uma categoria (ex: "Top 5 animes de 2026")
  - "deep_dive"  : Tudo sobre uma franquia/notícia grande
  - "event_recap": Resumo de um evento (Summer Game Fest, Comic-Con, etc.)

Formato: 1080x1080px (quadrado) — melhor para carrossel no Instagram.
Slides: capa + 3-6 slides de conteúdo + slide de CTA final.
"""
import io
import logging
import os
import textwrap
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Dimensões 4:5 — padrão do feed do Instagram (mesmo dos posts normais)
SLIDE_W = 1080
SLIDE_H = 1350

# Cores Morsa Digital
COLOR_ORANGE = (255, 107, 0)
COLOR_BLACK  = (0, 0, 0)
COLOR_WHITE  = (255, 255, 255)
COLOR_DARK   = (12, 12, 12)
COLOR_GRAY   = (40, 40, 40)
COLOR_LIGHT_GRAY = (160, 160, 160)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_PATH  = ASSETS_DIR / "morsa_logo.png"

HEADERS = {"User-Agent": "MorsaDigital-Autoposter/1.0"}


def _load_pil():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    return Image, ImageDraw, ImageFont, ImageFilter


def _get_font(font_name: str, size: int):
    from PIL import ImageFont
    fonts_dir = ASSETS_DIR / "fonts"
    candidates = [
        fonts_dir / f"{font_name}.ttf",
        fonts_dir / f"{font_name}.otf",
        fonts_dir / "BebasNeue-Regular.ttf",
        fonts_dir / "BebasNeue.ttf",          # nome real no repo
        Path("/System/Library/Fonts/HelveticaNeue.ttc"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                pass
    # Último recurso — default bitmap (vai ficar pequeníssimo, mas não quebra)
    return ImageFont.load_default(size=size)


def _round_logo(size: int = 80):
    """Retorna logo circular."""
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((size, size))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size-1, size-1), fill=255)
        logo.putalpha(mask)
        return logo
    except Exception:
        return None


def _fetch_image(url: str, target_size: tuple) -> Optional[object]:
    """Baixa imagem da URL e redimensiona para target_size com crop central."""
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        tw, th = target_size
        # Crop proporcional
        iw, ih = img.size
        scale = max(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - tw) // 2
        y = int((nh - th) * 0.35)  # bias superior para rostos
        return img.crop((x, y, x + tw, y + th))
    except Exception as e:
        logger.warning(f"Falha ao baixar imagem {url}: {e}")
        return None


def _draw_slide_base(dark: bool = True) -> tuple:
    """Retorna (Image, Draw) com fundo escuro ou claro."""
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    color = COLOR_DARK if dark else COLOR_GRAY
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), color)
    draw = ImageDraw.Draw(img)
    return img, draw


def _add_logo_watermark(img, corner: str = "bottom-right", size: int = 70):
    """Adiciona logo Morsa no canto especificado."""
    logo = _round_logo(size)
    if not logo:
        return img
    margin = 28
    if corner == "bottom-right":
        x, y = SLIDE_W - size - margin, SLIDE_H - size - margin
    elif corner == "bottom-left":
        x, y = margin, SLIDE_H - size - margin
    elif corner == "top-right":
        x, y = SLIDE_W - size - margin, margin
    else:
        x, y = margin, margin
    img.paste(logo, (x, y), logo)
    return img


def _add_progress_bar(draw, current: int, total: int):
    """Barra de progresso laranja no topo."""
    bar_h = 5
    bar_w = int(SLIDE_W * (current / total))
    draw.rectangle([0, 0, bar_w, bar_h], fill=COLOR_ORANGE)
    draw.rectangle([bar_w, 0, SLIDE_W, bar_h], fill=COLOR_GRAY)


def _wrap_text(text: str, font, draw, max_width: int) -> list:
    """Quebra texto para caber em max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Slides individuais
# ---------------------------------------------------------------------------

def make_cover_slide(title: str, subtitle: str, category_tag: str,
                     image_url: str = None) -> object:
    """
    Slide de capa: fundo escuro com acento laranja + título grande centralizado.
    """
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    img, draw = _draw_slide_base(dark=True)

    # Imagem de fundo se disponível
    if image_url:
        bg = _fetch_image(image_url, (SLIDE_W, SLIDE_H))
        if bg:
            dark_overlay = Image.new("RGB", (SLIDE_W, SLIDE_H), COLOR_BLACK)
            img = Image.blend(bg, dark_overlay, alpha=0.62)
            draw = ImageDraw.Draw(img)

    margin = 56
    max_w = SLIDE_W - margin * 2

    # Barra laranja no topo (grossa)
    draw.rectangle([0, 0, SLIDE_W, 10], fill=COLOR_ORANGE)

    # Bloco laranja lateral esquerdo (detalhe visual)
    draw.rectangle([0, 0, 10, SLIDE_H], fill=COLOR_ORANGE)

    # Tag de categoria — no topo
    tag_font = _get_font("BebasNeue-Regular", 34)
    tag_text = f"  {category_tag.upper()}  "
    tag_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = tag_bbox[3] - tag_bbox[1]
    tag_x = margin
    tag_y = 40
    draw.rectangle([tag_x, tag_y, tag_x + tag_w, tag_y + tag_h + 10], fill=COLOR_ORANGE)
    draw.text((tag_x, tag_y + 4), tag_text, font=tag_font, fill=COLOR_WHITE)

    # Linha separadora laranja
    sep_y = tag_y + tag_h + 28
    draw.rectangle([margin, sep_y, SLIDE_W - margin, sep_y + 3], fill=COLOR_ORANGE)

    # Título principal — grande e centralizado verticalmente
    title_font = _get_font("BebasNeue-Regular", 96)
    title_text = title.upper()
    lines = _wrap_text(title_text, title_font, draw, max_w)

    # Calcular altura total do bloco de título
    line_h = 106
    block_h = len(lines[:4]) * line_h
    y_start = (SLIDE_H - block_h) // 2 - 40  # levemente acima do centro

    for line in lines[:4]:
        draw.text((margin, y_start), line, font=title_font, fill=COLOR_WHITE)
        y_start += line_h

    # Subtítulo abaixo do título
    if subtitle:
        sub_font = _get_font("BebasNeue-Regular", 38)
        sub_lines = _wrap_text(subtitle, sub_font, draw, max_w)
        y_sub = y_start + 20
        for line in sub_lines[:2]:
            draw.text((margin, y_sub), line, font=sub_font, fill=COLOR_LIGHT_GRAY)
            y_sub += 46

    # Handle @morsadigital no rodapé
    handle_font = _get_font("BebasNeue-Regular", 32)
    handle_text = "@morsadigital"
    draw.text((margin, SLIDE_H - 70), handle_text, font=handle_font, fill=COLOR_ORANGE)

    # Logo
    img = _add_logo_watermark(img, "bottom-right", size=80)

    return img


def make_content_slide(number: int, total: int, headline: str,
                       body: str, image_url: str = None) -> object:
    """
    Slide de conteúdo numerado.
    Layout: número grande laranja + headline + corpo de texto.
    """
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    img, draw = _draw_slide_base(dark=True)

    # Imagem de fundo sutil se disponível
    if image_url:
        bg = _fetch_image(image_url, (SLIDE_W, SLIDE_H))
        if bg:
            dark_overlay = Image.new("RGB", (SLIDE_W, SLIDE_H), COLOR_BLACK)
            img = Image.blend(bg, dark_overlay, alpha=0.78)
            draw = ImageDraw.Draw(img)

    margin = 56
    max_w = SLIDE_W - margin * 2

    # Barra de progresso no topo
    _add_progress_bar(draw, number, total)

    # Bloco laranja lateral (consistência visual com a capa)
    draw.rectangle([0, 0, 10, SLIDE_H], fill=COLOR_ORANGE)

    # Número grande no canto superior — marca visual forte
    num_font = _get_font("BebasNeue-Regular", 200)
    num_str = str(number)
    # Transparente — serve como elemento gráfico de fundo
    num_bbox = draw.textbbox((0, 0), num_str, font=num_font)
    num_w = num_bbox[2] - num_bbox[0]
    # Posicionar no canto superior direito como elemento decorativo
    draw.text((SLIDE_W - num_w - 20, -20), num_str, font=num_font,
              fill=(255, 107, 0, 60))  # laranja bem transparente

    # Linha separadora laranja no terço superior
    line_y = 200
    draw.rectangle([margin, line_y, SLIDE_W - margin, line_y + 4], fill=COLOR_ORANGE)

    # Headline do slide — grande e impactante
    head_font = _get_font("BebasNeue-Regular", 72)
    head_lines = _wrap_text(headline.upper(), head_font, draw, max_w)
    y_cur = 50
    for line in head_lines[:2]:
        draw.text((margin, y_cur), line, font=head_font, fill=COLOR_WHITE)
        y_cur += 80
    y_cur = line_y + 28

    # Corpo do texto — fonte menor, cinza claro
    body_font = _get_font("BebasNeue-Regular", 40)
    body_lines = _wrap_text(body, body_font, draw, max_w)
    for line in body_lines[:7]:
        draw.text((margin, y_cur), line, font=body_font, fill=COLOR_LIGHT_GRAY)
        y_cur += 50

    # Número pequeno no rodapé (legível)
    count_font = _get_font("BebasNeue-Regular", 28)
    draw.text((margin, SLIDE_H - 55), f"{number} de {total}", font=count_font, fill=COLOR_ORANGE)

    # Logo pequena
    img = _add_logo_watermark(img, "bottom-right", size=65)

    return img


def make_cta_slide(handle: str = "@morsadigital",
                   cta_text: str = "Salva pra não esquecer 🔖",
                   secondary: str = "Segue pra não perder nada do universo nerd") -> object:
    """
    Último slide: CTA + branding Morsa.
    """
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    img, draw = _draw_slide_base(dark=True)

    # Acento laranja no topo
    draw.rectangle([0, 0, SLIDE_W, 8], fill=COLOR_ORANGE)

    # Logo centralizada grande
    logo = _round_logo(160)
    if logo:
        lx = (SLIDE_W - 160) // 2
        ly = 180
        img.paste(logo, (lx, ly), logo)

    # Handle
    handle_font = _get_font("BebasNeue-Regular", 52)
    handle_bbox = draw.textbbox((0, 0), handle, font=handle_font)
    handle_x = (SLIDE_W - (handle_bbox[2] - handle_bbox[0])) // 2
    draw.text((handle_x, 370), handle, font=handle_font, fill=COLOR_ORANGE)

    # CTA principal
    cta_font = _get_font("BebasNeue-Regular", 66)
    margin = 80
    cta_lines = _wrap_text(cta_text, cta_font, draw, SLIDE_W - margin * 2)
    y_cur = 500
    for line in cta_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=cta_font)
        x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_cur), line, font=cta_font, fill=COLOR_WHITE)
        y_cur += 76

    # Texto secundário
    sec_font = _get_font("BebasNeue-Regular", 36)
    sec_lines = _wrap_text(secondary, sec_font, draw, SLIDE_W - margin * 2)
    y_cur += 20
    for line in sec_lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=sec_font)
        x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_cur), line, font=sec_font, fill=COLOR_LIGHT_GRAY)
        y_cur += 44

    # Linha laranja inferior
    draw.rectangle([0, SLIDE_H - 8, SLIDE_W, SLIDE_H], fill=COLOR_ORANGE)

    return img


# ---------------------------------------------------------------------------
# Geração completa do carrossel
# ---------------------------------------------------------------------------

def generate_carousel(carousel_data: dict) -> list:
    """
    Gera todos os slides de um carrossel editorial.

    carousel_data = {
        "title": "Top 5 Games Mais Esperados de 2026",
        "subtitle": "O que a gente não pode perder esse ano",
        "category_tag": "Games",
        "cover_image_url": "https://...",
        "items": [
            {
                "headline": "God of War: Laufey",
                "body": "Santa Monica Studio confirmou...",
                "image_url": "https://..."  # opcional
            },
            ...
        ],
        "cta_text": "Salva pra não esquecer 🔖",
        "cta_secondary": "Qual você tá mais ansioso? Comenta aí"
    }

    Retorna: lista de bytes (JPEG) de cada slide.
    """
    slides_imgs = []

    # Slide de capa
    cover = make_cover_slide(
        title=carousel_data["title"],
        subtitle=carousel_data.get("subtitle", ""),
        category_tag=carousel_data.get("category_tag", "Editorial"),
        image_url=carousel_data.get("cover_image_url"),
    )
    slides_imgs.append(cover)

    # Slides de conteúdo
    items = carousel_data.get("items", [])
    for i, item in enumerate(items, 1):
        slide = make_content_slide(
            number=i,
            total=len(items),
            headline=item["headline"],
            body=item["body"],
            image_url=item.get("image_url"),
        )
        slides_imgs.append(slide)

    # Slide CTA
    cta = make_cta_slide(
        cta_text=carousel_data.get("cta_text", "Salva pra não esquecer 🔖"),
        secondary=carousel_data.get("cta_secondary", "Segue pra não perder nada"),
    )
    slides_imgs.append(cta)

    # Converter para bytes JPEG
    slides_bytes = []
    for img in slides_imgs:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        slides_bytes.append(buf.getvalue())

    logger.info(f"Carrossel gerado: {len(slides_bytes)} slides")
    return slides_bytes
