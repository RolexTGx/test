import feedparser
import re
from pyrogram import Client, filters

# Function to fetch torrents from YTS RSS feed
def crawl_yts():
    url = "https://yts.mx/rss/0/all/all/0"
    feed = feedparser.parse(url)

    torrents = []
    for entry in feed.entries:
        size = parse_size_yts(entry.description)
        if not size:
            continue
        
        download_link = entry.enclosures[0]["href"]  # Direct download link
        torrents.append(f"/l {download_link}")

    return torrents[:5]  # Limit to the latest 5 torrents

# Extract size from description (YTS format: "<b>Size:</b> 1.2 GB")
def parse_size_yts(description):
    match = re.search(r"<b>Size:</b>\s*([\d.]+\s*[GMK]B)", description)
    return match.group(1) if match else None

# Telegram command to fetch and send YTS torrents
@Client.on_message(filters.command("yts"))
async def send_torrents(client, message):
    torrents = crawl_yts()
    if torrents:
        await message.reply_text("\n".join(torrents))
    else:
        await message.reply_text("No torrents found.")
