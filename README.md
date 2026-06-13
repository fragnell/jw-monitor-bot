# 🤖 JW Monitor Bot

Bot Telegram che monitora **JW.org in italiano** e invia notifiche automatiche su Telegram quando vengono pubblicati nuovi contenuti.

---

## 📡 Cosa monitora

| Sezione | Fonte | Quando |
|---|---|---|
| 🎬 Nuovi video | API CDN JW | ogni 15 minuti |
| 📰 Nuove news | jw.org/it/news/ | ogni 15 minuti |
| 📚 Nuove riviste | jw.org/it/biblioteca-digitale/riviste/ | ogni 15 minuti |
| 🏠 Aggiornamento homepage | jw.org/it/ | ogni 15 minuti |
| 📖 Scrittura del giorno | wol.jw.org | ogni giorno alle 06:00 |
| 📅 Adunanza infrasettimanale | wol.jw.org | ogni lunedì alle 09:00 |
| 📋 Studio Torre di Guardia | wol.jw.org | ogni giovedì alle 09:00 |

---

## 🏗️ Architettura

Il bot gira interamente su servizi gratuiti:

- **cron-job.org** — triggera il workflow ogni 15 minuti
- **GitHub Actions** — esegue il bot in cloud
- **jw_state.json** — persistenza dello stato (versionato nel repository)
- **jw_log.json** — log eventi degli ultimi 365 giorni
- **Telegram Bot API** — invio notifiche

---

## ⚙️ Configurazione

### Secrets GitHub richiesti

| Secret | Descrizione |
|---|---|
| `BOT_TOKEN` | Token del bot Telegram (da @BotFather) |
| `CHAT_ID` | ID della chat personale Telegram |
| `GROUP_CHAT_ID` | ID del canale Telegram (opzionale) |

### Impostare i secrets

```
GitHub → Settings → Secrets and variables → Actions → New repository secret
```

---

## 🤖 Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/start` | Messaggio di benvenuto e lista funzionalità |
| `/help` | Lista comandi disponibili |
| `/status` | Verifica che il bot sia attivo |

---

## 📁 File del progetto

| File | Descrizione |
|---|---|
| `jw_bot.py` | Codice principale del bot |
| `jw_state.json` | Stato attuale del monitoraggio (non cancellare) |
| `jw_log.json` | Log eventi degli ultimi 365 giorni |
| `.github/workflows/jw-monitor.yml` | Workflow GitHub Actions |
| `requirements.txt` | Dipendenze Python |

---

## 📋 Requisiti

- Python 3.10 o superiore
- `requests`
- `beautifulsoup4`

Installa le dipendenze:

```
pip install -r requirements.txt
```

---

## 🕐 Orari di funzionamento

Il bot è attivo dalle **06:00 alle 23:00** (ora italiana) tramite cron-job.org.

| Orario | Notifica |
|---|---|
| Ogni giorno alle 06:00 | 📖 Scrittura del giorno |
| Ogni lunedì alle 09:00 | 📅 Adunanza infrasettimanale |
| Ogni giovedì alle 09:00 | 📋 Studio Torre di Guardia |
| Ogni 15 minuti | 🎬 Video, 📰 News, 📚 Riviste, 🏠 Homepage |

---

## 📁 Stato del monitoraggio

Il file `jw_state.json` tiene traccia di tutti i contenuti già notificati:

```json
{
  "videos": [],
  "news": [],
  "magazines": [],
  "homepage": [],
  "daily_text_id": "2026-06-13",
  "watchtower_id": "r6/lp-i/2026365",
  "meeting_id": "r6/lp-i/202026166"
}
```

Al primo avvio lo stato viene popolato senza inviare notifiche. Dalla run successiva vengono notificati solo i nuovi contenuti.

---

## 📊 Log eventi

Il file `jw_log.json` registra ogni notifica inviata con data/ora italiana, tipo e titolo. Mantiene gli ultimi 365 giorni di storico per analisi statistiche future.

```json
[
  {
    "date": "2026-06-13 09:00",
    "type": "daily_text",
    "id": "2026-06-13",
    "title": "Chi ha costruito ogni cosa è Dio (Ebr. 3:4)"
  }
]
```
