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
    """
    Extracts a file size from the provided text using regex.
    Looks for patterns like 12.3 GB, 500 MB, or 123 KB.
    """
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Unknown"

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
                    message = (
                        f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n"
                        f"#torrent powered by @MNBOTS"
                    )
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": referer,
            }
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            magnet_link = next((a["href"] for a in soup.find_all("a", href=True) if "magnet:" in a["href"]), None)
            final_link = magnet_link if magnet_link else page_url
            if magnet_link:
                logging.info(f"✅ Found magnet link for {title}")
            else:
                logging.warning(f"⚠️ No magnet link found for {title}")
            torrents.append({"title": title, "size": size, "link": final_link})
        except requests.exceptions.RequestException as e:
            logging.error(f"⚠️ Error fetching TamilMV magnet link: {e}")
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
    """
    PSArips feed is a standard blog feed.
    Since it does not include torrent-specific metadata,
    we default file size to "Unknown" and try to scrape a magnet link from the detail page.
    """
    url = "https://psa.wf/feed/"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = "Unknown"
        link = entry.link
        if should_skip_torrent(title):
            continue

        magnet_link = None
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(link, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            # Look for any anchor tag where href starts with "magnet:"
            magnet_link = next((a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("magnet:")), None)
        except requests.exceptions.RequestException as e:
            logging.error(f"⚠️ Error fetching PSArips detail page: {e}")

        if magnet_link is None:
            magnet_link = link  # Fallback to the detail page URL

        torrents.append({"title": title, "size": size, "link": magnet_link})
    return torrents[:15]

def crawl_eztv():
    """
    EZTV RSS feed is namespaced. Feedparser converts the torrent-specific tags into keys with underscores.
    For example:
      - <torrent:contentLength> becomes entry["torrent_contentlength"]
      - <torrent:magnetURI> becomes entry["torrent_magneturi"]
    """
    url = "https://eztvx.to/ezrss.xml"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = entry.get("torrent_contentlength", "Unknown")
        magnet_link = entry.get("torrent_magneturi", entry.link)
        if should_skip_torrent(title):
            continue
        torrents.append({"title": title, "size": size, "link": magnet_link})
    return torrents[:15]

def crawl_torrentfunk():
    url = "https://www.torrentfunk2.com/rss.html"
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

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
