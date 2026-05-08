# adhahi.dz Wilaya Monitor Bot — Setup Guide

## 1. Install Python dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

## 2. Configure the bot
Open `bot.py` and fill in the top section:

```python
TELEGRAM_TOKEN   = "123456789:ABCdef..."   # from @BotFather
TELEGRAM_CHAT_ID = "123456789"             # your chat ID
```

### Get your Chat ID:
1. Send any message to your bot on Telegram
2. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
3. Look for: "chat":{"id": 123456789}  ← that number is your chat ID

## 3. Run the bot
```bash
python bot.py
```

## 4. Run in background (Linux/VPS)
```bash
# Using screen:
screen -S adhahi
python bot.py
# Press Ctrl+A then D to detach

# Using nohup:
nohup python bot.py > bot.log 2>&1 &
```

## 5. Run as a service (systemd, optional)
```ini
# /etc/systemd/system/adhahi-bot.service
[Unit]
Description=adhahi.dz Monitor Bot
After=network.target

[Service]
WorkingDirectory=/path/to/your/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
systemctl enable adhahi-bot
systemctl start adhahi-bot
```

## How it works
- Launches a headless Chrome browser (Playwright)
- Opens adhahi.dz/register every 60 seconds
- Clicks the wilaya dropdown to load all 58 wilayas
- Compares status vs previous check
- If ANY wilaya changes from "غير متوفر" to available → sends Telegram alert immediately
- Saves state to wilaya_state.json so it survives restarts
