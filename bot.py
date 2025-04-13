import asyncio
import feedparser
import logging
import threading
import requests
import re
import cloudscraper
import io
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
    Extracts a file size from text (e.g. "12.3 GB", "500 MB", or "123 KB").
    """
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"

def should_skip_torrent(title):
    """
    Skip torrents marked as 4K/2160p.
    """
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
        torrents.append({"title": title, "size": size, "link": link, "site": "#yts"})
    return torrents[:15]

def crawl_tamilmv():
    """
    Scrapes the TamilMV RSS feed. For each entry, uses cloudscraper to bypass Cloudflare 
    and fetch the detail page. It extracts ALL magnet and torrent file links and concatenates 
    them (newline separated).
    """
    url = "https://cdn.mysitemapgenerator.com/shareapi/rss/12041002372"
    feed = feedparser.parse(url)
    torrents = []
    scraper = cloudscraper.create_scraper()  # Cloudflare bypass

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
                "Accept-Language": "en-US,en;q=0.9"
            }
            response = scraper.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract all magnet links and links ending with ".torrent"
            link_candidates = [
                a["href"].strip() for a in soup.find_all("a", href=True)
                if ("magnet:" in a["href"]) or (a["href"].strip().lower().endswith(".torrent"))
            ]
            final_link = "\n".join(link_candidates) if link_candidates else page_url
            torrents.append({"title": title, "size": size, "link": final_link, "site": "#tamilmv"})
            logging.info(f"✅ TamilMV: {title} - {len(link_candidates)} link(s) found")
        except Exception as e:
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
        torrents.append({"title": title, "size": size, "link": link, "site": "#tamilblasters"})
    return torrents[:15]

def crawl_psarips():
    """
    Uses cloudscraper to bypass Cloudflare for PSArips detail pages.
    """
    url = "https://psa.wf/feed/"
    feed = feedparser.parse(url)
    torrents = []
    scraper = cloudscraper.create_scraper()
    for entry in feed.entries:
        title = entry.title
        size = "Unknown"
        link = entry.link
        if should_skip_torrent(title):
            continue
        try:
            headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
            response = scraper.get(link, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            magnet_candidates = [
                a["href"].strip() for a in soup.find_all("a", href=True)
                if a["href"].startswith("magnet:")
            ]
            final_link = "\n".join(magnet_candidates) if magnet_candidates else link
            torrents.append({"title": title, "size": size, "link": final_link, "site": "#psa"})
            logging.info(f"✅ PSArips: {title} - {len(magnet_candidates)} link(s) found")
        except Exception as e:
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
        torrents.append({"title": title, "size": size, "link": link, "site": "#eztv"})
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
        torrents.append({"title": title, "size": size, "link": link, "site": "#torrentfunk"})
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
                    site_tag = torrent.get("site", "#torrent")
                    
                    # For TamilMV posts, try sending the torrent file if available.
                    if site_tag == "#tamilmv":
                        # Check if any of the links ends with '.torrent'
                        candidates = [link.strip() for link in torrent["link"].split("\n") if link.strip().lower().endswith(".torrent")]
                        if candidates:
                            # Attempt to download the first torrent file and send as document.
                            torrent_url = candidates[0]
                            try:
                                headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
                                file_resp = requests.get(torrent_url, headers=headers, timeout=10)
                                file_resp.raise_for_status()
                                file_bytes = io.BytesIO(file_resp.content)
                                # Name the file based on title (replace spaces with underscores)
                                filename = torrent["title"].replace(" ", "_") + ".torrent"
                                await self.send_document(self.channel_id, file_bytes, file_name=filename, caption=f"{torrent['title']}\n📦 {torrent['size']}\n\n{site_tag} powered by @MNBOTS")
                                self.last_posted_links.add(torrent["link"])
                                logging.info(f"✅ Sent torrent file for TamilMV: {torrent['title']}")
                                await asyncio.sleep(3)
                                continue  # Skip to next torrent after sending file
                            except Exception as file_err:
                                logging.error(f"⚠️ Failed to send torrent file for {torrent['title']}: {file_err}")
                                # Fall back to sending text message if file sending fails.
                    
                    # Default: send the torrent links as text message.
                    message = (
                        f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n"
                        f"{site_tag} powered by @MNBOTS"
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
