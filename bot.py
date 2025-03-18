import asyncio
import feedparser
import logging
import threading
import requests
import os
import bencodepy
import base64
import hashlib
import re
from bs4 import BeautifulSoup
from flask import Flask
from pyrogram import Client
from config import BOT, API, WEB, OWNER, CHANNEL  # Import CHANNEL from config

# Logging setup
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# Flask app for health check
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

class Private_Bots(Client):
    def __init__(self):
        super().__init__(
            "Forward-Tag-Remover",
            API.ID,
            API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = int(CHANNEL.ID)  # Use the new channel ID from config
        self.last_posted_yts = set()  # Track YTS torrents
        self.last_posted_tamilmv = set()  # Track TamilMV torrents

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        asyncio.create_task(self.auto_post_yts())
        asyncio.create_task(self.auto_post_tamilmv())

        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅",
        )
        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_yts(self):
        while True:
            try:
                torrents = crawl_yts()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_yts]
                if new_torrents:
                    for torrent in new_torrents:
                        message = f"{torrent['link']}\n\n{torrent['title']}\n{torrent['size']}\n\n#yts"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_yts.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new YTS torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_yts: {e}")
            await asyncio.sleep(1800)

    async def auto_post_tamilmv(self):
        while True:
            try:
                torrents = crawl_tamilmv()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_tamilmv]
                if new_torrents:
                    for torrent in new_torrents:
                        message = f"{torrent['link']}\n\n{torrent['title']}\n{torrent['size']}\n\n#tmv"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_tamilmv.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new TamilMV torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_tamilmv: {e}")
            await asyncio.sleep(1800)

# Fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        size = parse_size_yts(entry.description)
        if not size:
            continue
        torrents.append({
            "title": entry.title,
            "size": size,
            "link": entry.enclosures[0]["href"]
        })
    return torrents[:5]

# Extract size from YTS description
def parse_size_yts(description):
    match = re.search(r"<b>Size:</b>\\s*([\\d.]+\\s*[GMK]B)", description)
    return match.group(1) if match else "Unknown Size"

# Convert .torrent file to magnet link
def get_magnet_link(torrent_url):
    try:
        response = requests.get(torrent_url, stream=True)
        if response.status_code == 200:
            with open("temp.torrent", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            with open("temp.torrent", "rb") as f:
                decoded_torrent = bencodepy.decode(f.read())
            info = decoded_torrent[b'info']
            info_hash = hashlib.sha1(bencodepy.encode(info)).digest()
            magnet_link = f"magnet:?xt=urn:btih:{base64.b16encode(info_hash).decode().lower()}"
            os.remove("temp.torrent")
            return magnet_link
    except Exception as e:
        logging.error(f"⚠️ Error extracting magnet link: {e}")
    return None

# Scrape TamilMV torrents
def crawl_tamilmv():
    url = "https://www.1tamilmv.ms/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "lxml")
    torrents = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".torrent"):
            title = link.text.strip()
            magnet_link = get_magnet_link(href)
            if magnet_link:
                torrents.append({
                    "title": title,
                    "size": "Unknown Size",
                    "link": magnet_link
                })
    return torrents[:5]

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    Private_Bots().run()
