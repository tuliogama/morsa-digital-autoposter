"""
release_posts.py — Sistema de posts automáticos de estreia

Dois tipos de post gerados automaticamente na data de lançamento:

1. "ESTREIA HOJE" — imagem com arte especial + legenda com sinopse e
   pergunta "você vai assistir?" Postado como feed (carousel de 1 slide ou imagem).

2. "Trailer do dia" — repost do trailer oficial no dia da estreia, com
   legenda no estilo "Hoje é o dia! Você vai assistir?". Postado como Reel.

Fluxo:
  - run_release_posts() é chamado 1x/dia pelo GitHub Actions às 09h BRT
  - Carrega release_calendar.json e verifica se hoje é a data de algum filme
  - Para cada match: gera e publica post de estreia + reel do trailer
  - Marca como postado no JSON para não repetir
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)

CALENDAR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "release_calendar.json",
)

# ---------------------------------------------------------------------------
# Carregamento do calendário
# ---------------------------------------------------------------------------

def _load_calendar() -> list:
    try:
        with open(CALENDAR_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Falha ao carregar release_calendar.json: {e}")
        return []


def _save_calendar(items: list):
    try:
        with open(CALENDAR_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Falha ao salvar release_calendar.json: {e}")


def get_releases_today(offset_days: int = 0) -> list:
    """
    Retorna filmes/séries que estreiam hoje (ou em offset_days dias).
    offset_days=0 → hoje, offset_days=1 → amanhã (para antecipação)
    """
    target = (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")
    items = _load_calendar()
    return [i for i in items if i.get("release_date") == target]


# ---------------------------------------------------------------------------
# Geração de legenda "estreia hoje"
# ---------------------------------------------------------------------------

ESTREIA_SYSTEM = """Você é o social media sênior da Morsa Digital — canal brasileiro de cultura pop/nerd/geek com 27k seguidores.

Hoje é o dia da estreia de um filme. Escreva um post para o Instagram celebrando o lançamento.

ESTRUTURA OBRIGATÓRIA:

[ABERTURA — 1 linha declarando que o filme estreia hoje. Sem emoji no início. Ex: "Toy Story 5 estreia hoje nos cinemas."]

[linha em branco]

[SINOPSE/CONTEXTO — 2 a 3 linhas. Fale do que trata o filme e por que a galera BR vai se emocionar/hype. Use os dados fornecidos.]

[linha em branco]

[PERGUNTA DE ENGAJAMENTO — 1 linha. "Você vai assistir hoje?" / "Já tem ingresso?" / "Sala marcada?" / "Você está preparado?". Varie o CTA.]

[linha em branco]

#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6

REGRAS:
- Tom: fã empolgado, não robô corporativo
- NUNCA INVENTE FATOS — use apenas os dados fornecidos
- Mencione o nome do filme na primeira linha
- Hashtags: nome do filme + franquia + atores + #Estreia + #Cinema (ou #Streaming se for plataforma)
- Máximo 2200 caracteres"""

TRAILER_DIA_SYSTEM = """Você é o social media sênior da Morsa Digital — canal brasileiro de cultura pop/nerd/geek.

O trailer deste filme está sendo repostado NO DIA DA ESTREIA. Escreva a legenda do Reel.

ESTRUTURA OBRIGATÓRIA:

[REAÇÃO — 1 linha. "Hoje é o dia." ou "Chegou a hora." ou nome do filme + "está nos cinemas agora." Sem emoji no início.]

[linha em branco]

[HYPE — 2 linhas. Por que esse filme é especial. O que a galera mais esperava. Use os dados fornecidos.]

[linha em branco]

[CTA ENGAJAMENTO — 1 linha. "Você vai assistir hoje?" / "Já está na fila?" / "Conta nos comentários se vai hoje!"]

[linha em branco]

#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6

