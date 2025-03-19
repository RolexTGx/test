import asyncio
import feedparser
import logging
import threading
import re
from flask import Flask
from pyrogram import Client
from config import BOT, API, OWNER, CHANNEL  # Removed unused WEB import

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

MAX_SIZE_GB = 3.5  # Max file size limit in GB

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
        self.channel_id = int(CHANNEL.ID)
        self.last_posted_links = set()

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        # Start background tasks
        asyncio.create_task(self.auto_post_yts())
        asyncio.create_task(self.auto_post_nyaasi())

        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅",
        )

        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_yts(self):
        """Fetch and send new YTS torrents every 30 minutes"""
        while True:
            try:
                torrents = crawl_yts()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]
                
                if new_torrents:
                    for torrent in new_torrents:
                        if torrent["size_gb"] > MAX_SIZE_GB:
                            continue  # Skip torrents larger than 3.5GB

                        message = f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#yts powered by @MNBOTS"
                        await self.send_message(self.channel_id, message)
                        self.last_posted_links.add(torrent["link"])

                    logging.info("✅ Auto-posted new YTS torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_yts: {e}")

            await asyncio.sleep(1800)

    async def auto_post_nyaasi(self):
        """Fetch and send new Nyaa.si torrents every 30 minutes"""
        while True:
            try:
                torrents = crawl_nyaasi()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]
                
                if new_torrents:
                    for torrent in new_torrents:
                        if torrent["size_gb"] > MAX_SIZE_GB:
                            continue  # Skip torrents larger than 3.5GB

                        message = f"{torrent['link']}\n\n🎥 {torrent['title']}\n📦 {torrent['size']}\n\n#nyaasi powered by @MNBOTS"
                        await self.send_message(self.channel_id, message)
                        self.last_posted_links.add(torrent["link"])

                    logging.info("✅ Auto-posted new Nyaa.si torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_nyaasi: {e}")

            await asyncio.sleep(1800)

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = parse_size(entry.description)
        link = entry.enclosures[0]["href"]

        if size:
            torrents.append({
                "title": title,
                "size": size,
                "size_gb": convert_to_gb(size),
                "link": link
            })

    return torrents[:15]

# Function to fetch torrents from Nyaa.si RSS feed
def crawl_nyaasi():
    url = "https://nyaa.si/?page=rss"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = parse_size(entry.description)
        link = entry.link

        if size:
            torrents.append({
                "title": title,
                "size": size,
                "size_gb": convert_to_gb(size),
                "link": link
            })

    return torrents[:15]

# Extract size from description
def parse_size(description):
    match = re.search(r"<b>Size:</b>\s*([\d.]+)\s*([GMK]B)", description)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return "Unknown"

# Convert size to GB for filtering
def convert_to_gb(size_str):
    match = re.search(r"([\d.]+)\s*([GMK]B)", size_str)
    if not match:
        return 0
    size = float(match.group(1))
    unit = match.group(2).upper()
    if "GB" in unit:
        return size
    elif "MB" in unit:
        return size / 1024
    return 0

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()

