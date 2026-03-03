from __future__ import annotations
from aiogram import Bot

async def download_photo_bytes(bot: Bot, file_id: str) -> bytes:
    f = await bot.get_file(file_id)
    buf = bytearray()
    await bot.download_file(f.file_path, destination=buf)
    return bytes(buf)
