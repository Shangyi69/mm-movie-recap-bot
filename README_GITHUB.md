# 🎬 MM Movie Recap Telegram Bot

Myanmar Movie Recap Generator Bot for Telegram

Powered by AI: Whisper + Gemini + Edge TTS

---

## ✨ Features

- 📹 Video upload → Myanmar recap
- 🗣️ Male/Female voice options
- ⏩ Adjustable speed
- 🏷️ Custom watermark
- 🤖 24/7 Telegram bot

---

## 🚀 Quick Deploy on Render.com

### Requirements

- GitHub Account
- Render.com Account (free)
- Gemini API Key (free from https://ai.google.dev/)
- Telegram Bot Token (from @BotFather)

### Steps

1. **Fork this repository**
2. **Go to Render.com** → New Background Worker
3. **Connect your GitHub repo**
4. **Add Environment Variables:**
   ```
   GEMINI_API_KEY_1 = your_key
   TELEGRAM_BOT_TOKEN = your_token
   ```
5. **Deploy!**

See [RENDER_DEPLOY.md](RENDER_DEPLOY.md) for detailed Burmese guide.

---

## 📋 Files

- `bot.py` - Main bot application
- `requirements.txt` - Python dependencies
- `RENDER_DEPLOY.md` - Deployment guide (Burmese)

---

## 🤖 Bot Commands

```
/start - Start bot
/voice male/female - Change voice
/speed 0-50 - Change speed
/watermark <text> - Set watermark
/settings - Show current settings
/help - Show help
```

---

## 💻 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GEMINI_API_KEY_1=your_key
export TELEGRAM_BOT_TOKEN=your_token

# Run bot
python bot.py
```

---

## 📄 License

MIT License
