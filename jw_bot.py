#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

ROME_TZ = ZoneInfo("Europe/Rome")

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

STATE_FILE = "jw_state.json"
LOG_FILE = "jw_log.json"
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
DAILY_TEXT_FILE = "wol_page.html"
MEETINGS_FILE = "wol_meetings.html"
MEETING_FILE = "wol_meetings_detail.html"
MEETING_URL_ENV = "MEETING_URL"
WATCHTOWER_FILE = "wol_watchtower.html"

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
                "📖 Scrittura del giorno\n"
                "📋 Studio Torre di Guardia (ogni giovedì alle 9:00)\n"
                "📅 Adunanza infrasettimanale (ogni lunedì alle 9:00)\n\n"
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
            now = datetime.now(tz=ROME_TZ).strftime("%d/%m/%Y %H:%M")
            send_telegram_to(chat_id, (
                f"✅ <b>JW Monitor attivo</b>\n\n"
                f"🕐 Ultimo controllo: {now}\n"
                f"⏱ Frequenza: ogni 15 minuti\n\n"
                f"Monitoraggio attivo per:\n"
                f"🎬 Video\n"
                f"📰 News\n"
                f"📚 Riviste\n"
                f"🏠 Homepage\n"
                f"📖 Scrittura del giorno\n"
                f"📅 Adunanza infrasettimanale (lunedì alle 9:00)\n"
                f"📋 Studio Torre di Guardia (giovedì alle 9:00)"
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
    return {"videos": [], "news": [], "magazines": [], "homepage": [], "daily_text_id": "", "watchtower_id": "", "meeting_id": ""}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ─── Log eventi ──────────────────────────────────────────────────────────────

def load_log() -> list:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print("  [WARN] Log corrotto, reset.")
    return []


def save_log(log: list):
    """Mantieni solo gli ultimi 365 giorni."""
    cutoff = datetime.now(tz=ROME_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = cutoff.replace(year=cutoff.year - 1)
    filtered = [
        entry for entry in log
        if datetime.strptime(entry["date"], "%Y-%m-%d %H:%M").replace(tzinfo=ROME_TZ) >= cutoff
    ]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)


def log_event(log: list, event_type: str, item_id: str, title: str):
    """Aggiunge un evento al log con ora italiana."""
    log.append({
        "date": datetime.now(tz=ROME_TZ).strftime("%Y-%m-%d %H:%M"),
        "type": event_type,
        "id": item_id,
        "title": title,
    })


# ─── Fetch ───────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ─── Video ───────────────────────────────────────────────────────────────────

def fetch_videos() -> list:
    data = requests.get(VIDEOS_API, headers=HEADERS, timeout=30).json()
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
    """Legge la scrittura del giorno dal file HTML scaricato da curl."""
    if not os.path.exists(DAILY_TEXT_FILE):
        print(f"  [WARN] {DAILY_TEXT_FILE} non trovato, skip.")
        return None

    try:
        with open(DAILY_TEXT_FILE, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as e:
        print(f"  [ERROR] Lettura {DAILY_TEXT_FILE}: {e}")
        return None

    today = os.getenv("TODAY_ISO", datetime.now(tz=ROME_TZ).strftime("%Y-%m-%d"))
    container = soup.select_one(f'.tabContent[data-date^="{today}"]')
    if not container:
        print(f"  [WARN] Contenitore per data {today} non trovato nel file HTML.")
        return None

    h2 = container.select_one('header h2')
    date_text = h2.get_text(" ", strip=True) if h2 else ""

    theme = container.select_one('p.themeScrp')
    scripture = theme.get_text(" ", strip=True) if theme else ""

    body_p = container.select_one('div.bodyTxt p.sb')
    comment = body_p.get_text(" ", strip=True) if body_p else ""

    date_id = os.getenv("TODAY_ISO", datetime.now(tz=ROME_TZ).strftime("%Y-%m-%d"))
    print(f"  Identificativo scrittura: {date_id}")

    return {
        "id": date_id,
        "date": date_text,
        "scripture": scripture,
        "comment": comment,
        "url": DAILY_TEXT_URL,
    }


def check_daily_text(state: dict, log: list):
    """Controlla se la scrittura del giorno è cambiata e notifica."""
    print(f"[{datetime.now(tz=ROME_TZ):%d/%m/%Y %H:%M}] Controllo scrittura del giorno...")

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


# ─── Adunanza infrasettimanale ───────────────────────────────────────────────

def fetch_meeting() -> dict | None:
    """Estrae i dati dell'adunanza infrasettimanale."""
    if not os.path.exists(MEETING_FILE):
        print(f"  [WARN] {MEETING_FILE} non trovato, skip.")
        return None

    try:
        with open(MEETING_FILE, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as e:
        print(f"  [ERROR] Lettura {MEETING_FILE}: {e}")
        return None

    week = ""
    if os.path.exists(MEETINGS_FILE):
        try:
            with open(MEETINGS_FILE, "r", encoding="utf-8") as f:
                soup_m = BeautifulSoup(f.read(), "html.parser")
            links = soup_m.select('a[href*="/wol/d/"]')
            if links:
                raw = links[0].get_text(" ", strip=True)
                parts = raw.split()
                week_parts = []
                for p in parts:
                    week_parts.append(p)
                    if p[0].isalpha() and len(p) > 2:
                        break
                week = " ".join(week_parts)
        except Exception:
            pass

    bible_reading = ""
    for h2 in soup.select('h2'):
        cls = h2.get("class", [])
        cls_str = " ".join(cls) if cls else ""
        if "du-color" not in cls_str:
            bible_reading = h2.get_text(" ", strip=True).title()
            break

    treasures_theme = ""
    for h3 in soup.select('h3'):
        cls = " ".join(h3.get("class", []))
        if "teal" in cls:
            text = h3.get_text(" ", strip=True)
            if ". " in text:
                text = text.split(". ", 1)[1]
            treasures_theme = text
            break

    christian_life_parts = []
    for h3 in soup.select('h3'):
        cls = " ".join(h3.get("class", []))
        if "maroon" in cls:
            text = h3.get_text(" ", strip=True)
            if ". " in text:
                text = text.split(". ", 1)[1]
            christian_life_parts.append(text)

    study_ref = ""
    for h3 in soup.select('h3'):
        if "Studio biblico" in h3.get_text():
            section = h3.find_parent('li') or h3.find_parent()
            if section:
                pc_links = section.select('a[href*="/wol/pc/"]')
                if len(pc_links) >= 2:
                    study_ref = pc_links[-2].get_text(" ", strip=True)
            break

    if christian_life_parts and study_ref:
        last = christian_life_parts[-1]
        christian_life_parts[-1] = f"{last} ({study_ref})"

    url = os.getenv(MEETING_URL_ENV, "https://wol.jw.org/it/wol/meetings/r6/lp-i")
    article_id = url.split("/wol/d/")[-1] if "/wol/d/" in url else ""

    if not article_id:
        print("  [WARN] ID adunanza non trovato.")
        return None

    return {
        "id": article_id,
        "week": week,
        "bible_reading": bible_reading,
        "treasures_theme": treasures_theme,
        "christian_life_parts": christian_life_parts,
        "url": url,
    }


def check_meeting(state: dict, log: list):
    """Invia la notifica adunanza infrasettimanale solo il lunedì alle 9:00."""
    now = datetime.now(tz=ROME_TZ)
    if now.weekday() != 0 or now.hour != 9:
        print(f"[{now:%d/%m/%Y %H:%M}] Adunanza: non è lunedì alle 9:00, skip.")
        return

    print(f"[{now:%d/%m/%Y %H:%M}] Controllo adunanza infrasettimanale...")

    try:
        meeting = fetch_meeting()
    except Exception as e:
        print(f"  [ERROR] {e}")
        send_error("Errore nel fetch dell'<b>adunanza infrasettimanale</b>", e)
        return

    if not meeting:
        return

    last_id = state.get("meeting_id", "")

    if meeting["id"] == last_id:
        print(f"  Adunanza già inviata per {meeting['id']}, skip.")
        return

    print(f"  Nuova adunanza: {meeting['id']}")

    parts_text = "\n".join(f"• {p}" for p in meeting["christian_life_parts"])

    msg = (
        f"📅 <b>Adunanza infrasettimanale — {meeting['week']}</b>\n\n"
        f"📖 <b>Lettura biblica:</b> {meeting['bible_reading']}\n\n"
        f"🔵 <b>Tesori della Parola di Dio:</b>\n{meeting['treasures_theme']}\n\n"
        f"🟤 <b>Vita cristiana:</b>\n{parts_text}\n\n"
        f"🔗 {meeting['url']}"
    )
    send_telegram(msg)
    state["meeting_id"] = meeting["id"]


# ─── Torre di Guardia settimanale ────────────────────────────────────────────

def fetch_watchtower() -> dict | None:
    """Estrae titolo e testo 'In questo articolo' dalla Torre di Guardia."""
    if not os.path.exists(WATCHTOWER_FILE):
        print(f"  [WARN] {WATCHTOWER_FILE} non trovato, skip.")
        return None

    try:
        with open(WATCHTOWER_FILE, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as e:
        print(f"  [ERROR] Lettura {WATCHTOWER_FILE}: {e}")
        return None

    title_el = soup.select_one('h1')
    title = title_el.get_text(" ", strip=True) if title_el else ""

    theme_el = soup.select_one('p.themeScrp')
    theme = theme_el.get_text(" ", strip=True) if theme_el else ""

    week = ""
    if os.path.exists(MEETINGS_FILE):
        try:
            with open(MEETINGS_FILE, "r", encoding="utf-8") as f:
                soup_m = BeautifulSoup(f.read(), "html.parser")
            links = soup_m.select('a[href*="/wol/d/"]')
            if links:
                raw = links[0].get_text(" ", strip=True)
                parts = week.split()
                week_parts = []
                for p in raw.split():
                    week_parts.append(p)
                    if p[0].isalpha() and len(p) > 2:
                        break
                week = " ".join(week_parts)
        except Exception:
            pass

    synopsis = ""
    refs = soup.select('p.pubRefs')
    for i, p in enumerate(refs):
        if "IN QUESTO ARTICOLO" in p.get_text():
            if i + 1 < len(refs):
                synopsis = refs[i + 1].get_text(" ", strip=True)
            break

    url = os.getenv("WATCHTOWER_URL", "https://wol.jw.org/it/wol/meetings/r6/lp-i")
    article_id = url.split("/wol/d/")[-1] if "/wol/d/" in url else ""

    if not title or not article_id:
        print("  [WARN] Titolo o ID Torre di Guardia non trovati.")
        return None

    return {
        "id": article_id,
        "title": title,
        "theme": theme,
        "synopsis": synopsis,
        "week": week,
        "url": url,
    }


def check_watchtower(state: dict, log: list):
    """Invia la notifica Torre di Guardia solo il giovedì alle 9:00."""
    now = datetime.now(tz=ROME_TZ)
    if now.weekday() != 3 or now.hour != 9:
        print(f"[{now:%d/%m/%Y %H:%M}] Torre di Guardia: non è giovedì alle 9:00, skip.")
        return

    print(f"[{now:%d/%m/%Y %H:%M}] Controllo Torre di Guardia settimanale...")

    try:
        wt = fetch_watchtower()
    except Exception as e:
        print(f"  [ERROR] {e}")
        send_error("Errore nel fetch della <b>Torre di Guardia</b>", e)
        return

    if not wt:
        return

    last_id = state.get("watchtower_id", "")

    if wt["id"] == last_id:
        print(f"  Torre di Guardia già inviata per {wt['id']}, skip.")
        return

    print(f"  Nuova Torre di Guardia: {wt['id']}")

    msg = (
        f"📖 <b>Studio Torre di Guardia — {wt['week']}</b>\n\n"
        f"<b>{wt['title']}</b>\n\n"
        f"<i>{wt['theme']}</i>\n\n"
        f"<b>In questo articolo:</b>\n{wt['synopsis']}\n\n"
        f"🔗 {wt['url']}"
    )
    send_telegram(msg)
    state["watchtower_id"] = wt["id"]


# ─── Check principale ────────────────────────────────────────────────────────

SECTIONS = {
    "videos":    {"fetch": fetch_videos,    "emoji": "🎬", "label": "Nuovo Video JW.org"},
    "news":      {"fetch": fetch_news,      "emoji": "📰", "label": "Nuova News JW.org"},
    "magazines": {"fetch": fetch_magazines, "emoji": "📚", "label": "Nuova Pubblicazione JW.org"},
    "homepage":  {"fetch": fetch_homepage,  "emoji": "🏠", "label": "Homepage JW.org aggiornata"},
}


def check_all():
    state = load_state()
    log = load_log()

    check_daily_text(state, log)
    check_meeting(state, log)
    check_watchtower(state, log)

    consecutive_errors = state.get("consecutive_errors", {})

    for key, cfg in SECTIONS.items():
        now = datetime.now(tz=ROME_TZ).strftime("%d/%m/%Y %H:%M")
        print(f"[{now}] Controllo {key}...")

        try:
            items = cfg["fetch"]()
            consecutive_errors[key] = 0
        except Exception as e:
            count = consecutive_errors.get(key, 0) + 1
            consecutive_errors[key] = count
            print(f"  [ERROR] {e} (errore #{count})")
            if count >= 3:
                send_error(f"Errore persistente nel fetch di <b>{key}</b> ({count} volte di fila)", e)
                consecutive_errors[key] = 0
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
            log_event(log, key, item["id"], item["title"])
            time.sleep(1)

        state[key] = [x["id"] for x in items][:500]

    state["consecutive_errors"] = consecutive_errors
    save_state(state)
    save_log(log)


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
