import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from app.config import settings
from app.handlers.card_flow import router as card_router
from app.services.prompts import PromptsRepo, PromptConfigError


logger = logging.getLogger(__name__)

async def main():
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    try:
        prompts = PromptsRepo(settings.PROMPTS_PATH)
        prompts.reload()

        dp.include_router(card_router)
        await dp.start_polling(bot, prompts=prompts)
    except PromptConfigError as exc:
        logger.exception("Prompt config error: %s", exc)
        raise RuntimeError(f"Invalid prompts config: {exc}") from exc
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())


