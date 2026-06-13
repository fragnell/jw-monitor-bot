# 🤖 JW Monitor Bot

Bot Telegram che monitora **JW.org in italiano** e invia notifiche automatiche su Telegram quando vengono pubblicati nuovi contenuti.

---

## 📡 Cosa monitora

| Sezione | Fonte | Frequenza |
|---|---|---|
| 🎬 Nuovi video | API CDN JW | ogni 15 minuti |
| 📰 Nuove news | jw.org/it/news/ | ogni 15 minuti |
| 📚 Nuove riviste | jw.org/it/biblioteca-digitale/riviste/ | ogni 15 minuti |
| 🏠 Aggiornamento homepage | jw.org/it/ | ogni 15 minuti |
| 📖 Scrittura del giorno | wol.jw.org | una volta al giorno |

---

## 🏗️ Architettura

Il bot gira interamente su servizi gratuiti:

- **cron-job.org** — triggera il workflow ogni 15 minuti
- **GitHub Actions** — esegue il bot in cloud
- **jw_state.json** — persistenza dello stato (versionato nel repository)
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

Il bot è attivo dalle **06:00 alle 23:00** (ora italiana) ogni giorno.
La scrittura del giorno viene inviata alla prima run utile dopo la mezzanotte.

---

## 📁 Stato del monitoraggio

Il file `jw_state.json` tiene traccia di tutti i contenuti già notificati:

```json
{
  "videos": [],
  "news": [],
  "magazines": [],
  "homepage": [],
  "daily_text_id": "2026-06-13"
}
```

Al primo avvio lo stato viene popolato senza inviare notifiche. Dalla run successiva vengono notificati solo i nuovi contenuti.
