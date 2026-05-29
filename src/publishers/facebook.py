"""
Publica posts no Facebook via Graph API.
Requer: FB_PAGE_ID, FB_ACCESS_TOKEN (Page Access Token com pages_manage_posts)
"""
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"


def publish(post: dict) -> dict:
    """Publica post na Page do Facebook."""
    page_id = os.environ["FB_PAGE_ID"]
    token = os.environ["FB_ACCESS_TOKEN"]

    text = post["content"]
    url = post.get("url", "")

    params = {
        "message": text,
        "access_token": token,
    }
    if url:
        params["link"] = url

    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        f"{GRAPH_URL}/{page_id}/feed",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        post_id = result["id"]
        logger.info(f"Facebook post publicado: {post_id}")
        return {"platform": "facebook", "id": post_id}
