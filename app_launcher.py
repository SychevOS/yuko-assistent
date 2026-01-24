"""
app_launcher.py
Модуль для запуска приложений Windows с умным автоматическим поиском.

- Использует индекс приложений (app_indexer.load_app_index) — список объектов {name, path}.
- Проверяет, что exe совместим (32/64-битный PE).
- Умеет запускать системные команды и обычные программы.
- Поддерживает статические и динамические алиасы: как пользователь говорит → реальное имя из индекса.
"""

import os
import json
import subprocess
from pathlib import Path
import traceback
from typing import Any
import winreg
import win32file  # для проверки типа бинарника через GetBinaryType

from app_indexer import load_app_index, APP_INDEX_PATH  # индекс путей (list[{"name","path"}])


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

    "anydesk": "AnyDesk",
    "энни дэск": "AnyDesk",
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
# Методы поиска (реестр, Пуск, файловая система)
# ==========================

def _iter_uninstall_keys():
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, subkey_path in reg_paths:
        try:
            with winreg.OpenKey(hive, subkey_path) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        yield hive, f"{subkey_path}\\{subkey_name}"
                    except Exception:
                        continue
        except Exception:
            continue


def find_app_in_registry(app_name: str) -> str | None:
    app_name = app_name.lower().strip()

    try:
        for hive, full_subkey_path in _iter_uninstall_keys():
            try:
                with winreg.OpenKey(hive, full_subkey_path) as subkey:
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except Exception:
                        display_name = ""

                    if not display_name:
                        continue

                    if app_name not in display_name.lower():
                        continue

                    display_icon = ""
                    install_location = ""

                    try:
                        display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                    except Exception:
                        display_icon = ""

                    try:
                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                    except Exception:
                        install_location = ""

                    candidates: list[str] = []

                    if display_icon:
                        icon_path = display_icon.split(",")[0].strip().strip('"')
                        if icon_path and os.path.isfile(icon_path):
                            candidates.append(icon_path)

                    if install_location and os.path.isdir(install_location):
                        for file in os.listdir(install_location):
                            if not file.lower().endswith(".exe"):
                                continue
                            stem = file.lower()
                            if app_name in stem or any(t in stem for t in app_name.split()):
                                full_path = os.path.join(install_location, file)
                                candidates.append(full_path)

                    for path in candidates:
                        if is_executable_compatible(path):
                            return path
            except Exception:
                continue
    except Exception:
        pass

    return None


def find_in_start_menu(app_name: str) -> str | None:
    app_name_lower = app_name.lower().strip()
    try:
        start_menu_paths = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        ]

        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")

        for start_path in start_menu_paths:
            if not start_path.exists():
                continue

            for shortcut in start_path.rglob("*.lnk"):
                if app_name_lower in shortcut.stem.lower():
                    try:
                        shortcut_obj = shell.CreateShortcut(str(shortcut))
                        target = shortcut_obj.TargetPath
                        if target and is_executable_compatible(target):
                            return target
                    except Exception:
                        continue
    except Exception:
        pass
    return None


def search_filesystem(app_name: str) -> str | None:
    app_name_lower = app_name.lower().strip()
    search_terms = [app_name_lower]
    if " " in app_name_lower:
        search_terms.append(app_name_lower.replace(" ", ""))

    search_paths = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path.home() / "AppData" / "Local" / "Programs",
        Path.home() / "AppData" / "Roaming",
    ]

    for base_path in search_paths:
        if not base_path.exists():
            continue
        try:
            checked = 0
            max_checked = 5000

            for exe_file in base_path.rglob("*.exe"):
                checked += 1
                if checked > max_checked:
                    break

                stem_lower = exe_file.stem.lower()
                if any(term in stem_lower for term in search_terms):
                    try:
                        if exe_file.stat().st_size > 10000 and is_executable_compatible(str(exe_file)):
                            return str(exe_file)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue

    return None


