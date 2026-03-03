from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.states import CardFlow
from app.services.prompts import PromptsRepo
# from app.queue.tasks import enqueue_generate /// 1) Убираем очередь из кода/ Удаляем импорт и вызов enqueue_generate

from aiogram.types import BufferedInputFile
from app.config import settings
from app.services.openai_images import OpenAIImageClient
from app.services.telegram_files import download_photo_bytes

router = Router()

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

@router.message(F.text == "/start")
async def start(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CardFlow.waiting_photo)
    await m.answer("Привет! Пришли фото, и я сделаю открытку 🎁")

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
    holiday_key = c.data.split(":", 1)[1]
    await state.update_data(holiday_key=holiday_key)

    phrases = prompts.list_phrases(holiday_key)
    await state.set_state(CardFlow.waiting_phrase)
    if phrases:
        await c.message.edit_text("Выбери фразу или напиши свою:", reply_markup=kb_phrases(prompts, holiday_key))
    else:
        await c.message.edit_text("Напиши фразу (2–60 символов):")

@router.callback_query(CardFlow.waiting_phrase, F.data.startswith("phrase:"))
async def pick_phrase_button(c: CallbackQuery, state: FSMContext, prompts: PromptsRepo):
    pick = c.data.split(":", 1)[1]
    data = await state.get_data()
    holiday_key = data["holiday_key"]

    if pick == "custom":
        await c.message.edit_text("Ок! Напиши свою фразу (2–60 символов):")
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
    phrase = m.text.strip()
    if len(phrase) < 2 or len(phrase) > 60:
        await m.answer("Сделай фразу покороче (2–60 символов). Напиши ещё раз:")
        return
    await state.update_data(user_phrase=phrase)
    await state.set_state(CardFlow.waiting_format)
    await m.answer("Выбери формат:", reply_markup=kb_formats())

# @router.callback_query(CardFlow.waiting_format, F.data.startswith("fmt:"))
# async def pick_format(c: CallbackQuery, state: FSMContext):
#     fmt = c.data.split(":", 1)[1]
#     data = await state.get_data()
#     await state.clear()

#     await c.message.edit_text("Принято ✅ Генерирую открытку…")

#     await enqueue_generate(
#         telegram_chat_id=c.message.chat.id,
#         telegram_message_id=c.message.message_id,
#         user_id=c.from_user.id,
#         photo_file_id=data["photo_file_id"],
#         holiday_key=data["holiday_key"],
#         user_phrase=data["user_phrase"],
#         fmt=fmt,
#     )

# простой “антидубль”: один пользователь = одна генерация одновременно
IN_FLIGHT: set[int] = set()

@router.callback_query(CardFlow.waiting_format, F.data.startswith("fmt:"))
async def pick_format(c: CallbackQuery, state: FSMContext, prompts: PromptsRepo):
    user_id = c.from_user.id
    if user_id in IN_FLIGHT:
        await c.answer("Я уже делаю тебе открытку 🙂 Подожди немного.", show_alert=True)
        return

    fmt = c.data.split(":", 1)[1]  # "3:4" или "4:3"
    data = await state.get_data()
    await state.clear()

    await c.message.edit_text("Принято ✅ Генерирую открытку…")

    IN_FLIGHT.add(user_id)
    try:
        # 1) скачиваем фото из Telegram в память (ничего не храним)
        photo_bytes = await download_photo_bytes(c.bot, data["photo_file_id"])

        # 2) формируем промпт из YAML
        prompt, size, model = prompts.render_prompt(
            data["holiday_key"],
            data["user_phrase"],
            fmt
        )
        quality = prompts.get_holiday(data["holiday_key"]).default_quality

        # 3) вызываем OpenAI
        client = OpenAIImageClient(settings.OPENAI_API_KEY)
        out_bytes = client.edit_image(
            image_bytes=photo_bytes,
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
        )

        # 4) отправляем картинку
        await c.message.answer_photo(
            BufferedInputFile(out_bytes, filename="card.png"),
            caption="Готово 🎉"
        )

    except Exception:
        # чтобы бот не “молчал” при ошибке
        await c.message.answer(
            "Упс 😕 Не получилось сгенерировать открытку. "
            "Попробуй ещё раз через минуту."
        )
        raise
    finally:
        IN_FLIGHT.discard(user_id)


