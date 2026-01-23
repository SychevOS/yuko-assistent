"""
Модуль для запуска приложений Windows с умным поиском
"""

import os
import json
import subprocess
from pathlib import Path
import winreg
import win32api
import win32con

# Путь к конфигу приложений
CONFIG_PATH = Path(__file__).parent / "apps.json"

# Системные приложения (короткие имена)
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

    "AnyDesk": "AnyDesk",
    "энни дэск": "AnyDesk",
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
        # Ищем в стандартных местах реестра
        registry_locations = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\Applications"),
        ]

        for hive, key_path in registry_locations:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            if app_name.lower() in subkey_name.lower().replace('.exe', ''):
                                subkey_path = f"{key_path}\\{subkey_name}"
                                with winreg.OpenKey(hive, subkey_path) as subkey:
                                    path = winreg.QueryValue(subkey, None)
                                    if os.path.isfile(path):
                                        return path
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception:
        pass
    return None

def search_filesystem(app_name: str) -> str | None:
    """
    Умный поиск приложения по файловой системе
    Ищет .exe файлы содержащие имя приложения
    """
    app_name_lower = app_name.lower().strip()

    # Расширяем поисковый запрос
    search_terms = [app_name_lower]
    if ' ' in app_name_lower:
        search_terms.append(app_name_lower.replace(' ', ''))

    # Типичные места установки программ
    search_paths = [

        # Рабочий стол и документы
        Path.home() / "Desktop",
        Path.home() / "Documents",

        # Program Files
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),

        # AppData пользователя
        Path.home() / "AppData" / "Local" / "Programs",
        Path.home() / "AppData" / "Roaming",

        # Корень дисков
        Path(r"C:\\"),
        Path(r"D:\\"),
    ]

    # Быстрый поиск по известным путям
    for base_path in search_paths:
        if not base_path.exists():
            continue

        try:
            # Сначала ищем по точному имени
            for exe_file in base_path.rglob(f"*{app_name_lower}*.exe"):
                if any(term in exe_file.stem.lower() for term in search_terms):
                    if exe_file.stat().st_size > 10000:  # Не слишком маленький файл
                        return str(exe_file)

            # Затем ищем по частичному совпадению
            for exe_file in base_path.rglob("*.exe"):
                stem_lower = exe_file.stem.lower()
                if any(term in stem_lower for term in search_terms):
                    if exe_file.stat().st_size > 10000:
                        return str(exe_file)

        except (PermissionError, OSError):
            continue

    return None

def find_in_start_menu(app_name: str) -> str | None:
    """Поиск приложения в меню Пуск"""
    try:
        start_menu_paths = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        ]

        app_name_lower = app_name.lower()

        for start_path in start_menu_paths:
            if not start_path.exists():
                continue

            for shortcut in start_path.rglob("*.lnk"):
                if app_name_lower in shortcut.stem.lower():
                    # Пытаемся получить целевой путь из ярлыка
                    try:
                        import win32com.client
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shortcut_obj = shell.CreateShortcut(str(shortcut))
                        target = shortcut_obj.TargetPath
                        if target and os.path.isfile(target):
                            return target
                    except Exception:
                        # Если не получилось, просто вернем имя ярлыка
                        return str(shortcut)
    except Exception:
        pass
    return None

def search_app_windows_api(app_name: str) -> str | None:
    """Поиск через Windows API"""
    try:
        import ctypes
        from ctypes import wintypes

        # Используем SHGetFolderPath для получения специальных папок
        CSIDL_PROGRAMS = 0x0002
        SHGFP_TYPE_CURRENT = 0

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PROGRAMS, None, SHGFP_TYPE_CURRENT, buf)
        programs_path = buf.value

        # Ищем в папке программ
        for root, dirs, files in os.walk(programs_path):
            for file in files:
                if file.endswith('.exe') and app_name.lower() in file.lower():
                    full_path = os.path.join(root, file)
                    if os.path.exists(full_path):
                        return full_path
    except Exception:
        pass
    return None

