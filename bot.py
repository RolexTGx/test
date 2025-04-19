import asyncio
import logging
import threading
import io
import re
import cloudscraper
from flask import Flask
from bs4 import BeautifulSoup
from pyrogram import Client, errors
from config import BOT, API, OWNER, CHANNEL

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

# ------------------ Utility Function ------------------
def extract_size(text):
    match = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|KB))", text, re.IGNORECASE)
    return match.group(1).upper().replace(' ', '') if match else "Unknown"

# ------------------ TamilMV Crawler ------------------
def extract_tamilmv_post_details(post_url, scraper):
    response = scraper.get(post_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    torrent_files = []
    for tag in soup.find_all("a", attrs={"data-fileext": "torrent"}):
        if not tag.has_attr("href"):
            continue
        link = tag["href"].strip()
        title = tag.get_text(strip=True)
        prefix = "www.1TamilMV.esq - "
        if title.startswith(prefix):
            title = title[len(prefix):]
        if title.lower().endswith(".torrent"):
            title = title[:-len(".torrent")].strip()

        file_size = extract_size(title)
        torrent_files.append({
            "type": "torrent",
            "title": title,
            "link": link,
            "size": file_size,
        })

    overall_title = torrent_files[0]["title"] if torrent_files else "TamilMV Post"
    overall_size = extract_size(overall_title)
    return {
        "thread_url": post_url,
        "title": overall_title,
        "size": overall_size,
        "links": torrent_files,
    }

def crawl_tamilmv():
    base_url = "https://www.1tamilmv.esq"
    scraper = cloudscraper.create_scraper()
    torrents = []

    try:
        resp = scraper.get(base_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        post_paths = {
            a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/'))
            if a.get("href")
        }
        for path in list(post_paths)[:15]:
            full_url = path if path.startswith("http") else base_url + path
            try:
                details = extract_tamilmv_post_details(full_url, scraper)
                torrents.append(details)
            except Exception as e:
                logging.error(f"Error scraping TamilMV {full_url}: {e}")
    except Exception as e:
        logging.error(f"Failed to load TamilMV homepage: {e}")

    return torrents

# ------------------ TamilBlasters Crawler ------------------
def crawl_tbl():
    base_url = "https://www.1tamilblasters.gold"
    torrents = []
    scraper = cloudscraper.create_scraper()

    try:
        resp = scraper.get(base_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        topic_links = [
            a["href"] for a in soup.find_all("a", href=re.compile(r'/forums/topic/'))
            if a.get("href")
        ]
        for rel_url in list(dict.fromkeys(topic_links))[:15]:
            try:
                full_url = rel_url if rel_url.startswith("http") else base_url + rel_url
                dresp = scraper.get(full_url)
                dresp.raise_for_status()
                post_soup = BeautifulSoup(dresp.text, "html.parser")

                torrent_tags = post_soup.find_all("a", attrs={"data-fileext": "torrent"})
                file_links = []
                for tag in torrent_tags:
                    href = tag.get("href")
                    if not href:
                        continue
                    link = href.strip()
                    raw_text = tag.get_text(strip=True)
                    title = raw_text.replace("www.1TamilBlasters.red - ", "").rstrip(".torrent").strip()
                    size = extract_size(raw_text)

                    file_links.append({
                        "type": "torrent",
                        "title": title,
                        "link": link,
                        "size": size
                    })

                if file_links:
                    torrents.append({
                        "thread_url": full_url,
                        "title": file_links[0]["title"],
                        "size": file_links[0]["size"],
                        "links": file_links
                    })

            except Exception as post_err:
                logging.error(f"TBL post error {rel_url}: {post_err}")

    except Exception as e:
        logging.error(f"TBL homepage error: {e}")

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
            workers=16
        )
        self.channel_id = int(CHANNEL.ID)
        self.tbl_seen = set()
        self.tmv_seen = set()
        self.last_posted = set()

    async def safe_send_message(self, chat_id, text, **kwargs):
        if len(text) <= self.MAX_MSG_LENGTH:
            return await self.send_message(chat_id, text, **kwargs)
        for i in range(0, len(text), self.MAX_MSG_LENGTH):
            await self.send_message(chat_id, text[i:i+self.MAX_MSG_LENGTH], **kwargs)
            await asyncio.sleep(1)

    async def start(self):
        await super().start()
        me = await self.get_me()
        BOT.USERNAME = f"@{me.username}"
        asyncio.create_task(self.auto_post_torrents())
        await self.send_message(int(OWNER.ID), f"{me.first_name} ✅ BOT started")
        logging.info("Bot started")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot stopped")

    async def auto_post_torrents(self):
        while True:
            try:
                for source, crawl_func, seen_set, tag in [
                    ("TamilMV", crawl_tamilmv, self.tmv_seen, "#tamilmv"),
                    ("TamilBlasters", crawl_tbl, self.tbl_seen, "#tbl")
                ]:
                    threads = crawl_func()
                    for thread in threads:
                        tid = thread["thread_url"]
                        if tid not in seen_set:
                            for file in thread["links"]:
                                await self._send_torrent(file, tag)
                            seen_set.add(tid)
                        else:
                            for file in thread["links"]:
                                if file["link"] not in self.last_posted:
                                    await self._send_torrent(file, tag)
                logging.info("Sleeping for 15 minutes…")
            except Exception as e:
                logging.error(f"auto_post_torrents error: {e}")
            await asyncio.sleep(900)

    async def _send_torrent(self, file, tag):
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(file["link"])
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
            self.last_posted.add(file["link"])
            await asyncio.sleep(3)
        except Exception as ex:
            logging.error(f"Failed to send {file['title']}: {ex}")

# ------------------ Main ------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    MN_Bot().run()
