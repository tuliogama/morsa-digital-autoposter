#!/usr/bin/env python3
"""
refresh_backlog.py — abastece data/trailer_backlog.json automaticamente com
trailers OFICIAIS detectados nas notícias do RSS.

Princípios (aprendidos na marra):
- NUNCA inventa dados. Só usa o que está no texto da notícia.
- data_estreia só é preenchida quando uma data real é extraída do texto;
  senão fica "" (o reel lida com isso e a legenda simplesmente não cita data).
- Dedup por id estável (slug do título). O reel ainda tem is_duplicate na hora
  de postar, então mesmo um item repetido não vira post duplicado.
- Poda itens já postados e antigos, e limita o tamanho do backlog.

Uso:
  python3 refresh_backlog.py            # abastece e salva
  python3 refresh_backlog.py --dry-run  # mostra o que adicionaria, sem salvar
"""
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from news_fetcher import fetch_all_news
from content_generator import _categorize

# Reel deve ser nerd/geek (Marvel, DC, anime, games top, Star Wars, cinema/série
# pop). Categorias fora disso não entram no backlog (evita reel off-brand tipo
# desenho adulto random). Espelha a prioridade do select_best_news.
# Só categorias claramente nerd/geek. "movie"/"series" ficam de fora porque
# casam com "netflix"/"cinema" genéricos (pegavam desenho adulto random).
_ONBRAND_CATS = {"dc", "marvel", "anime", "starwars", "game_big"}

# Backlog é premium: exige "trailer"/"teaser" NO TÍTULO (is_trailer_news é frouxo
# — "revealed"/"watch the" pegam artigos que não são trailer).
_STRONG_TRAILER_RE = re.compile(r"\b(trailer|teaser)\b", re.IGNORECASE)
# Listas/rankings não são trailers ("15 Embarrassing Moments", "7 Best...").
_LIST_TITLE_RE = re.compile(r"^\s*\d{1,2}\s+\w", re.IGNORECASE)


def _is_strong_trailer(news_item: dict) -> bool:
    title = news_item.get("title", "")
    if _LIST_TITLE_RE.search(title):
        return False
    return bool(_STRONG_TRAILER_RE.search(title))


def _signature(titulo: str) -> frozenset:
    """Palavras significativas p/ detectar mesmo evento de fontes diferentes."""
    stop = {"trailer", "teaser", "oficial", "official", "novo", "new", "para",
            "the", "de", "do", "da", "of", "to", "in", "filme", "movie", "series",
            "série", "netflix", "first", "primeiro", "revela", "unveils", "reveals"}
    words = {w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", titulo.lower()) if w not in stop}
    return frozenset(words)

BACKLOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trailer_backlog.json")
MAX_BACKLOG = 40          # teto de itens
PRUNE_POSTED_DAYS = 30    # remove postados mais velhos que isso

_MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "set": 9, "oct": 10, "out": 10, "nov": 11, "dez": 12, "dec": 12,
}
_MESES_RE = "|".join(sorted(_MESES.keys(), key=len, reverse=True))


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    return t[:60] or "trailer"


def _clean_title(title: str) -> str:
    # Remove ruído de fonte e prefixos comuns de notícia de trailer
    for noise in [" - IGN", " | IGN", " - Kotaku", " | Kotaku", " - GameSpot",
                  " | ComicBook", " - ComicBook", " | Crunchyroll"]:
        title = title.replace(noise, "")
    # Se a manchete cita a obra entre aspas (‘Alley Cats’, "X"), usa isso —
    # é o nome real do filme/série, sem o ruído jornalístico em volta.
    # Só aspas curvas ‘’ “” ou aspas duplas " — NUNCA o apóstrofo reto '
    # (que aparece em possessivos: Prince's, Anime's).
    q = re.findall(r"[‘“]([^‘’“”]{3,60})[’”]|\"([^\"]{3,60})\"", title)
    q = [a or b for a, b in q]
    if q:
        # pega a aspa mais longa (geralmente o título da obra)
        return max(q, key=len).strip()
    title = re.sub(r"^(novo |primeiro |assista( ao)?:?|veja( o)?:?|trailer d[eo]:?)\s+",
                   "", title, flags=re.IGNORECASE)
    return title.strip()


