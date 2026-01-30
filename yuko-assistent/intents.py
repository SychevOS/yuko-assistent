# intents.py
import os
import subprocess
import webbrowser
import re
from typing import Tuple, List, Dict, Any

from app_indexer import load_app_index, build_app_index
from words_config import (
    INTENT_KEYWORDS,
    WAKE_WORDS,
    BROWSER_TRIGGER_WORDS,
    APP_NAME_ALIASES,
)
from app_launcher import launch_app
from file_actions import search_file, open_file, show_in_explorer, delete_file


# ---------- модель интента ----------

IntentDict = Dict[str, Any]


def _has_keyword(t: str, key: str) -> bool:
    return any(w in t for w in INTENT_KEYWORDS.get(key, []))


def has_wake_word(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in WAKE_WORDS)


def extract_app_name(text: str) -> str | None:
    """
    Достаём «сырое» имя приложения из фразы пользователя.
    Примеры:
      - "Юко, открой дискордик" -> "дискордик"
      - "запусти мне, пожалуйста, escape from tarkov" -> "escape from tarkov"
    """
    t = text.lower()
    triggers = ["открой", "запусти", "включи", "запуск", "запускать"]

    for trigger in triggers:
        if trigger in t:
            part = t.split(trigger, 1)[1]
            break
    else:
        return None

    # вычищаем сервисные слова
    junk_words = ["юко", "юка", "юкка", "юкко", "пожалуйста", "плиз", "мне", "если можно"]
    for j in junk_words:
        part = part.replace(j, " ")

    part = " ".join(part.split())
    return part or None


def normalize_app_slot(name: str) -> str:
    """
    Приводим имя приложения к более каноничному виду.
    Сначала словарь APP_NAME_ALIASES, потом просто trim+lower.
    """
    n = name.strip().lower()
    for wrong, canonical in APP_NAME_ALIASES.items():
        if wrong in n:
            return canonical
    return n


def analyze(text: str) -> IntentDict:
    """
    Анализ фразы пользователя и возврат структурированного интента.

    Возвращает словарь:
      {
        "intent": <str>,
        "slots": { ... },
        "confidence": <float 0..1>,
        "raw_text": <str>
      }

    Примеры:
      - exit / thanks / scan_apps
      - open_app (с конкретными shortcut'ами и общим случаем)
      - open_browser / open_youtube
      - fallback -> "ai"
    """
    t_raw = text or ""
    t = t_raw.lower().replace("ё", "е")
    slots: Dict[str, Any] = {}
    intent = "ai"
    confidence = 0.5

    # 1. Явные системные команды (высокий приоритет)
    if _has_keyword(t, "exit"):
        return {
            "intent": "exit",
            "slots": {},
            "confidence": 0.99,
            "raw_text": t_raw,
        }

    if _has_keyword(t, "thanks"):
        return {
            "intent": "thanks",
            "slots": {},
            "confidence": 0.99,
            "raw_text": t_raw,
        }

    if _has_keyword(t, "scan_apps"):
        return {
            "intent": "scan_apps",
            "slots": {},
            "confidence": 0.95,
            "raw_text": t_raw,
        }

    # 2. Команды вида "открой / запусти / включи ..."
    has_open_verb = any(w in t for w in ["открой", "запусти", "включи"])
    if has_open_verb:
        # shortcut-приложения из INTENT_KEYWORDS
        if _has_keyword(t, "calc"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "system", "target": "calc"},
                "confidence": 0.95,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "notepad"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "system", "target": "notepad"},
                "confidence": 0.95,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "browser"):
            return {
                "intent": "open_browser",
                "slots": {},
                "confidence": 0.95,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "youtube"):
            return {
                "intent": "open_youtube",
                "slots": {},
                "confidence": 0.95,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "discord"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "shortcut", "target": "discord"},
                "confidence": 0.9,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "telegram"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "shortcut", "target": "telegram"},
                "confidence": 0.9,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "steam"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "shortcut", "target": "steam"},
                "confidence": 0.9,
                "raw_text": t_raw,
            }
        if _has_keyword(t, "AnyDesk"):
            return {
                "intent": "open_app",
                "slots": {"app_type": "shortcut", "target": "AnyDesk"},
                "confidence": 0.9,
                "raw_text": t_raw,
            }

        # общий случай — "открой <что‑то>", пусть будет open_app с raw_name
        app_raw = extract_app_name(t_raw)
        if app_raw:
            slots["app_type"] = "generic"
            slots["raw_name"] = app_raw
            slots["normalized_name"] = normalize_app_slot(app_raw)
            intent = "open_app"
            confidence = 0.7
            return {
                "intent": intent,
                "slots": slots,
                "confidence": confidence,
                "raw_text": t_raw,
            }

    # 3. Браузерные команды без явного глагола
    if any(w in t for w in BROWSER_TRIGGER_WORDS):
        # можно потом расширить: поиск / конкретный сайт и т.д.
        return {
            "intent": "open_browser",
            "slots": {},
            "confidence": 0.7,
            "raw_text": t_raw,
        }

    # 4. Fallback — всё остальное отдаём ИИ
    return {
        "intent": "ai",
        "slots": {},
        "confidence": confidence,
        "raw_text": t_raw,
    }


