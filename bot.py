import os
import json
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from google import genai
from google.genai import types

# === Загрузка .env ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)

# === Настройка Gemini ===
client = genai.Client(api_key=GEMINI_API_KEY)

# === Telegram Bot ===
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
router = Router()

# === FSM состояния ===
class UserState(StatesGroup):
    program = State()

# === Конфигурация программ ===
PROGRAMS = {
    "ai": {
        "title": "Искусственный интеллект",
        "file": "data/ai_program.json"
    },
    "product": {
        "title": "AI Product",
        "file": "data/ai_product.json"
    },
    "both": {
        "title": "Ещё не определился",
        "file": ["data/ai_program.json", "data/ai_product.json"]
    }
}

# === Быстрые вопросы ===
quick_question_map = {
    "cost": "Сколько стоит обучение?",
    "admission": "Можно ли поступить без профильного образования?",
    "scholarship": "Какие есть стипендии?",
    "final": "Что можно выбрать как выпускную работу?",
}

def get_quick_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"quick:{qid}")]
        for qid, text in quick_question_map.items()
    ])

# === Клавиатура выбора программы ===
def get_program_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cfg["title"], callback_data=f"program:{pid}")]
        for pid, cfg in PROGRAMS.items()
    ])

# === Загрузка JSON одной или обеих программ ===
def load_program_json(program_id: str):
    try:
        files = PROGRAMS[program_id]["file"]
        if isinstance(files, list):
            merged = {}
            for path in files:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged.update(data)
            return merged
        else:
            with open(files, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка при загрузке JSON: {e}")
        return None

# === /start ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот-консультант по магистратуре ИТМО.\n\nВыбери образовательную программу:",
        reply_markup=get_program_keyboard()
    )

# === выбор программы ===
@router.callback_query(F.data.startswith("program:"))
async def handle_program_choice(callback: CallbackQuery, state: FSMContext):
    program_id = callback.data.split(":")[1]
    if program_id not in PROGRAMS:
        await callback.answer("❌ Неизвестная программа")
        return

    await state.set_state(UserState.program)
    await state.update_data(program_id=program_id)
    await callback.message.answer(
        f"✅ Программа выбрана: {PROGRAMS[program_id]['title']}\n\nЗадай вопрос или выбери из популярных:",
        reply_markup=get_quick_keyboard()
    )
    await callback.answer()

# === быстрые вопросы ===
@router.callback_query(F.data.startswith("quick:"))
async def handle_quick(callback: CallbackQuery, state: FSMContext):
    qid = callback.data.split(":")[1]
    question = quick_question_map.get(qid)
    if question:
        await callback.message.answer(f"❓ {question}")
        await handle_question(callback.message, question, state)
    await callback.answer()

# === свободный текст ===
@router.message(F.text)
async def handle_free_question(message: Message, state: FSMContext):
    await handle_question(message, message.text.strip(), state)

# === обработка вопроса ===
async def handle_question(message: Message, question: str, state: FSMContext):
    user_data = await state.get_data()
    program_id = user_data.get("program_id")

    if not program_id:
        await message.answer("⛔ Сначала выбери программу:", reply_markup=get_program_keyboard())
        return

    data = load_program_json(program_id)
    if not data:
        await message.answer("⚠ Не удалось загрузить данные о программе.")
        return

    # === Промпт для Gemini ===
    prompt = (
        "Ты — бот-консультант по магистратуре Университета ИТМО. "
        "Отвечай только на основе следующего JSON:\n\n"
        f"{json.dumps(data, ensure_ascii=False)}"
    )

    await message.answer("🤖 Думаю над ответом...")
    try:
        contents = [
            types.Content(role="user", parts=[types.Part(text=prompt)]),
            types.Content(role="user", parts=[types.Part(text=question)])
        ]
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                candidate_count=1,
                temperature=0.6
            )
        )
        reply = response.candidates[0].content.parts[0].text
        await message.answer(reply)
    except Exception as e:
        logging.exception("Gemini error")
        await message.answer("⚠ Ошибка при обращении к модели Gemini.")

# === запуск ===
async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
