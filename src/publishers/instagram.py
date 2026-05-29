"""
Publica posts no Instagram via Meta Graph API (conta Business/Creator).
Requer: IG_USER_ID, FB_ACCESS_TOKEN

Fluxo:
  1. Gera imagem 4:5 (1080x1350) com logo Morsa Digital
  2. Sobe para Imgur (URL pública)
  3. Cria container no Instagram → publica
"""
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request

# Adicionar src ao path para importar image_generator
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"

DEFAULT_IMAGE_URL = os.environ.get(
    "IG_DEFAULT_IMAGE_URL",
    "https://via.placeholder.com/1080x1350/1a1a2e/ffffff?text=Morsa+Digital",
)


def _create_container(ig_user_id: str, token: str, caption: str, image_url: str) -> str:
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        f"{GRAPH_URL}/{ig_user_id}/media",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["id"]


def _publish_container(ig_user_id: str, token: str, container_id: str) -> str:
    params = {
        "creation_id": container_id,
        "access_token": token,
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        f"{GRAPH_URL}/{ig_user_id}/media_publish",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["id"]


def publish(post: dict) -> dict:
    """Publica imagem com legenda no Instagram."""
    ig_user_id = os.environ["IG_USER_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    caption = post["content"]
    news_item = post.get("news_item", {})

    # 1. Gerar imagem 4:5 com logo Morsa Digital
    image_url = None
    try:
        from image_generator import generate_post_image
        image_url = generate_post_image(news_item)
    except Exception as e:
        logger.warning(f"Falha ao gerar imagem: {e}")

    # 2. Fallback para imagem padrão
    if not image_url:
        image_url = os.environ.get("IG_DEFAULT_IMAGE_URL", DEFAULT_IMAGE_URL)
        logger.info(f"Usando imagem de fallback: {image_url}")

    logger.info(f"Imagem para Instagram: {image_url}")

    # 3. Criar container e publicar
    container_id = _create_container(ig_user_id, token, caption, image_url)
    logger.info(f"Container IG criado: {container_id} — aguardando processamento...")
    time.sleep(8)  # API precisa de alguns segundos para processar a imagem

    media_id = _publish_container(ig_user_id, token, container_id)
    logger.info(f"Instagram post publicado: {media_id}")
    return {"platform": "instagram", "id": media_id}
