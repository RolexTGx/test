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
from pyrogram import Client, errors, utils as pyroutils
from urllib.parse import urlparse
from config import BOT, API, OWNER, CHANNEL

# ** Peer ID Fix **
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -10099999999999

# ------------------ Logging Setup ------------------
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ------------------ Flask App for Health Check ------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

# ------------------ Utility Functions ------------------
def extract_size(text):
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"

def should_skip_torrent(title):
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping torrent: {title}")
        return True
    return False

def extract_all_rarefilmm_gofile_links(page_url, scraper):
    try:
        response = scraper.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        a_tags = soup.find_all("a", href=re.compile(r"gofile\.io"))
        links = [a["href"].strip() for a in a_tags if a.has_attr("href")]
        return links
    except Exception as e:
        logging.error(f"Error extracting GOFILE links from {page_url}: {e}")
        return []

# ------------------ RSS Crawlers ------------------
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
        torrents.append({
            "title": title,
            "size": size,
            "link": link,
            "site": "#yts"
        })
    return torrents[:5]

def crawl_internet_archive():
    url = "https://archive.org/services/collection-rss.php?collection=feature_films"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        summary = entry.get("summary", "")
        size = extract_size(summary)
        if hasattr(entry, "enclosures") and entry.enclosures:
            link = entry.enclosures[0]["href"]
        else:
            link = entry.link
        torrents.append({
            "title": title,
            "size": size,
            "link": link,
            "site": "#internetarchive"
        })
    return torrents[:25]

def crawl_rarefilmm():
    url = "https://rarefilmm.com/feed/"
    feed = feedparser.parse(url)
    torrents = []
    scraper = cloudscraper.create_scraper()
    for entry in feed.entries:
        title = entry.title
        summary = entry.get("description", "")
        size = extract_size(summary)
        page_url = entry.link
        gofile_links = extract_all_rarefilmm_gofile_links(page_url, scraper)
        combined_link = "\n".join(gofile_links) if gofile_links else page_url
        torrents.append({
            "title": title,
            "size": size,
            "link": combined_link,
            "site": "#rarefilmm"
        })
    return torrents[:25]

