"""
Revisão noturna: lê o engajamento real do Instagram, aprende o que funcionou e
ajusta a curadoria do dia seguinte.

Gera três arquivos:
  data/learned_weights.json   — ajuste de prioridade por categoria (lido por _tier)
  logs/day_brief.json         — orientação editorial de amanhã (lida pelo main.py)
  data/daily_review/AAAA-MM-DD.md — relatório legível

Nota de cada post = curtidas + comentários + salvamentos + compartilhamentos.
Alcance entra no relatório. Sem instagram_manage_insights no token, cai para
curtidas + comentários.
"""
import json
import logging
import os
import statistics
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("morsa.review")

BRT = timezone(timedelta(hours=-3))
ROOT = Path(__file__).parent.parent
WEIGHTS_PATH = ROOT / "data" / "learned_weights.json"
BRIEF_PATH = ROOT / "logs" / "day_brief.json"
REPORT_DIR = ROOT / "data" / "daily_review"

WINDOW_DAYS = 30      # janela de aprendizado
MATURE_HOURS = 20     # post mais novo que isso ainda está ganhando curtida
MIN_SAMPLE = 5        # abaixo disso a categoria não muda de prioridade
BOOST_RATIO = 1.4     # mediana ≥ 1,4× a geral → sobe um degrau
DEMOTE_RATIO = 0.6    # mediana ≤ 0,6× a geral → desce um degrau


def fetch_media(max_posts: int = 150) -> list[dict]:
    token = os.environ["FB_ACCESS_TOKEN"]
    ig_user_id = os.environ["IG_USER_ID"]
    url = (f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
           f"?fields=id,timestamp,media_type,like_count,comments_count,caption"
           f"&limit=50&access_token={token}")
    posts = []
    while url and len(posts) < max_posts:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
        posts.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
    return posts


def fetch_insights(media_id: str) -> dict:
    """Alcance, salvamentos e compartilhamentos de um post ({} se indisponível)."""
    token = os.environ["FB_ACCESS_TOKEN"]
    url = (f"https://graph.facebook.com/v19.0/{media_id}/insights"
           f"?metric=reach,saved,shares&access_token={token}")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read()).get("data", [])
    except Exception:
        return {}
    return {m["name"]: m["values"][0]["value"] for m in data if m.get("values")}


def _normalize(posts: list[dict], now: datetime) -> list[dict]:
    from content_generator import _categorize
    rows = []
    for p in posts:
        ts = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(BRT)
        first_line = (p.get("caption") or "").split("\n")[0]
        likes, comments = p.get("like_count", 0), p.get("comments_count", 0)
        age_h = (now - ts).total_seconds() / 3600
        ins = fetch_insights(p["id"]) if age_h <= WINDOW_DAYS * 24 else {}
        saved, shares = ins.get("saved", 0), ins.get("shares", 0)
        rows.append({
            "ts": ts,
            "age_h": (now - ts).total_seconds() / 3600,
            "is_video": p.get("media_type") == "VIDEO",
            "cat": _categorize({"title": first_line}),
            "title": first_line[:90],
            "likes": likes,
            "comments": comments,
            "reach": ins.get("reach"),
            "saved": saved,
            "shares": shares,
            "score": likes + comments + saved + shares,
        })
    return rows


def learn_weights(rows: list[dict]) -> dict:
    """Ajuste de prioridade por categoria, só com posts de feed já maduros."""
    mature = [r for r in rows if not r["is_video"]
              and MATURE_HOURS <= r["age_h"] <= WINDOW_DAYS * 24]
    if len(mature) < 20:
        return {"baseline_median": None, "sample": len(mature), "categories": {}}

    baseline = statistics.median(r["score"] for r in mature)
    by_cat = defaultdict(list)
    for r in mature:
        by_cat[r["cat"]].append(r["score"])

    cats = {}
    for cat, scores in sorted(by_cat.items()):
        med = statistics.median(scores)
        adjust = 0
        if len(scores) >= MIN_SAMPLE and baseline > 0:
            if med >= BOOST_RATIO * baseline:
                adjust = -1
            elif med <= DEMOTE_RATIO * baseline:
                adjust = 1
        cats[cat] = {"n": len(scores), "median": med, "adjust": adjust}
    return {"baseline_median": baseline, "sample": len(mature), "categories": cats}


def _fallback_note(weights: dict) -> str:
    cats = weights.get("categories", {})
    up = [c for c, v in cats.items() if v["adjust"] < 0]
    down = [c for c, v in cats.items() if v["adjust"] > 0 and c != "gta"]
    parts = []
    if up:
        parts.append(f"Priorizar {', '.join(up)} (acima da mediana nos últimos {WINDOW_DAYS} dias).")
    if down:
        parts.append(f"Segurar {', '.join(down)} (abaixo da mediana).")
    return " ".join(parts) or "Sem desvio claro por categoria: seguir a prioridade padrão."


