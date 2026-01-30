# main.py
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


def main():
    # ---------- баннер запуска ----------

    banner = (
        "=" * 50 + "\n"
        + "🚀 YUKO ASSISTANT ЗАПУЩЕН\n"
        + f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + "=" * 50
    )
    print(banner)
    logger.info("=" * 50)
    logger.info("🚀 YUKO ASSISTANT ЗАПУЩЕН")
    logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    print("Юко готова. Скажи её имя, чтобы разбудить.")
    logger.info("Юко AI запущена. Ожидаю команду пользователя.")

    # ---------- параметры активации ----------

    ACTIVE_WINDOW_SEC = 10.0  # окно после wake-word

    active = False
    active_until: float | None = None

    # ---------- главный цикл ----------

    while True:
        # --- слушаем микрофон ---
        try:
            phrase = listen()
        except Exception:
            logger.exception("Ошибка при работе listen()")
            continue

        if not phrase:
            continue

        phrase = phrase.strip().lower()
        set_last_phrase(phrase)

        now = time.time()

        # если окно активации истекло — засыпаем
        if active and active_until is not None and now > active_until:
            active = False
            active_until = None
            logger.info("STATE: Юко ушла в сон (окно активации истекло)")
            print("💤 Юко уснула, ждёт имени.")

        # ----- wake word / активация -----
        if not active:
            if has_wake_word(phrase):
                active = True
                active_until = time.time() + ACTIVE_WINDOW_SEC

                logger.info(f"WAKE: фраза '{phrase}' — Юко активировалась")
                print("Юко: Я тебя слышу, говори, что сделать.")
                # НЕ делаем continue — команда может быть в той же фразе
            else:
                # без имени — молча игнорим
                continue
        else:
            # уже активна — продлеваем окно
            active_until = time.time() + ACTIVE_WINDOW_SEC

        # ----- анализ намерения -----
        try:
            intent_data = analyze(phrase)
        except Exception:
            logger.exception(f"Ошибка analyze() для фразы '{phrase}'")
            # при ошибке анализа лучше усыпить, чтобы не зациклиться
            active = False
            active_until = None
            continue

        # ----- локальные команды -----
        try:
            handled = handle_intent(intent_data)
        except Exception:
            logger.exception(
                f"Ошибка handle_intент() для intent_data={intent_data}, phrase='{phrase}'"
            )
            handled = False

        if handled:
            active = False
            active_until = None
            logger.info("STATE: локальная команда выполнена, Юко ушла в сон")
            print("✅ Команда выполнена. 💤 Юко уснула.")
            continue

        # ----- запрос к ИИ -----
        print("Юко думает...")
        logger.info(f"AI_REQUEST: '{phrase}'")

        clean_query = phrase
        for w in WAKE_WORDS:
            clean_query = clean_query.replace(w, " ")
        clean_query = " ".join(clean_query.split())

        try:
            resp = ask_ai(clean_query)
        except Exception:
            logger.exception(f"Ошибка при запросе к ИИ: '{clean_query}'")
            print("Юко: Что-то пошло не так при обращении к ИИ.")
            active = False
            active_until = None
            continue

        logger.info("AI_RESPONSE: получен ответ от модели")

        try:
            text, cmds = parse_commands(resp)
        except Exception:
            logger.exception("Ошибка parse_commands() для ответа модели")
            text, cmds = resp, []  # fallback, хотя бы текст сказать

        logger.info(f"AI_CMDS: извлечено {len(cmds)} команд(ы)")

        for ct, p in cmds:
            logger.info(
                f"EXEC_CMD: type={ct}, payload={p}, src_phrase='{phrase}'"
            )
            try:
                execute_cmd(ct, p, context_phrase=phrase)
            except Exception:
                logger.exception(
                    f"Ошибка execute_cmd() для type={ct}, payload={p}, phrase='{phrase}'"
                )

        if text:
            print("Юко:", text)
            logger.info(f"AI_REPLY: '{text}'")

        # после ответа ИИ засыпаем
        active = False
        active_until = None
        logger.info("STATE: ответ отправлен, Юко ушла в сон")
        print("Юко уснула, позови её по имени, когда будет нужна.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # "большой тент" — ловим все неожиданные фатальные ошибки
        logger.exception("Необработанное исключение в Yuko main()")
        raise
