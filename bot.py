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

pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -10099999999999

logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

def extract_size(text):
    match = re.search(r"(\d+(\.\d+)?\s*(GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"

def should_skip_torrent(title):
    return "2160p" in title or "4K" in title

def extract_all_rarefilmm_gofile_links(page_url, scraper):
    try:
        response = scraper.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links = [a["href"].strip() for a in soup.find_all("a", href=re.compile(r"gofile\.io")) if a.has_attr("href")]
        return links
    except Exception as e:
        logging.error(f"Error extracting GOFILE links from {page_url}: {e}")
        return []

def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        if should_skip_torrent(title):
            continue
        summary = entry.get("summary", "")
        size = extract_size(summary)
        link = entry.enclosures[0]["href"]
        torrents.append({"title": title, "size": size, "link": link, "site": "#yts"})
    return torrents[:5]

def crawl_internet_archive():
    url = "https://archive.org/services/collection-rss.php?collection=feature_films"
    feed = feedparser.parse(url)
    torrents = []
    for entry in feed.entries:
        title = entry.title
        summary = entry.get("summary", "")
        size = extract_size(summary)
        link = entry.enclosures[0]["href"] if entry.enclosures else entry.link
        torrents.append({"title": title, "size": size, "link": link, "site": "#internetarchive"})
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
        torrents.append({"title": title, "size": size, "link": combined_link, "site": "#rarefilmm"})
    return torrents[:25]

def crawl_publicdomain():
    homepage = "https://www.publicdomaintorrents.info/"
    torrents = []
    try:
        response = requests.get(homepage, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for movie_link in soup.find_all("a", href=re.compile(r'^nshowmovie\.html\?movieid=\d+'))[:5]:
            title = movie_link.get_text(strip=True) or "Unknown Title"
            detail_url = homepage + movie_link["href"]
            try:
                detail_page = requests.get(detail_url, timeout=10)
                detail_page.raise_for_status()
                detail_soup = BeautifulSoup(detail_page.text, "html.parser")
                for tag in detail_soup.find_all("a", href=re.compile(r'btdownload\.php\?type=torrent')):
                    torrent_link = tag["href"]
                    if torrent_link.startswith("/"):
                        torrent_link = "http://www.publicdomaintorrents.com" + torrent_link
                    size = extract_size(tag.get_text(strip=True))
                    torrents.append({
                        "title": f"{title} - {tag.get_text(strip=True)}",
                        "size": size,
                        "link": torrent_link,
                        "site": "#publicdomaintorrents"
                    })
            except Exception as e:
                logging.error(f"Error loading {detail_url}: {e}")
    except Exception as e:
        logging.error(f"Error in crawl_publicdomain: {e}")
    return torrents

def crawl_tbl():
    base_url = "https://www.1tamilblasters.gold"
    torrents = []
    scraper = cloudscraper.create_scraper()

    try:
        response = scraper.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        topic_links = [a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/')) if a.get("href")]
        topic_links = list(set(topic_links))[:15]

        for post_url in topic_links:
            try:
                full_url = post_url if post_url.startswith("http") else base_url + post_url
                detail_resp = scraper.get(full_url, timeout=10)
                detail_resp.raise_for_status()
                post_soup = BeautifulSoup(detail_resp.text, "html.parser")

                torrent_tags = post_soup.find_all("a", attrs={"data-fileext": "torrent"})
                file_links = []
                for tag in torrent_tags:
                    if not tag.has_attr("href"):
                        continue
                    link = tag["href"].strip()
                    raw_text = tag.get_text(strip=True)

                    title = raw_text.replace("www.1TamilBlasters.red - ", "")
                    if title.lower().endswith(".torrent"):
                        title = title[:-len(".torrent")].strip()

                    file_links.append({
                        "type": "torrent",
                        "title": title,
                        "link": link
                    })

                if file_links:
                    torrents.append({
                        "title": file_links[0]["title"],
                        "size": extract_size(file_links[0]["title"]),
                        "links": file_links,
                        "site": "#tbl"
                    })

            except Exception as post_err:
                logging.error(f"⚠️ Failed to parse topic: {post_url} | {post_err}")

    except Exception as e:
        logging.error(f"❌ Failed to fetch TBL homepage: {e}")

    return torrents

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
            for i in range(0, len(message), self.MAX_MSG_LENGTH):
                await self.send_message(chat_id, message[i:i + self.MAX_MSG_LENGTH], **kwargs)
                await asyncio.sleep(1)

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
                new_torrents = []
                for t in torrents:
                    if t.get("site") == "#tbl":
                        new_torrents.append(t)
                    elif t.get("link") not in self.last_posted_links:
                        new_torrents.append(t)

                for t in new_torrents:
                    site_tag = t.get("site", "#torrent")
                    if site_tag == "#tbl":
                        for file in t["links"]:
                            if file["type"] != "torrent" or file["link"] in self.last_posted_links:
                                continue
                            try:
                                scraper = cloudscraper.create_scraper()
                                file_resp = scraper.get(file["link"], timeout=10)
                                file_resp.raise_for_status()
                                if not file_resp.content:
                                    continue
                                file_bytes = io.BytesIO(file_resp.content)
                                filename = file["title"].replace(" ", "_") + ".torrent"
                                await self.send_document(self.channel_id, file_bytes, file_name=filename,
                                                         caption=f"{file['title']}\n📦 {t['size']}\n\n#tbl torrent file")
                                self.last_posted_links.add(file["link"])
                                await asyncio.sleep(3)
                            except Exception as e:
                                logging.error(f"Error sending TBL file: {e}")
                        continue

                    if t["link"].lower().endswith(".torrent"):
                        try:
                            scraper = cloudscraper.create_scraper()
                            resp = scraper.get(t["link"], timeout=10)
                            resp.raise_for_status()
                            file_bytes = io.BytesIO(resp.content)
                            filename = t["title"].replace(" ", "_") + ".torrent"
                            await self.send_document(self.channel_id, file_bytes, file_name=filename,
                                                     caption=f"{t['title']}\n📦 {t['size']}\n\n{site_tag} torrent file")
                            self.last_posted_links.add(t["link"])
                            await asyncio.sleep(3)
                        except Exception as e:
                            logging.error(f"Error sending file: {e}")
                    else:
                        message = f"{t['link']}\n\n🎬 {t['title']}\n📦 {t['size']}\n\n{site_tag} powered by @MNBOTS"
                        try:
                            await self.safe_send_message(self.channel_id, message)
                            self.last_posted_links.add(t["link"])
                            await asyncio.sleep(3)
                        except errors.FloodWait as e:
                            await asyncio.sleep(e.value)

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
        await self.send_message(chat_id=OWNER.ID, text=f"{me.first_name} ✅✅ BOT started successfully ✅✅")
        logging.info(f"✅ {me.first_name} BOT started successfully")
        asyncio.create_task(self.auto_post_torrents())

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
