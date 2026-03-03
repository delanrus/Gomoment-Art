from __future__ import annotations
from pathlib import Path
import tempfile
from arq.connections import RedisSettings
from aiogram import Bot
from aiogram.types import FSInputFile

from app.config import settings
from app.services.prompts import PromptsRepo
from app.services.openai_images import OpenAIImageClient

prompts = PromptsRepo(settings.PROMPTS_PATH)
openai_images = OpenAIImageClient(settings.OPENAI_API_KEY)

async def generate_card(ctx, payload: dict):
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    chat_id = payload["telegram_chat_id"]
    photo_file_id = payload["photo_file_id"]
    holiday_key = payload["holiday_key"]
    user_phrase = payload["user_phrase"]
    fmt = payload["fmt"]

    file = await bot.get_file(photo_file_id)
    with tempfile.TemporaryDirectory() as td:
        src_path = Path(td) / "input.jpg"
        await bot.download_file(file.file_path, destination=src_path)

        prompt, size, model = prompts.render_prompt(holiday_key, user_phrase, fmt)
        quality = prompts.get_holiday(holiday_key).default_quality

        img_bytes = openai_images.edit_image(
            image_bytes=src_path.read_bytes(),
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
        )

        out_path = Path(td) / "card.png"
        out_path.write_bytes(img_bytes)

        await bot.send_photo(chat_id, photo=FSInputFile(out_path), caption="Готово 🎉")

    await bot.session.close()

class WorkerSettings:
    functions = [generate_card]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
