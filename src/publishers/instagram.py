"""
Publica posts no Instagram via Meta Graph API (conta Business/Creator).
Requer: IG_USER_ID, FB_ACCESS_TOKEN, IG_IMAGE_URL (imagem pública acessível)

Fluxo: cria container → publica container (2 chamadas obrigatórias da API).
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"

# Imagem padrão do Morsa Digital (substitua por uma URL pública real)
DEFAULT_IMAGE_URL = os.environ.get(
    "IG_DEFAULT_IMAGE_URL",
    "https://via.placeholder.com/1080x1080/1a1a2e/ffffff?text=Morsa+Digital",
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
    image_url = os.environ.get("IG_DEFAULT_IMAGE_URL", DEFAULT_IMAGE_URL)

    caption = post["content"]

    container_id = _create_container(ig_user_id, token, caption, image_url)
    logger.info(f"Container IG criado: {container_id} — aguardando processamento...")
    time.sleep(5)  # API precisa de alguns segundos para processar a imagem

    media_id = _publish_container(ig_user_id, token, container_id)
    logger.info(f"Instagram post publicado: {media_id}")
    return {"platform": "instagram", "id": media_id}
