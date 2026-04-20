import os
import sys
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ─── CONFIG ───
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "MarkKomodo/fbhusernames"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
PORT = int(os.environ.get("PORT", 10000))

# Only these channels can trigger updates
ALLOWED_CHANNELS = [
    -1001189317946,
    -1001899939123,
    -1001610106957,
    -1002119676540,
]

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

# ─── HEALTH SERVER ───
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")
    
    def log_message(self, format, *args):
        pass

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        log(f"Health server listening on port {PORT}")
        server.serve_forever()
    except Exception as e:
        log(f"Health server failed: {e}")

# ─── TELEGRAM HANDLER ───
async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both regular messages and channel posts
    msg = update.message or update.channel_post
    if not msg:
        return
    
    text = msg.text or msg.caption or ""
    if not text.strip():
        return
    
    chat_id = update.effective_chat.id
    log(f"Processing message from chat {chat_id}")
    
    payload = {
        "event_type": "new-creators",
        "client_payload": {
            "text": text,
            "source": "telegram",
            "chat_id": chat_id,
            "user": update.effective_user.username or str(update.effective_user.id) if update.effective_user else "channel"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            GITHUB_API,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            },
            json=payload
        ) as resp:
            if resp.status == 204:
                log(f"✅ Triggered GitHub Action for chat {chat_id}")
            else:
                err = await resp.text()
                log(f"❌ GitHub Error {resp.status}: {err}")

# ─── MAIN ───
async def run_bot():
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        log("ERROR: BOT_TOKEN not set!")
        return
    
    log("Initializing bot...")
    
    channel_filter = filters.Chat(chat_id=ALLOWED_CHANNELS)
    
    app = Application.builder().token(token).build()
    
    # Regular messages in groups/supergroups
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & channel_filter, 
        handle_update
    ))
    
    # Channel broadcasts
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST & filters.TEXT & channel_filter,
        handle_update
    ))
    
    log("Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    stop_event = asyncio.Event()
    await stop_event.wait()

def main():
    try:
        log("=== Starting FBH Telegram Bot ===")
        log(f"PORT={PORT}")
        log(f"Monitoring channels: {ALLOWED_CHANNELS}")
        log(f"GITHUB_TOKEN set: {bool(GITHUB_TOKEN)}")
        
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()
        log("Health server thread started")
        
        asyncio.run(run_bot())
        
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        raise

if __name__ == "__main__":
    main()