def find_app_path(app_name: str) -> str | None:
    """Умный поиск пути к приложению с использованием всех методов"""
    app_name_lower = app_name.lower().strip()

    # 1. Системные приложения
    if app_name_lower in SYSTEM_APPS:
        return SYSTEM_APPS[app_name_lower]

    # 2. Сохранённая конфигурация
    config = load_config()
    if app_name_lower in config:
        path = config[app_name_lower]
        if os.path.isfile(path):
            return path

    # 3. Реестр Windows
    registry_path = find_app_in_registry(app_name_lower)
    if registry_path:
        return registry_path

    # 4. Меню Пуск
    start_menu_path = find_in_start_menu(app_name_lower)
    if start_menu_path:
        return start_menu_path

    # 5. Поиск по файловой системе
    filesystem_path = search_filesystem(app_name_lower)
    if filesystem_path:
        return filesystem_path

    # 6. Windows API
    api_path = search_app_windows_api(app_name_lower)
    if api_path:
        return api_path

    return None

def smart_search(app_name: str) -> list:
    """
    Умный поиск всех возможных вариантов приложения
    Возвращает список найденных путей
    """
    app_name_lower = app_name.lower().strip()
    found_paths = []

    # Все методы поиска
    search_methods = [
        ("Filesystem", search_filesystem),
        ("Registry", find_app_in_registry),
        ("Start Menu", find_in_start_menu),
    ]

    for method_name, method_func in search_methods:
        try:
            result = method_func(app_name_lower)
            if result and os.path.exists(result) and result not in found_paths:
                found_paths.append(result)
        except Exception:
            continue

    return found_paths

def register_app(name: str, path: str):
    """Ручная регистрация приложения"""
    name = name.lower().strip()
    config = load_config()
    config[name] = path
    save_config(config)

def launch_app(app_name: str, args: list = None) -> bool:
    """
    Запуск приложения по имени с интеллектуальным поиском
    """
    app_path = find_app_path(app_name)

    if not app_path:
        print(f"🔍 Юко: ищу '{app_name}'...")

        # Предлагаем умный поиск
        found_paths = smart_search(app_name)

        if found_paths:
            print(f"📋 Юко: нашла несколько вариантов:")
            for i, path in enumerate(found_paths[:5], 1):
                print(f"  {i}. {path}")

            try:
                choice = input("Выберите номер (или 0 для отмены): ")
                if choice.isdigit() and 1 <= int(choice) <= len(found_paths):
                    app_path = found_paths[int(choice) - 1]
                    # Запоминаем выбранный путь
                    register_app(app_name, app_path)
                else:
                    return False
            except Exception:
                return False
        else:
            print(f"❌ Юко: не нашла приложение '{app_name}'")
            print("💡 Подсказка:")
            print("  1. Укажите полный путь к .exe файлу")
            print("  2. Или перетащите файл сюда")

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

def open_app(app_name: str):
    """Алиас для launch_app"""
    return launch_app(app_name)

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

# Дополнительные функции
def search_and_launch(app_name: str):
    """Поиск и запуск с выбором из найденного"""
    return launch_app(app_name)

def get_installed_apps() -> list:
    """Получить список установленных программ"""
    try:
        import winreg
        apps = []

        # Читаем из реестра установленные программы
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, path in reg_paths:
            try:
                with winreg.OpenKey(hive, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                    if display_name:
                                        apps.append({
                                            "name": display_name,
                                            "path": install_location if install_location else ""
                                        })
                                except Exception:
                                    continue
                        except Exception:
                            continue
            except Exception:
                continue

        return apps
    except Exception:
        return []

__all__ = ["launch_app", "list_registered_apps", "register_app", "find_app_path",
           "search_and_launch", "get_installed_apps", "smart_search"]

if __name__ == "__main__":
    print("🧪 Тест модуля app_launcher с умным поиском")
    print("=" * 50)

    test_apps = ["калькулятор", "discord", "telegram", "whatsapp", "steam"]

    for app in test_apps:
        print(f"\n🔍 Поиск: {app}")
        found = smart_search(app)
        if found:
            print(f"✅ Найдено {len(found)} вариантов:")
            for path in found[:3]:
                print(f"   • {path}")
        else:
            print(f"❌ Не найдено")

    # Тест запуска
    print("\n" + "=" * 50)
    user_app = input("Введите имя программы для запуска: ")
    if user_app:
        launch_app(user_app)