# ---------- парсинг команд из текста ИИ ----------

CMD_PATTERN = re.compile(r"\[([A-Z_]+)(?::([^\]]*))?\]", re.IGNORECASE)


def parse_commands(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    if not text:
        return "", []
    actions = CMD_PATTERN.findall(text)
    clean = CMD_PATTERN.sub("", text)
    clean = " ".join(clean.split())
    return clean, actions


# ---------- вспомогательные функции ----------

def open_default_browser(url: str | None = None):
    try:
        # Можно вынести путь в конфиг
        subprocess.run(
            [r"C:\Users\Administrator\AppData\Local\Programs\Opera GX\opera.exe", "--new-tab"],
            check=False,
        )
    except Exception:
        webbrowser.open(url if url else "https://speeddial.opera.com")


# ---------- исполнение команд из [CMD:...] ----------

_last_user_phrase = ""


def set_last_phrase(text: str):
    global _last_user_phrase
    _last_user_phrase = text or ""


def execute_cmd(cmd_type: str, param: str, context_phrase: str = ""):
    global _last_user_phrase
    ct = cmd_type.lower()
    p = param.strip()
    phrase = (context_phrase or _last_user_phrase).lower()

    try:
        if ct in ("open_browser", "open_browser_url"):
            if not any(w in phrase for w in BROWSER_TRIGGER_WORDS):
                return

        if ct == "run_program":
            programs = {
                "calc": "calc",
                "калькулятор": "calc",
                "notepad": "notepad",
                "блокнот": "notepad",
            }
            prog = programs.get(p.lower(), p)
            subprocess.Popen(prog, shell=True)

        elif ct == "open_browser":
            open_default_browser()

        elif ct == "open_browser_url":
            url = p.strip()
            open_default_browser(url if url else None)

        elif ct == "search_file":
            if not p:
                print("Юко: что искать?")
                return
            results = search_file(p)
            if not results:
                print("Юко: ничего не нашла.")
            else:
                print("Юко: нашла файлы:")
                for i, path in enumerate(results, 1):
                    print(f"{i}. {path}")

        elif ct == "open_file":
            open_file(p)

        elif ct == "show_in_explorer":
            show_in_explorer(p)

        elif ct == "delete_file":
            delete_file(p)
            print("Юко: отправила файл в корзину.")

        elif ct == "youtube_search":
            if p:
                webbrowser.open(f"https://www.youtube.com/results?search_query={p}")

        elif ct == "web_search":
            if p:
                webbrowser.open(f"https://yandex.ru/search/?text={p}")

    except PermissionError:
        print("Юко: в системные файлы я не лезу, это опасно.")
    except FileNotFoundError:
        print("Юко: файл или папка не найдены.")
    except Exception as e:
        print(f"Юко: ошибка при выполнении команды {ct}: {e}")


# ---------- маппинг интента на действие (для main.py) ----------

def handle_intent(intent_data: IntentDict) -> bool:
    """
    Выполняет действие по интенту.
    Возвращает True, если интент обработан и дальше можно не звать ИИ.

    Ожидает словарь от analyze():
      {
        "intent": <str>,
        "slots": {...},
        ...
      }
    """
    intent = intent_data.get("intent", "ai")
    slots = intent_data.get("slots", {})
    phrase = intent_data.get("raw_text", "") or ""

    # системные
    if intent == "exit":
        print("Юко: Пока 👋")
        os._exit(0)

    if intent == "thanks":
        print("Юко: Пожалуйста 💜")
        return True

    if intent == "scan_apps":
        print("Юко: Сканирую установленные приложения, это может занять немного времени...")
        index = build_app_index()
        print(f"Юко: Готово, я запомнила {len(index)} приложений.")
        return True

    # открытие приложений / браузера / ютуба
    if intent == "open_browser":
        print("Юко: Открываю браузер.")
        open_default_browser()
        return True

    if intent == "open_youtube":
        print("Юко: Открываю YouTube.")
        webbrowser.open("https://youtube.com")
        return True

    if intent == "open_app":
        app_type = slots.get("app_type", "generic")
        target = slots.get("target")
        raw_name = slots.get("raw_name") or target

        if app_type == "system" and target:
            print(f"Юко: Открываю {target}.")
            # системные штуки через subprocess
            subprocess.Popen(target, shell=True)
            return True

        if app_type == "shortcut" and target:
            print(f"Юко: Открываю {target}.")
            launch_app(target)
            return True

        if raw_name:
            print(f"Юко: Пытаюсь открыть {raw_name}.")
            launch_app(raw_name)
            return True

        print("Юко: Не поняла, какое приложение открыть.")
        return True

    # всё остальное — пусть main отправляет в ИИ
    return False
