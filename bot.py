import asyncio
import logging
import threading
import io
import re
import cloudscraper
from urllib.parse import urlparse
from flask import Flask
from bs4 import BeautifulSoup
from pyrogram import Client, errors, utils as pyroutils
from config import BOT, API, OWNER, CHANNEL

# ------------------ Logging ------------------
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ------------------ Flask App ------------------
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run_flask():
    app.run(host='0.0.0.0', port=8000)

# ------------------ Chat ID Handling ------------------
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -10099999999999

# ------------------ Utility ------------------
def extract_size(text):
    match = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1).strip() if match else "Unknown"

# ------------------ TamilMV Domain Resolver ------------------
def resolve_tamilmv_base(redirector="https://1tamilmv.com"):
    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(redirector, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        parsed = urlparse(resp.url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception as e:
        logging.warning(f"Could not resolve TamilMV via {redirector}: {e}")
        return "https://www.1tamilmv.esq"

# ------------------ TamilBlasters Domain Resolver ------------------
def resolve_tbl_base(redirector="https://www.1tamilblasters.net"):
    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(redirector, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        parsed = urlparse(resp.url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception as e:
        logging.warning(f"Could not resolve TBL via {redirector}: {e}")
        return "https://www.1tamilblasters.gold"

# ------------------ TamilMV Crawler ------------------
def extract_tamilmv_post_details(post_url, scraper):
    resp = scraper.get(post_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    torrent_files = []
    for tag in soup.find_all("a", attrs={"data-fileext": "torrent"}):
        if not tag.has_attr("href"):
            continue
        link = tag["href"].strip()
        title = tag.get_text(strip=True)
        if title.startswith("www.1TamilMV.esq - "):
            title = title[len("www.1TamilMV.esq - "):]
        if title.lower().endswith(".torrent"):
            title = title[:-8].strip()
        file_size = extract_size(title)
        torrent_files.append({
            "type": "torrent",
            "title": title,
            "link": link,
            "size": file_size
        })

    return {
        "thread_url": post_url,
        "title": torrent_files[0]["title"] if torrent_files else "TamilMV Post",
        "links": torrent_files
    }

def crawl_tamilmv():
    base_url = resolve_tamilmv_base()
    scraper = cloudscraper.create_scraper()
    torrents = []

    try:
        resp = scraper.get(base_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        post_paths = {
            a["href"]
            for a in soup.find_all("a", href=re.compile(r'/forums/topic/'))
            if a.get("href")
        }

        for path in list(post_paths)[:15]:
            full_url = path if path.startswith("http") else base_url + path
            try:
                details = extract_tamilmv_post_details(full_url, scraper)
                if details["links"]:
                    torrents.append(details)
            except Exception as e:
                logging.error(f"TamilMV error parsing {full_url}: {e}")

    except Exception as e:
        logging.error(f"Failed to fetch TamilMV homepage: {e}")

    return torrents

# ------------------ TamilBlasters Crawler ------------------
def crawl_tbl():
    base_url = resolve_tbl_base()
    scraper = cloudscraper.create_scraper()
    torrents = []

    try:
        resp = scraper.get(base_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        topic_links = [
            a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/'))
            if a.get("href")
        ]
        for rel_url in list(dict.fromkeys(topic_links))[:15]:
            try:
                full_url = rel_url if rel_url.startswith("http") else base_url + rel_url
                dresp = scraper.get(full_url, timeout=15)
                dresp.raise_for_status()
                post_soup = BeautifulSoup(dresp.text, "html.parser")

                torrent_tags = post_soup.find_all("a", attrs={"data-fileext": "torrent"})
                file_links = []
                for tag in torrent_tags:
                    href = tag.get("href")
                    if not href:
                        continue
                    link = href.strip()
                    title = tag.get_text(strip=True).replace("www.1TamilBlasters.red - ", "").rstrip(".torrent").strip()
                    size = extract_size(title)

                    file_links.append({
                        "type": "torrent",
                        "title": title,
                        "link": link,
                        "size": size
                    })

                if file_links:
                    torrents.append({
                        "topic_url": full_url,
                        "title": file_links[0]["title"],
                        "links": file_links
                    })

            except Exception as e:
                logging.error(f"TBL error parsing topic {rel_url}: {e}")

    except Exception as e:
        logging.error(f"Failed to fetch TBL homepage: {e}")

    return torrents

# ------------------ Telegram Bot ------------------
class MN_Bot(Client):
    MAX_MSG_LENGTH = 4000

    def __init__(self):
        super().__init__(
            "MN-Bot",
            api_id=API.ID,
            api_hash=API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16
        )
        self.channel_id = int(CHANNEL.ID)
        self.last_posted = set()
        self.seen_threads = set()
        self.seen_tbl_topics = set()

    async def safe_send_message(self, chat_id, text, **kwargs):
        for chunk in (text[i:i+self.MAX_MSG_LENGTH] for i in range(0, len(text), self.MAX_MSG_LENGTH)):
            await self.send_message(chat_id, chunk, **kwargs)
            await asyncio.sleep(1)

    async def _send_torrent(self, file, tag):
        link = file["link"]
        if link in self.last_posted:
            return
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(link, timeout=15)
            resp.raise_for_status()
            bio = io.BytesIO(resp.content)
            filename = f"{file['title'].replace(' ', '_')}.torrent"
            caption = f"{file['title']}\n📦 {file['size']}\n\n{tag}"
            await self.send_document(
                self.channel_id,
                bio,
                file_name=filename,
                caption=caption
            )
            self.last_posted.add(link)
            await asyncio.sleep(3)
        except Exception as ex:
            logging.error(f"Failed to send {file['title']}: {ex}")

    async def auto_post_torrents(self):
        while True:
            try:
                # TamilMV
                for thread in crawl_tamilmv():
                    tid = thread["thread_url"]
                    if tid not in self.seen_threads:
                        for file in thread["links"]:
                            await self._send_torrent(file, "#tamilmv")
                        self.seen_threads.add(tid)
                    else:
                        for file in thread["links"]:
                            await self._send_torrent(file, "#tamilmv")

                # TamilBlasters
                for post in crawl_tbl():
                    tid = post["topic_url"]
                    if tid not in self.seen_tbl_topics:
                        for file in post["links"]:
                            await self._send_torrent(file, "#tbl")
                        self.seen_tbl_topics.add(tid)
                    else:
                        for file in post["links"]:
                            await self._send_torrent(file, "#tbl")

            except Exception as e:
                logging.error(f"auto_post_torrents error: {e}")

            await asyncio.sleep(900)

    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        await self.send_message(int(OWNER.ID), f"{me.first_name} ✅ BOT started")
        logging.info("MN-Bot started")
        asyncio.create_task(self.auto_post_torrents())

    async def stop(self, *args):
        await super().stop()
        logging.info("MN-Bot stopped")

# ------------------ Entry Point ------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    MN_Bot().run()
