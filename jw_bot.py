#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "jw_state.json"
MAX_NOTIFY = 3
BASE_URL = "https://www.jw.org"

VIDEOS_API = (
    "https://b.jw-cdn.org/apis/mediator/v1/categories/I/LatestVideos"
    "?detailed=1&clientType=www"
)
NEWS_URL = "https://www.jw.org/it/news/"
MAGAZINES_URL = "https://www.jw.org/it/biblioteca-digitale/riviste/"

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  [TELEGRAM ERROR] {e}")


def send_error(context: str, error: Exception):
    """Notifica errori critici via Telegram."""
    msg = f"⚠️ <b>JW Monitor — Errore</b>\n\n{context}\n<code>{error}</code>"
    send_telegram(msg)


# ─── Stato ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                # Validazione struttura
                assert "videos" in state
                assert "news" in state
                assert "magazines" in state
                return state
        except Exception:
            print("  [WARN] Stato corrotto, reset.")
    return {"videos": [], "news": [], "magazines": []}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ─── Fetch ───────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ─── Video ───────────────────────────────────────────────────────────────────

def fetch_videos() -> list:
    data = requests.get(VIDEOS_API, headers=HEADERS, timeout=20).json()
    items = []
    for video in data["category"]["media"]:
        guid = video.get("guid")
        title = video.get("title", "").strip()
        natural_key = video.get("languageAgnosticNaturalKey", "")
        if not guid or not title:
            continue
        finder_url = (
            f"https://www.jw.org/finder?lank={natural_key}&wtlocale=I"
            if natural_key else ""
        )
        items.append({
            "id": guid,                  # identificativo stabile
            "title": title,
            "url": finder_url,
        })
    return items


# ─── News ─────────────────────────────────────────────────────────────────────

def fetch_news() -> list:
    soup = fetch_html(NEWS_URL)
    seen_slugs = set()
    items = []

    for a in soup.select('a[href*="/news/area-geografica/"]'):
        path = unquote(a.get("href", "")).rstrip("/")
        parts = [p for p in path.split("/") if p]

        # Struttura valida: it/news/area-geografica/paese/titolo = 5 parti
        if len(parts) != 5:
            continue

        slug = f"{parts[3]}/{parts[4]}"   # paese/titolo — identificativo stabile
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        title = a.get_text(" ", strip=True)
        if len(title) < 8:
            # Prova col testo dell'H3 vicino
            title = parts[4].replace("-", " ").title()

        items.append({
            "id": slug,
            "title": title,
            "url": f"{BASE_URL}/it/{'/'.join(parts[1:])}",
        })

    return items


# ─── Riviste ──────────────────────────────────────────────────────────────────

def fetch_magazines() -> list:
    soup = fetch_html(MAGAZINES_URL)
    seen_slugs = set()
    items = []

    for a in soup.select('a[href*="/biblioteca-digitale/riviste/"]'):
        href = a.get("href", "").rstrip("/")
        parts = href.split("/riviste/")

        if len(parts) != 2 or not parts[1]:
            continue  # salta link alla pagina categoria

        slug = parts[1].rstrip("/")       # identificativo stabile
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        title = a.get_text(" ", strip=True)
        if len(title) < 4:
            title = slug.replace("-", " ").title()

        items.append({
            "id": slug,
            "title": title,
            "url": f"{BASE_URL}/it/biblioteca-digitale/riviste/{slug}/",
        })

    return items


# ─── Check principale ─────────────────────────────────────────────────────────

SECTIONS = {
    "videos":    {"fetch": fetch_videos,    "emoji": "🎬", "label": "Nuovo Video JW.org"},
    "news":      {"fetch": fetch_news,      "emoji": "📰", "label": "Nuova News JW.org"},
    "magazines": {"fetch": fetch_magazines, "emoji": "📚", "label": "Nuova Pubblicazione JW.org"},
}


def check_all():
    state = load_state()

    for key, cfg in SECTIONS.items():
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        print(f"[{now}] Controllo {key}...")

        try:
            items = cfg["fetch"]()
        except Exception as e:
            print(f"  [ERROR] {e}")
            send_error(f"Errore nel fetch di <b>{key}</b>", e)
            continue

        print(f"  Trovati: {len(items)}")

        known = set(state.get(key, []))

        # Primo avvio: popola lo stato senza notificare
        if not known:
            state[key] = [x["id"] for x in items]
            print(f"  Primo avvio: salvati {len(items)} elementi, nessuna notifica.")
            continue

        new_items = [x for x in items if x["id"] not in known]
        print(f"  Nuovi: {len(new_items)}")

        for item in new_items[:MAX_NOTIFY]:
            msg = (
                f"{cfg['emoji']} <b>{cfg['label']}</b>\n\n"
                f"📌 {item['title']}\n\n"
                f"🔗 {item['url']}"
            )
            send_telegram(msg)
            time.sleep(1)

        # Aggiorna stato con gli ID correnti (cap a 500 per non crescere all'infinito)
        state[key] = [x["id"] for x in items][:500]

    save_state(state)


def main():
    try:
        check_all()
    except Exception as e:
        print(f"Errore critico: {e}")
        send_error("Errore critico in <b>check_all</b>", e)
        raise  # Fa fallire il job GitHub Actions


if __name__ == "__main__":
    main()
