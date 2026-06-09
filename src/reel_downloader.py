"""
Reel Downloader — busca trailers oficiais no YouTube e processa para Instagram.

Lógica:
  - Busca trailer PT-BR dublado/legendado no YouTube
  - Verifica se existe versão vertical nativa (Shorts 9:16)
  - Se tem vertical → retorna (horizontal, vertical) = 2 posts
  - Se não tem → retorna só (horizontal,) = 1 post
  - Adiciona logo Morsa redondinha (top-right, opacidade 55%, zona segura)
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_SIZE   = 70   # px
LOGO_ALPHA  = 0.55 # opacidade
LOGO_TOP    = 130  # px do topo — abaixo do header do Instagram


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _make_round_logo(size: int = LOGO_SIZE) -> Path:
    """Gera PNG da logo redondinha com opacidade para uso no ffmpeg."""
    from PIL import Image, ImageDraw

    logo_path = ASSETS_DIR / "morsa_logo.png"
    out_path  = Path(tempfile.gettempdir()) / f"morsa_logo_round_{size}.png"

    if out_path.exists():
        return out_path

    logo = Image.open(logo_path).convert("RGBA").resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)

    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(logo, (0, 0), mask)

    r, g, b, a = output.split()
    a = a.point(lambda x: int(x * LOGO_ALPHA))
    Image.merge("RGBA", (r, g, b, a)).save(str(out_path))

    return out_path


def _ytdlp(*args) -> subprocess.CompletedProcess:
    """Executa yt-dlp com cookies do Chrome."""
    cmd = ["yt-dlp", "--cookies-from-browser", "chrome", "--no-playlist"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _search_youtube(query: str, max_results: int = 5, max_age_days: int = 90) -> list[dict]:
    """
    Busca vídeos no YouTube filtrando por recência.
    max_age_days: ignora vídeos mais antigos que isso (padrão 90 dias).
    """
    import json
    from datetime import datetime, timedelta

    result = _ytdlp(
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--skip-download",
    )

    cutoff = datetime.now() - timedelta(days=max_age_days)
    videos = []
    for line in result.stdout.splitlines():
        try:
            v = json.loads(line)
            date_str = v.get("upload_date", "")

            # Filtra por data de upload
            if date_str:
                try:
                    upload_date = datetime.strptime(date_str, "%Y%m%d")
                    if upload_date < cutoff:
                        logger.info(f"Vídeo ignorado (muito antigo: {date_str}): {v.get('title','')[:50]}")
                        continue
                except Exception:
                    pass

            videos.append({
                "id":       v["id"],
                "title":    v.get("title", ""),
                "channel":  v.get("uploader", ""),
                "duration": int(v.get("duration", 0)),
                "width":    v.get("width", 0),
                "height":   v.get("height", 0),
                "date":     date_str,
                "views":    v.get("view_count", 0),
            })
        except Exception:
            pass

    logger.info(f"YouTube: {len(videos)} vídeos recentes encontrados para '{query[:50]}'")
    return videos


def _is_official(channel: str) -> bool:
    """Verifica se o canal é oficial do estúdio."""
    official_keywords = [
        "warner", "sony", "marvel", "disney", "paramount", "universal",
        "netflix", "amazon", "hbo", "dc", "pixar", "20th century",
        "brasil", "brazil", "official", "oficial",
    ]
    ch = channel.lower()
    return any(k in ch for k in official_keywords)


def _build_query(news_item: dict) -> str:
    """Monta query de busca priorizando PT-BR. Usa override do backlog se disponível."""
    if news_item.get("_search_query_override"):
        return news_item["_search_query_override"]
    title = news_item.get("title", "")
    for noise in [" - IGN", " | IGN", " - Kotaku", " - GameSpot"]:
        title = title.replace(noise, "")
    return f"{title} trailer dublado português brasileiro"


def _has_vertical_format(video_id: str) -> bool:
    """Verifica se o vídeo tem formato nativo vertical (Shorts 9:16)."""
    result = _ytdlp(
        f"https://www.youtube.com/watch?v={video_id}",
        "--list-formats",
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        for part in parts:
            if "x" in part:
                try:
                    w, h = part.split("x")
                    if int(h) > int(w):  # altura > largura = vertical
                        return True
                except Exception:
                    pass
    return False


def _download_video(video_id: str, output_path: str) -> bool:
    """Baixa o vídeo em melhor qualidade disponível."""
    result = _ytdlp(
        f"https://www.youtube.com/watch?v={video_id}",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
    )
    if result.returncode != 0:
        logger.warning(f"Falha no download {video_id}: {result.stderr[-200:]}")
        return False
    return os.path.exists(output_path)


def _add_logo_horizontal(input_path: str, output_path: str, logo_path: str):
    """Processa vídeo horizontal 16:9 com logo."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", logo_path,
        "-filter_complex",
        f"[0:v][1:v]overlay=W-w-20:{LOGO_TOP}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg horizontal falhou: {r.stderr[-300:]}")


