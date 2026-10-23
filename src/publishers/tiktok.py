"""
Publicação no TikTok do @morsadigital via Zernio (antigo Late).

Por que não a API oficial direto: app próprio não auditado só publica em modo
privado, e o TikTok recusa na auditoria ferramentas de uso interno ("utilitário
que sobe conteúdo para contas suas ou do seu time"). A Zernio já tem app
auditado; a conta do TikTok é conectada lá e daqui só chamamos a API dela.

Ativa quando existe ZERNIO_API_KEY. Sem a chave, tudo aqui é no-op.
"""
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BASE_URL = "https://zernio.com/api/v1"


def enabled() -> bool:
    return bool(os.environ.get("ZERNIO_API_KEY"))


def _api(method: str, path: str, body: dict = None) -> dict:
    req = urllib.request.Request(
        BASE_URL + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}",
                 "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Zernio {method} {path}: HTTP {e.code} {e.read().decode()[:300]}")


def account_id() -> str:
    """ID da conta TikTok conectada (TIKTOK_ACCOUNT_ID, ou a primeira ativa)."""
    if os.environ.get("TIKTOK_ACCOUNT_ID"):
        return os.environ["TIKTOK_ACCOUNT_ID"]
    accounts = [a for a in _api("GET", "/accounts").get("accounts", [])
                if a.get("platform") == "tiktok" and a.get("isActive", True)]
    if not accounts:
        raise RuntimeError("nenhuma conta TikTok conectada na Zernio")
    return accounts[0]["_id"]


def _cap(caption: str) -> str:
    from publishers.instagram import cap_hashtags
    return cap_hashtags(caption)


def post_video(video_url: str, caption: str, scheduled_for: str = None, wait: bool = True) -> dict:
    """
    Publica (ou agenda, com `scheduled_for` em ISO 8601) um vídeo público.
    Devolve {"id", "status", "url"}; com wait=True espera o TikTok processar.
    """
    body = {
        "content": _cap(caption)[:2200],
        "mediaItems": [{"type": "video", "url": video_url}],
        "platforms": [{"platform": "tiktok", "accountId": account_id()}],
        "tiktokSettings": {
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "allow_comment": True, "allow_duet": True, "allow_stitch": True,
            "content_preview_confirmed": True, "express_consent_given": True,
        },
    }
    if scheduled_for:
        body.update(scheduledFor=scheduled_for, timezone="America/Sao_Paulo")
    else:
        body["publishNow"] = True
    post = _api("POST", "/posts", body).get("post", {})
    result = {"id": post.get("_id"), "status": post.get("status"), "url": None}
    if scheduled_for or not wait or not result["id"]:
        return result

    for _ in range(30):                       # até ~5 min
        time.sleep(10)
        post = _api("GET", f"/posts/{result['id']}").get("post", {})
        result["status"] = post.get("status")
        if result["status"] in ("published", "failed", "partial"):
            entry = next((p for p in post.get("platforms", []) if p.get("platform") == "tiktok"), {})
            result["url"] = entry.get("platformPostUrl")
            if result["status"] != "published":
                raise RuntimeError(f"TikTok recusou o post: {json.dumps(entry)[:300]}")
            return result
    return result


def post_photos(image_urls: list[str], caption: str, scheduled_for: str = None) -> dict:
    """
    Post de FOTO no TikTok (carrossel de imagens, com música sugerida pelo TikTok).
    Desde 14/10/2026: os vídeos repostados caíram em "conteúdo não original" e o
    TikTok passou a recomendar foto ao Morsa; a notícia estática é arte nossa.
    `content` vira o título (90 caracteres, sem hashtag); a legenda inteira vai em
    `description`.
    """
    # Imgur devolve "conteúdo indisponível na sua região" para o servidor da Zernio
    # (22/10/2026: os dois posts da CCXP saíram assim). Imagem fora do GitHub é
    # rehospedada na Release pública antes de ir para o TikTok.
    import hashlib
    key = "x" + hashlib.md5("".join(image_urls).encode()).hexdigest()[:10]
    # Carrossel de 5 ou 6 imagens (desde 23/10/2026): capa, a notícia em partes, a
    # pergunta em destaque e "segue o Morsa". Com 2 imagens a foto tinha 2 ou 3
    # curtidas a cada 50 views. Se a montagem falhar, vai como antes.
    if os.environ.get("TIKTOK_CAROUSEL", "on") != "off":
        try:
            import tiktok_slides
            from tiktok_photos import host_bytes
            slides = tiktok_slides.build(image_urls[0], caption, image_urls[1] if len(image_urls) > 1 else None)
            image_urls = host_bytes(slides, key)
        except Exception as e:
            logger.warning(f"Carrossel não montou ({str(e)[:150]}); vai com as imagens do post")
    if any("github" not in u for u in image_urls):
        from tiktok_photos import _host
        image_urls = _host(image_urls, key)
    caption = _cap(caption)
    title = re.sub(r"#\w+", "", caption.split("\n")[0]).strip()[:90]
    body = {
        "content": title,
        "mediaItems": [{"type": "image", "url": u} for u in image_urls[:35]],
        "platforms": [{"platform": "tiktok", "accountId": account_id()}],
        "tiktokSettings": {
            "privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True,
            "media_type": "photo", "photo_cover_index": 0,
            "description": caption[:4000], "auto_add_music": True,
            "content_preview_confirmed": True, "express_consent_given": True,
        },
    }
    if scheduled_for:
        body.update(scheduledFor=scheduled_for, timezone="America/Sao_Paulo")
    else:
        body["publishNow"] = True
    post = _api("POST", "/posts", body).get("post", {})
    return {"id": post.get("_id"), "status": post.get("status")}
