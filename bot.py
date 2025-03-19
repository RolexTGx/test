import asyncio
import feedparser
import logging
import threading
import re
from flask import Flask
from pyrogram import Client
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

        # Start background tasks for auto-posting torrents
        asyncio.create_task(self.auto_post_nyaasi())
        asyncio.create_task(self.auto_post_yts())

        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅",
        )
        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_nyaasi(self):
        """Fetch and send new Nyaa.si torrents every 10 minutes"""
        while True:
            try:
                torrents = crawl_nyaasi()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]

                for torrent in new_torrents:
                    message = f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#nyaasi powered by @MNBOTS"
                    await self.send_message(self.channel_id, message)
                    self.last_posted_links.add(torrent["link"])

                if new_torrents:
                    logging.info("✅ Auto-posted new Nyaa.si torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_nyaasi: {e}")

            await asyncio.sleep(600)  # Wait 10 minutes before checking again

    async def auto_post_yts(self):
        """Fetch and send new YTS torrents every 30 minutes"""
        while True:
            try:
                torrents = crawl_yts()
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]

                for torrent in new_torrents:
                    message = f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#yts powered by @MNBOTS"
                    await self.send_message(self.channel_id, message)
                    self.last_posted_links.add(torrent["link"])

                if new_torrents:
                    logging.info("✅ Auto-posted new YTS torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_yts: {e}")

            await asyncio.sleep(1800)  # Wait 30 minutes before checking again

# Function to fetch torrents from Nyaa.si RSS feed
def crawl_nyaasi():
    url = "https://nyaa.si/?page=rss"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = parse_size_nyaasi(entry.torrents[0]["size"])
        link = entry.link

        if should_skip_torrent(title, size):
            continue

        torrents.append({"title": title, "size": size, "link": link})

    return torrents[:15]  # Limit to the latest 15 torrents

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = parse_size_yts(entry.description)
        link = entry.enclosures[0]["href"]

        if should_skip_torrent(title, size):
            continue

        torrents.append({"title": title, "size": size, "link": link})

    return torrents[:15]  # Limit to the latest 15 torrents

# Extract size from Nyaa.si feed (e.g., "1.5 GiB" → "1.5 GB")
def parse_size_nyaasi(size_str):
    match = re.search(r"([\d.]+)\s*(GiB|MiB|KiB)", size_str)
    if not match:
        return "Unknown"
    
    size = float(match.group(1))
    unit = match.group(2)

    if unit == "GiB":
        size_gb = size
    elif unit == "MiB":
        size_gb = size / 1024
    elif unit == "KiB":
        size_gb = size / (1024 * 1024)
    else:
        size_gb = 0

    return f"{size_gb:.2f} GB"

# Extract size from YTS feed
def parse_size_yts(description):
    match = re.search(r"<b>Size:</b>\s*([\d.]+)\s*(GB|MB|KB)", description)
    if not match:
        return "Unknown"

    size = float(match.group(1))
    unit = match.group(2)

    if unit == "GB":
        size_gb = size
    elif unit == "MB":
        size_gb = size / 1024
    elif unit == "KB":
        size_gb = size / (1024 * 1024)
    else:
        size_gb = 0

    return f"{size_gb:.2f} GB"

# Check if torrent should be skipped based on size or resolution
def should_skip_torrent(title, size_str):
    # Skip torrents labeled as 4K (2160p)
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping 4K torrent: {title}")
        return True

    # Convert size to float for comparison
    match = re.match(r"([\d.]+)", size_str)
    if match:
        size_gb = float(match.group(1))
        if size_gb > 3.5:
            logging.info(f"❌ Skipping large torrent: {title} ({size_gb} GB)")
            return True

    return False

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