def build_brief(rows: list[dict], weights: dict, for_date) -> dict:
    """Orientação de amanhã. O Groq redige; os números vêm prontos, ele não calcula."""
    yesterday = [r for r in rows if 0 < r["age_h"] <= 48 and not r["is_video"]]
    best = sorted(yesterday, key=lambda r: -r["score"])[:3]
    worst = sorted(yesterday, key=lambda r: r["score"])[:3]
    note = _fallback_note(weights)
    try:
        from content_generator import _call_groq
        facts = (
            f"Mediana geral (feed, {WINDOW_DAYS} dias): {weights.get('baseline_median')}\n"
            "Por categoria (n, mediana): "
            + "; ".join(f"{c} n={v['n']} med={v['median']}"
                        for c, v in weights.get("categories", {}).items()) + "\n"
            "Melhores das últimas 48h: "
            + " | ".join(f"{r['title']} ({r['score']})" for r in best) + "\n"
            "Piores das últimas 48h: "
            + " | ".join(f"{r['title']} ({r['score']})" for r in worst)
        )
        text = _call_groq(
            "Você é o editor-chefe do @morsadigital (cultura pop/nerd, Brasil). "
            "Com base SÓ nos números fornecidos, escreva a orientação de pauta de amanhã "
            "em 2 frases diretas: o que priorizar e o que evitar. GTA tem cota fixa de "
            "1 post por dia por decisão editorial: nunca recomende cortar GTA; se for o "
            "caso, diga qual ângulo de GTA rendeu mais. Não invente dados, "
            "não cite números que não estejam no texto. Sem travessão.",
            facts, max_tokens=160,
        ).strip()
        if 30 <= len(text) <= 500:
            note = text
    except Exception as e:
        logger.warning(f"Groq indisponível para o brief ({e}); usando texto padrão")
    return {
        "date": for_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_note": note,
    }


