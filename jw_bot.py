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
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

STATE_FILE = "jw_state.json"
MAX_NOTIFY = 3
BASE_URL = "https://www.jw.org"

VIDEOS_API = (
    "https://b.jw-cdn.org/apis/mediator/v1/categories/I/LatestVideos"
    "?detailed=1&clientType=www"
)
NEWS_URL = "https://www.jw.org/it/news/"
MAGAZINES_URL = "https://www.jw.org/it/biblioteca-digitale/riviste/"
HOME_URL = "https://www.jw.org/it/"
DAILY_TEXT_URL = "https://wol.jw.org/it/wol/h/r6/lp-i"

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    try:
        send_telegram_to(CHAT_ID, text)
        if GROUP_CHAT_ID:
            send_telegram_to(GROUP_CHAT_ID, text)
    except Exception as e:
        print(f"  [TELEGRAM ERROR] {e}")


def send_telegram_to(chat_id, text: str):
    """Invia un messaggio a un chat_id specifico."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except Exception as e:
        print(f"  [TELEGRAM ERROR] {e}")


def send_error(context: str, error: Exception):
    """Notifica errori critici via Telegram."""
    msg = f"⚠️ <b>JW Monitor — Errore</b>\n\n{context}\n<code>{error}</code>"
    send_telegram(msg)


# ─── Comandi Telegram ────────────────────────────────────────────────────────

def get_updates() -> list:
    """Legge i messaggi in arrivo e li marca subito tutti come letti."""
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"timeout": 3},
            timeout=10,
        )
        results = r.json().get("result", [])
        if results:
            last_id = results[-1]["update_id"]
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_id + 1, "timeout": 1},
                timeout=5,
            )
        return results
    except Exception:
        return []


def handle_commands():
    """Processa i comandi ricevuti dall'ultima esecuzione."""
    updates = get_updates()

    if not updates:
        return

    for update in updates:
        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            continue

        print(f"  [CMD] {text} da {chat_id}")

        if text.startswith("/start"):
            send_telegram_to(chat_id, (
                "👋 <b>Benvenuto su JW Monitor!</b>\n\n"
                "Riceverai notifiche automatiche quando su JW.org (italiano) escono:\n\n"
                "🎬 Nuovi video\n"
                "📰 Nuove news\n"
                "📚 Nuove riviste\n"
                "🏠 Aggiornamento homepage\n"
                "📖 Scrittura del giorno\n\n"
                "Il bot è in funzione dalle 06:00 alle 23:00.\n\n"
                "<b>Comandi disponibili:</b>\n"
                "/start — questo messaggio\n"
                "/help — lista comandi\n"
                "/status — stato del bot"
            ))

        elif text.startswith("/help"):
            send_telegram_to(chat_id, (
                "📋 <b>Comandi JW Monitor</b>\n\n"
                "/start — messaggio di benvenuto\n"
                "/help — lista comandi\n"
                "/status — verifica che il bot sia attivo"
            ))

        elif text.startswith("/status"):
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            send_telegram_to(chat_id, (
                f"✅ <b>JW Monitor attivo</b>\n\n"
                f"🕐 Ultimo controllo: {now}\n"
                f"⏱ Frequenza: ogni 15 minuti\n\n"
                f"Monitoraggio attivo per:\n"
                f"🎬 Video\n"
                f"📰 News\n"
                f"📚 Riviste\n"
                f"🏠 Homepage\n"
                f"📖 Scrittura del giorno"
            ))


# ─── Stato ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                assert "videos" in state
                assert "news" in state
                assert "magazines" in state
                assert "homepage" in state
                return state
        except Exception:
            print("  [WARN] Stato corrotto, reset.")
    return {"videos": [], "news": [], "magazines": [], "homepage": [], "daily_text_id": ""}


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
            "id": guid,
            "title": title,
            "url": finder_url,
        })
    return items


# ─── News ────────────────────────────────────────────────────────────────────

def fetch_news() -> list:
    soup = fetch_html(NEWS_URL)
    seen_slugs = set()
    items = []

    for a in soup.select('a[href*="/news/area-geografica/"]'):
        path = unquote(a.get("href", "")).rstrip("/")
        parts = [p for p in path.split("/") if p]

        if len(parts) != 5:
            continue

        slug = f"{parts[3]}/{parts[4]}"
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        title = a.get_text(" ", strip=True)
        if len(title) < 8:
            title = parts[4].replace("-", " ").title()

        items.append({
            "id": slug,
            "title": title,
            "url": f"{BASE_URL}/it/{'/'.join(parts[1:])}",
        })

    return items


