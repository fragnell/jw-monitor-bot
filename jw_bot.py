#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "jw_state.json"
CHECK_INTERVAL = 300
MAX_NOTIFY = 3
BASE_URL = "https://www.jw.org"

SOURCES = {
    "videos": {
        "url": "https://www.jw.org/it/cosa-nuovo/",
        "emoji": "🎬",
        "label": "Nuovo Video JW.org",
    },
    "news": {
        "url": "https://www.jw.org/it/news/",
        "emoji": "📰",
        "label": "Nuova News JW.org",
    },
    "magazines": {
        "url": "https://www.jw.org/it/biblioteca-digitale/riviste/",
        "emoji": "📚",
        "label": "Nuova Pubblicazione JW.org",
    },
}


def send_telegram(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
            verify=False,
        )
    except Exception as e:
        print("Telegram error:", e)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"videos": [], "news": [], "magazines": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def fetch(url):
    r = requests.get(url, timeout=20, verify=False)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def abs_url(href):
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return BASE_URL + href


def dedup(items):
    seen = set()
    out = []

    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            out.append(item)

    return out


VIDEOS_API = "https://b.jw-cdn.org/apis/mediator/v1/categories/I/LatestVideos?detailed=1&clientType=www"

def fetch_videos_api():
    data = requests.get(
        VIDEOS_API,
        timeout=20,
        verify=False
    ).json()

    items = []

    for video in data["category"]["media"]:
        guid = video.get("guid")
        title = video.get("title", "").strip()

        if not guid or not title:
            continue

        natural_key = video.get("languageAgnosticNaturalKey", "")

        finder_url = ""
        if natural_key:
            finder_url = f"https://www.jw.org/finder?lank={natural_key}&wtlocale=I"

        items.append({
            "title": title,
            "link": f"VIDEO::{guid}",
            "url": finder_url
        })

    return items


def extract_news(soup):
    items = []

    for a in soup.find_all("a", href=True):
        href = abs_url(a.get("href", ""))
        title = a.get_text(" ", strip=True)

        if "/news/area-geografica/" not in href:
            continue

        parts = href.rstrip("/").split("/")

        # ignora pagine categoria tipo /russia/ o /norvegia/
        if len(parts) <= 7:
            continue

        if len(title) < 8:
            continue

        items.append({"title": title, "link": href})

    return dedup(items)


def extract_magazines(soup):
    items = []

    for a in soup.find_all("a", href=True):
        href = abs_url(a.get("href", ""))
        title = a.get_text(" ", strip=True)

        if "b.jw-cdn.org" in href:
            continue

        if "GETPUBMEDIALINKS" in href:
            continue

        if "/biblioteca-digitale/riviste/" not in href:
            continue

        if href.rstrip("/") == "https://www.jw.org/it/biblioteca-digitale/riviste":
            continue

        if len(title) < 4:
            continue

        items.append({"title": title, "link": href})

    return dedup(items)


EXTRACTORS = {
    "news": extract_news,
    "magazines": extract_magazines,
}


def check_all():
    state = load_state()

    for key, cfg in SOURCES.items():
        print(f"[{datetime.now():%d/%m/%Y %H:%M}] Controllo {key}")

        if key == "videos":
            items = fetch_videos_api()
        else:
            soup = fetch(cfg["url"])
            items = EXTRACTORS[key](soup)

        print(f"  Trovati {len(items)} elementi")

        old = set(state.get(key, []))

        if not old:
            state[key] = [x["link"] for x in items]
            print(f"  Primo controllo: salvati {len(items)} elementi")
            continue

        new_items = [x for x in items if x["link"] not in old]

        print(f"  Nuovi elementi: {len(new_items)}")

        for item in new_items[:MAX_NOTIFY]:

            if key == "videos":
                msg = (
                    f"{cfg['emoji']} <b>{cfg['label']}</b>\n\n"
                    f"📌 {item['title']}"
                )

                if item.get("url"):
                    msg += f"\n\n🔗 {item['url']}"

                send_telegram(msg)

            else:
                send_telegram(
                    f"{cfg['emoji']} <b>{cfg['label']}</b>\n\n"
                    f"📌 {item['title']}\n\n"
                    f"🔗 {item['link']}"
                )

            time.sleep(1)

        state[key] = [x["link"] for x in items][:500]

    save_state(state)


def main():
    send_telegram(
        "✅ <b>JW Monitor Bot avviato</b>\n\n🎬 Video\n📰 News\n📚 Riviste"
    )

    while True:
        try:
            check_all()
        except Exception as e:
            print("Errore:", e)

        print("Attendo prossimo controllo...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
