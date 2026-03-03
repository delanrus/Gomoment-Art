from aiogram.fsm.state import State, StatesGroup

class CardFlow(StatesGroup):
    waiting_photo = State()
    waiting_holiday = State()
    waiting_phrase = State()
    waiting_format = State()
