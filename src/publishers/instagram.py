"""
Publica posts no Instagram via Meta Graph API (conta Business/Creator).
Requer: IG_USER_ID, FB_ACCESS_TOKEN

Formatos suportados:
  - Feed (imagem única) — publish()
  - Carrossel editorial  — publish_carousel()
  - Reel (vídeo 9:16)    — publish_reel()

Fluxo feed:
  1. Gera imagem 4:5 (1080x1350) com logo Morsa Digital
  2. Sobe para Imgur (URL pública)
  3. Cria container → publica no Feed
  4. Posta nos Stories + comunidade Clã do Morsa

Fluxo carrossel:
  1. Gera slides via carousel_generator.py
  2. Sobe cada slide para Imgur
  3. Cria child containers (is_carousel_item=true)
  4. Cria container pai (media_type=CAROUSEL)
  5. Publica

Fluxo reel:
  1. Gera vídeo MP4 via reel_generator.py
  2. Faz upload do vídeo (resumable) via Meta API
  3. Cria container (media_type=REELS)
  4. Publica
"""
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"


class NoImageError(Exception):
    """Lançada quando não há imagem real disponível para o post."""


def _post(url: str, params: dict) -> dict:
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _create_container(ig_user_id: str, token: str, caption: str, image_url: str) -> str:
    params = {
        "image_url": image_url,
        "caption": caption,
        "like_and_view_counts_disabled": "true",
        "access_token": token,
    }
    # Cross-post para Facebook se pages_manage_posts estiver disponível
    fb_page_id = os.environ.get("FB_PAGE_ID", "")
    if fb_page_id:
        params["publish_to_facebook"] = "true"
        params["facebook_page_id"] = fb_page_id
    result = _post(f"{GRAPH_URL}/{ig_user_id}/media", params)
    return result["id"]


def _publish_container(ig_user_id: str, token: str, container_id: str) -> str:
    result = _post(f"{GRAPH_URL}/{ig_user_id}/media_publish", {
        "creation_id": container_id,
        "access_token": token,
    })
    return result["id"]


def _disable_like_count(media_id: str, token: str) -> bool:
    """
    Tenta desabilitar contagem de likes pós-publicação.
    Requer instagram_manage_comments — falha silenciosamente se não disponível.
    """
    try:
        result = _post(f"{GRAPH_URL}/{media_id}", {
            "like_and_view_counts_disabled": "true",
            "access_token": token,
        })
        return result.get("success", False)
    except Exception as e:
        logger.debug(f"like_count disable pós-publicação indisponível: {e}")
        return False


def _post_to_stories(ig_user_id: str, token: str, feed_media_id: str) -> Optional[str]:
    """
    Compartilha o post do feed nos Stories (card do feed, não imagem avulsa).
    Requer instagram_content_publish (já temos).
    """
    try:
        container_id = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
            "media_type": "STORIES",
            "source_type": "FEED_MEDIA",
            "source_media_id": feed_media_id,
            "access_token": token,
        })["id"]

        time.sleep(5)

        story_id = _publish_container(ig_user_id, token, container_id)
        logger.info(f"Story (reshare do feed) publicado: {story_id}")
        return story_id
    except Exception as e:
        logger.warning(f"Falha ao compartilhar feed post no Story: {e}")
        return None


def _post_to_broadcast_channel(token: str, media_id: str) -> bool:
    """
    Compartilha o post no canal de transmissão (comunidade) do Instagram.
    Requer MORSA_BROADCAST_CHANNEL_ID no environment.
    """
    channel_id = os.environ.get("MORSA_BROADCAST_CHANNEL_ID", "")
    if not channel_id:
        logger.debug("MORSA_BROADCAST_CHANNEL_ID não configurado — comunidade ignorada")
        return False

    try:
        result = _post(f"{GRAPH_URL}/{channel_id}/messages", {
            "message_type": "SHARED_POST",
            "media_id": media_id,
            "access_token": token,
        })
        success = bool(result.get("id") or result.get("success"))
        if success:
            logger.info(f"Post compartilhado na comunidade Clã do Morsa")
        return success
    except Exception as e:
        logger.warning(f"Falha ao compartilhar na comunidade: {e}")
        return False


def _get_broadcast_channel_id(ig_user_id: str, token: str) -> Optional[str]:
    """
    Busca o ID do canal de transmissão "Clã do Morsa".
    Usar para descobrir o MORSA_BROADCAST_CHANNEL_ID pela primeira vez.
    """
    try:
        url = f"{GRAPH_URL}/{ig_user_id}/broadcast_channels?access_token={token}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        channels = data.get("data", [])
        for ch in channels:
            logger.info(f"Canal encontrado: id={ch.get('id')} name={ch.get('name')}")
        return channels[0]["id"] if channels else None
    except Exception as e:
        logger.warning(f"Falha ao listar canais de transmissão: {e}")
        return None


