# app_launcher.py
"""
Модуль для запуска приложений Windows с умным автоматическим поиском.

- Использует индекс приложений (app_indexer.load_app_index) — список объектов {name, path, variants}.
- Проверяет, что exe совместим (32/64-битный PE).
- Умеет запускать системные команды и обычные программы.
- Поддерживает статические и динамические алиасы: как пользователь говорит → реальное имя из индекса.
"""

import os
import json
import subprocess
from pathlib import Path
import traceback
from typing import Any, Optional
from Logger import logger
import winreg
import win32file  # для проверки типа бинарника через GetBinaryType

from app_indexer import load_app_index, APP_INDEX_PATH
from transcription import RussianTranscriber, AppNameMatcher
from words_config import APP_NAME_ALIASES


# Пути к конфигам
CONFIG_PATH = Path(__file__).parent / "apps.json"      # кеш путей (если нужно)
ALIASES_PATH = Path(__file__).parent / "aliases.json"  # динамические алиасы

print("DEBUG APP_INDEX_PATH:", APP_INDEX_PATH)
APP_INDEX = load_app_index()
print("DEBUG APP_INDEX size:", len(APP_INDEX))


# Системные приложения (человек → команда)
SYSTEM_APPS = {
    "калькулятор": "calc",
    "calc": "calc",
    "calculator": "calc",

    "блокнот": "notepad",
    "notepad": "notepad",

    "paint": "mspaint",
    "паинт": "mspaint",

    "проводник": "explorer",
    "explorer": "explorer",

    "диспетчер задач": "taskmgr",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",

    "cmd": "cmd",
    "командная строка": "cmd",

    "powershell": "powershell",
    "павершелл": "powershell",
}


# Статические алиасы: заранее известные фразы → каноническое имя из индекса
ALIASES_STATIC = {
    # Escape from Tarkov
    "эскейп фромтарков": "escape from tarkov",
    "эскейп фром тарков": "escape from tarkov",
    "эскейп тарков": "escape from tarkov",
    "тарков": "escape from tarkov",

    # Escape the Backrooms
    "эскейп за бэкрумс": "escape the backrooms",
    "эскейп зэ бэкрумс": "escape the backrooms",
    "эскейп бэкрумс": "escape the backrooms",
    "эскейп за": "escape the backrooms",

    # Wallpaper Engine (пример)
    "вэлл пэпер энджин": "wallpaper engine",
    "вэлл пэпер энжен": "wallpaper engine",
    "валл пейпер энжин": "wallpaper engine",
    "валл пейпер": "wallpaper engine",

    # PAYDAY 2 (пример)
    "пей дей два": "payday 2",
    "пейдей два": "payday 2",
    "пей дей 2": "payday 2",
    "пейдей 2": "payday 2",
}


# ==========================
# Проверка бинарника
# ==========================

def is_executable_compatible(path: str) -> bool:
    """
    Проверяет, что файл — нормальный Windows-исполняемый файл (32/64 бит),
    а не старый/битый/левый бинарник.
    """
    if not os.path.isfile(path):
        return False
    try:
        bin_type = win32file.GetBinaryType(path)
        # SCS_32BIT_BINARY = 0, SCS_64BIT_BINARY = 6
        return bin_type in (0, 6)
    except Exception:
        return False


# ==========================
# Работа с конфигом приложений (apps.json)
# ==========================

