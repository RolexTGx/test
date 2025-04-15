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
from config import BOT, API, OWNER, CHANNEL, RARE_CHANNEL

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
    """
    Extracts a file size from text (e.g. "12.3 GB", "500 MB", or "123 KB").
    """
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"

def should_skip_torrent(title):
    """
    Skips torrents marked as 4K/2160p.
    """
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping torrent: {title}")
        return True
    return False

def extract_all_rarefilmm_gofile_links(page_url, scraper):
    """
    Fetches the given RareFilmm page and extracts all GOFILE links.
    Returns a list of GOFILE links.
    """
    try:
        response = scraper.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # Find all anchor tags with href containing "gofile.io"
        a_tags = soup.find_all("a", href=re.compile(r"gofile\.io"))
        links = [a["href"].strip() for a in a_tags if a.has_attr("href")]
        return links
    except Exception as e:
        logging.error(f"Error extracting GOFILE links from {page_url}: {e}")
        return []

# ------------------ RSS Crawlers for Various Sources ------------------
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

def extract_tamilmv_post_details(post_url, scraper):
    """
    Extract details from a 1TamilMV forum post.
    Finds all torrent file attachments (data-fileext="torrent")
    and magnet links on the page.
    Returns a dict with:
      - title: from the first torrent file’s cleaned text (or default),
      - size: extracted from that text,
      - links: a list of dicts with keys "type", "title", and "link".
    """
    response = scraper.get(post_url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    torrent_files = []
    torrent_tags = soup.find_all("a", attrs={"data-fileext": "torrent"})
    for tag in torrent_tags:
        if tag.has_attr("href"):
            torrent_link = tag["href"].strip()
            torrent_text = tag.get_text(strip=True)
            prefix = "www.1TamilMV.esq - "
            if torrent_text.startswith(prefix):
                torrent_text = torrent_text[len(prefix):]
            if torrent_text.lower().endswith(".torrent"):
                torrent_text = torrent_text[:-len(".torrent")].strip()
            torrent_files.append({
                "type": "torrent",
                "title": torrent_text,
                "link": torrent_link
            })
    
    magnet_links = []
    magnet_tags = soup.find_all("a", class_="skyblue-button", href=re.compile(r'^magnet:'))
    for tag in magnet_tags:
        if tag.has_attr("href"):
            magnet_links.append({
                "type": "magnet",
                "title": "",
                "link": tag["href"].strip()
            })
    
    all_links = torrent_files + magnet_links
    overall_title = torrent_files[0]["title"] if torrent_files else "TamilMV Post"
    size = extract_size(overall_title)
    return {"title": overall_title, "size": size, "links": all_links}

def crawl_tamilmv():
    """
    Scrapes 1TamilMV website at https://www.1tamilmv.esq for recent forum posts.
    For posts with "/forums/topic/", file details are extracted using extract_tamilmv_post_details().
    """
    base_url = "https://www.1tamilmv.esq"
    torrents = []
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        post_links = [a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/')) if a.get("href")]
        post_links = list(set(post_links))
        logging.info(f"Found {len(post_links)} thread links on TamilMV homepage.")
        if not post_links:
            logging.warning("No thread links found on TamilMV homepage.")
        post_links = post_links[:15]
        for post_url in post_links:
            try:
                full_url = post_url if post_url.startswith("http") else base_url + post_url
                logging.info(f"Processing TamilMV post: {full_url}")
                if "/forums/topic/" in full_url:
                    details = extract_tamilmv_post_details(full_url, scraper)
                    torrents.append({
                        "title": details["title"],
                        "size": details["size"],
                        "links": details["links"],
                        "site": "#tamilmv"
                    })
                    logging.info(f"✅ TamilMV: {details['title']} extracted with {len(details['links'])} link(s)")
                else:
                    post_response = scraper.get(full_url, timeout=10)
                    post_response.raise_for_status()
                    post_soup = BeautifulSoup(post_response.text, "html.parser")
                    title_tag = post_soup.select_one("h1.thread-title")
                    title = title_tag.get_text(strip=True) if title_tag else "Untitled"
                    content = post_soup.get_text()
                    size = extract_size(content)
                    magnet_links = [a["href"].strip() for a in post_soup.select("a[href^='magnet:']")]
                    torrent_links = [a["href"].strip() for a in post_soup.select("a[href$='.torrent']")]
                    links = list(set(magnet_links + torrent_links))
                    torrents.append({
                        "title": title,
                        "size": size,
                        "links": [{"type": "mixed", "title": title, "link": "\n".join(links)}],
                        "site": "#tamilmv"
                    })
                    logging.info(f"✅ TamilMV Fallback: {title} - {len(links)} link(s) found")
            except Exception as e:
                logging.error(f"⚠️ TamilMV post error ({post_url}): {e}")
    except Exception as e:
        logging.error(f"❌ Failed to scrape TamilMV: {e}")
    return torrents[:5]

def crawl_nyaasi():
    url = "https://nyaa.si/?page=rss"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = entry.get("nyaa_size")
        if not size:
            summary = entry.get("summary", "")
            soup = BeautifulSoup(summary, "html.parser")
            text = soup.get_text()
            size = extract_size(text)
        if hasattr(entry, "enclosures") and entry.enclosures:
            link = entry.enclosures[0]["href"]
        else:
            link = entry.link
        if should_skip_torrent(title):
            continue
        torrents.append({
            "title": title,
            "size": size,
            "link": link,
            "site": "#nyaasi"
        })
    return torrents[:5]

def crawl_eztv():
    url = "https://eztvx.to/ezrss.xml"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        size = entry.get("torrent_contentlength", "Unknown")
        magnet_link = entry.get("torrent_magneturi", entry.link)
        if should_skip_torrent(title):
            continue
        torrents.append({
            "title": title,
            "size": size,
            "link": magnet_link,
            "site": "#eztv"
        })
    return torrents[:5]

def crawl_internet_archive():
    """
    Crawls the Internet Archive's Vintage Movie Collection RSS feed.
    Returns torrent entries for public domain movies.
    """
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
    return torrents[:5]

def crawl_rarefilmm():
    """
    Crawls RareFilmm's RSS feed for obscure and hard-to-find films.
    For each entry, fetches the full page and extracts all GOFILE links.
    Returns torrent entries with a combined GOFILE link string.
    """
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
        # Join all GOFILE links with newline for clarity
        combined_link = "\n".join(gofile_links) if gofile_links else page_url
        torrents.append({
            "title": title,
            "size": size,
            "link": combined_link,
            "site": "#rarefilmm"
        })
    return torrents[:5]

# ------------------ Bot Class ------------------
class MN_Bot(Client):
    MAX_MSG_LENGTH = 4000  # Telegram message text limit

    def __init__(self):
        super().__init__(
            "MN-Bot",
            api_id=API.ID,
            api_hash=API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = int(CHANNEL["ID"])
        self.rare_channel_id = int(RARE_CHANNEL["ID"])  # Channel for rare/internetarchive torrents
        self.last_posted_links = set()

    async def safe_send_message(self, chat_id, message, **kwargs):
        if len(message) <= self.MAX_MSG_LENGTH:
            return await self.send_message(chat_id, message, **kwargs)
        else:
            parts = [message[i:i + self.MAX_MSG_LENGTH] for i in range(0, len(message), self.MAX_MSG_LENGTH)]
            for part in parts:
                await self.send_message(chat_id, part, **kwargs)
                await asyncio.sleep(1)

    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username
        asyncio.create_task(self.auto_post_torrents())
        await self.send_message(chat_id=int(OWNER["ID"]),
                                text=f"{me.first_name} ✅✅ BOT started successfully ✅✅")
        logging.info(f"✅ {me.first_name} BOT started successfully")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_torrents(self):
        while True:
            try:
                # Aggregate torrents from all sources
                torrents = (crawl_yts() + crawl_tamilmv() + crawl_nyaasi() + crawl_eztv() +
                            crawl_internet_archive() + crawl_rarefilmm())
                new_torrents = []
                for t in torrents:
                    if t.get("site") == "#tamilmv":
                        new_torrents.append(t)
                    else:
                        if t.get("link") not in self.last_posted_links:
                            new_torrents.append(t)
                for i, torrent in enumerate(new_torrents):
                    site_tag = torrent.get("site", "#torrent")
                    # Determine target channel based on source:
                    # Internet Archive and RareFilmm go to the rare channel,
                    # others go to the default channel.
                    if site_tag in ("#internetarchive", "#rarefilmm"):
                        target_channel = self.rare_channel_id
                    else:
                        target_channel = self.channel_id

                    if site_tag == "#tamilmv":
                        for file in torrent["links"]:
                            if file["type"] != "torrent":
                                continue
                            if file["link"] in self.last_posted_links:
                                continue
                            try:
                                scraper_download = cloudscraper.create_scraper()
                                file_resp = scraper_download.get(file["link"], timeout=10)
                                file_resp.raise_for_status()
                                if not file_resp.content:
                                    logging.error(f"⚠️ Empty torrent file content for {file['title']}")
                                    continue
                                file_bytes = io.BytesIO(file_resp.content)
                                filename = file["title"].replace(" ", "_") + ".torrent"
                                await self.send_document(target_channel,
                                                         file_bytes,
                                                         file_name=filename,
                                                         caption=f"{file['title']}\n📦 {torrent['size']}\n\n#tamilmv torrent file")
                                self.last_posted_links.add(file["link"])
                                await asyncio.sleep(3)
                            except Exception as file_err:
                                logging.error(f"⚠️ Failed to send torrent file for {file['title']}: {file_err}")
                        continue
                    # For YTS and NyaaSI: if the link ends with .torrent, download and send as file.
                    if site_tag in ("#yts", "#nyaasi"):
                        if torrent["link"].lower().endswith(".torrent"):
                            try:
                                scraper_download = cloudscraper.create_scraper()
                                file_resp = scraper_download.get(torrent["link"], timeout=10)
                                file_resp.raise_for_status()
                                if not file_resp.content:
                                    logging.error(f"⚠️ Empty torrent file content for {torrent['title']}")
                                    continue
                                file_bytes = io.BytesIO(file_resp.content)
                                filename = torrent["title"].replace(" ", "_") + ".torrent"
                                await self.send_document(target_channel,
                                                         file_bytes,
                                                         file_name=filename,
                                                         caption=f"{torrent['title']}\n📦 {torrent['size']}\n\n{site_tag} torrent file")
                                self.last_posted_links.add(torrent["link"])
                                await asyncio.sleep(3)
                            except Exception as file_err:
                                logging.error(f"⚠️ Failed to send torrent file for {torrent['title']}: {file_err}")
                        else:
                            message = (f"{torrent['link']}\n\n🎬 {torrent['title']}\n"
                                       f"📦 {torrent['size']}\n\n{site_tag} powered by @MNBOTS")
                            try:
                                await self.safe_send_message(target_channel, message)
                                self.last_posted_links.add(torrent["link"])
                                await asyncio.sleep(3)
                            except errors.FloodWait as e:
                                logging.warning(f"⚠️ Flood wait: sleeping {e.value} seconds")
                                await asyncio.sleep(e.value)
                    else:
                        # For RareFilmm, send all GOFILE links in one message.
                        if site_tag == "#rarefilmm":
                            message = (f"🎬 {torrent['title']}\n📦 {torrent['size']}\n\nGOFILE Links:\n{torrent['link']}\n\n{site_tag} powered by @MNBOTS")
                            try:
                                await self.safe_send_message(target_channel, message)
                                self.last_posted_links.add(torrent["link"])
                                await asyncio.sleep(3)
                            except errors.FloodWait as e:
                                logging.warning(f"⚠️ Flood wait: sleeping {e.value} seconds")
                                await asyncio.sleep(e.value)
                        else:
                            message = (f"{torrent['link']}\n\n🎬 {torrent['title']}\n"
                                       f"📦 {torrent['size']}\n\n{site_tag} powered by @MNBOTS")
                            try:
                                await self.safe_send_message(target_channel, message)
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

# ------------------ Main ------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
