# main.py
import sys
import time
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

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


# ---------- состояния Юко (для GUI/логики) ----------

class YukoState(str, Enum):
    IDLE = "idle"         # спит, ждёт wake-word
    LISTENING = "listening"   # слушает/распознаёт
    THINKING = "thinking"     # думает / ждём LLM
    HAPPY = "happy"           # всё ок, команда/ответ выполнены
    ERROR = "error"           # ошибка в любой части пайплайна


# Типы коллбеков для GUI
StateCallback = Optional[Callable[[YukoState], None]]
LogCallback = Optional[Callable[[str], None]]


# ---------- базовая настройка ----------

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "yuko_data"
DATA_DIR.mkdir(exist_ok=True)


def _emit_state(cb: StateCallback, state: YukoState) -> None:
    if cb is not None:
        cb(state)


def _emit_log(cb: LogCallback, text: str) -> None:
    if cb is not None:
        cb(text)


def run_yuko_core(
    on_state_change: StateCallback = None,
    on_log: LogCallback = None,
) -> None:
    """
    Главный цикл Юко, подготовленный для интеграции с GUI.

    on_state_change(state: YukoState) вызывается при смене состояния.
    on_log(text: str) вызывается для отображения важных событий в интерфейсе.
    """

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

    msg_ready = "Юко готова. Скажи её имя, чтобы разбудить."
    print(msg_ready)
    logger.info("Юко AI запущена. Ожидаю команду пользователя.")
    _emit_log(on_log, msg_ready)
    _emit_state(on_state_change, YukoState.IDLE)

    # ---------- параметры активации ----------
    ACTIVE_WINDOW_SEC = 15.0

    active = False
    active_until: float | None = None

    # ---------- главный цикл ----------
    while True:
        # --- слушаем микрофон ---
        try:
            _emit_state(on_state_change, YukoState.LISTENING)
            phrase = listen()
        except Exception:
            logger.exception("Ошибка при работе listen()")
            _emit_state(on_state_change, YukoState.ERROR)
            _emit_log(on_log, "Ошибка записи с микрофона")
            # при ошибке записи продолжаем, но считаем, что Юко «спит»
            _emit_state(on_state_change, YukoState.IDLE)
            continue

        if not phrase:
            logger.info("STT: empty/None phrase, continue")
            # тишина -> спим
            _emit_state(on_state_change, YukoState.IDLE)
            continue

        logger.info(f"STT: raw phrase='{phrase}'")
        _emit_log(on_log, f"Ты: {phrase}")

        phrase = phrase.strip().lower()
        set_last_phrase(phrase)

        now = time.time()

        # если окно активации истекло — засыпаем
        if active and active_until is not None and now > active_until:
            active = False
            active_until = None
            logger.info("STATE: Юко ушла в сон (окно активации истекло)")
            msg_sleep = "💤 Юко уснула, ждёт имени."
            print(msg_sleep)
            _emit_log(on_log, msg_sleep)
            _emit_state(on_state_change, YukoState.IDLE)

        # ----- wake word / активация -----
        if not active:
            if has_wake_word(phrase):
                active = True
                active_until = time.time() + ACTIVE_WINDOW_SEC

                logger.info(f"WAKE: фраза '{phrase}' — Юко активировалась")
                msg_wake = "Юко: Я тебя слышу, говори, что сделать."
                print(msg_wake)
                _emit_log(on_log, msg_wake)
                # НЕ делаем continue — команда может быть в той же фразе
            else:
                # ЛОГИРУЕМ, но игнорим
                logger.info("STATE: фраза без wake-word, Юко спит")
                _emit_state(on_state_change, YukoState.IDLE)
                continue
        else:
            # уже активна — продлеваем окно
            active_until = time.time() + ACTIVE_WINDOW_SEC
            logger.info(f"STATE: продлили окно активации до {active_until}")

        # ----- анализ намерения -----
        try:
            _emit_state(on_state_change, YukoState.THINKING)
            intent_data = analyze(phrase)
        except Exception:
            logger.exception(f"Ошибка analyze() для фразы '{phrase}'")
            _emit_state(on_state_change, YukoState.ERROR)
            _emit_log(on_log, "Юко: Не смогла понять намерение, попробуй ещё раз.")
            # при ошибке анализа лучше усыпить, чтобы не зациклиться
            active = False
            active_until = None
            _emit_state(on_state_change, YukoState.IDLE)
            continue

        logger.info(f"INTENT: {intent_data}")

        # ----- локальные команды -----
        try:
            handled = handle_intent(intent_data)
        except Exception:
            logger.exception(
                f"Ошибка handle_intент() для intent_data={intent_data}, phrase='{phrase}'"
            )
            handled = False
            _emit_state(on_state_change, YukoState.ERROR)
            _emit_log(on_log, "Юко: Ошибка при выполнении локальной команды.")

        if handled:
            active = False
            active_until = None
            logger.info("STATE: локальная команда выполнена, Юко ушла в сон")
            msg_done = "✅ Команда выполнена. 💤 Юко уснула."
            print(msg_done)
            _emit_log(on_log, msg_done)
            _emit_state(on_state_change, YukoState.HAPPY)
            # чуть позже снова считаем, что она спит
            _emit_state(on_state_change, YukoState.IDLE)
            continue

        # ----- запрос к ИИ -----
        msg_think = "Юко думает..."
        print(msg_think)
        logger.info(f"AI_REQUEST: '{phrase}'")
        _emit_log(on_log, msg_think)
        _emit_state(on_state_change, YukoState.THINKING)

        clean_query = phrase
        for w in WAKE_WORDS:
            clean_query = clean_query.replace(w, " ")
        clean_query = " ".join(clean_query.split())

        try:
            resp = ask_ai(clean_query)
        except Exception:
            logger.exception(f"Ошибка при запросе к ИИ: '{clean_query}'")
            msg_err_ai = "Юко: Что-то пошло не так при обращении к ИИ."
            print(msg_err_ai)
            _emit_log(on_log, msg_err_ai)
            _emit_state(on_state_change, YukoState.ERROR)
            active = False
            active_until = None
            _emit_state(on_state_change, YukoState.IDLE)
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
            reply = f"Юко: {text}"
            print(reply)
            logger.info(f"AI_REPLY: '{text}'")
            _emit_log(on_log, reply)
            _emit_state(on_state_change, YukoState.HAPPY)
        else:
            _emit_state(on_state_change, YukoState.ERROR)

        # после ответа ИИ засыпаем
        active = False
        active_until = None
        logger.info("STATE: ответ отправлен, Юко ушла в сон")
        msg_sleep2 = "Юко уснула, позови её по имени, когда будет нужна."
        print(msg_sleep2)
        _emit_log(on_log, msg_sleep2)
        _emit_state(on_state_change, YukoState.IDLE)


def main() -> None:
    """Консольный запуск без GUI (для совместимости)."""
    run_yuko_core()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # "большой тент" — ловим все неожиданные фатальные ошибки
        logger.exception("Необработанное исключение в Yuko main()")
        raise
