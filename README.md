# 🤖 JW.org Monitor Bot

Bot Telegram che monitora **JW.org in italiano** e ti notifica su Telegram
quando escono nuovi video, news o aggiornamenti alla homepage.

---

## 📋 Requisiti

- Python 3.10 o superiore
- Connessione internet

---

## ⚙️ Installazione

### 1. Installa Python
Scarica da https://www.python.org/downloads/ (spunta "Add to PATH" durante l'installazione)

### 2. Installa le dipendenze
Apri il terminale (CMD o PowerShell) nella cartella del bot e digita:
```
pip install -r requirements.txt
```

### 3. Avvia il bot
```
python jw_bot.py
```

---

## 🚀 Come funziona

- Al primo avvio salva lo stato attuale di JW.org (nessuna notifica)
- Ogni **5 minuti** controlla se ci sono cambiamenti
- Se rileva nuovi contenuti ti manda un messaggio Telegram con titolo e link

---

## 🔄 Tenerlo sempre attivo (opzionale)

Per tenerlo attivo 24/7 puoi usare:
- **Windows**: Task Scheduler → esegui `python jw_bot.py` all'avvio
- **Linux/Mac**: `nohup python jw_bot.py &` oppure un servizio systemd
- **Cloud gratuito**: Railway.app o Render.com (piano free)

---

## 📁 File generati

- `jw_state.json` → salva lo stato delle pagine monitorate (non cancellarlo!)

---

## ⚠️ Note

Il bot monitora queste pagine:
- `https://www.jw.org/it/notizie/` — News
- `https://www.jw.org/it/biblioteca/video/` — Video
- `https://www.jw.org/it/` — Homepage generale

<!-- aggiornamento -->