def publish(post: dict) -> dict:
    """
    Publica no Instagram como carrossel de 2 slides:
      Slide 1: imagem com título, gradiente e logo (formato feed padrão)
      Slide 2: fundo escuro + logo no canto inferior direito (assinatura)

    Lança NoImageError se não conseguir gerar a imagem principal.
    """
    ig_user_id = os.environ["IG_USER_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    caption = post["content"]
    news_item = post.get("news_item", {})

    # 1. Gerar par de imagens (slide 1 = feed normal, slide 2 = imagem limpa + logo)
    image_url = None
    slide2_url = None
    image_headline = post.get("image_headline", news_item.get("title", ""))
    try:
        from image_generator import generate_post_image_pair
        image_url, slide2_url = generate_post_image_pair(news_item, headline=image_headline)
    except Exception as e:
        logger.warning(f"Falha ao gerar imagens: {e}")

    if not image_url:
        raise NoImageError(f"Sem imagem real para: {news_item.get('title', '')[:60]}")

    logger.info(f"Slide 1: {image_url}")
    if slide2_url:
        logger.info(f"Slide 2 (imagem limpa): {slide2_url}")

    # 2. Publicar como carrossel (2 slides) ou fallback para imagem simples
    if slide2_url:
        # Criar child containers
        slide_urls = [image_url, slide2_url]
        child_ids = []
        for url in slide_urls:
            result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": token,
            })
            child_ids.append(result["id"])
            time.sleep(2)

        logger.info(f"Child containers criados: {child_ids}")

        # Criar container pai CAROUSEL
        carousel_result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "like_and_view_counts_disabled": "true",
            "access_token": token,
        })
        container_id = carousel_result["id"]
        logger.info(f"Container CAROUSEL criado: {container_id}")
    else:
        # Fallback: imagem simples se o slide de logo falhou
        container_id = _create_container(ig_user_id, token, caption, image_url)
        logger.info(f"Container IMAGE criado (fallback): {container_id}")

    time.sleep(8)

    # 4. Publicar
    media_id = _publish_container(ig_user_id, token, container_id)
    logger.info(f"Instagram feed publicado: {media_id}")

    # 5. Desabilitar contagem de likes
    time.sleep(3)
    if _disable_like_count(media_id, token):
        logger.info("Contagem de likes desabilitada")

    # 6. Compartilhar nos Stories
    time.sleep(3)
    _post_to_stories(ig_user_id, token, media_id)

    # 7. Compartilhar na comunidade Clã do Morsa
    time.sleep(2)
    _post_to_broadcast_channel(token, media_id)

    # 8. Registrar no log persistente
    try:
        from posts_log import record_post
        record_post(media_id, "instagram", news_item, caption, image_url=image_url)
    except Exception as e:
        logger.warning(f"Falha ao registrar no posts_log: {e}")

    return {"platform": "instagram", "id": media_id, "image_url": image_url}


# ---------------------------------------------------------------------------
# Publicação de Carrossel Editorial
# ---------------------------------------------------------------------------

