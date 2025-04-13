import asyncio
import feedparser
import logging
import threading
import requests
import re
from flask import Flask
from bs4 import BeautifulSoup
from pyrogram import Client, errors
from urllib.parse import urlparse
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

def extract_size(text):
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Unknown"

def should_skip_torrent(title):
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping 4K torrent: {title}")
        return True
    return False

def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        summary = entry.get("summary", "")
        size = extract_size(summary)
        link = entry.enclosures[0]["href"]
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": size, "link": link})
    return torrents[:15]

def crawl_tamilmv():
    url = "https://cdn.mysitemapgenerator.com/shareapi/rss/12041002372"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        page_url = entry.link
        summary = entry.get("summary", "")
        size = extract_size(summary)
        if should_skip_torrent(title):
            continue
        try:
            parsed = urlparse(page_url)
            referer = f"{parsed.scheme}://{parsed.netloc}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": referer,
            }
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            magnet_link = next((a["href"] for a in soup.find_all("a", href=True) if "magnet:" in a["href"]), None)
            final_link = magnet_link if magnet_link else page_url
            torrents.append({"title": title, "size": size, "link": final_link})
        except requests.exceptions.RequestException as e:
            logging.error(f"⚠️ TamilMV error: {e}")
    return torrents[:15]

def crawl_tamilblasters():
    url = "https://tamilblasters.kokilaprasad.repl.co/feed"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        summary = entry.get("summary", "")
        size = extract_size(summary)
        link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": size, "link": link})
    return torrents[:15]

def crawl_psarips():
    url = "https://psa.wf/feed/"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = "Unknown"
        link = entry.link
        if should_skip_torrent(title):
            continue
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(link, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            magnet_link = next((a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("magnet:")), None)
            final_link = magnet_link if magnet_link else link
            torrents.append({"title": title, "size": size, "link": final_link})
        except requests.exceptions.RequestException as e:
            logging.error(f"⚠️ PSArips error: {e}")
    return torrents[:15]

def crawl_eztv():
    url = "https://eztv.re/ezrss.xml"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        size = extract_size(entry.get("summary", ""))
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": size, "link": link})
    return torrents[:15]

def crawl_torrentfunk():
    url = "https://www.torrentfunk.com/rss/movies.html"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        size = extract_size(entry.get("summary", ""))
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": size, "link": link})
    return torrents[:15]

class MN_Bot(Client):
    def __init__(self):
        super().__init__(
            "MN-Bot",
            api_id=API.ID,
            api_hash=API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = int(CHANNEL.ID)
        self.last_posted_links = set()

    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username
        asyncio.create_task(self.auto_post_torrents())
        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅"
        )
        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_torrents(self):
        while True:
            try:
                torrents = (
                    crawl_yts() +
                    crawl_tamilmv() +
                    crawl_tamilblasters() +
                    crawl_psarips() +
                    crawl_eztv() +
                    crawl_torrentfunk()
                )
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]

                for i, torrent in enumerate(new_torrents):
                    message = (
                        f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n"
                        f"#torrent powered by @MNBOTS"
                    )
                    try:
                        await self.send_message(self.channel_id, message)
                        self.last_posted_links.add(torrent["link"])
                        await asyncio.sleep(3)
                    except errors.FloodWait as e:
                        logging.warning(f"⚠️ Flood wait: sleeping {e.value} seconds")
                        await asyncio.sleep(e.value)

                    if i == 14:
                        await asyncio.sleep(3)

                if new_torrents:
                    logging.info(f"✅ Posted {len(new_torrents)} new torrents")

            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_torrents: {e}")

            await asyncio.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
