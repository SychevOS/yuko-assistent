import os
import sys
import subprocess
import zipfile
from pathlib import Path
import webbrowser
import re
import json
import traceback

import requests
from dotenv import load_dotenv  # можно закомментировать, если .env не нужен

from file_actions import search_file, open_file, show_in_explorer, delete_file
from words_config import (
    CORRECTIONS,
    BROWSER_TRIGGER_WORDS,
    WAKE_WORDS,
    INTENT_KEYWORDS,
    APP_NAME_ALIASES,
)
from app_launcher import launch_app, list_registered_apps

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

from groq import Groq


# ---------- базовая настройка ----------

load_dotenv()  # закомментируй, если не используешь .env

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "yuko_data"
MODELS_DIR = DATA_DIR / "models"
TEMP_DIR = DATA_DIR / "temp"
BROWSERS_CFG_PATH = BASE_DIR / "browsers.json"

for d in (DATA_DIR, MODELS_DIR, TEMP_DIR):
    d.mkdir(exist_ok=True)

print("Юко AI запущена. Скажи 'выход', чтобы завершить.\n")

# ---------- установка пакетов ----------

def install_package(pkg: str):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pkg, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

for m in ("sounddevice", "numpy", "faster-whisper", "groq", "send2trash"):
    try:
        __import__(m)
    except ImportError:
        install_package(m)

# ---------- проверка звука ----------

try:
    _devices = sd.query_devices()
except Exception as e:
    print("Ошибка доступа к устройствам звука:", e)


# ---------- Whisper модель ----------

# small — компромисс по качеству и скорости; device="cpu" если без GPU
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")


# ---------- Groq ----------

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# ---------- конфиг браузеров ----------

def load_browsers_cfg() -> dict:
    if BROWSERS_CFG_PATH.is_file():
        try:
            with open(BROWSERS_CFG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_browsers_cfg(cfg: dict):
    with open(BROWSERS_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

BROWSERS_CFG = load_browsers_cfg()

def get_browser_path(name: str) -> str | None:
    name = name.lower()
    return BROWSERS_CFG.get(name)

def register_browser(name: str, path: str):
    name = name.lower()
    BROWSERS_CFG[name] = path
    save_browsers_cfg(BROWSERS_CFG)

def open_default_browser(url: str | None = None):
    try:
        subprocess.run(
            [r"C:\Users\Administrator\AppData\Local\Programs\Opera GX\opera.exe", "--new-tab"],
            check=False,
        )
    except Exception:
        webbrowser.open(url if url else "https://speeddial.opera.com")


# ---------- постобработка фразы / имена приложений ----------

def normalize_app_name(name: str) -> str:
    name = name.strip().lower()
    for wrong, canonical in APP_NAME_ALIASES.items():
        if wrong in name:
            return canonical
    return name

def extract_app_name(text: str) -> str | None:
    """
    Пытается вытащить имя приложения из фразы:
      'юко открой дискорд' -> 'дискорд'
      'запусти steam'      -> 'steam'
    """
    t = text.lower()
    for trigger in ["открой", "запусти", "включи"]:
        if trigger in t:
            part = t.split(trigger, 1)[1].strip()
            for junk in ["юко", "пожалуйста", "плиз"]:
                part = part.replace(junk, " ")
            part = " ".join(part.split())
            return part or None
    return None


# ---------- распознавание речи (Whisper) ----------

def listen() -> str:
    # длина записи, можно подстроить (2.0–4.0)
    duration = 5.0

    try:
        audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
    except Exception as e:
        print("Ошибка записи с микрофона:", e)
        return ""

    samples = audio.flatten()

    try:
        segments, info = whisper_model.transcribe(
            samples,
            language="ru",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )
    except Exception as e:
        print("Ошибка распознавания Whisper:", e)
        return ""

    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)

    text = " ".join(text_parts).strip().lower()
    return text


# ---------- Groq / офлайн-ответ ----------

def ask_groq(msg: str) -> str | None:
    if not client:
        print("Юко: ключ GROQ_API_KEY не задан, работаю офлайн.")
        return None
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Yuko, a helpful AI assistant. "
                        "You are a female. "
                        "Answer briefly in Russian, 2-4 sentences. "
                        "You may sometimes control the PC using tags, BUT ONLY when the user явно просит выполнить действие.\n"
                        "Rules for tags:\n"
                        "1) Use [OPEN_BROWSER] or [OPEN_BROWSER_URL:url] ONLY if the request clearly asks to open a browser "
                        "or a website (e.g. \"открой браузер\", \"открой интернет\", \"зайди на сайт\", \"найди в интернете ...\").\n"
                        "2) Never open the browser if the user just asks a question (weather, study, programming, etc.). "
                        "In such cases respond with pure text only, without any tags.\n"
                        "3) For file operations use [SEARCH_FILE:query], [OPEN_FILE:path], [SHOW_IN_EXPLORER:path], "
                        "[DELETE_FILE:path] only if the user explicitly asks to find/open/delete a file.\n"
                        "4) If the user says phrases like \"найди в интернете ...\", \"найди рецепт ...\", "
                        "you SHOULD use [WEB_SEARCH:запрос] tag.\n"
                        "5) If the user asks to open YouTube (\"открой ютуб\", \"открой youtube\"), "
                        "use [OPEN_BROWSER_URL:https://www.youtube.com].\n"
                        "6) Never invent tags without necessity. If no tag is clearly needed, answer with text only."
                        "Your creator has name Finn. "
                    ),
                },
                {"role": "user", "content": msg},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        answer = completion.choices[0].message.content.strip()
        return answer
    except Exception:
        print("Юко: ошибка при запросе в Groq:")
        traceback.print_exc()
        return None

