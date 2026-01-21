"""
Модуль для запуска приложений Windows
Поддерживает автопоиск и ручную регистрацию программ
"""

import os
import json
import subprocess
from pathlib import Path
import winreg

# Путь к конфигу приложений
CONFIG_PATH = Path(__file__).parent / "apps.json"

# Базовые приложения Windows (работают без полного пути)
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

# Популярные приложения и их возможные пути
COMMON_APPS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "opera": [
        r"C:\Users\{username}\AppData\Local\Programs\Opera\opera.exe",
    ],
    "opera gx": [
        r"C:\Users\{username}\AppData\Local\Programs\Opera GX\opera.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
    "telegram": [
        r"C:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe",
    ],
    "discord": [
        r"C:\Users\{username}\AppData\Local\Discord\Update.exe",
        r"C:\Users\{username}\AppData\Local\Discord\app-*\Discord.exe",
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ],
    "spotify": [
        r"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe",
    ],
    "vscode": [
        r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "code": [
        r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "word": [
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    ],
    "excel": [
        r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    ],
    "photoshop": [
        r"C:\Program Files\Adobe\Adobe Photoshop *\Photoshop.exe",
    ],
}

def load_config() -> dict:
    """Загрузка сохранённых путей к приложениям"""
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config: dict):
    """Сохранение путей к приложениям"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def find_app_in_registry(app_name: str) -> str | None:
    """Поиск приложения в реестре Windows"""
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    if app_name.lower() in subkey_name.lower():
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            path = winreg.QueryValue(subkey, None)
                            if os.path.isfile(path):
                                return path
                except Exception:
                    continue
    except Exception:
        pass
    return None

def find_app_path(app_name: str) -> str | None:
    """Умный поиск пути к приложению"""
    app_name = app_name.lower().strip()

    # 1. Системные приложения
    if app_name in SYSTEM_APPS:
        return SYSTEM_APPS[app_name]

    # 2. Сохранённая конфигурация
    config = load_config()
    if app_name in config:
        path = config[app_name]
        if os.path.isfile(path):
            return path

    # 3. Популярные приложения
    username = os.environ.get("USERNAME", "Administrator")

    for key, paths in COMMON_APPS.items():
        if app_name in key or key in app_name:
            for path_template in paths:
                path = path_template.replace("{username}", username)

                # Поддержка wildcards
                if "*" in path:
                    from glob import glob
                    matches = glob(path)
                    if matches:
                        return matches[0]
                elif os.path.isfile(path):
                    return path

    # 4. Реестр
    registry_path = find_app_in_registry(app_name)
    if registry_path:
        return registry_path

    # 5. Поиск по стандартным путям
    search_paths = [
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path.home() / "AppData" / "Local" / "Programs",
    ]

    for base_path in search_paths:
        if not base_path.exists():
            continue

        try:
            for item in base_path.iterdir():
                if not item.is_dir():
                    continue

                if app_name in item.name.lower():
                    for exe_file in item.rglob("*.exe"):
                        if app_name in exe_file.stem.lower():
                            return str(exe_file)
        except PermissionError:
            continue

    return None

def register_app(name: str, path: str):
    """Ручная регистрация приложения"""
    name = name.lower().strip()
    config = load_config()
    config[name] = path
    save_config(config)

def launch_app(app_name: str, args: list = None) -> bool:
    """
    Запуск приложения по имени
    """
    app_path = find_app_path(app_name)

    if not app_path:
        print(f"❌ Юко: не нашла приложение '{app_name}'")
        print("💡 Подсказка: перетащи сюда .exe файл программы")
        user_input = input("Путь к программе (или Enter для отмены): ").strip('" ').strip()

        if user_input and os.path.isfile(user_input):
            register_app(app_name, user_input)
            print(f"✅ Юко: запомнила {app_name}")
            app_path = user_input
        else:
            return False

    try:
        if app_path in SYSTEM_APPS.values():
            subprocess.Popen(app_path, shell=True)
        else:
            cmd = [app_path]
            if args:
                cmd.extend(args)
            subprocess.Popen(cmd)

        print(f"✅ Юко: запустила {app_name}")
        return True
    except Exception as e:
        print(f"❌ Юко: ошибка при запуске {app_name}: {e}")
        return False

def list_registered_apps():
    """Показать список зарегистрированных приложений"""
    config = load_config()

    if not config:
        print("📝 Юко: у меня пока нет сохранённых приложений")
        return

    print("📝 Юко: я знаю эти приложения:")
    for name, path in config.items():
        exists = "✅" if os.path.isfile(path) else "❌"
        print(f"  {exists} {name}: {path}")

def open_app(app_name: str):
    """Алиас для launch_app"""
    return launch_app(app_name)

__all__ = ["launch_app", "list_registered_apps", "register_app", "find_app_path"]

if __name__ == "__main__":
    print("🧪 Тест модуля app_launcher")
    print("=" * 50)

    test_apps = ["калькулятор", "chrome", "telegram", "vscode"]
    for app in test_apps:
        path = find_app_path(app)
        if path:
            print(f"✅ {app}: {path}")
        else:
            print(f"❌ {app}: не найден")