def load_config() -> dict:
    """Загрузка сохранённых путей к приложениям."""
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict):
    """Сохранение путей к приложениям."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def register_app(name: str, path: str):
    """Регистрация приложения в кеше (если путь совместим)."""
    if not is_executable_compatible(path):
        return
    name = name.lower().strip()
    config = load_config()
    config[name] = path
    save_config(config)


def list_registered_apps():
    """Показать список сохранённых приложений."""
    config = load_config()
    if not config:
        print("📝 Юко: у меня пока нет сохранённых приложений")
        return

    print("📝 Юко: я знаю эти приложения:")
    for name, path in config.items():
        exists = "✅" if os.path.isfile(path) and is_executable_compatible(path) else "❌"
        print(f"  {exists} {name}: {path}")


# ==========================
# Динамические алиасы (aliases.json)
# ==========================

def load_aliases() -> dict:
    """Загрузка динамических алиасов (как я говорю → реальное имя из индекса)."""
    if ALIASES_PATH.is_file():
        try:
            with open(ALIASES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_aliases(aliases: dict):
    """Сохранение динамических алиасов."""
    with open(ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)


ALIASES_DYNAMIC: dict[str, str] = load_aliases()


def teach_alias(spoken: str, actual_name: str):
    """
    Запоминает, что фраза spoken (как пользователь сказал) означает приложение actual_name (из индекса).
    """
    spoken_q = _normalize_name(spoken)
    actual_q = _normalize_name(actual_name)

    if not spoken_q or not actual_q:
        return

    aliases = load_aliases()
    aliases[spoken_q] = actual_q
    save_aliases(aliases)
    ALIASES_DYNAMIC.clear()
    ALIASES_DYNAMIC.update(aliases)

    print(f"DEBUG teach_alias: '{spoken_q}' -> '{actual_q}' сохранён в aliases.json")


# ==========================
# Вспомогательные нормализации
# ==========================

def translit_ru_to_lat(s: str) -> str:
    """Очень простой транслит кириллицы в латиницу для матчинга имён."""
    table = {
        "а": "a",  "б": "b",  "в": "v",   "г": "g",  "д": "d",
        "е": "e",  "ё": "e",  "ж": "zh",  "з": "z",  "и": "i",
        "й": "y",  "к": "k",  "л": "l",   "м": "m",  "н": "n",
        "о": "o",  "п": "p",  "р": "r",   "с": "s",  "т": "t",
        "у": "u",  "ф": "f",  "х": "h",   "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "sch","ъ": "",    "ы": "y",  "ь": "",
        "э": "e",  "ю": "yu", "я": "ya",
        " ": " ",
    }
    res = []
    for ch in s.lower():
        res.append(table.get(ch, ch))
    return "".join(res)


def _normalize_name(raw: str) -> str:
    s = (raw or "").strip().lower()
    for ch in [".", ",", "!", "?", "-", "_"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


# ==========================
# Индекс приложений в памяти + умный поиск
# ==========================

_APP_INDEX_CACHE: list[dict] | None = None


def _get_app_index() -> list[dict]:
    global _APP_INDEX_CACHE
    if _APP_INDEX_CACHE is None:
        global APP_INDEX
        if APP_INDEX:
            _APP_INDEX_CACHE = APP_INDEX
        else:
            _APP_INDEX_CACHE = load_app_index()
        print(f"DEBUG app_launcher: loaded {_APP_INDEX_CACHE and len(_APP_INDEX_CACHE) or 0} apps from index")
    return _APP_INDEX_CACHE or []

def find_app_by_name(query: str, threshold: float = 0.45) -> Optional[str]:
    query = (query or "").strip().lower()
    if not query:
        return None

    index = _get_app_index()
    if not index:
        print("DEBUG app_launcher: empty app index")
        return None

    # 1) Точное совпадение по name
    for item in index:
        name = str(item.get("name", "")).strip().lower()
        path = str(item.get("path", "")).strip()
        if not name or not path:
            continue
        if name == query:
            print(f"DEBUG app_launcher: exact match '{query}' -> '{name}' -> {path}")
            return path

    # 2) Fuzzy‑поиск по variants
    candidates_texts: list[str] = []
    candidates_meta: list[tuple[str, str]] = []

    for item in index:
        display_name = item["name"]
        path = item["path"]
        variants = item.get("variants")
        if not isinstance(variants, list):
            variants = RussianTranscriber.normalize_app_name(display_name)
        for v in variants:
            v_clean = (v or "").strip().lower()
            if not v_clean:
                continue
            candidates_texts.append(v_clean)
            candidates_meta.append((display_name, path))

    best_text, score = AppNameMatcher.find_best_match(query, candidates_texts, threshold=threshold)
    if not best_text:
        print(f"DEBUG app_launcher: no fuzzy match for '{query}' (score < {threshold})")
        return None

    for (display_name, path), cand_text in zip(candidates_meta, candidates_texts):
        if cand_text == best_text:
            print(
                f"DEBUG app_launcher: fuzzy matched '{query}' -> "
                f"'{display_name}' ({best_text}), score={score:.3f}"
            )
            return path

    return None


# ==========================
# Поиск пути к приложению
# ==========================

def find_app_path(app_name: str) -> Optional[str]:
    """
    Основной поиск пути к приложению.
      0. Алиасы (статические, динамические, APP_NAME_ALIASES).
      1. Индекс приложений (точный + fuzzy).
      2. Системные команды.
      3. Кеш (apps.json).
      4. Реестр.
      5. Меню Пуск.
      6. Файловая система.
    """
    original_spoken = app_name
    query = _normalize_name(app_name)
    print(f"DEBUG find_app_path: asked_for='{app_name}' canon='{query}'")

    if not query:
        print("DEBUG find_app_path: empty query after normalize")
        return None

    query_translit = translit_ru_to_lat(query)
    if query_translit != query:
        print(f"DEBUG translit: '{query}' -> '{query_translit}'")

    # 0. Статические алиасы
    if query in ALIASES_STATIC:
        alias = ALIASES_STATIC[query]
        print(f"DEBUG alias(static): '{query}' -> '{alias}'")
        query = _normalize_name(alias)
        query_translit = translit_ru_to_lat(query)

    # 0.1. Динамические алиасы
    if query in ALIASES_DYNAMIC:
        alias = ALIASES_DYNAMIC[query]
        print(f"DEBUG alias(dynamic): '{query}' -> '{alias}'")
        query = _normalize_name(alias)
        query_translit = translit_ru_to_lat(query)

    # 0.2. Алиасы из words_config.APP_NAME_ALIASES
    alias_wc = APP_NAME_ALIASES.get(query)
    if alias_wc:
        print(f"DEBUG alias(words_config): '{query}' -> '{alias_wc}'")
        query = _normalize_name(alias_wc)
        query_translit = translit_ru_to_lat(query)

    # 1. Умный поиск по индексу
    smart_path = find_app_by_name(query)
    if smart_path:
        print(f"DEBUG find_app_path: smart matcher hit -> {smart_path}")
        register_app(query, smart_path)
        return smart_path

    # 2. Системные приложения
    if query in SYSTEM_APPS:
        return SYSTEM_APPS[query]

    # 3. Кеш (apps.json)
    config = load_config()
    if query in config:
        path = config[query]
        if is_executable_compatible(path) or (path in SYSTEM_APPS.values() and os.path.sep not in path):
            return path

    # 4. Реестр / 5. Пуск / 6. Файловая система — оставим как резерв,
    # если тебе нужно — можно вернуть твой старый код этих функций и вызывать их здесь.
    print(f"DEBUG find_app_path: no path found for '{app_name}'")
    return None

# ==========================
# Запуск приложения
# ==========================

def launch_app(path: str) -> bool:
    try:
        if not path:
            logger.error("launch_app: empty path")
            return False

        if not os.path.exists(path):
            logger.error(f"launch_app: path not exists: {path}")
            return False

        ext = os.path.splitext(path)[1].lower()

        # --- новое: поддержка ярлыков ---
        if ext == ".lnk":
            try:
                os.startfile(path)
                logger.info(f"launch_app: started shortcut: {path}")
                return True
            except OSError as e:
                logger.error(f"launch_app: failed to start .lnk {path}: {e}")
                return False

        # --- твоя старая ветка для .exe ---
        if ext == ".exe":
            try:
                subprocess.Popen([path])
                logger.info(f"launch_app: started exe: {path}")
                return True
            except Exception as e:
                logger.error(f"launch_app: failed to start exe {path}: {e}")
                return False

        logger.error(f"launch_app: unsupported extension: {path}")
        return False

    except Exception as e:
        logger.error(f"launch_app: unexpected error for {path}: {e}")
        return False


def open_app(app_name: str) -> bool:
    """Алиас для launch_app."""
    return launch_app(app_name)


__all__ = [
    "launch_app",
    "open_app",
    "list_registered_apps",
    "register_app",
    "find_app_path",
]
