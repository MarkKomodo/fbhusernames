import os
import sys
import asyncio
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ─── CONFIG ───
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "MarkKomodo/fbhusernames"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
PORT = int(os.environ.get("PORT", 10000))

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

# ─── HEALTH SERVER (threading, not asyncio) ───
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")
    
    def log_message(self, format, *args):
        pass  # suppress default HTTP logging

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        log(f"Health server listening on port {PORT}")
        server.serve_forever()
    except Exception as e:
        log(f"Health server failed: {e}")

# ─── TELEGRAM HANDLER ───
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or update.message.caption or ""
    if not text.strip():
        await update.message.reply_text("❌ Empty message.")
        return
    
    payload = {
        "event_type": "new-creators",
        "client_payload": {
            "text": text,
            "source": "telegram",
            "user": update.effective_user.username or str(update.effective_user.id)
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
                await update.message.reply_text("✅ Added to index! Refresh Carrd to see updates.")
            else:
                err = await resp.text()
                await update.message.reply_text(f"❌ Error {resp.status}: {err}")

# ─── MAIN ───
async def run_bot():
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        log("ERROR: BOT_TOKEN not set!")
        return
    
    log("Initializing bot...")
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    log("Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Block forever
    stop_event = asyncio.Event()
    await stop_event.wait()

def main():
    try:
        log("=== Starting FBH Telegram Bot ===")
        log(f"PORT={PORT}")
        log(f"GITHUB_REPO={GITHUB_REPO}")
        log(f"GITHUB_TOKEN set: {bool(GITHUB_TOKEN)}")
        
        # Start health server in background thread
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()
        log("Health server thread started")
        
        # Run bot in main thread with its own event loop
        asyncio.run(run_bot())
        
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        raise

if __name__ == "__main__":
    main()
