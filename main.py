import sys
from pathlib import Path
from dotenv import load_dotenv
from Logger import logger
from datetime import datetime

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
from ai_client import ask_ai  # <<< теперь ИИ вынесен

# ---------- базовая настройка ----------

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "yuko_data"
DATA_DIR.mkdir(exist_ok=True)

logger.log("=" * 50)
logger.log("🚀 YUKO ASSISTANT ЗАПУЩЕН")
logger.log(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.log("=" * 50)

print("Юко AI запущена. Скажи 'выход', чтобы завершить.\n")

# ---------- главный цикл ----------

while True:
    phrase = listen()
    if not phrase:
        continue

    phrase = phrase.strip().lower()
    set_last_phrase(phrase)

    print("Распознано:", phrase)

    intent = analyze(phrase)
    wake = has_wake_word(phrase)  # на будущее

    handled = handle_intent(intent, phrase)
    if handled:
        continue

    clean_query = phrase
    for w in WAKE_WORDS:
        clean_query = clean_query.replace(w, " ")
    clean_query = " ".join(clean_query.split())

    resp = ask_ai(clean_query)

    text, cmds = parse_commands(resp)

    for ct, p in cmds:
        execute_cmd(ct, p, context_phrase=phrase)

    if text:
        print("Юко:", text)