def _add_logo_vertical_native(input_path: str, output_path: str, logo_path: str):
    """Processa vídeo vertical nativo 9:16 com logo."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", logo_path,
        "-filter_complex",
        f"[0:v][1:v]overlay=W-w-20:{LOGO_TOP}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg vertical nativo falhou: {r.stderr[-300:]}")


def _make_vertical_blur(input_path: str, output_path: str, logo_path: str):
    """Converte horizontal para 9:16 com blur fill."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", logo_path,
        "-filter_complex",
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=40:6[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[composed];"
        f"[composed][1:v]overlay=W-w-20:{LOGO_TOP}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg blur fill falhou: {r.stderr[-300:]}")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def find_trailer(news_item: dict) -> dict | None:
    """
    Busca o trailer oficial no YouTube para a notícia.
    Retorna dict com metadados ou None se não encontrar.
    """
    query = _build_query(news_item)
    logger.info(f"Buscando trailer: {query}")

    videos = _search_youtube(query, max_results=5)
    if not videos:
        logger.warning("Nenhum vídeo encontrado")
        return None

    # Prioriza canais oficiais, depois por views
    official = [v for v in videos if _is_official(v["channel"])]
    candidates = official if official else videos

    # Filtra duração razoável (30s a 5min = trailer/teaser)
    candidates = [v for v in candidates if 25 <= v["duration"] <= 330]

    if not candidates:
        logger.warning("Nenhum candidato com duração válida")
        return None

    best = sorted(candidates, key=lambda v: v["views"], reverse=True)[0]
    logger.info(f"Trailer encontrado: {best['title']} ({best['channel']}, {best['duration']}s)")
    return best


def download_and_process(news_item: dict, output_dir: str = None) -> list[str]:
    """
    Busca, baixa e processa o trailer da notícia.

    Retorna lista de caminhos de vídeos processados:
      - [horizontal.mp4]              → só horizontal (sem vertical nativo)
      - [horizontal.mp4, vertical.mp4] → tem versão vertical nativa

    Retorna [] se não encontrar ou falhar.
    """
    trailer = find_trailer(news_item)
    if not trailer:
        return []

    tmp = output_dir or tempfile.mkdtemp(prefix="morsa_reel_")
    raw_path = os.path.join(tmp, f"raw_{trailer['id']}.mp4")

    # Download
    logger.info(f"Baixando {trailer['id']}...")
    if not _download_video(trailer["id"], raw_path):
        return []

    # Logo redondinha
    try:
        logo_path = str(_make_round_logo())
    except Exception as e:
        logger.error(f"Erro ao gerar logo: {e}")
        return []

    results = []

    # Versão horizontal (sempre)
    h_path = os.path.join(tmp, f"horizontal_{trailer['id']}.mp4")
    try:
        _add_logo_horizontal(raw_path, h_path, logo_path)
        results.append(h_path)
        logger.info(f"Horizontal gerado: {h_path}")
    except Exception as e:
        logger.error(f"Erro horizontal: {e}")
        return []

    # Versão vertical nativa (só se existir)
    has_vertical = _has_vertical_format(trailer["id"])
    if has_vertical:
        logger.info("Versão vertical nativa encontrada — gerando...")
        # Re-download em formato vertical
        v_raw = os.path.join(tmp, f"raw_vertical_{trailer['id']}.mp4")
        _ytdlp(
            f"https://www.youtube.com/watch?v={trailer['id']}",
            "-f", "bestvideo[width<bestvideo[height]]+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", v_raw,
        )
        if os.path.exists(v_raw):
            v_path = os.path.join(tmp, f"vertical_{trailer['id']}.mp4")
            try:
                _add_logo_vertical_native(v_raw, v_path, logo_path)
                results.append(v_path)
                logger.info(f"Vertical nativo gerado: {v_path}")
            except Exception as e:
                logger.warning(f"Vertical falhou, mantendo só horizontal: {e}")
    else:
        logger.info("Sem vertical nativo — postando só horizontal")

    # Limpa raw
    try:
        os.remove(raw_path)
    except Exception:
        pass

    return results


def is_trailer_news(news_item: dict) -> bool:
    """Verifica se a notícia é sobre trailer/teaser recém-lançado."""
    keywords = [
        "trailer", "teaser", "primeiro olhar", "first look",
        "clipe oficial", "cena inédita", "revealed", "revelado",
        "watch the", "assista", "veja o"
    ]
    title = (news_item.get("title", "") + " " + news_item.get("description", "")).lower()
    return any(k in title for k in keywords)
