import asyncio
import logging
import threading
import io

from flask import Flask
from bs4 import BeautifulSoup
import cloudscraper
import re

from pyrogram import Client, errors, utils as pyroutils
from config import BOT, API, OWNER, CHANNEL

# Ensure proper chat/channel ID handling
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -10099999999999

# Logging configuration
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# Flask health check
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Run Flask in a separate thread
def run_flask():
    app.run(host='0.0.0.0', port=8000)

class MN_Bot(Client):
    MAX_MSG_LENGTH = 4000

    def __init__(self):
        super().__init__(
            "MN-Bot",
            api_id=API.ID,
            api_hash=API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=8
        )


    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        await self.send_message(
            OWNER.ID,
            text=f"{me.first_name} ✅ BOT started "
        )
        logging.info("MN-Bot started ")
        asyncio.create_task(self.auto_post_torrents())

    async def stop(self, *args):
        await super().stop()
        logging.info("MN-Bot stopped")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    MN_Bot().run()
