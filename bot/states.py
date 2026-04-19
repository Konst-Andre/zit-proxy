from aiogram.fsm.state import State, StatesGroup


class ZitFSM(StatesGroup):
    subject      = State()
    scene        = State()
    subject_type = State()   # між scene і style_group
    style_group  = State()
    style        = State()
    lighting     = State()
    mood         = State()
    genre        = State()
    result       = State()


class VisionFSM(StatesGroup):
    photo   = State()   # чекаємо фото
    confirm = State()   # показуємо розпізнані параметри → підтвердити або змінити