def _extract_date(text: str) -> str:
    """Extrai data de estreia real do texto. Retorna 'YYYY-MM-DD' ou ''."""
    low = text.lower()
    hoje = datetime(2026, 1, 1)  # base estável (sem Date.now); ano inferido abaixo
    # 1) DD de MÊS de YYYY
    m = re.search(rf"(\d{{1,2}})\s+de\s+({_MESES_RE})\s+de\s+(\d{{4}})", low)
    if m:
        d, mes, y = int(m.group(1)), _MESES[m.group(2)], int(m.group(3))
        return _fmt(y, mes, d)
    # 2) DD/MM/YYYY ou DD/MM
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", low)
    if m:
        d, mes = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else _infer_year(mes, d)
        return _fmt(y, mes, d)
    # 3) MÊS de YYYY (sem dia) → dia 1
    m = re.search(rf"\b({_MESES_RE})\s+de\s+(\d{{4}})", low)
    if m:
        return _fmt(int(m.group(2)), _MESES[m.group(1)], 1)
    # 4) Month DD, YYYY (inglês)
    m = re.search(rf"\b({_MESES_RE})\s+(\d{{1,2}}),?\s+(\d{{4}})", low)
    if m:
        return _fmt(int(m.group(3)), _MESES[m.group(1)], int(m.group(2)))
    return ""


def _infer_year(mes: int, dia: int) -> int:
    """Sem ano explícito: se a data já passou em 2026, assume 2027 (lançamento futuro)."""
    base = datetime(2026, 6, 22)  # hoje aproximado (passado via ambiente seria ideal)
    try:
        cand = datetime(2026, mes, dia)
    except ValueError:
        return 2026
    return 2026 if cand >= base else 2027


def _fmt(y: int, mes: int, d: int) -> str:
    try:
        return datetime(y, mes, d).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _load() -> list:
    try:
        with open(BACKLOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _prune(items: list) -> list:
    """Remove postados antigos; mantém o backlog enxuto."""
    kept = []
    for it in items:
        if it.get("postado"):
            data = it.get("data_estreia", "")
            if data:
                try:
                    if (datetime(2026, 6, 22) - datetime.strptime(data, "%Y-%m-%d")).days > PRUNE_POSTED_DAYS:
                        continue
                except ValueError:
                    pass
        kept.append(it)
    return kept


def refresh(dry_run: bool = False) -> dict:
    backlog = _load()
    existing_ids = {it.get("id") for it in backlog}

    news = fetch_all_news(limit=50)
    trailers = [n for n in news if _is_strong_trailer(n)]

    # Assinaturas do que já existe, para barrar o mesmo evento de outra fonte
    seen_sigs = {_signature(it.get("titulo", "")) for it in backlog}

    added = []
    for n in trailers:
        if _categorize(n) not in _ONBRAND_CATS:
            continue  # off-brand (não é nerd/geek) — fora do backlog
        titulo = _clean_title(n.get("title", ""))
        if len(titulo) < 4:
            continue
        item_id = _slug(titulo)
        if item_id in existing_ids:
            continue
        sig = _signature(titulo)
        if sig and any(len(sig & s) >= 2 for s in seen_sigs):
            continue  # mesmo evento já no backlog/lote
        seen_sigs.add(sig)
        blob = f"{n.get('title','')} {n.get('description','')}"
        data_estreia = _extract_date(blob)
        entry = {
            "id": item_id,
            "titulo": titulo,
            "ano": (data_estreia[:4] if data_estreia else ""),
            "data_estreia": data_estreia,           # "" se não houver data real
            "status": "pre_estreia" if data_estreia else "",
            "elenco": "",                            # RSS raramente traz; nunca inventar
            "contexto": html.unescape(re.sub(r"<[^>]+>", "", n.get("description", "") or titulo))[:300].strip(),
            "query_youtube": f"{titulo} trailer oficial dublado português",
            "prioridade": 3,                         # abaixo dos curados (1-2)
            "postado": False,
            "_origem": "auto-rss",
        }
        backlog.append(entry)
        existing_ids.add(item_id)
        added.append(entry)

    backlog = _prune(backlog)
    # Mantém os curados (prioridade 1-2) e corta o excesso de auto-rss
    backlog.sort(key=lambda x: x.get("prioridade", 3))
    backlog = backlog[:MAX_BACKLOG]

    if not dry_run:
        with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
            json.dump(backlog, f, ensure_ascii=False, indent=2)

    return {"trailers_no_rss": len(trailers), "adicionados": len(added),
            "total_backlog": len(backlog), "novos": [a["titulo"] for a in added]}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    r = refresh(dry_run=dry)
    print(f"Trailers no RSS: {r['trailers_no_rss']} | adicionados: {r['adicionados']} | backlog: {r['total_backlog']}")
    for t in r["novos"]:
        print(f"  + {t}")
    if dry:
        print("(dry-run — nada salvo)")
