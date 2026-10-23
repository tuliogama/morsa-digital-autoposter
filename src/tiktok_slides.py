"""
Carrossel de 5 ou 6 imagens para o TikTok (desde 23/10/2026).

Os posts de foto saíam com 2 imagens (arte + "segue o Morsa") e tinham 2 ou 3
curtidas a cada 50 views. Análises de 2025-26 apontam 5 a 6 imagens como o ponto
forte do carrossel em conta pequena, e menos de 3 rende menos. Aqui a notícia vira
uma sequência:

  1. capa: a arte do post (título + logo), como no Instagram
  2-4. a notícia contada em partes, uma ideia por imagem, texto grande
  5. a pergunta da legenda em destaque ("X ou Y?"), para puxar comentário
  6. "segue o Morsa"

O fundo dos slides de texto é a própria arte, desfocada e escurecida, para o
carrossel ter a cara da notícia. Tudo com Pillow; a fonte Montserrat (licença OFL)
fica em assets/fonts.
"""
import io
import re
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent.parent
FONT = ROOT / "assets" / "fonts" / "Montserrat.ttf"
W, H = 1080, 1350
ORANGE = (255, 107, 0)
WHITE = (255, 255, 255)
MAX_TEXT_SLIDES = 3


def _font(size: int, weight: str = "Bold"):
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _background(cover: Image.Image) -> Image.Image:
    bg = cover.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(38))
    return Image.blend(bg, Image.new("RGB", (W, H), (8, 8, 10)), 0.62)


def _logo(img: Image.Image) -> Image.Image:
    try:
        from image_generator import _paste_logo
        return _paste_logo(img)
    except Exception:
        return img


def _text_slide(bg: Image.Image, text: str, label: str, page: str, big: bool = False) -> Image.Image:
    img = bg.copy()
    d = ImageDraw.Draw(img)
    d.text((80, 96), label, font=_font(30, "ExtraBold"), fill=ORANGE)
    d.rectangle((80, 142, 160, 148), fill=ORANGE)
    for size in ((78, 70, 62, 56) if big else (60, 54, 48, 44)):
        font = _font(size, "ExtraBold" if big else "Bold")
        lines = _wrap(d, text, font, W - 160)
        lh = int(size * 1.28)
        if len(lines) * lh <= H - 420:
            break
    top = (H - len(lines) * lh) // 2
    for i, line in enumerate(lines):
        d.text((80, top + i * lh), line, font=font, fill=WHITE)
    d.text((80, H - 110), page, font=_font(30, "SemiBold"), fill=(200, 200, 200))
    return _logo(img)


def _split_caption(caption: str) -> tuple[list[str], str | None]:
    """Corpo em blocos (até 3) e a pergunta final. Ignora hashtag, crédito e linha vazia."""
    lines = [l.strip() for l in (caption or "").splitlines()]
    lines = [l for l in lines if l and not l.startswith("#") and not re.match(r"^(Vídeo|Imagem|Foto):", l)]
    if not lines:
        return [], None
    question = next((l for l in reversed(lines) if l.endswith("?")), None)
    body = [l for l in lines[1:] if l != question]           # a 1ª linha já está na capa
    sentences = []
    for block in body:
        sentences += [s.strip() for s in re.split(r"(?<=[.!])\s+", block) if s.strip()]
    chunks, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) > 190 and cur:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    if len(chunks) > MAX_TEXT_SLIDES:                         # junta o excesso no último
        chunks = chunks[:MAX_TEXT_SLIDES - 1] + [" ".join(chunks[MAX_TEXT_SLIDES - 1:])]
        if len(chunks[-1]) > 320:
            chunks[-1] = chunks[-1][:317].rsplit(" ", 1)[0] + "..."
    return chunks, question


def _load(src) -> Image.Image:
    if isinstance(src, (bytes, bytearray)):
        return Image.open(io.BytesIO(src))
    with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
        return Image.open(io.BytesIO(r.read()))


def build(cover_src, caption: str, cta_src=None) -> list[bytes]:
    """
    Monta o carrossel. `cover_src` é a arte do post (URL ou bytes); `cta_src`, o slide
    "segue o Morsa" já pronto (opcional). Devolve JPEGs, de 4 a 6 imagens.
    """
    cover = _load(cover_src).convert("RGB")
    chunks, question = _split_caption(caption)
    bg = _background(cover)
    total = 1 + len(chunks) + (1 if question else 0) + 1
    slides = [cover.resize((W, int(cover.height * W / cover.width)))]
    for i, chunk in enumerate(chunks):
        slides.append(_text_slide(bg, chunk, "ENTENDA", f"{i + 2}/{total}"))
    if question:
        slides.append(_text_slide(bg, question, "E VOCÊ?", "Responde nos comentários", big=True))
    if cta_src is not None:
        slides.append(_load(cta_src).convert("RGB"))
    else:
        slides.append(_text_slide(bg, "Segue o Morsa pra não perder nada de cultura pop", "MORSA DIGITAL",
                                  "@morsadigital", big=True))
    out = []
    for s in slides:
        buf = io.BytesIO()
        s.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
        out.append(buf.getvalue())
    return out