# ─── Riviste ─────────────────────────────────────────────────────────────────

def fetch_magazines() -> list:
    soup = fetch_html(MAGAZINES_URL)
    seen_slugs = set()
    items = []

    for a in soup.select('a[href*="/biblioteca-digitale/riviste/"]'):
        href = a.get("href", "").rstrip("/")
        parts = href.split("/riviste/")

        if len(parts) != 2 or not parts[1]:
            continue

        slug = parts[1].rstrip("/")
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


# ─── Homepage ────────────────────────────────────────────────────────────────

def fetch_homepage() -> list:
    soup = fetch_html(HOME_URL)

    a = soup.select_one('h3.billboardTitle a[href*="/biblioteca-digitale/"]')
    if not a:
        return []

    href = a.get("href", "").rstrip("/")
    title = a.get_text(" ", strip=True)

    if not href or not title:
        return []

    slug = href.split("/it/")[-1].rstrip("/")

    return [{
        "id": slug,
        "title": title,
        "url": f"https://www.jw.org/it/{slug}/",
    }]


# ─── Scrittura del giorno ────────────────────────────────────────────────────

def fetch_daily_text() -> dict | None:
    """Estrae la scrittura del giorno da WOL."""
    soup = fetch_html(DAILY_TEXT_URL)

    container = soup.select_one('#dailyText .tabContent')
    if not container:
        print("  [WARN] Contenitore dailyText non trovato.")
        return None

    # Data
    h2 = container.select_one('header h2')
    date_text = h2.get_text(" ", strip=True) if h2 else ""

    # Versetto
    theme = container.select_one('p.themeScrp')
    scripture = theme.get_text(" ", strip=True) if theme else ""

    # Commento (primo paragrafo del corpo)
    body_p = container.select_one('div.bodyTxt p.sb')
    comment = body_p.get_text(" ", strip=True) if body_p else ""

    # Tronca il commento a 300 caratteri
    if len(comment) > 300:
        comment = comment[:300].rstrip() + "…"

    # Identificativo = data nel formato YYYY-MM-DD
    data_date = container.get("data-date", "")
    date_id = data_date[:10] if data_date else datetime.now().strftime("%Y-%m-%d")

    return {
        "id": date_id,
        "date": date_text,
        "scripture": scripture,
        "comment": comment,
        "url": DAILY_TEXT_URL,
    }


def check_daily_text(state: dict):
    """Controlla se la scrittura del giorno è cambiata e notifica."""
    print(f"[{datetime.now():%d/%m/%Y %H:%M}] Controllo scrittura del giorno...")

    try:
        daily = fetch_daily_text()
    except Exception as e:
        print(f"  [ERROR] {e}")
        send_error("Errore nel fetch della <b>scrittura del giorno</b>", e)
        return

    if not daily:
        return

    last_id = state.get("daily_text_id", "")

    if daily["id"] == last_id:
        print(f"  Scrittura già inviata per {daily['id']}, skip.")
        return

    print(f"  Nuova scrittura del giorno: {daily['id']}")

    msg = (
        f"📖 <b>Scrittura del giorno — {daily['date']}</b>\n\n"
        f"<i>{daily['scripture']}</i>\n\n"
        f"{daily['comment']}\n\n"
        f"🔗 {daily['url']}"
    )
    send_telegram(msg)
    state["daily_text_id"] = daily["id"]


# ─── Check principale ────────────────────────────────────────────────────────

SECTIONS = {
    "videos":    {"fetch": fetch_videos,    "emoji": "🎬", "label": "Nuovo Video JW.org"},
    "news":      {"fetch": fetch_news,      "emoji": "📰", "label": "Nuova News JW.org"},
    "magazines": {"fetch": fetch_magazines, "emoji": "📚", "label": "Nuova Pubblicazione JW.org"},
    "homepage":  {"fetch": fetch_homepage,  "emoji": "🏠", "label": "Homepage JW.org aggiornata"},
}


def check_all():
    state = load_state()

    check_daily_text(state)

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

        state[key] = [x["id"] for x in items][:500]

    save_state(state)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    try:
        handle_commands()
        check_all()
    except Exception as e:
        print(f"Errore critico: {e}")
        send_error("Errore critico in <b>check_all</b>", e)
        raise


if __name__ == "__main__":
    main()
