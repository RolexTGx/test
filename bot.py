import asyncio
import feedparser
import re
import logging
from pyrogram import Client
from config import BOT, API, WEB, OWNER, CHANNEL  # Ensure CHANNEL is added in config

# Logging setup
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

class Private_Bots(Client):

    def __init__(self):
        super().__init__(
            "Forward-Tag-Remover",
            API.ID,
            API.HASH,
            bot_token=BOT.TOKEN,
            plugins=dict(root="plugins"),
            workers=16,
        )
        self.channel_id = int(CHANNEL.ID)  # Ensure your config has CHANNEL.ID
        self.last_posted_links = set()  # To track previously posted torrents

    async def start(self):
        await super().start()
        me = await self.get_me()
        if me.username:
            BOT.USERNAME = f"@{me.username}"
        self.mention = me.mention
        self.username = me.username

        # Start background task for auto-posting torrents
        asyncio.create_task(self.auto_post_yts())

        await self.send_message(
            chat_id=int(OWNER.ID),
            text=f"{me.first_name} ✅✅ BOT started successfully ✅✅",
        )

        logging.info(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped 🙄")

    async def auto_post_yts(self):
        """Fetch and send new YTS torrents every 30 minutes"""
        while True:
            try:
                torrents = crawl_yts()
                new_torrents = [t for t in torrents if t not in self.last_posted_links]
                
                if new_torrents:
                    for torrent in new_torrents:
                        await self.send_message(self.channel_id, torrent)
                    self.last_posted_links.update(new_torrents)

                logging.info("✅ Auto-posted new YTS torrents")
            except Exception as e:
                logging.error(f"⚠️ Error in auto_post_yts: {e}")

            await asyncio.sleep(1800)  # Wait 30 minutes before checking again

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        download_link = entry.enclosures[0]["href"]  # Direct download link
        torrents.append(f"/l {download_link}")

    return torrents[:5]  # Limit to the latest 5 torrents

# Start the bot
Private_Bots().run()
