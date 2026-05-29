"""
Publica tweets usando a Twitter API v2 (OAuth 1.0a User Context).
Requer: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
"""
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import base64
import secrets

logger = logging.getLogger(__name__)

TWEET_URL = "https://api.twitter.com/2/tweets"


def _oauth1_header(method: str, url: str, params: dict) -> str:
    api_key = os.environ["TWITTER_API_KEY"]
    api_secret = os.environ["TWITTER_API_SECRET"]
    access_token = os.environ["TWITTER_ACCESS_TOKEN"]
    access_secret = os.environ["TWITTER_ACCESS_SECRET"]

    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    all_params = {**params, **oauth_params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )

    base_str = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])

    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature

    header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return header


def publish(post: dict) -> dict:
    """Publica um tweet. Trunca automaticamente para 280 chars."""
    text = post["content"]
    url = post.get("url", "")

    # Adiciona URL se couber (Twitter conta ~23 chars por URL)
    if url and len(text) + 24 <= 280:
        text = f"{text}\n\n{url}"
    elif len(text) > 280:
        text = text[:277] + "..."

    body = json.dumps({"text": text}).encode("utf-8")
    auth_header = _oauth1_header("POST", TWEET_URL, {})

    req = urllib.request.Request(
        TWEET_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        tweet_id = result["data"]["id"]
        logger.info(f"Tweet publicado: {tweet_id}")
        return {"platform": "twitter", "id": tweet_id, "url": f"https://x.com/i/web/status/{tweet_id}"}
