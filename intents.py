# intents.py
import os
import subprocess
import webbrowser
import re
from typing import Tuple, List

from words_config import (
    INTENT_KEYWORDS,
    WAKE_WORDS,
    BROWSER_TRIGGER_WORDS,
    APP_NAME_ALIASES,
)
from app_launcher import launch_app
from file_actions import search_file, open_file, show_in_explorer, delete_file


# ---------- анализ намерения ----------

def analyze(text: str) -> str:
    t = text.lower().replace("ё", "е")

    def has(key: str) -> bool:
        return any(w in t for w in INTENT_KEYWORDS.get(key, []))

    if has("exit"):
        return "exit"
    if has("thanks"):
        return "thanks"

    if any(w in t for w in ["открой", "запусти", "включи"]):
        if has("calc"):
            return "calc"
        if has("notepad"):
            return "notepad"
        if has("browser"):
            return "browser"
        if has("youtube"):
            return "youtube"
        if has("discord"):
            return "discord"
        if has("telegram"):
            return "telegram"
        if has("steam"):
            return "steam"
        if has("AnyDesk"):
            return "AnyDesk"
        return "app"

    return "ai"


def has_wake_word(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in WAKE_WORDS)


# ---------- нормализация названий приложений ----------

def normalize_app_name(name: str) -> str:
    name = name.strip().lower()
    for wrong, canonical in APP_NAME_ALIASES.items():
        if wrong in name:
            return canonical
    return name


def extract_app_name(text: str) -> str | None:
    t = text.lower()
    for trigger in ["открой", "запусти", "включи"]:
        if trigger in t:
            part = t.split(trigger, 1)[1].strip()
            for junk in ["юко", "пожалуйста", "плиз"]:
                part = part.replace(junk, " ")
            part = " ".join(part.split())
            return part or None
    return None


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

def handle_intent(intent: str, phrase: str) -> bool:
    """
    Выполняет действие по интенту.
    Возвращает True, если интент обработан и дальше можно не звать ИИ.
    """
    if intent == "exit":
        print("Юко: Пока 👋")
        os._exit(0)

    if intent == "thanks":
        print("Юко: Пожалуйста 💜")
        return True

    if intent == "calc":
        print("Юко: Открываю калькулятор.")
        subprocess.Popen("calc", shell=True)
        return True

    if intent == "notepad":
        print("Юко: Открываю блокнот.")
        subprocess.Popen("notepad", shell=True)
        return True

    if intent == "browser":
        print("Юко: Открываю браузер.")
        open_default_browser()
        return True

    if intent == "youtube":
        print("Юко: Открываю YouTube.")
        webbrowser.open("https://youtube.com")
        return True

    if intent == "anydesk":
        print("Юко: Открываю AnyDesk.")
        launch_app("anydesk")
        return True

    if intent == "discord":
        print("Юко: Открываю Discord.")
        launch_app("discord")
        return True

    if intent == "telegram":
        print("Юко: Открываю Telegram.")
        launch_app("telegram")
        return True

    if intent == "steam":
        print("Юко: Открываю Steam.")
        launch_app("steam")
        return True

    if intent == "app":
        app_raw = extract_app_name(phrase)
        if not app_raw:
            print("Юко: Не поняла, какое приложение открыть.")
            return True
        app_name = normalize_app_name(app_raw)
        print(f"Юко: Пытаюсь открыть {app_name}.")
        launch_app(app_name)
        return True

    return False  # "ai" и всё остальное — пусть main отправляет в ИИ
