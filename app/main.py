import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers.card_flow import router as card_router
from app.services.prompts import PromptsRepo

async def main():
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    prompts = PromptsRepo(settings.PROMPTS_PATH)
    prompts.reload()

    dp.include_router(card_router)
    await dp.start_polling(bot, prompts=prompts)

if __name__ == "__main__":
    asyncio.run(main())
