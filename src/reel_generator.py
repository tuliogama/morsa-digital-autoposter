"""
Gerador de Reels para @morsadigital usando ffmpeg.

Formato: 1080x1920px (9:16 vertical), 15-30 segundos.
Cada imagem de notícia aparece por 5 segundos com texto overlay.
Transição: crossfade suave entre slides.

Reels performam significativamente melhor que posts estáticos no algoritmo Instagram.
"""
import io
import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REEL_W = 1080
REEL_H = 1920
SLIDE_DURATION = 5   # segundos por slide
FADE_DURATION  = 0.5 # segundos de crossfade
MAX_SLIDES     = 5   # máximo de imagens por reel
MIN_SLIDES     = 3   # mínimo aceitável

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_PATH  = ASSETS_DIR / "morsa_logo.png"
FONTS_DIR  = ASSETS_DIR / "fonts"

HEADERS = {"User-Agent": "MorsaDigital-Autoposter/1.0"}

# Cor laranja em hex para ffmpeg
ORANGE_HEX = "FF6B00"
WHITE_HEX  = "FFFFFF"
BLACK_HEX  = "000000"


def _find_font() -> str:
    """Retorna caminho para BebasNeue ou fallback do sistema."""
    candidates = [
        FONTS_DIR / "BebasNeue.ttf",           # nome real no repo
        FONTS_DIR / "BebasNeue-Regular.ttf",
        Path("/System/Library/Fonts/HelveticaNeue.ttc"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ""


def _fetch_image_to_file(url: str, out_path: str) -> bool:
    """Baixa imagem e salva em arquivo temporário. Retorna True se ok."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        logger.warning(f"Falha ao baixar imagem {url}: {e}")
        return False


def _prepare_slide_image(src_path: str, out_path: str) -> bool:
    """
    Redimensiona imagem para 1080x1920 (crop central com bias superior)
    usando ffmpeg — sem PIL.
    """
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vf", (
            f"scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=increase,"
            f"crop={REEL_W}:{REEL_H}:0:'(in_h-{REEL_H})*0.3'"
        ),
        "-frames:v", "1",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    return result.returncode == 0


def _build_ffmpeg_filter(n_slides: int, font_path: str, texts: list) -> str:
    """
    Monta o filtro ffmpeg complexo para:
    - Concatenar slides com crossfade
    - Adicionar texto overlay em cada slide
    - Adicionar barra laranja no topo + logo watermark
    """
    dur = SLIDE_DURATION
    fade = FADE_DURATION

    # Escalar cada entrada para o tamanho correto
    scale_parts = []
    for i in range(n_slides):
        scale_parts.append(f"[{i}:v]scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=increase,"
                           f"crop={REEL_W}:{REEL_H},setsar=1,fps=25[v{i}]")

    # Crossfade entre slides
    xfade_parts = []
    prev_label = "v0"
    for i in range(1, n_slides):
        offset = dur * i - fade * i
        out_label = f"xf{i}" if i < n_slides - 1 else "xfinal"
        xfade_parts.append(
            f"[{prev_label}][v{i}]xfade=transition=fade:duration={fade}:offset={offset}[{out_label}]"
        )
        prev_label = out_label

    if n_slides == 1:
        prev_label = "v0"

    # Text overlays com estilo Morsa
    text_filters = []
    if font_path:
        for i, text in enumerate(texts):
            if not text:
                continue
            t_start = dur * i
            t_end = dur * (i + 1)
            # Limitar texto a 40 chars por linha, máx 2 linhas
            safe_text = text[:80].replace("'", "\\'").replace(":", "\\:").replace("\\", "\\\\")
            # Quebra em 2 linhas se > 35 chars
            if len(text) > 35:
                mid = text[:35].rfind(" ")
                if mid > 15:
                    line1 = text[:mid].replace("'", "\\'").replace(":", "\\:")
                    line2 = text[mid+1:70].replace("'", "\\'").replace(":", "\\:")
                    safe_text = line1 + "\\n" + line2

            # Box escuro atrás do texto
            text_filters.append(
                f"drawtext=font='{font_path}':text='{safe_text}':"
                f"fontsize=54:fontcolor=white:x=(w-text_w)/2:"
                f"y=h-280:line_spacing=14:"
                f"box=1:boxcolor=black@0.65:boxborderw=18:"
                f"enable='between(t,{t_start},{t_end})'"
            )

        # Tag @morsadigital no topo (sempre visível)
        handle_txt = "@morsadigital"
        text_filters.append(
            f"drawtext=font='{font_path}':text='{handle_txt}':"
            f"fontsize=38:fontcolor=white:x=(w-text_w)/2:y=60:"
            f"box=1:boxcolor=0x{ORANGE_HEX}@0.9:boxborderw=12"
        )

    # Barra laranja no topo
    bar_filter = f"drawbox=x=0:y=0:w={REEL_W}:h=8:color=#{ORANGE_HEX}:t=fill"

    # Montar filtro completo
    all_filters = scale_parts + xfade_parts
    post_filters = [bar_filter] + text_filters

    full = ",".join(filter(None, [
        ";".join(all_filters) if (scale_parts or xfade_parts) else "",
        f"[{prev_label}]" + ",".join(post_filters) + "[out]"
        if post_filters else ""
    ]))

    # Versão mais simples e robusta
    simple_scale = ";".join(scale_parts)
    simple_xfade = ";".join(xfade_parts) if xfade_parts else ""
    post = f"[{prev_label}]" + ",".join([bar_filter] + text_filters) + "[out]"

    parts = [p for p in [simple_scale, simple_xfade, post] if p]
    return ";".join(parts)


def _make_slide_with_text(image_path: str, text: str, out_path: str) -> bool:
    """
    Usa PIL para criar slide 1080x1920 com texto overlay baked in.
    Não depende de drawtext no ffmpeg.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        img = Image.open(image_path).convert("RGB")
        iw, ih = img.size
        tw, th = REEL_W, REEL_H

        # Crop central com bias superior (preservar rostos)
        scale = max(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - tw) // 2
        y = int((nh - th) * 0.3)
        img = img.crop((x, y, x + tw, y + th))

        draw = ImageDraw.Draw(img)

        # Overlay escuro no rodapé para legibilidade
        for row in range(th - 400, th):
            alpha = min(1.0, (row - (th - 400)) / 300) * 0.75
            r1, g1, b1 = img.getpixel((tw // 2, row))
            nr = int(r1 * (1 - alpha))
            ng = int(g1 * (1 - alpha))
            nb = int(b1 * (1 - alpha))
            draw.line([(0, row), (tw, row)], fill=(nr, ng, nb))

        # Barra laranja no topo
        draw.rectangle([0, 0, tw, 10], fill=(255, 107, 0))

        # Handle no topo
        handle_font_path = _find_font()
        if handle_font_path:
            try:
                hfont = ImageFont.truetype(handle_font_path, 40)
                draw.rectangle([0, 12, tw, 75], fill=(255, 107, 0, 200))
                handle = "@morsadigital"
                hbbox = draw.textbbox((0, 0), handle, font=hfont)
                hx = (tw - (hbbox[2] - hbbox[0])) // 2
                draw.text((hx, 18), handle, font=hfont, fill=(255, 255, 255))
            except Exception:
                pass

        # Texto principal no rodapé
        if text and handle_font_path:
            try:
                tfont = ImageFont.truetype(handle_font_path, 60)
                # Quebrar texto em múltiplas linhas
                words = text.split()
                lines = []
                cur = ""
                for word in words:
                    test = (cur + " " + word).strip()
                    bbox = draw.textbbox((0, 0), test, font=tfont)
                    if bbox[2] > tw - 80 and cur:
                        lines.append(cur)
                        cur = word
                    else:
                        cur = test
                if cur:
                    lines.append(cur)

                lines = lines[:3]
                total_h = len(lines) * 72
                y_text = th - total_h - 60

                for line in lines:
                    lbbox = draw.textbbox((0, 0), line, font=tfont)
                    lw = lbbox[2] - lbbox[0]
                    lx = (tw - lw) // 2
                    # Sombra
                    draw.text((lx + 2, y_text + 2), line, font=tfont, fill=(0, 0, 0))
                    draw.text((lx, y_text), line, font=tfont, fill=(255, 255, 255))
                    y_text += 72
            except Exception:
                pass

        img.save(out_path, "JPEG", quality=88)
        return True

    except Exception as e:
        logger.warning(f"PIL slide falhou: {e}")
        return False


def generate_reel(slides: list, output_path: str) -> bool:
    """
    Gera um reel MP4 a partir de uma lista de slides.

    slides = [
        {"image_url": "https://...", "text": "God of War: Laufey anunciado!"},
        {"image_url": "https://...", "text": "Marvel revela Doomsday trailer"},
        ...
    ]

    Usa PIL para texto (sem depender de drawtext no ffmpeg).
    Retorna True se gerado com sucesso.
    """
    n = min(len(slides), MAX_SLIDES)
    if n < MIN_SLIDES:
        logger.warning(f"Poucos slides para reel ({n} < {MIN_SLIDES})")
        return False

    slides = slides[:n]

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Baixar imagem + preparar slide com PIL (texto baked in)
        prepared = []
        for i, slide in enumerate(slides):
            raw_path  = os.path.join(tmpdir, f"raw_{i}.jpg")
            prep_path = os.path.join(tmpdir, f"slide_{i}.jpg")

            ok = _fetch_image_to_file(slide["image_url"], raw_path)
            if ok:
                ok = _make_slide_with_text(raw_path, slide.get("text", ""), prep_path)

            if not ok:
                _make_black_slide(prep_path)

            prepared.append(prep_path)

        n_slides = len(prepared)
        total_duration = SLIDE_DURATION * n_slides - FADE_DURATION * (n_slides - 1)

        # 2. Montar vídeo com ffmpeg — sem drawtext
        input_args = []
        for prep_path in prepared:
            input_args += ["-loop", "1", "-t", str(SLIDE_DURATION), "-i", prep_path]

        # Filtro: scale + xfade entre slides
        filter_parts = []
        for i in range(n_slides):
            filter_parts.append(
                f"[{i}:v]scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=increase,"
                f"crop={REEL_W}:{REEL_H}:0:0,setsar=1,fps=25[vs{i}]"
            )

        if n_slides == 1:
            current = "vs0"
        else:
            current = "vs0"
            for i in range(1, n_slides):
                offset = SLIDE_DURATION * i - FADE_DURATION * i
                nxt = f"xf{i}" if i < n_slides - 1 else "vout"
                filter_parts.append(
                    f"[{current}][vs{i}]xfade=transition=fade:"
                    f"duration={FADE_DURATION}:offset={offset:.2f}[{nxt}]"
                )
                current = nxt

        filter_graph = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
        ] + input_args + [
            "-filter_complex", filter_graph,
            "-map", f"[{current}]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-t", str(total_duration),
            "-r", "25",
            output_path,
        ]

        logger.info(f"Gerando reel: {n_slides} slides, {total_duration:.1f}s")
        result = subprocess.run(cmd, capture_output=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"ffmpeg falhou: {result.stderr.decode()[-400:]}")
            return False

        logger.info(f"Reel gerado: {output_path} ({os.path.getsize(output_path)//1024}KB)")
        return True


def _make_black_slide(out_path: str):
    """Cria slide preto como fallback."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:size={REEL_W}x{REEL_H}:rate=25",
        "-frames:v", "1", out_path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=15)


def _build_simple_filter(n_slides: int, font_path: str, texts: list) -> str:
    """
    Filtro ffmpeg simplificado e robusto:
    - Scale + pad cada slide para 1080x1920
    - Xfade entre slides
    - Texto overlay
    - Barra laranja
    """
    dur = SLIDE_DURATION
    fade = FADE_DURATION

    parts = []

    # Escalar cada slide
    for i in range(n_slides):
        parts.append(
            f"[{i}:v]scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=increase,"
            f"crop={REEL_W}:{REEL_H}:0:0,setsar=1,fps=25[vs{i}]"
        )

    # Xfade chain
    if n_slides == 1:
        current = "vs0"
    else:
        current = "vs0"
        for i in range(1, n_slides):
            offset = dur * i - fade * i
            nxt = f"xf{i}"
            parts.append(f"[{current}][vs{i}]xfade=transition=fade:duration={fade}:offset={offset:.2f}[{nxt}]")
            current = nxt

    # Post-processing: barra + texto
    post = []
    post.append(f"drawbox=x=0:y=0:w={REEL_W}:h=8:color=#{ORANGE_HEX}:t=fill")

    if font_path:
        # Handle sempre visível
        post.append(
            f"drawtext=fontfile='{font_path}':text='@morsadigital':"
            f"fontsize=36:fontcolor=white:x=(w-text_w)/2:y=55:"
            f"box=1:boxcolor=0x{ORANGE_HEX}@0.85:boxborderw=10"
        )
        # Texto de cada slide
        for i, text in enumerate(texts):
            if not text:
                continue
            t_start = max(0, dur * i - fade * i * 0.5)
            t_end   = dur * (i + 1) - fade * max(0, i)
            safe = text[:60].replace("'", "").replace(":", "").replace("\\", "")
            # Quebra em 2 linhas
            if len(safe) > 32:
                mid = safe[:32].rfind(" ")
                if mid > 10:
                    line1 = safe[:mid]
                    line2 = safe[mid+1:60]
                    safe = line1 + "\n" + line2
            post.append(
                f"drawtext=fontfile='{font_path}':text='{safe}':"
                f"fontsize=52:fontcolor=white:x=(w-text_w)/2:y=h-300:"
                f"line_spacing=10:"
                f"box=1:boxcolor=black@0.7:boxborderw=16:"
                f"enable='between(t\\,{t_start:.2f}\\,{t_end:.2f})'"
            )

    parts.append(f"[{current}]" + ",".join(post) + "[out]")
    return ";".join(parts)