def fetch_reach_split(days: int = 7) -> dict:
    """Alcance da conta por seguidor / não seguidor. Não seguidor perto de zero é o
    sinal de que o Instagram tirou a conta das recomendações."""
    token, ig = os.environ["FB_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    now = int(datetime.now(timezone.utc).timestamp())
    url = (f"https://graph.facebook.com/v21.0/{ig}/insights?metric=reach&period=day"
           f"&metric_type=total_value&breakdown=follow_type&since={now - days * 86400}&until={now}"
           f"&access_token={token}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            results = json.loads(r.read())["data"][0]["total_value"]["breakdowns"][0]["results"]
        return {x["dimension_values"][0]: x["value"] for x in results}
    except Exception as e:
        logger.warning(f"Alcance por tipo de seguidor indisponível: {e}")
        return {}


def fetch_tiktok(days: int = 7) -> list[dict]:
    """Posts do TikTok com números, via Zernio (inclui os postados à mão no app)."""
    if not os.environ.get("ZERNIO_API_KEY"):
        return []
    since = (datetime.now(BRT) - timedelta(days=days)).date().isoformat()
    req = urllib.request.Request(
        f"https://zernio.com/api/v1/analytics?platform=tiktok&source=all&fromDate={since}&limit=100&sortBy=date",
        headers={"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            posts = json.loads(r.read()).get("posts", [])
    except Exception as e:
        logger.warning(f"Números do TikTok indisponíveis: {e}")
        return []
    rows = []
    for p in posts:
        a = p.get("analytics") or {}
        try:
            ts = datetime.fromisoformat(p["publishedAt"].replace("Z", "+00:00")).astimezone(BRT)
        except (KeyError, ValueError):
            continue
        rows.append({"ts": ts, "title": (p.get("content") or "").split("\n")[0][:80],
                     "views": a.get("views", 0), "likes": a.get("likes", 0),
                     "comments": a.get("comments", 0), "shares": a.get("shares", 0),
                     "ours": bool(p.get("latePostId") or not p.get("isExternal", False))})
    return sorted(rows, key=lambda r: r["ts"])


def _tiktok_section(tk: list[dict]) -> list[str]:
    if not tk:
        return ["", "## TikTok", "", "Sem dados (conta não ligada ou sem posts no período)."]
    views = [r["views"] for r in tk]
    lines = ["", "## TikTok — últimos 7 dias", "",
             f"- Vídeos: {len(tk)} | views no total: {sum(views)} | mediana por vídeo: {statistics.median(views)}",
             f"- Curtidas: {sum(r['likes'] for r in tk)} | comentários: {sum(r['comments'] for r in tk)}"
             f" | compartilhamentos: {sum(r['shares'] for r in tk)}", "",
             "| Quando | Views | Curtidas | Coment. | Compart. | Vídeo |", "|---|---|---|---|---|---|"]
    for r in sorted(tk, key=lambda r: -r["views"])[:15]:
        lines.append(f"| {r['ts']:%d/%m %H:%M} | {r['views']} | {r['likes']} | {r['comments']} | {r['shares']} | {r['title']} |")
    by_hour = defaultdict(list)
    for r in tk:
        by_hour[r["ts"].hour].append(r["views"])
    if len(tk) >= 8:
        lines += ["", "Mediana de views por horário: " +
                  " · ".join(f"{h}h: {statistics.median(v):.0f} ({len(v)})" for h, v in sorted(by_hour.items()))]
    return lines


def write_report(rows: list[dict], weights: dict, brief: dict, now: datetime,
                 tiktok: list[dict] = None, split: dict = None) -> Path:
    today = [r for r in rows if r["ts"].date() == now.date()]
    last7 = [r for r in rows if r["age_h"] <= 7 * 24]
    lines = [f"# Revisão diária @morsadigital — {now:%d/%m/%Y %H:%M} BRT", ""]

    lines += ["## Hoje (números ainda subindo)", "",
              "| Hora | Tipo | Categoria | Alcance | Curtidas | Coment. | Salvos | Compart. | Post |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(today, key=lambda r: r["ts"]):
        kind = "reel" if r["is_video"] else "feed"
        lines.append(f"| {r['ts']:%H:%M} | {kind} | {r['cat']} | {r['reach'] if r['reach'] is not None else '-'} | "
                     f"{r['likes']} | {r['comments']} | {r['saved']} | {r['shares']} | {r['title']} |")
    if not today:
        lines.append("| - | - | - | - | - | - | - | - | nenhum post hoje |")

    feed7 = [r for r in last7 if not r["is_video"]]
    reels7 = [r for r in last7 if r["is_video"]]
    lines += ["", "## Últimos 7 dias", "",
              f"- Posts de feed: {len(feed7)} | mediana {statistics.median([r['score'] for r in feed7]) if feed7 else 0}",
              f"- Reels: {len(reels7)} | mediana {statistics.median([r['score'] for r in reels7]) if reels7 else 0}",
              f"- Alcance mediano por post de feed: {statistics.median([r['reach'] for r in feed7 if r['reach'] is not None] or [0])}",
              f"- Alcance mediano por reel: {statistics.median([r['reach'] for r in reels7 if r['reach'] is not None] or [0])}",
              f"- Comentários: {sum(r['comments'] for r in last7)} | salvamentos: {sum(r['saved'] for r in last7)}"
              f" | compartilhamentos: {sum(r['shares'] for r in last7)}", ""]
    for label, sel in (("Melhores", sorted(last7, key=lambda r: -r["score"])[:5]),
                       ("Piores", sorted(feed7, key=lambda r: r["score"])[:5])):
        lines.append(f"**{label}:**")
        lines += [f"- {r['score']} (alcance {r['reach']}) · {r['cat']} · {r['title']}" for r in sel]
        lines.append("")

    lines += [f"## Aprendizado por categoria ({WINDOW_DAYS} dias, feed, posts com +{MATURE_HOURS}h)", "",
              f"Mediana geral: {weights.get('baseline_median')} em {weights.get('sample')} posts", "",
              "| Categoria | Posts | Mediana | Ajuste |", "|---|---|---|---|"]
    label = {-1: "sobe", 0: "mantém", 1: "desce"}
    for cat, v in sorted(weights.get("categories", {}).items(), key=lambda kv: -kv[1]["median"]):
        lines.append(f"| {cat} | {v['n']} | {v['median']} | {label[v['adjust']]} |")

    if split:
        total = sum(split.values()) or 1
        non = split.get("NON_FOLLOWER", 0)
        lines += ["", "## De onde vem o alcance (7 dias)", "",
                  f"- Seguidores alcançados: {split.get('FOLLOWER', 0)}",
                  f"- Não seguidores alcançados: {non} ({100 * non / total:.0f}% do alcance)",
                  "- Não seguidor perto de zero por vários dias = conta fora das recomendações "
                  "(conferir em Configurações > Status da conta)."]
    lines += _tiktok_section(tiktok or [])
    lines += ["", f"## Orientação para {brief['date']}", "", brief["strategy_note"], ""]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{now:%Y-%m-%d}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    now = datetime.now(BRT)
    rows = _normalize(fetch_media(), now)

    weights = learn_weights(rows)
    weights["generated_at"] = now.isoformat()
    WEIGHTS_PATH.write_text(json.dumps(weights, indent=2, ensure_ascii=False), encoding="utf-8")

    # Rodando de madrugada (cron atrasado), a orientação vale para o próprio dia
    target = now.date() if now.hour < 9 else now.date() + timedelta(days=1)
    brief = build_brief(rows, weights, target)
    BRIEF_PATH.parent.mkdir(exist_ok=True)
    BRIEF_PATH.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    report = write_report(rows, weights, brief, now, tiktok=fetch_tiktok(), split=fetch_reach_split())
    logger.info(f"Relatório: {report}")
    logger.info(f"Ajustes: { {c: v['adjust'] for c, v in weights['categories'].items() if v['adjust']} }")
    logger.info(f"Orientação {brief['date']}: {brief['strategy_note']}")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
