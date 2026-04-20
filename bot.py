import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = "MarkKomodo/fbhusernames"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"

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

async def main():
    token = os.environ["BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Keep running until interrupted
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
