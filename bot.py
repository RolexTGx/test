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
    Skips torrents marked as 4K/2160p.
    This function is used for all sources except where explicitly overridden.
    """
    if "2160p" in title or "4K" in title:
        logging.info(f"❌ Skipping torrent: {title}")
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

def extract_tamilmv_post_details(post_url, scraper):
    """
    Given a forum post URL from 1TamilMV, this function extracts:
     - The torrent file's display text (which includes the file name and size),
     - Downloads the torrent attachment URL, and
     - Extracts the magnet link.
    It returns a dict with:
      - title: the cleaned file name,
      - size: extracted from the torrent text,
      - link: a newline-separated combination of the torrent attachment URL and the magnet link.
    """
    response = scraper.get(post_url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Look for the torrent attachment link (for the torrent file)
    torrent_tag = soup.find("a", attrs={"data-fileext": "torrent"})
    if torrent_tag and torrent_tag.has_attr("href"):
        torrent_link = torrent_tag["href"].strip()
        # Get the displayed torrent text which contains the file name and size.
        torrent_text = torrent_tag.get_text(strip=True)
        # Remove known prefix "www.1TamilMV.esq - " if present.
        prefix = "www.1TamilMV.esq - "
        if torrent_text.startswith(prefix):
            torrent_text = torrent_text[len(prefix):]
        # Remove trailing ".torrent" if present.
        if torrent_text.lower().endswith(".torrent"):
            torrent_text = torrent_text[:-len(".torrent")].strip()
    else:
        torrent_link = ""
        torrent_text = "No file details"

    # Use the torrent text as the title (which should contain the file name)
    title = torrent_text
    # Extract size from the torrent text
    size = extract_size(torrent_text)
    
    # Extract magnet link from the post using class "skyblue-button"
    magnet_tag = soup.find("a", class_="skyblue-button", href=re.compile(r'^magnet:'))
    magnet_link = magnet_tag["href"].strip() if magnet_tag and magnet_tag.has_attr("href") else ""
    
    # Build final link string: we'll keep torrent_link and magnet_link separately (separated by newline)
    links = []
    if torrent_link:
        links.append(torrent_link)
    if magnet_link:
        links.append(magnet_link)
    final_link = "\n".join(links) if links else post_url
    return {"title": title, "size": size, "link": final_link}

def crawl_tamilmv():
    """
    Scrapes the 1TamilMV website at https://www.1tamilmv.esq and extracts recent forum topic links.
    If a link contains "/forums/topic/", extract file details using extract_tamilmv_post_details().
    (The 4K/2160p skip is not applied for TamilMV.)
    """
    base_url = "https://www.1tamilmv.esq"
    torrents = []
    scraper = cloudscraper.create_scraper()  # Cloudflare bypass

    try:
        response = scraper.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for all <a> tags with href containing "/forums/topic/"
        post_links = [a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/')) if a.get("href")]
        post_links = list(set(post_links))
        logging.info(f"Found {len(post_links)} thread links on TamilMV homepage.")
        if not post_links:
            logging.warning("No thread links found on TamilMV homepage. Check the selector or site structure.")
        post_links = post_links[:15]  # Limit to 15 posts
        
        for post_url in post_links:
            try:
                full_url = post_url if post_url.startswith("http") else base_url + post_url
                logging.info(f"Processing TamilMV post: {full_url}")
                if "/forums/topic/" in full_url:
                    details = extract_tamilmv_post_details(full_url, scraper)
                    torrents.append({
                        "title": details["title"],
                        "size": details["size"],
                        "link": details["link"],
                        "site": "#tamilmv"
                    })
                    logging.info(f"✅ TamilMV Forum: {details['title']} extracted with size {details['size']}")
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
                    final_link = "\n".join(links) if links else full_url
                    
                    torrents.append({
                        "title": title,
                        "size": size,
                        "link": final_link,
                        "site": "#tamilmv"
                    })
                    logging.info(f"✅ TamilMV: {title} - {len(links)} link(s) found")
            except Exception as e:
                logging.error(f"⚠️ TamilMV post error ({post_url}): {e}")
    except Exception as e:
        logging.error(f"❌ Failed to scrape TamilMV: {e}")

    return torrents[:15]

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
        torrents.append({"title": title, "size": size, "link": link, "site": "#nyaasi"})
    return torrents[:15]

def crawl_eztv():
    """
    EZTV RSS feed is namespaced. Feedparser converts torrent-specific tags into keys with underscores.
    For example, <torrent:contentLength> becomes entry["torrent_contentlength"].
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
        torrents.append({"title": title, "size": size, "link": magnet_link, "site": "#eztv"})
    return torrents[:15]

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
        self.channel_id = int(CHANNEL.ID)
        self.last_posted_links = set()

    async def safe_send_message(self, chat_id, message, **kwargs):
        """Send a message, splitting into chunks if the text is too long."""
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
        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅"
        )
        logging.info(f"✅ {me.first_name} BOT started successfully")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_torrents(self):
        while True:
            try:
                torrents = (
                    crawl_yts() +
                    crawl_tamilmv() +
                    crawl_nyaasi() +
                    crawl_eztv()
                )
                new_torrents = [t for t in torrents if t["link"] not in self.last_posted_links]
                for i, torrent in enumerate(new_torrents):
                    site_tag = torrent.get("site", "#torrent")
                    if site_tag == "#tamilmv":
                        links_list = [l.strip() for l in torrent["link"].split("\n") if l.strip()]
                        # For TamilMV, send torrent file and magnet link separately.
                        for l in links_list:
                            if l.lower().endswith(".torrent"):
                                try:
                                    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
                                    file_resp = requests.get(l, headers=headers, timeout=10)
                                    file_resp.raise_for_status()
                                    file_bytes = io.BytesIO(file_resp.content)
                                    # Use the extracted title as file name
                                    filename = torrent["title"].replace(" ", "_") + ".torrent"
                                    await self.send_document(
                                        self.channel_id, file_bytes, file_name=filename,
                                        caption=f"{torrent['title']}\n📦 {torrent['size']}\n\n#tamilmv torrent file"
                                    )
                                    await asyncio.sleep(3)
                                except Exception as file_err:
                                    logging.error(f"⚠️ Failed to send torrent file for {torrent['title']}: {file_err}")
                            elif l.lower().startswith("magnet:"):
                                try:
                                    msg = f"{l}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n#tamilmv magnet link"
                                    await self.safe_send_message(self.channel_id, msg)
                                    await asyncio.sleep(3)
                                except errors.FloodWait as e:
                                    logging.warning(f"⚠️ Flood wait: sleeping {e.value} seconds")
                                    await asyncio.sleep(e.value)
                        self.last_posted_links.add(torrent["link"])
                        continue
                    # For other sources, send a combined message.
                    message = (
                        f"{torrent['link']}\n\n🎬 {torrent['title']}\n📦 {torrent['size']}\n\n"
                        f"{site_tag} powered by @MNBOTS"
                    )
                    try:
                        await self.safe_send_message(self.channel_id, message)
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
