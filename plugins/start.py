from pyrogram import Client as Private_Bots
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from translation import TEXT, INLINE
import asyncio


@Private_Bots.on_message(filters.command("start"))
async def start(client: Private_Bots, msg: Message):
    await msg.reply_text(
        TEXT.START.format(msg.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=INLINE.START_BTN,
    )