REGRAS:
- Tom: celebração, como um fã que está ansioso para o dia chegar
- NUNCA INVENTE FATOS — use apenas os dados fornecidos
- Máximo 2200 caracteres"""


def _generate_estreia_caption(item: dict) -> str:
    from content_generator import _call_groq
    import re

    plataforma_texto = "nos cinemas" if item.get("plataforma") == "cinema" else f"no {item.get('plataforma', 'streaming')}"
    dt = datetime.strptime(item["release_date"], "%Y-%m-%d")
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    data_legivel = f"{dt.day} de {meses[dt.month-1]} de {dt.year}"

    user_msg = (
        f"Filme: {item['titulo']}\n"
        f"Data de estreia: {data_legivel} — HOJE\n"
        f"Plataforma: {plataforma_texto}\n"
        f"Elenco: {item.get('elenco','')}\n"
        f"Sinopse: {item.get('sinopse','')}\n"
        f"Contexto de hype: {item.get('contexto_hype','')}\n\n"
        f"Escreva o post de estreia para o Instagram."
    )

    for attempt in range(2):
        try:
            raw = _call_groq(ESTREIA_SYSTEM, user_msg, max_tokens=500)
            raw = re.sub(r'\n[ \t]*\n+', '\n\n', raw).strip()
            if len(raw) >= 80:
                return raw
        except Exception as e:
            logger.warning(f"Groq estreia caption falhou tentativa {attempt+1}: {e}")

    # fallback
    return (
        f"{item['titulo']} estreia hoje {plataforma_texto}.\n\n"
        f"{item.get('sinopse','')}\n\n"
        f"Você vai assistir?\n\n"
        f"#Estreia #Cinema #MorsaDigital"
    )


def _generate_trailer_dia_caption(item: dict) -> str:
    from content_generator import _call_groq
    import re

    plataforma_texto = "nos cinemas" if item.get("plataforma") == "cinema" else f"no {item.get('plataforma', 'streaming')}"

    user_msg = (
        f"Filme: {item['titulo']}\n"
        f"Estreia: HOJE — {plataforma_texto}\n"
        f"Elenco: {item.get('elenco','')}\n"
        f"Contexto de hype: {item.get('contexto_hype','')}\n\n"
        f"Escreva a legenda do Reel (trailer sendo repostado no dia da estreia)."
    )

    for attempt in range(2):
        try:
            raw = _call_groq(TRAILER_DIA_SYSTEM, user_msg, max_tokens=400)
            raw = re.sub(r'\n[ \t]*\n+', '\n\n', raw).strip()
            if len(raw) >= 80:
                return raw
        except Exception as e:
            logger.warning(f"Groq trailer dia caption falhou tentativa {attempt+1}: {e}")

    return (
        f"{item['titulo']} está nos cinemas agora.\n\n"
        f"{item.get('contexto_hype','O momento chegou.')}\n\n"
        f"Você vai assistir hoje?\n\n"
        f"#Estreia #Cinema #MorsaDigital"
    )


# ---------------------------------------------------------------------------
# Geração de arte "ESTREIA HOJE"
# ---------------------------------------------------------------------------

def _generate_estreia_image(item: dict) -> bytes | None:
    """
    Gera imagem 1080x1350 (4:5) com badge 'ESTREIA HOJE', título do filme,
    elenco principal e logo Morsa. Usa o mesmo pipeline do image_generator.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import urllib.request

        W, H = 1080, 1350

        # Fundo gradiente escuro (azul-marinho → preto)
        img = Image.new("RGB", (W, H), (8, 8, 20))
        draw = ImageDraw.Draw(img)

        # Gradiente manual: linhas de cima (azul escuro) para baixo (preto)
        for y in range(H):
            ratio = y / H
            r = int(8 + (30 - 8) * (1 - ratio))
            g = int(8 + (20 - 8) * (1 - ratio))
            b = int(20 + (60 - 20) * (1 - ratio))
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Badge "ESTREIA HOJE"
        badge_text = "ESTREIA HOJE"
        try:
            font_badge = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        except Exception:
            font_badge = ImageFont.load_default()

        badge_w = draw.textlength(badge_text, font=font_badge) + 60
        badge_h = 70
        badge_x = (W - badge_w) // 2
        badge_y = 180

        # Fundo do badge (laranja Morsa)
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=10, fill=(255, 102, 0)
        )
        draw.text(
            (badge_x + 30, badge_y + 10),
            badge_text, font=font_badge, fill=(255, 255, 255)
        )

        # Título do filme
        titulo = item["titulo"].upper()
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
        except Exception:
            font_title = ImageFont.load_default()

        # Quebra linha se necessário
        words = titulo.split()
        lines = []
        current = ""
        for w in words:
            test = (current + " " + w).strip()
            if draw.textlength(test, font=font_title) < W - 80:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

        title_y = 310
        for line in lines:
            tw = draw.textlength(line, font=font_title)
            draw.text(((W - tw) // 2, title_y), line, font=font_title, fill=(255, 255, 255))
            title_y += 95

        # Elenco
        elenco = item.get("elenco", "")
        if elenco:
            try:
                font_cast = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
            except Exception:
                font_cast = ImageFont.load_default()
            cast_y = title_y + 20
            # Quebra em 2 linhas se longo
            if draw.textlength(elenco, font=font_cast) > W - 80:
                nomes = elenco.split(", ")
                mid = len(nomes) // 2
                l1 = ", ".join(nomes[:mid])
                l2 = ", ".join(nomes[mid:])
                for l in [l1, l2]:
                    lw = draw.textlength(l, font=font_cast)
                    draw.text(((W - lw) // 2, cast_y), l, font=font_cast, fill=(200, 200, 200))
                    cast_y += 50
            else:
                lw = draw.textlength(elenco, font=font_cast)
                draw.text(((W - lw) // 2, cast_y), elenco, font=font_cast, fill=(200, 200, 200))

        # Linha separadora
        draw.line([(80, H - 250), (W - 80, H - 250)], fill=(255, 102, 0), width=2)

        # Plataforma
        plataforma = item.get("plataforma", "cinema").upper()
        if plataforma == "CINEMA":
            plat_text = "NOS CINEMAS"
        else:
            plat_text = f"NO {plataforma}"
        try:
            font_plat = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
        except Exception:
            font_plat = ImageFont.load_default()
        pw = draw.textlength(plat_text, font=font_plat)
        draw.text(((W - pw) // 2, H - 220), plat_text, font=font_plat, fill=(255, 102, 0))

        # Logo Morsa
        from image_generator import _round_logo, _paste_logo
        img = img.convert("RGBA")
        _paste_logo(img, logo_size=90)
        img = img.convert("RGB")

        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    except Exception as e:
        logger.error(f"Erro ao gerar arte de estreia: {e}")
        return None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run_release_posts(dry_run: bool = False) -> list:
    """
    Verifica se hoje tem estreia no calendário e publica:
    1. Post de feed "ESTREIA HOJE" (imagem com arte)
    2. Reel "trailer do dia" (repost do trailer com legenda de estreia)

    Retorna lista de resultados publicados.
    """
    from posts_log import is_duplicate, record_post

    releases = get_releases_today()
    if not releases:
        logger.info("Sem estreias hoje.")
        return []

    logger.info(f"{len(releases)} estreia(s) hoje: {[r['titulo'] for r in releases]}")

    calendar = _load_calendar()
    results = []

    for item in releases:
        titulo = item["titulo"]
        item_id = item["id"]

        # ── 1. Post de feed "ESTREIA HOJE" ──────────────────────────────────
        if not item.get("postado_estreia", False):
            if is_duplicate(titulo + "_estreia_hoje", platform="instagram", lookback_days=1):
                logger.info(f"Post de estreia já publicado: {titulo}")
            else:
                logger.info(f"Gerando post de estreia: {titulo}")
                caption = _generate_estreia_caption(item)
                logger.info(f"Legenda: {caption[:120]}...")

                if not dry_run:
                    try:
                        image_bytes = _generate_estreia_image(item)
                        if image_bytes:
                            from image_generator import _upload_image
                            from publishers.instagram import publish_image
                            cdn_url = _upload_image(image_bytes)
                            if cdn_url:
                                result = publish_image(cdn_url, caption)
                                record_post(
                                    media_id=result.get("id", ""),
                                    platform="instagram",
                                    news_item={
                                        "title": f"{titulo} — ESTREIA HOJE",
                                        "source": "release_calendar",
                                        "url": "",
                                    },
                                    caption=caption,
                                    image_url=cdn_url,
                                )
                                # Marca no calendário
                                for cal_item in calendar:
                                    if cal_item["id"] == item_id:
                                        cal_item["postado_estreia"] = True
                                results.append({"tipo": "estreia_feed", "titulo": titulo, "result": result})
                                logger.info(f"✅ Post de estreia publicado: {titulo}")
                    except Exception as e:
                        logger.error(f"Erro ao publicar post de estreia ({titulo}): {e}")
                else:
                    logger.info(f"[DRY RUN] Post de estreia: {titulo}")
                    logger.info(f"[DRY RUN] Legenda:\n{caption}")

        # ── 2. Reel "trailer do dia" ─────────────────────────────────────────
        if not item.get("postado_trailer_dia", False):
            if is_duplicate(titulo + "_trailer_dia", platform="instagram_reel", lookback_days=1):
                logger.info(f"Reel do trailer do dia já publicado: {titulo}")
            else:
                logger.info(f"Gerando Reel do trailer do dia: {titulo}")
                trailer_caption = _generate_trailer_dia_caption(item)

                # Monta news_item para reel_downloader
                news_item = {
                    "title": titulo,
                    "source": "release_calendar",
                    "url": "",
                    "contexto": item.get("contexto_hype", ""),
                    "elenco": item.get("elenco", ""),
                    "ano": item.get("release_date", "")[:4],
                    "data_estreia": item.get("release_date", ""),
                    "_status_calculado": "em_cartaz",  # é o dia da estreia
                    "_search_query_override": item.get("query_youtube_trailer", ""),
                }

                if not dry_run:
                    try:
                        from reel_downloader import download_and_process
                        from publishers.instagram import publish_video_reel

                        video_paths = download_and_process(news_item)
                        if video_paths:
                            result = publish_video_reel(video_paths[0], trailer_caption)
                            record_post(
                                media_id=result.get("id", ""),
                                platform="instagram_reel",
                                news_item={
                                    "title": f"{titulo} — Trailer do Dia da Estreia",
                                    "source": "release_calendar",
                                    "url": "",
                                },
                                caption=trailer_caption,
                                image_url="",
                            )
                            for cal_item in calendar:
                                if cal_item["id"] == item_id:
                                    cal_item["postado_trailer_dia"] = True
                            results.append({"tipo": "trailer_dia_reel", "titulo": titulo, "result": result})
                            logger.info(f"✅ Reel do trailer do dia publicado: {titulo}")
                        else:
                            logger.warning(f"Não encontrou trailer para: {titulo}")
                    except Exception as e:
                        logger.error(f"Erro ao publicar Reel do dia ({titulo}): {e}")
                else:
                    logger.info(f"[DRY RUN] Reel do trailer do dia: {titulo}")
                    logger.info(f"[DRY RUN] Legenda:\n{trailer_caption}")

    _save_calendar(calendar)
    return results


# ---------------------------------------------------------------------------
# Preview (mostra o que seria publicado hoje ou em N dias)
# ---------------------------------------------------------------------------

def preview_upcoming(days: int = 30):
    """Lista as próximas estreias e o que seria publicado."""
    from datetime import datetime, timedelta
    hoje = datetime.now()
    items = _load_calendar()
    print(f"\nPróximas estreias (hoje + {days} dias):\n")
    for item in sorted(items, key=lambda x: x.get("release_date", "")):
        try:
            dt = datetime.strptime(item["release_date"], "%Y-%m-%d")
        except Exception:
            continue
        delta = (dt - hoje).days
        if -1 <= delta <= days:
            status_estreia = "✅ já postado" if item.get("postado_estreia") else "🔲 pendente"
            status_trailer = "✅ já postado" if item.get("postado_trailer_dia") else "🔲 pendente"
            print(f"  {item['release_date']} ({delta:+d}d) | {item['titulo']}")
            print(f"    Post estreia: {status_estreia} | Reel trailer: {status_trailer}")
            print()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"

    if mode == "preview":
        preview_upcoming(days=200)
    elif mode == "dry-run":
        run_release_posts(dry_run=True)
    elif mode == "run":
        results = run_release_posts(dry_run=False)
        print(f"\nPublicados: {len(results)}")
        for r in results:
            print(f"  {r['tipo']}: {r['titulo']}")
    else:
        print("Uso: python release_posts.py [preview|dry-run|run]")
