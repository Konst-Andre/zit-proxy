from aiogram.fsm.state import State, StatesGroup


class ZitFSM(StatesGroup):
    subject      = State()
    scene        = State()
    subject_type = State()
    style_group  = State()
    style        = State()
    lighting     = State()
    mood         = State()
    genre        = State()
    result       = State()


class VisionFSM(StatesGroup):
    photo   = State()
    confirm = State()


class ImageFSM(StatesGroup):
    subject = State()
    scene   = State()
    result  = State()


class ChatFSM(StatesGroup):
    active = State()   # активна сесія чату
