from aiogram.fsm.state import State, StatesGroup


class ZitFSM(StatesGroup):
    subject     = State()
    scene       = State()
    style_group = State()
    style       = State()
    lighting    = State()
    mood        = State()
    genre       = State()
    result      = State()
