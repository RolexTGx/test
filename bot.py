import asyncio
import feedparser
import logging
import threading
import re
from time import sleep
from flask import Flask
from pyrogram import Client, errors
from config import BOT, API, OWNER, CHANNEL

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

class MN_Bot(Client):
    def __init__(self):
        super().__init__(
            "MN-Bot",
            API.ID,
            API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = int(CHANNEL.ID)  # Telegram channel ID
        self.last_posted_links = set()  # Store previously posted torrents

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        # Start real-time monitoring for new torrents
        asyncio.create_task(self.auto_post_torrents())

        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅",
        )
        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_torrents(self):
        """Continuously check for new torrents and post them immediately"""
        while True:
            try:
                torrents = crawl_yts() + crawl_tamilmv() + crawl_tamilblasters() + crawl_torrentgalaxy() + crawl_phe()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]

                for i, torrent in enumerate(new_torrents):
                    message = f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#torrent powered by @MNBOTS"
                    try:
                        await self.send_message(self.channel_id, message)
                        self.last_posted_links.add(torrent["link"])
                        await asyncio.sleep(3)  # Avoid flood wait
                    except errors.FloodWait as e:
                        logging.warning(f"⚠️ Flood wait triggered! Sleeping for {e.value} seconds.")
                        await asyncio.sleep(e.value)
                    
                    # Add delay after last 15 torrents when bot starts
                    if i == 14:
                        await asyncio.sleep(3)

                if new_torrents:
                    logging.info(f"✅ Posted {len(new_torrents)} new torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_torrents: {e}")

            await asyncio.sleep(120)  # Check every 2 minutes for new torrents

# Function to check torrent quality limit (under 4K)
def should_skip_torrent(title):
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping 4K torrent: {title}")
        return True
    return False

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.enclosures[0]["href"]

        if should_skip_torrent(title):
            continue

        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

# Function to fetch torrents from TamilMV
def crawl_tamilmv():
    return []  # Implement TamilMV scraping logic

# Function to fetch torrents from Tamil Blasters
def crawl_tamilblasters():
    return []  # Implement Tamil Blasters scraping logic

# Function to fetch torrents from Torrent Galaxy
def crawl_torrentgalaxy():
    return []  # Implement Torrent Galaxy scraping logic

# Function to fetch torrents from PHE
def crawl_phe():
    return []  # Implement PHE scraping logic

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
