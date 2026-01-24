import sys
import time
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from Logger import logger
from audio_stt import listen
from intents import (
    analyze,
    has_wake_word,
    parse_commands,
    execute_cmd,
    handle_intent,
    set_last_phrase,
)
from words_config import WAKE_WORDS
from ai_client import ask_ai


# ---------- базовая настройка ----------

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "yuko_data"
DATA_DIR.mkdir(exist_ok=True)

# Табличка запуска — и в консоль, и в лог
banner = (
    "=" * 50 + "\n"
    + "🚀 YUKO ASSISTANT ЗАПУЩЕН\n"
    + f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    + "=" * 50
)
print(banner)
logger.log("=" * 50)
logger.log("🚀 YUKO ASSISTANT ЗАПУЩЕН")
logger.log(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.log("=" * 50)

print("Юко готова. Скажи её имя, чтобы разбудить.")
logger.log("Юко AI запущена. Ожидаю команду пользователя.")


# ---------- параметры активации ----------

ACTIVE_WINDOW_SEC = 10.0  # окно после wake-word

active = False
active_until: float | None = None


# ---------- главный цикл ----------

while True:
    phrase = listen()
    if not phrase:
        continue

    phrase = phrase.strip().lower()
    set_last_phrase(phrase)

    now = time.time()

    # если окно активации истекло — засыпаем
    if active and active_until is not None and now > active_until:
        active = False
        active_until = None
        logger.log("STATE: Юко ушла в сон")
        print("💤 Юко уснула, ждёт имени.")

    # ----- wake word / активация -----
    if not active:
        if has_wake_word(phrase):
            active = True
            active_until = time.time() + ACTIVE_WINDOW_SEC

            logger.log(f"WAKE: фраза '{phrase}' — Юко активировалась")
            print("Юко: Я тебя слышу, говори, что сделать.")
            # НЕ делаем continue — команда может быть в той же фразе
        else:
            # без имени — молча игнорим
            continue
    else:
        # уже активна — продлеваем окно
        active_until = time.time() + ACTIVE_WINDOW_SEC

    # ----- анализ намерения -----
    intent = analyze(phrase)

    # ----- локальные команды -----
    handled = handle_intent(intent, phrase)
    if handled:
        active = False
        active_until = None
        logger.log("STATE: локальная команда выполнена, Юко ушла в сон")
        print("✅ Команда выполнена. 💤 Юко уснула.")
        continue

    # ----- запрос к ИИ -----
    # Здесь она "думает"
    print("Юко думает...")
    logger.log(f"AI_REQUEST: '{phrase}'")

    clean_query = phrase
    for w in WAKE_WORDS:
        clean_query = clean_query.replace(w, " ")
    clean_query = " ".join(clean_query.split())

    resp = ask_ai(clean_query)
    logger.log("AI_RESPONSE: получен ответ от модели")

    text, cmds = parse_commands(resp)
    logger.log(f"AI_CMDS: извлечено {len(cmds)} команд(ы)")

    for ct, p in cmds:
        logger.log(f"EXEC_CMD: type={ct}, payload={p}, src_phrase='{phrase}'")
        execute_cmd(ct, p, context_phrase=phrase)

    if text:
        print("Юко:", text)
        logger.log(f"AI_REPLY: '{text}'")

    # после ответа ИИ засыпаем
    active = False
    active_until = None
    logger.log("STATE: ответ отправлен, Юко ушла в сон")
    print("Юко уснула, позови её по имени, когда будет нужна.")
