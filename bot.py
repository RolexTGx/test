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
from config import BOT, API, WEB, OWNER, CHANNEL

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
        self.channel_id = int(CHANNEL.ID)
        self.last_posted_yts = set()
        self.last_posted_tamilmv = set()
        self.last_posted_1337x_movies = set()
        self.last_posted_1337x_series = set()
        self.last_posted_piratebay = set()
        self.last_posted_nyaa = set()

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        asyncio.create_task(self.auto_post_yts())
        asyncio.create_task(self.auto_post_tamilmv())
        asyncio.create_task(self.auto_post_1337x_movies())
        asyncio.create_task(self.auto_post_1337x_series())
        asyncio.create_task(self.auto_post_piratebay())
        asyncio.create_task(self.auto_post_nyaa())

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
                        message = f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#yts"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_yts.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new YTS torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_yts: {e}")
            await asyncio.sleep(1800)

    async def auto_post_1337x_movies(self):
        while True:
            try:
                torrents = crawl_1337x("Movies")
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_1337x_movies]
                if new_torrents:
                    for torrent in new_torrents:
                        message = f"{torrent['link']}\n\n🎥 {torrent['title']}\n📦 {torrent['size']}\n\n#1337x #Movies"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_1337x_movies.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new 1337x movies")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_1337x_movies: {e}")
            await asyncio.sleep(1800)

    async def auto_post_1337x_series(self):
        while True:
            try:
                torrents = crawl_1337x("TV")
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_1337x_series]
                if new_torrents:
                    for torrent in new_torrents:
                        message = f"{torrent['link']}\n\n📺 {torrent['title']}\n📦 {torrent['size']}\n\n#1337x #Series"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_1337x_series.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new 1337x series")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_1337x_series: {e}")
            await asyncio.sleep(1800)

    async def auto_post_nyaa(self):
        while True:
            try:
                torrents = crawl_nyaa()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_nyaa]
                if new_torrents:
                    for torrent in new_torrents:
                        message = f"{torrent['link']}\n\n🎌 {torrent['title']}\n📦 {torrent['size']}\n\n#Anime"
                        await self.send_message(self.channel_id, message)
                    self.last_posted_nyaa.update([t["link"] for t in new_torrents])
                logging.info("✅ Auto-posted new Nyaa anime torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_nyaa: {e}")
            await asyncio.sleep(1800)

# Fetch torrents from YTS
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        torrents.append({
            "title": entry.title,
            "size": "Unknown Size",
            "link": entry.enclosures[0]["href"]
        })
    return torrents[:5]

# Fetch torrents from 1337x (Movies or Series)
def crawl_1337x(category):
    url = f"https://1337x.to/rss/category/{category}/1/"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        torrents.append({
            "title": entry.title,
            "size": "Unknown Size",
            "link": entry.link
        })
    return torrents[:5]

# Fetch anime torrents from Nyaa.si
def crawl_nyaa():
    url = "https://nyaa.si/?page=rss"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        torrents.append({
            "title": entry.title,
            "size": "Unknown Size",
            "link": entry.link
        })
    return torrents[:5]

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    Private_Bots().run()
