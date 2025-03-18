import asyncio
import feedparser
import logging
import threading
import requests
from bs4 import BeautifulSoup
import torrent_parser as tp
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

        # Start background tasks for auto-posting torrents
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
        """Fetch and send new YTS torrents every 30 minutes"""
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

            await asyncio.sleep(1800)  # Wait 30 minutes before checking again

    async def auto_post_tamilmv(self):
        """Fetch and send new TamilMV torrents every 30 minutes"""
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

            await asyncio.sleep(1800)  # Wait 30 minutes before checking again

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        download_link = entry.enclosures[0]["href"]
        torrents.append({
            "title": entry.title,
            "size": "Unknown Size",  # YTS RSS doesn't provide size
            "link": download_link
        })

    return torrents[:5]  # Limit to the latest 5 torrents

# Function to scrape TamilMV for torrents
def crawl_tamilmv():
    url = "https://www.1tamilmv.ms/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "lxml")

    torrents = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".torrent"):
            title = link.text.strip()
            size = get_torrent_size(href)
            torrents.append({
                "title": title,
                "size": size,
                "link": href
            })

    return torrents[:5]  # Limit to the latest 5 torrents

# Function to get the size of the torrent file
def get_torrent_size(torrent_url):
    try:
        response = requests.get(torrent_url, stream=True)
        if response.status_code == 200:
            with open("temp.torrent", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            data = tp.parse_torrent_file("temp.torrent")
            if "files" in data["info"]:
                size = sum(file["length"] for file in data["info"]["files"])
            else:
                size = data["info"]["length"]

            os.remove("temp.torrent")  # Delete temp file after parsing

            # Convert size to MB or GB
            if size > 1e9:
                return f"{round(size / 1e9, 2)} GB"
            return f"{round(size / 1e6, 2)} MB"
    except Exception as e:
        logging.error(f"⚠️ Error getting torrent size: {e}")
    return "Unknown Size"

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    Private_Bots().run()
