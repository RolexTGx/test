import asyncio
import feedparser
import logging
import threading
import requests
from flask import Flask
from bs4 import BeautifulSoup
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
        self.channel_id = int(CHANNEL.ID)
        self.last_posted_links = set()

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        # Start the auto-posting task
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
                    message = (f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n"
                               f"#torrent powered by @MNBOTS")
                    try:
                        await self.send_message(self.channel_id, message)
                        self.last_posted_links.add(torrent["link"])
                        await asyncio.sleep(3)
                    except errors.FloodWait as e:
                        logging.warning(f"⚠️ Flood wait triggered! Sleeping for {e.value} seconds.")
                        await asyncio.sleep(e.value)

                    if i == 14:
                        await asyncio.sleep(3)

                if new_torrents:
                    logging.info(f"✅ Posted {len(new_torrents)} new torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_torrents: {e}")
            await asyncio.sleep(120)

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
        link = entry.enclosures[0]["href"]
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

# Updated crawl_tamilmv using the new RSS feed from MySitemapGenerator
def crawl_tamilmv():
    url = "https://cdn.mysitemapgenerator.com/shareapi/rss/12041002372"
    feed = feedparser.parse(url)
    torrents = []
    tamilmv_url = "https://www.1tamilmv.ms/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": tamilmv_url,
    }
    for entry in feed.entries:
        title = entry.title
        page_url = entry.link
        if should_skip_torrent(title):
            continue
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            magnet_link = next(
                (link["href"] for link in soup.find_all("a", href=True)
                 if "magnet:?" in link["href"]),
                None
            )
            # If a magnet link is found, use it; otherwise retain the original page URL.
            link = magnet_link if magnet_link else page_url
            if magnet_link:
                logging.info(f"✅ Found magnet link for {title}")
            else:
                logging.warning(f"⚠️ No magnet link found for {title}")
            torrents.append({"title": title, "size": "Unknown", "link": link})
        except requests.exceptions.RequestException as e:
            logging.error(f"⚠️ Error fetching TamilMV magnet link: {e}")
    return torrents[:15]

def crawl_tamilblasters():
    url = "https://tamilblasters.kokilaprasad.repl.co/feed"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

def crawl_psarips():
    url = "https://psa.wf/feed/"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

def crawl_eztv():
    url = "https://eztv.re/ezrss.xml"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

def crawl_torrentfunk():
    url = "https://www.torrentfunk2.com/rss.html"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": "Unknown", "link": link})
    return torrents[:15]

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()

# ---------------------------------------------------
# To embed the RSS feed into a website, add the following HTML snippet:
#
# <div id="mysitemapgenerator_loadcorsdata" data-token="d8e786eaf927b1c1fd5bd819833deae2" data-domain="www.mysitemapgenerator.com"></div>
# <script src="https://cdn.mysitemapgenerator.com/api/embedfeed.m.js"></script>
#
# This snippet loads a dynamic feed widget on your webpage.
