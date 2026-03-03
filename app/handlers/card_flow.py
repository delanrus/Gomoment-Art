import re
import logging
import asyncio

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.states import CardFlow
from app.services.prompts import PromptsRepo
from app.services.telegram_files import download_photo_bytes
from app.services.openai_images import OpenAIImageClient, OpenAIBillingLimitError
from app.config import settings
from app.services.welcome_media import WelcomeMediaStore, resolve_welcome_media

router = Router()
logger = logging.getLogger(__name__)

# простой “антидубль”: один пользователь = одна генерация одновременно
IN_FLIGHT: set[int] = set()


async def send_welcome_message(m: Message):
    text = (
        "Привет👋 Меня зовут Руслан и я помогу вам удивить близких и создать им персональную открытку по вашей фотографии!\n\n"
        "Идея простая: Вы присылаете фото — я превращаю его в стильную праздничную открытку.\n\n"
        "К 8 марта💐\n"
        "Ко дню рождения🎉\n"
        "На годовщину💞\n"
        "И к любому другому празднику.\n\n"
        "Присылай скорее фотографию того, кого хочешь поздравить!📷"
    )
    media = resolve_welcome_media()

    if not media:
        await m.answer(text)
        return

    media_type, media_file_id = media
    if media_type == "photo":
        await m.answer_photo(media_file_id, caption=text)
        return

    await m.answer_video(media_file_id, caption=text)


def kb_holidays(repo: PromptsRepo):
    kb = InlineKeyboardBuilder()
    for h in repo.list_holidays():
        kb.button(text=h.title, callback_data=f"holiday:{h.key}")
    kb.adjust(1)
    return kb.as_markup()


def kb_formats():
    kb = InlineKeyboardBuilder()
    kb.button(text="3:4 (портрет)", callback_data="fmt:3:4")
    kb.button(text="4:3 (горизонт)", callback_data="fmt:4:3")
    kb.adjust(1)
    return kb.as_markup()


def kb_phrases(repo: PromptsRepo, holiday_key: str):
    phrases = repo.list_phrases(holiday_key)
    kb = InlineKeyboardBuilder()
    for i, text in enumerate(phrases[:12]):
        kb.button(text=text, callback_data=f"phrase:{i}")
    kb.button(text="✍️ Своя фраза", callback_data="phrase:custom")
    kb.adjust(1)
    return kb.as_markup()




def _is_admin(user_id: int | None) -> bool:
    if user_id is None:
        return False

    allowed_ids = {settings.ADMIN_USER_ID, settings.TELEGRAM_BOT_ID}
    return user_id in allowed_ids



def _is_set_welcome_media_caption(caption: str | None) -> bool:
    if not caption:
        return False

    match = re.match(r"^/welcome(?:@(?P<mention>\w+))?(?:\s|$)", caption)
    if not match:
        return False

    mention = match.group("mention")
    if mention is None:
        return True

    if mention.isdigit() and settings.TELEGRAM_BOT_ID is not None:
        return int(mention) == settings.TELEGRAM_BOT_ID

    return True


@router.message(StateFilter("*"), F.photo | F.video, lambda m: _is_set_welcome_media_caption(m.caption))
async def set_welcome_media(m: Message):
    if not _is_admin(m.from_user.id if m.from_user else None):
        await m.answer("Эта команда доступна только администратору.")
        return

    if m.photo:
        media_type = "photo"
        file_id = m.photo[-1].file_id
    elif m.video:
        media_type = "video"
        file_id = m.video.file_id
    else:
        await m.answer("Пришли фото или видео вместе с командой /welcome")
        return

    WelcomeMediaStore().save(media_type, file_id)
    await m.answer("Сохранил приветственное медиа ✅")




@router.message(StateFilter("*"), Command("welcome"))
async def set_welcome_media_prompt(m: Message):
    if not _is_admin(m.from_user.id if m.from_user else None):
        await m.answer(
            "Команда /welcome доступна только администратору.\n"
            "Проверь, что ADMIN_USER_ID в .env равен твоему Telegram user id."
        )
        return

    await m.answer(
        "Отправь фото или видео с подписью /welcome.\n"
        "Например: прикрепи фото и в подписи напиши /welcome"
    )

@router.message(StateFilter("*"), Command("clear_welcome_media"))
async def clear_welcome_media(m: Message):
    if not _is_admin(m.from_user.id if m.from_user else None):
        await m.answer("Эта команда доступна только администратору.")
        return

    WelcomeMediaStore().clear()
    await m.answer("Приветственное медиа очищено. Будет текст по умолчанию.")


@router.message(StateFilter("*"), Command("welcome_help"))
async def welcome_media_help(m: Message):
    if not _is_admin(m.from_user.id if m.from_user else None):
        await m.answer(
            "Подсказка доступна только администратору.\n"
            "Проверь, что ADMIN_USER_ID в .env равен твоему Telegram user id."
        )
        return

    await m.answer(
        "Как выбрать медиа для приветствия:\n"
        "1) Отправь фото/видео с подписью /welcome\n"
        "2) Чтобы убрать медиа: /clear\n"
        "3) После этого /start отправит выбранное медиа с текстом."
    )


@router.message(StateFilter("*"), Command("help"))
async def help_command(m: Message):
    await m.answer(
        "Этот бот помогает создавать праздничные открытки из твоих фотографий.\n"
        "Отправь фото, выбери праздник, фразу и формат — бот сгенерирует готовую открытку."
    )

@router.message(F.text == "/start")
async def start(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CardFlow.waiting_photo)
    await send_welcome_message(m)


