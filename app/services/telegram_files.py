from __future__ import annotations
import io
from aiogram import Bot

async def download_photo_bytes(bot: Bot, file_id: str) -> bytes:
    f = await bot.get_file(file_id)
    bio = io.BytesIO()
    await bot.download_file(f.file_path, destination=bio)
    return bio.getvalue()
