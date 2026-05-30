"""
Publica posts no Instagram via Meta Graph API (conta Business/Creator).
Requer: IG_USER_ID, FB_ACCESS_TOKEN

Fluxo por post:
  1. Gera imagem 4:5 (1080x1350) com logo Morsa Digital
  2. Sobe para Imgur (URL pública)
  3. Cria container no Instagram → publica no Feed
  4. Tenta desabilitar contagem de likes (requer instagram_manage_comments)
  5. Posta a mesma imagem nos Stories
  6. Compartilha na comunidade "Clã do Morsa" (requer MORSA_BROADCAST_CHANNEL_ID)
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
    result = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
        "image_url": image_url,
        "caption": caption,
        "like_and_view_counts_disabled": "true",
        "access_token": token,
    })
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


def _post_to_stories(ig_user_id: str, token: str, image_url: str) -> Optional[str]:
    """
    Posta a mesma imagem nos Stories do Instagram.
    Requer instagram_content_publish (já temos).
    """
    try:
        container_id = _post(f"{GRAPH_URL}/{ig_user_id}/media", {
            "image_url": image_url,
            "media_type": "STORIES",
            "access_token": token,
        })["id"]

        time.sleep(5)

        media_id = _publish_container(ig_user_id, token, container_id)
        logger.info(f"Story publicado: {media_id}")
        return media_id
    except Exception as e:
        logger.warning(f"Falha ao publicar Story: {e}")
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
    """Publica imagem com legenda no Instagram. Lança NoImageError se sem imagem real."""
    ig_user_id = os.environ["IG_USER_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    caption = post["content"]
    news_item = post.get("news_item", {})

    # 1. Gerar imagem real (sem imagem → pula o post)
    image_url = None
    try:
        from image_generator import generate_post_image
        image_url = generate_post_image(news_item)
    except Exception as e:
        logger.warning(f"Falha ao gerar imagem: {e}")

    if not image_url:
        raise NoImageError(f"Sem imagem real para: {news_item.get('title', '')[:60]}")

    logger.info(f"Imagem para Instagram: {image_url}")

    # 2. Criar container e publicar no Feed
    container_id = _create_container(ig_user_id, token, caption, image_url)
    logger.info(f"Container IG criado: {container_id} — aguardando processamento...")
    time.sleep(8)

    media_id = _publish_container(ig_user_id, token, container_id)
    logger.info(f"Instagram feed publicado: {media_id}")

    # 3. Desabilitar contagem de likes (requer instagram_manage_comments)
    time.sleep(3)
    if _disable_like_count(media_id, token):
        logger.info("Contagem de likes desabilitada via update pós-publicação")
    else:
        logger.info("like_count_disabled enviado na criação (update requer instagram_manage_comments)")

    # 4. Publicar nos Stories com a mesma imagem
    time.sleep(3)
    _post_to_stories(ig_user_id, token, image_url)

    # 5. Compartilhar na comunidade Clã do Morsa
    time.sleep(2)
    _post_to_broadcast_channel(token, media_id)

    # 6. Registrar no log persistente
    try:
        from posts_log import record_post
        record_post(media_id, "instagram", news_item, caption)
    except Exception as e:
        logger.warning(f"Falha ao registrar no posts_log: {e}")

    return {"platform": "instagram", "id": media_id, "image_url": image_url}