# ==========================
# Универсальный матчинг имени
# ==========================
def translit_ru_to_lat(s: str) -> str:
    """Очень простой транслит кириллицы в латиницу для матчингa имён."""
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
    s = raw.strip().lower()
    for ch in [".", ",", "!", "?", "-", "_"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _score_name(query: str, candidate: str) -> float:
    """
    Простая метрика похожести:
      - общие слова
      - длина
      - бонус за совпадение начала/точное совпадение
      - штраф за слова типа service/updater/helper/client/streaming
    """
    if not query or not candidate:
        return 0.0

    q = _normalize_name(query)
    c = _normalize_name(candidate)

    q_words = set(q.split())
    c_words = set(c.split())

    if not q_words or not c_words:
        return 0.0

    common = q_words & c_words
    if not common:
        return 0.0

    word_score = len(common) / max(len(q_words), len(c_words))
    len_score = 1.0 - abs(len(c) - len(q)) / max(len(c), len(q), 1)
    prefix_score = 1.0 if c.startswith(q) or q.startswith(c) else 0.0

    bad_words = {"service", "updater", "helper", "client", "streaming", "bootstrapper"}
    penalty = 0.0
    if any(bad in c_words for bad in bad_words):
        penalty = 0.3

    exact_bonus = 0.0
    if q == c:
        exact_bonus = 0.3

    base = 0.5 * word_score + 0.4 * len_score + 0.1 * prefix_score
    return max(0.0, base + exact_bonus - penalty)


# ==========================
# Основная логика поиска пути
# ==========================

from typing import Any  # убедись, что это есть вверху файла

def find_app_path(app_name: str) -> str | None:
    """
    Основной поиск пути к приложению.
      0. Алиасы (статические и динамические).
      1. Индекс приложений (APP_INDEX) с _score_name + транслит кириллицы→латиницу.
      2. Системные команды.
      3. Кеш (apps.json).
      4. Реестр.
      5. Меню Пуск.
      6. Файловая система.
    """
    # как сказал пользователь (сырая фраза из ASR)
    original_spoken = app_name

    query = _normalize_name(app_name)
    print(f"DEBUG find_app_path: asked_for='{app_name}' canon='{query}'")

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

    best_score = 0.0
    best_path: str | None = None
    best_item: dict[str, Any] | None = None
    scored: list[tuple[float, str, str]] = []  # (score, name, path)

    # 1. Индекс приложений
    if APP_INDEX:
        for item in APP_INDEX:
            name = item.get("name", "")
            path = item.get("path", "")
            if not name or not path:
                continue
            if not os.path.isfile(path) or not is_executable_compatible(path):
                continue

            score_orig = _score_name(query, name)
            score_translit = _score_name(query_translit, name) if query_translit else 0.0
            score = max(score_orig, score_translit)

            # Fallback: если _score_name дал 0, пробуем тупой подстроковый матч
            if score == 0.0:
                q = (query_translit or query).lower()
                n = name.lower()
                simple_score = 0.0
                if q and q in n:
                    simple_score = len(q) / len(n)
                elif q and any(part and part in n for part in q.split()):
                    simple_score = 0.3
                score = simple_score

            scored.append((score, name, path))

            if score > best_score:
                best_score = score
                best_path = path
                best_item = item

        if scored:
            scored.sort(reverse=True, key=lambda x: x[0])
            print("DEBUG candidates (top 5):")
            for s, n, p in scored[:5]:
                print(f"  {s:.2f}  {n}  ->  {p}")

        THRESHOLD = 0.3
        if best_path and best_score >= THRESHOLD:
            print(f"DEBUG index match: '{query}' score={best_score:.2f} -> {best_path}")

            # Авто-обучение алиаса
            if best_item:
                canonical_name = best_item.get("name", "")
                spoken_norm = _normalize_name(original_spoken)
                canonical_norm = _normalize_name(canonical_name)
                print(
                    f"DEBUG alias_check: spoken='{spoken_norm}' "
                    f"canonical='{canonical_norm}' score={best_score:.2f}"
                )
                if spoken_norm and canonical_norm and spoken_norm != canonical_norm:
                    teach_alias(spoken_norm, canonical_name)

            return best_path

    # 2. Системные приложения
    if query in SYSTEM_APPS:
        return SYSTEM_APPS[query]

    # 3. Кеш (apps.json)
    config = load_config()
    if query in config:
        path = config[query]
        if is_executable_compatible(path) or (path in SYSTEM_APPS.values() and os.path.sep not in path):
            return path

    # 4. Реестр
    reg_path = find_app_in_registry(original_spoken)
    if reg_path:
        register_app(query, reg_path)
        return reg_path

    # 5. Меню Пуск
    start_menu_path = find_in_start_menu(original_spoken)
    if start_menu_path:
        register_app(query, start_menu_path)
        return start_menu_path

    # 6. Файловая система
    fs_path = search_filesystem(original_spoken)
    if fs_path:
        register_app(query, fs_path)
        return fs_path

    print(f"DEBUG find_app_path: no path found for '{app_name}'")
    return None




# ==========================
# Запуск приложения
# ==========================

def launch_app(app_name: str, args: list | None = None) -> bool:
    app_name_clean = app_name.strip()
    app_path = find_app_path(app_name_clean)

    if not app_path:
        print(f"DEBUG launch_app: path not found for '{app_name_clean}'")
        return False

    # финальная проверка
    if not (app_path in SYSTEM_APPS.values() and os.path.sep not in app_path):
        if not is_executable_compatible(app_path):
            print(f"DEBUG launch_app: incompatible exe '{app_path}'")
            return False

    print(f"DEBUG launch_app: about to run '{app_path}'")

    try:
        cmd = [app_path]
        if args:
            cmd.extend(args)
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        print("DEBUG launch_app ERROR:", e)
        traceback.print_exc()
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