def crawl_publicdomain():
    homepage_url = "https://www.publicdomaintorrents.info/"
    torrents = []
    try:
        response = requests.get(homepage_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        movie_links = soup.find_all("a", href=re.compile(r'^nshowmovie\.html\?movieid=\d+'))
        for movie_link in movie_links[:5]:
            movie_title = movie_link.get_text(strip=True) or "Unknown Title"
            detail_url = movie_link.get("href")
            if detail_url.startswith("nshowmovie.html"):
                detail_url = homepage_url + detail_url
            try:
                detail_response = requests.get(detail_url, timeout=10)
                detail_response.raise_for_status()
                detail_soup = BeautifulSoup(detail_response.text, "html.parser")
                torrent_tags = detail_soup.find_all("a", href=re.compile(r'btdownload\.php\?type=torrent'))
                for tag in torrent_tags:
                    torrent_text = tag.get_text(strip=True)
                    torrent_link = tag.get("href")
                    if torrent_link.startswith('/'):
                        torrent_link = "http://www.publicdomaintorrents.com" + torrent_link
                    size = extract_size(torrent_text)
                    torrents.append({
                        "title": f"{movie_title} - {torrent_text}",
                        "size": size,
                        "link": torrent_link,
                        "site": "#publicdomaintorrents"
                    })
            except Exception as detail_err:
                logging.error(f"Error fetching detail page {detail_url}: {detail_err}")
        return torrents
    except Exception as e:
        logging.error(f"Error in crawl_publicdomain: {e}")
        return []

def crawl_tbl():
    homepage_url = "https://www.1tamilblasters.gold/"
    torrents = []

    try:
        # Step 1: Get homepage and extract all topic URLs
        response = requests.get(homepage_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        topic_links = soup.find_all("a", href=re.compile(r'/index\.php\?/forums/topic/\d+'))
        topic_urls = []
        for link in topic_links:
            href = link.get("href")
            if href and href.startswith("/"):
                parsed = urlparse(homepage_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            if href not in topic_urls:
                topic_urls.append(href)

        # Step 2: Crawl each topic for torrent file attachments
        for url in topic_urls[:10]:  # Adjust as needed
            try:
                detail_response = requests.get(url, timeout=10)
                detail_response.raise_for_status()
                detail_soup = BeautifulSoup(detail_response.text, "html.parser")

                attach_links = detail_soup.find_all("a", href=re.compile(r'/applications/core/interface/file/attachment\.php\?id=\d+'))
                for link in attach_links:
                    torrent_link = link.get("href")
                    if not torrent_link.startswith("http"):
                        parsed = urlparse(url)
                        torrent_link = f"{parsed.scheme}://{parsed.netloc}{torrent_link}"

                    title_span = link.find("span", class_="ipsAttachLink_title")
                    raw_title = title_span.get_text(strip=True) if title_span else "Unknown"
                    title = re.sub(r'^(www\.[^\s]+?\s*-\s*)?', '', raw_title)
                    title = re.sub(r'\.torrent$', '', title).strip()

                    meta_span = link.find("span", class_="ipsAttachLink_metaInfo")
                    meta_text = meta_span.get_text(strip=True) if meta_span else ""
                    size_match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", meta_text, re.IGNORECASE)
                    size = size_match.group(1) if size_match else "Unknown"

                    torrents.append({
                        "title": title,
                        "size": size,
                        "link": torrent_link,
                        "site": "#tbl"
                    })

            except Exception as detail_err:
                logging.error(f"Error fetching torrent from {url}: {detail_err}")

    except Exception as e:
        logging.error(f"Error in crawl_tbl homepage: {e}")

    return torrents

# ------------------ Bot Class ------------------
class MN_Bot(Client):
    MAX_MSG_LENGTH = 4000

    def __init__(self):
        super().__init__(
            "MN-Bot",
            api_id=API.ID,
            api_hash=API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = CHANNEL.ID
        self.last_posted_links = set()

    async def safe_send_message(self, chat_id, message, **kwargs):
        if len(message) <= self.MAX_MSG_LENGTH:
            return await self.send_message(chat_id, message, **kwargs)
        else:
            parts = [message[i:i + self.MAX_MSG_LENGTH] for i in range(0, len(message), self.MAX_MSG_LENGTH)]
            for part in parts:
                await self.send_message(chat_id, part, **kwargs)
                await asyncio.sleep(1)

    async def post_torrent(self, torrent):
        site_tag = torrent.get("site", "#torrent")
        target_channel = self.channel_id
        if torrent["link"].lower().endswith(".torrent"):
            try:
                scraper_download = cloudscraper.create_scraper()
                file_resp = scraper_download.get(torrent["link"], timeout=10)
                file_resp.raise_for_status()
                if file_resp.content:
                    file_bytes = io.BytesIO(file_resp.content)
                    filename = torrent["title"].replace(" ", "_") + ".torrent"
                    await self.send_document(target_channel,
                                             file_bytes,
                                             file_name=filename,
                                             caption=f"{torrent['title']}\n📦 {torrent['size']}\n\n{site_tag} torrent file")
                    return
                else:
                    raise Exception("Empty torrent file content")
            except Exception as file_err:
                logging.error(f"⚠️ Failed to send torrent file for {torrent['title']}: {file_err}")
        message = (f"{torrent['link']}\n\n🎬 {torrent['title']}\n"
                   f"📦 {torrent['size']}\n\n{site_tag} powered by @MNBOTS")
        try:
            await self.safe_send_message(target_channel, message)
        except errors.FloodWait as e:
            logging.warning(f"⚠️ Flood wait: sleeping {e.value} seconds")
            await asyncio.sleep(e.value)

    async def initial_post_torrents(self):
        crawler_functions = [
            crawl_yts,
            crawl_internet_archive,
            crawl_rarefilmm,
            crawl_publicdomain,
            crawl_tbl
        ]
        for crawler in crawler_functions:
            try:
                torrents = crawler()
                for torrent in torrents[:5]:
                    if torrent.get("link") not in self.last_posted_links:
                        await self.post_torrent(torrent)
                        self.last_posted_links.add(torrent["link"])
                        await asyncio.sleep(3)
            except Exception as e:
                logging.error(f"Error posting initial torrents from {crawler.__name__}: {e}")

    async def auto_post_torrents(self):
        while True:
            try:
                torrents = (
                    crawl_yts() +
                    crawl_internet_archive() +
                    crawl_rarefilmm() +
                    crawl_publicdomain() +
                    crawl_tbl()
                )
                new_torrents = [t for t in torrents if t.get("link") not in self.last_posted_links]
                for torrent in new_torrents:
                    await self.post_torrent(torrent)
                    self.last_posted_links.add(torrent["link"])
                    await asyncio.sleep(3)
                if new_torrents:
                    logging.info(f"✅ Posted {len(new_torrents)} new torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_torrents: {e}")
            await asyncio.sleep(120)

    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username
        await self.initial_post_torrents()
        asyncio.create_task(self.auto_post_torrents())
        await self.send_message(chat_id=OWNER.ID,
                                text=f"{me.first_name} ✅✅ BOT started successfully ✅✅")
        logging.info(f"✅ {me.first_name} BOT started successfully")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

# ------------------ Main ------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