def ask_offline(msg: str) -> str:
    m = msg.lower()
    if "привет" in m:
        return "Привет. Чем помочь."
    if "python" in m:
        return "Python — язык программирования, на нем удобно писать ассистентов."
    if any(w in m for w in ["открой браузер", "открой интернет"]):
        return "Открываю браузер. [OPEN_BROWSER]"
    return "Не совсем поняла запрос, попробуй переформулировать."

def ask_ai(msg: str) -> str:
    resp = ask_groq(msg)
    if resp:
        return resp
    return ask_offline(msg)


# ---------- парсинг команд ----------

CMD_PATTERN = re.compile(r"\[([A-Z_]+)(?::([^\]]*))?\]", re.IGNORECASE)

def parse_commands(text: str):
    if not text:
        return "", []
    actions = CMD_PATTERN.findall(text)
    clean = CMD_PATTERN.sub("", text)
    clean = " ".join(clean.split())
    return clean, actions


# ---------- выполнение команд ----------

last_user_phrase = ""

def execute_cmd(cmd_type: str, param: str, context_phrase: str = ""):
    global last_user_phrase
    ct = cmd_type.lower()
    p = param.strip()
    try:
        if ct in ("open_browser", "open_browser_url", "open_browser_named"):
            t = (context_phrase or last_user_phrase).lower()
            if not any(w in t for w in BROWSER_TRIGGER_WORDS):
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

        elif ct == "open_browser_named":
            parts = p.split("|", 1)
            name = parts[0].strip().lower()
            url = parts[1].strip() if len(parts) == 2 else None

            path = get_browser_path(name)
            if not path:
                print(f"Юко: я не знаю, где установлен браузер '{name}'.")
                print("Перетащи сюда его .exe или введи полный путь.")
                user_path = input("Путь к браузеру: ").strip('" ').strip()

                if not user_path or not os.path.isfile(user_path):
                    print("Юко: путь некорректный, открываю браузер по умолчанию.")
                    open_default_browser(url)
                    return

                register_browser(name, user_path)
                path = user_path
                print(f"Юко: запомнила браузер '{name}'.")

            cmd = f'"{path}"'
            if url:
                cmd += f' "{url}"'
            subprocess.Popen(cmd)

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


# ---------- анализ намерения ----------

def analyze(text: str) -> str:
    t = text.lower().replace("ё", "е")

    def has(key):
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
        # общее приложение
        return "app"

    return "ai"


def has_wake_word(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in WAKE_WORDS)


# ---------- главный цикл ----------

while True:
    phrase = listen()
    if not phrase:
        continue

    phrase = phrase.strip().lower()
    last_user_phrase = phrase

    print("🎧 Распознано:", phrase)

    intent = analyze(phrase)
    wake = has_wake_word(phrase)

    if intent == "exit":
        print("Юко: Пока 👋")
        break

    if intent == "thanks":
        print("Юко: Пожалуйста 💜")
        continue

    if intent == "calc":
        print("Юко: Открываю калькулятор.")
        subprocess.Popen("calc", shell=True)
        continue

    if intent == "notepad":
        print("Юко: Открываю блокнот.")
        subprocess.Popen("notepad", shell=True)
        continue

    if intent == "browser":
        print("Юко: Открываю браузер.")
        open_default_browser()
        continue

    if intent == "youtube":
        print("Юко: Открываю YouTube.")
        webbrowser.open("https://youtube.com")
        continue

    if intent == "discord":
        print("Юко: Открываю Discord.")
        launch_app("discord")
        continue

    if intent == "telegram":
        print("Юко: Открываю Telegram.")
        launch_app("telegram")
        continue

    if intent == "steam":
        print("Юко: Открываю Steam.")
        launch_app("steam")
        continue

    if intent == "app":
        app_raw = extract_app_name(phrase)
        if not app_raw:
            print("Юко: Не поняла, какое приложение открыть.")
            continue
        app_name = normalize_app_name(app_raw)
        print(f"Юко: Пытаюсь открыть {app_name}.")
        launch_app(app_name)
        continue

    if intent == "ai":
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