@router.message(CardFlow.waiting_photo, F.photo)
async def got_photo(m: Message, state: FSMContext, prompts: PromptsRepo):
    photo = m.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await state.set_state(CardFlow.waiting_holiday)
    await m.answer("Выбери праздник:", reply_markup=kb_holidays(prompts))


@router.message(CardFlow.waiting_photo)
async def no_photo(m: Message):
    await m.answer("Нужно отправить фото (не файл). Попробуй ещё раз 🙂")


@router.callback_query(CardFlow.waiting_holiday, F.data.startswith("holiday:"))
async def pick_holiday(c: CallbackQuery, state: FSMContext, prompts: PromptsRepo):
    await c.answer()
    holiday_key = c.data.split(":", 1)[1]
    if not prompts.has_holiday(holiday_key):
        await c.message.edit_text("Не нашёл такой праздник. Нажми /start и выбери снова.")
        await state.clear()
        return

    await state.update_data(holiday_key=holiday_key)
    await state.set_state(CardFlow.waiting_phrase)

    phrases = prompts.list_phrases(holiday_key)
    if phrases:
        await c.message.edit_text("Выбери фразу или напиши свою:", reply_markup=kb_phrases(prompts, holiday_key))
    else:
        await c.message.edit_text("Напиши фразу (2–60 символов):")


@router.callback_query(CardFlow.waiting_phrase, F.data.startswith("phrase:"))
async def pick_phrase_button(c: CallbackQuery, state: FSMContext, prompts: PromptsRepo):
    await c.answer()
    pick = c.data.split(":", 1)[1]
    data = await state.get_data()
    holiday_key = data.get("holiday_key")

    if not holiday_key or not prompts.has_holiday(holiday_key):
        await c.message.edit_text("Сессия устарела. Нажми /start и начни заново 🙂")
        await state.clear()
        return

    if pick == "custom":
        await c.message.edit_text("Ок! Напиши свою фразу (2–60 символов):")
        return

    if not pick.isdigit():
        await c.answer("Некорректный выбор фразы. Попробуй ещё раз.", show_alert=True)
        return

    idx = int(pick)
    phrases = prompts.list_phrases(holiday_key)
    if idx < 0 or idx >= len(phrases):
        await c.answer("Фраза не найдена. Выбери ещё раз.", show_alert=True)
        return

    await state.update_data(user_phrase=phrases[idx])
    await state.set_state(CardFlow.waiting_format)
    await c.message.edit_text("Выбери формат:", reply_markup=kb_formats())


@router.message(CardFlow.waiting_phrase, F.text)
async def pick_phrase_text(m: Message, state: FSMContext):
    phrase = (m.text or "").strip()
    if len(phrase) < 2 or len(phrase) > 60:
        await m.answer("Сделай фразу покороче (2–60 символов). Напиши ещё раз:")
        return
    await state.update_data(user_phrase=phrase)
    await state.set_state(CardFlow.waiting_format)
    await m.answer("Выбери формат:", reply_markup=kb_formats())


@router.callback_query(CardFlow.waiting_format, F.data.startswith("fmt:"))
async def pick_format(c: CallbackQuery, state: FSMContext, prompts: PromptsRepo):
    user_id = c.from_user.id
    if user_id in IN_FLIGHT:
        await c.answer("Я уже делаю тебе открытку 🙂 Подожди немного.", show_alert=True)
        return

    fmt = c.data.split(":", 1)[1]  # "3:4" или "4:3"
    if not prompts.has_format(fmt):
        await c.answer("Некорректный формат. Выбери формат из кнопок.", show_alert=True)
        return

    data = await state.get_data()
    required_fields = ("photo_file_id", "holiday_key", "user_phrase")
    if any(not data.get(k) for k in required_fields):
        await c.message.edit_text("Сессия устарела. Нажми /start и начни заново 🙂")
        await state.clear()
        return

    if not prompts.has_holiday(data["holiday_key"]):
        await c.message.edit_text("Праздник больше недоступен. Нажми /start и выбери заново.")
        await state.clear()
        return

    await state.clear()

    await c.message.edit_text("Принято ✅ Генерирую открытку…")

    IN_FLIGHT.add(user_id)
    try:
        # 1) скачиваем фото из Telegram
        photo_bytes = await download_photo_bytes(c.bot, data["photo_file_id"])

        # 2) промпт из YAML
        prompt, size, model = prompts.render_prompt(
            data["holiday_key"],
            data["user_phrase"],
            fmt
        )
        quality = prompts.get_holiday(data["holiday_key"]).default_quality

        # 3) OpenAI image edit
        client = OpenAIImageClient(settings.OPENAI_API_KEY)
        out_bytes = await asyncio.to_thread(
            client.edit_image,
            image_bytes=photo_bytes,
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
        )

        # 4) отправка результата
        await c.message.answer_photo(
            BufferedInputFile(out_bytes, filename="card.png"),
            caption="Готово 🎉"
        )

    except OpenAIBillingLimitError:
        logger.error(
            "Card generation blocked by OpenAI billing limit for user=%s holiday=%s format=%s",
            user_id,
            data.get("holiday_key"),
            fmt,
        )
        await c.message.answer(
            "Сервис временно недоступен из-за лимита биллинга 😕\n"
            "Мы уже занимаемся этим. Попробуй позже или напиши в поддержку: t.me/delanrus"
        )
    except Exception:
        logger.exception(
            "Card generation failed for user=%s holiday=%s format=%s",
            user_id,
            data.get("holiday_key"),
            fmt,
        )
        await c.message.answer(
            "Упс 😕 Не получилось сгенерировать открытку. "
            "Попробуй ещё раз через минуту."
        )
    finally:
        IN_FLIGHT.discard(user_id)