def publish_carousel(carousel_data: dict, caption: str) -> dict:
    """
    Publica carrossel de múltiplos slides no Instagram.

    carousel_data: dict no formato de carousel_generator.generate_carousel()
    caption: legenda completa do carrossel (gerada pelo content_generator)

    Fluxo Meta API:
      1. Gera slides (PIL)
      2. Faz upload de cada slide para Imgur
      3. Cria child containers (is_carousel_item=true)
      4. Cria container pai CAROUSEL com lista de children
      5. Publica
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    ig_user_id = os.environ["IG_USER_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    # 1. Gerar slides
    from carousel_generator import generate_carousel
    slides_bytes = generate_carousel(carousel_data)

    if len(slides_bytes) < 2:
        raise ValueError("Carrossel precisa de ao menos 2 slides")

    # Limitar a 10 slides (limite da API do Instagram)
    slides_bytes = slides_bytes[:10]

    # 2. Upload de cada slide para Imgur
    from image_generator import _upload_image
    slide_urls = []
    for i, slide_bytes in enumerate(slides_bytes):
        url = _upload_image(slide_bytes)
        if not url:
            logger.warning(f"Falha no upload do slide {i+1} — pulando")
            continue
        slide_urls.append(url)
        logger.info(f"Slide {i+1}/{len(slides_bytes)} enviado: {url}")
        time.sleep(1)

    if len(slide_urls) < 2:
        raise NoImageError("Upload de slides falhou — não há slides suficientes")

    # 3. Criar child containers
    child_ids = []
    for url in slide_urls:
        result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": token,
        })
        child_ids.append(result["id"])
        logger.info(f"Child container criado: {result['id']}")
        time.sleep(2)

    # 4. Criar container pai CAROUSEL
    carousel_result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "like_and_view_counts_disabled": "true",
        "access_token": token,
    })
    carousel_container_id = carousel_result["id"]
    logger.info(f"Container CAROUSEL criado: {carousel_container_id}")

    # 5. Publicar
    time.sleep(10)
    media_id = _publish_container(ig_user_id, token, carousel_container_id)
    logger.info(f"Carrossel publicado: {media_id}")

    # Stories + comunidade
    time.sleep(3)
    _post_to_stories(ig_user_id, token, media_id)
    time.sleep(2)
    _post_to_broadcast_channel(token, media_id)

    # Registrar
    try:
        from posts_log import record_post
        record_post(media_id, "instagram_carousel",
                    {"title": carousel_data.get("title", "Carrossel")},
                    caption, image_url=slide_urls[0] if slide_urls else "")
    except Exception as e:
        logger.warning(f"Falha ao registrar no posts_log: {e}")

    return {
        "platform": "instagram",
        "format": "carousel",
        "id": media_id,
        "slides": len(slide_urls),
    }


# ---------------------------------------------------------------------------
# Publicação de Reel (vídeo 9:16)
# ---------------------------------------------------------------------------

def _upload_video_to_meta(video_path: str, ig_user_id: str, token: str) -> str:
    """
    Upload de vídeo para Meta usando upload resumível.
    Retorna video_url (path no servidor Meta) para criar o container.
    """
    file_size = os.path.getsize(video_path)

    # 1. Iniciar sessão de upload
    init_result = _post(
        f"https://rupload.facebook.com/video-upload/v19.0/{ig_user_id}/videos",
        {
            "upload_phase": "start",
            "file_size": str(file_size),
            "access_token": token,
        }
    )
    upload_session_id = init_result.get("upload_session_id") or init_result.get("id")
    if not upload_session_id:
        raise ValueError(f"Falha ao iniciar upload: {init_result}")

    # 2. Transferir arquivo
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_url = f"https://rupload.facebook.com/video-upload/v19.0/{upload_session_id}"
    req = urllib.request.Request(
        upload_url,
        data=video_data,
        method="POST",
        headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        upload_result = json.loads(r.read())

    logger.info(f"Vídeo enviado: {upload_result}")
    return upload_session_id


def publish_reel(reel_data: dict, caption: str) -> dict:
    """
    Gera e publica um Reel no Instagram.

    reel_data = {
        "slides": [
            {"image_url": "https://...", "text": "Headline da notícia"},
            ...
        ],
        "title": "Top anúncios da semana"
    }
    caption: legenda do reel (gerada pelo content_generator)
    """
    import tempfile, sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    ig_user_id = os.environ["IG_USER_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    slides = reel_data.get("slides", [])
    if len(slides) < 3:
        raise ValueError("Reel precisa de ao menos 3 slides")

    # 1. Gerar vídeo com ffmpeg
    from reel_generator import generate_reel
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        video_path = tmp.name

    try:
        success = generate_reel(slides, video_path)
        if not success or not os.path.exists(video_path):
            raise ValueError("Falha ao gerar vídeo do reel")

        file_size = os.path.getsize(video_path)
        logger.info(f"Vídeo gerado: {video_path} ({file_size//1024}KB)")

        # 2. Fazer upload do vídeo para o servidor Meta
        upload_session_id = _upload_video_to_meta(video_path, ig_user_id, token)

        # 3. Criar container REELS
        container_result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
            "media_type": "REELS",
            "upload_id": upload_session_id,
            "caption": caption,
            "share_to_feed": "true",
            "like_and_view_counts_disabled": "true",
            "access_token": token,
        })
        container_id = container_result["id"]
        logger.info(f"Container REELS criado: {container_id}")

        # 4. Aguardar processamento do vídeo (poll status)
        for attempt in range(12):  # máx 2 minutos
            time.sleep(10)
            status_url = (
                f"{GRAPH_URL}/{container_id}"
                f"?fields=status_code,status&access_token={token}"
            )
            with urllib.request.urlopen(status_url, timeout=15) as r:
                status = json.loads(r.read())
            code = status.get("status_code", "")
            logger.info(f"Status do vídeo ({attempt+1}/12): {code}")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise ValueError(f"Erro no processamento do vídeo: {status}")

        # 5. Publicar
        media_id = _publish_container(ig_user_id, token, container_id)
        logger.info(f"Reel publicado: {media_id}")

        # Comunidade
        time.sleep(3)
        _post_to_broadcast_channel(token, media_id)

        # Registrar
        try:
            from posts_log import record_post
            record_post(media_id, "instagram_reel",
                        {"title": reel_data.get("title", "Reel")},
                        caption, image_url="")
        except Exception as e:
            logger.warning(f"Falha ao registrar no posts_log: {e}")

        return {
            "platform": "instagram",
            "format": "reel",
            "id": media_id,
        }

    finally:
        if os.path.exists(video_path):
            os.unlink(video_path)
