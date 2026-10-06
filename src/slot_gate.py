"""
Portão de horários do feed: decide se há um post de feed "devido" agora.

O cron do GitHub Actions atrasa horas (o das 22h BRT chegava ~04h) e o watchdog
disparava runs extras, então saíam 5 posts/dia em horários aleatórios. Aqui a
regra é uma só, para qualquer gatilho: publica se o número de slots já vencidos
hoje (BRT) for maior que o número de posts de feed já publicados hoje.

Só stdlib: roda no runner antes do pip install.
Saída: "due=true|false" em $GITHUB_OUTPUT (se existir) e exit 0.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
SLOTS_BRT = [int(h) for h in os.environ.get("FEED_SLOTS_BRT", "11,16,21").split(",")]
MIN_GAP_MIN = int(os.environ.get("FEED_MIN_GAP_MIN", "90"))


def fetch_recent_media(limit: int = 15) -> list[dict]:
    token = os.environ["FB_ACCESS_TOKEN"]
    ig_user_id = os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
           f"?fields=timestamp,media_type&limit={limit}&access_token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read()).get("data", [])


def decide(media: list[dict], now: datetime) -> tuple[bool, str]:
    feed_times = sorted(
        (datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(BRT)
         for m in media if m.get("media_type") != "VIDEO"),
        reverse=True,
    )
    posted_today = sum(1 for t in feed_times if t.date() == now.date())
    slots_due = sum(1 for h in SLOTS_BRT if now.hour >= h)
    state = f"{now:%H:%M} BRT | slots vencidos: {slots_due} | feed hoje: {posted_today}"

    if posted_today >= slots_due:
        return False, f"{state} → nada devido"
    if feed_times:
        gap = (now - feed_times[0]).total_seconds() / 60
        if gap < MIN_GAP_MIN:
            return False, f"{state} → último post há {gap:.0f} min (mínimo {MIN_GAP_MIN})"
    return True, f"{state} → post devido"


def main():
    try:
        due, reason = decide(fetch_recent_media(), datetime.now(BRT))
    except Exception as e:
        # Sem leitura do Instagram não dá para garantir que não vai duplicar
        due, reason = False, f"falha ao consultar o Instagram ({e}) → não publica"
    print(reason)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"due={'true' if due else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
