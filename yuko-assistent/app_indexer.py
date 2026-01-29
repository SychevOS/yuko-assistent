"""
app_indexer.py
Сканирует систему и строит индекс установленных приложений:
  - DisplayName из реестра (Uninstall)
  - ярлыки из меню Пуск
  - верхний уровень Program Files / Program Files (x86)
Результат: список объектов { "name": <str>, "path": <str> } в app_index.json.
"""

import os
import json
from pathlib import Path
import winreg
import win32file


APP_INDEX_PATH = Path(__file__).parent / "app_index.json"


# exe, которые НЕ хотим считать запускаемыми приложениями (жёсткие имена)
BAD_LEAFS = {
    "unins000.exe",
    "uninstall.exe",
    "setup.exe",
    "install.exe",
    "vc_redist.x86.exe",
    "vc_redist.x64.exe",
}

# Подстроки в имени файла, которые считаем "служебными"/вспомогательными
BAD_SUBSTRINGS = [
    "updater", "update", "crash", "dump", "helper",
    "streaming_client", "streaming-client",
    "unins", "uninstall", "report", "bug",
    "diagnostic", "service", "watcher", "tray",
    "bootstrapper", "installer", "setup",
]


def is_executable_compatible(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        bin_type = win32file.GetBinaryType(path)
        # 0 = 32-bit, 6 = 64-bit
        return bin_type in (0, 6)
    except Exception:
        return False


def is_main_exe(path: Path) -> bool:
    """
    Общий фильтр "главных" exe:
      - отбрасываем по BAD_SUBSTRINGS,
      - отбрасываем слишком маленькие exe (часто это лаунчеры/утилиты).
    """
    name = path.stem.lower()

    if any(bad in name for bad in BAD_SUBSTRINGS):
        return False

    try:
        size = path.stat().st_size
        if size < 200 * 1024:  # 200 KB
            return False
    except OSError:
        return False

    return True


def _prefer_real_exe(exe_path: str) -> str:
    """
    Если путь похож на лаунчер/апдейтер, пробуем найти более «настоящий» exe
    в той же папке (крупный файл, не update/launcher/install/setup).
    """
    bad_names = {"update.exe", "launcher.exe", "install.exe", "setup.exe", "uninstall.exe", "unins000.exe"}

    p = Path(exe_path)
    if p.name.lower() not in bad_names:
        return exe_path

    folder = p.parent
    if not folder.exists():
        return exe_path

    candidates = []
    try:
        for f in folder.glob("*.exe"):
            if f.name.lower() in bad_names:
                continue
            if f.stat().st_size < 5_000_000:
                continue
            if not is_executable_compatible(str(f)):
                continue
            # общий фильтр "главных" exe
            if not is_main_exe(f):
                continue
            candidates.append(f)
    except (PermissionError, OSError):
        return exe_path

    if not candidates:
        return exe_path

    best = max(candidates, key=lambda x: x.stat().st_mtime)
    return str(best)


# ---------- Скан реестра ----------

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


def scan_registry_apps() -> list[dict]:
    apps = []
    for hive, subkey_path in _iter_uninstall_keys():
        try:
            with winreg.OpenKey(hive, subkey_path) as subkey:
                try:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                except Exception:
                    continue

                if not display_name:
                    continue

                exe_path = None

                # DisplayIcon
                try:
                    display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                    icon_path = display_icon.split(",")[0].strip().strip('"')
                    if icon_path and is_executable_compatible(icon_path):
                        exe_path = icon_path
                except Exception:
                    pass

                # InstallLocation fallback
                if not exe_path:
                    try:
                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        if install_location and os.path.isdir(install_location):
                            for file in os.listdir(install_location):
                                if file.lower().endswith(".exe"):
                                    candidate = os.path.join(install_location, file)
                                    if not is_executable_compatible(candidate):
                                        continue
                                    # фильтр "главных" exe
                                    if not is_main_exe(Path(candidate)):
                                        continue
                                    exe_path = candidate
                                    break
                    except Exception:
                        pass

                if not exe_path:
                    continue

                exe_path = _prefer_real_exe(exe_path)

                leaf = Path(exe_path).name.lower()
                if leaf in BAD_LEAFS:
                    continue

                # окончательная проверка на "главность"
                if not is_main_exe(Path(exe_path)):
                    continue

                name_key = display_name.strip().lower()
                apps.append({"name": name_key, "path": exe_path})
        except Exception:
            continue
    return apps


# ---------- Скан меню Пуск ----------

def scan_start_menu_apps() -> list[dict]:
    apps = []

    start_menu_paths = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
    ]

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        return apps

    for base in start_menu_paths:
        if not base.exists():
            continue
        for shortcut in base.rglob("*.lnk"):
            try:
                shortcut_obj = shell.CreateShortcut(str(shortcut))
                target = shortcut_obj.TargetPath
                if not target or not is_executable_compatible(target):
                    continue
                # фильтр "главных" exe и здесь, чтобы не ловить ярлыки на апдейтеры
                if not is_main_exe(Path(target)):
                    continue
                display_name = shortcut.stem
                name_key = display_name.strip().lower()
                apps.append({"name": name_key, "path": target})
            except Exception:
                continue

    return apps


# ---------- Скан Program Files (верхний уровень) ----------

def scan_program_files() -> list[dict]:
    apps = []
    base_dirs = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ]
    bad_names = {"unins000.exe", "uninstall.exe", "update.exe", "launcher.exe", "install.exe", "setup.exe"}

    for base in base_dirs:
        if not base.exists():
            continue

        for app_dir in base.iterdir():
            if not app_dir.is_dir():
                continue

            exe_candidates = []
            try:
                for exe in app_dir.rglob("*.exe"):
                    name = exe.name.lower()
                    if name in bad_names:
                        continue
                    if exe.stat().st_size < 5_000_000:
                        continue
                    if not is_executable_compatible(str(exe)):
                        continue
                    # общий фильтр "главных" exe
                    if not is_main_exe(exe):
                        continue
                    exe_candidates.append(exe)
            except (PermissionError, OSError):
                continue

            if not exe_candidates:
                continue

            main_exe = max(exe_candidates, key=lambda x: x.stat().st_mtime)

            leaf = main_exe.name.lower()
            if leaf in BAD_LEAFS:
                continue

            if not is_main_exe(main_exe):
                continue

            display_name = app_dir.name.replace("_", " ").replace("-", " ")
            name_key = display_name.strip().lower()
            apps.append({"name": name_key, "path": str(main_exe)})

    return apps


# ---------- Построение индекса ----------

def build_app_index() -> list[dict]:
    """
    Строит общий индекс приложений и сохраняет его в app_index.json.

      1. Реестр (Uninstall)
      2. Меню Пуск
      3. Program Files / Program Files (x86)
    """
    index: list[dict] = []

    print("DEBUG app_indexer: scanning registry...")
    reg_apps = scan_registry_apps()
    print("DEBUG app_indexer: registry apps:", len(reg_apps))
    index.extend(reg_apps)

    print("DEBUG app_indexer: scanning start menu...")
    start_apps = scan_start_menu_apps()
    print("DEBUG app_indexer: start menu apps:", len(start_apps))
    index.extend(start_apps)

    print("DEBUG app_indexer: scanning Program Files...")
    pf_apps = scan_program_files()
    print("DEBUG app_indexer: pf apps:", len(pf_apps))
    index.extend(pf_apps)

    # удаляем дубли по (name, path)
    seen = set()
    unique_index = []
    for item in index:
        key = (item["name"], item["path"])
        if key in seen:
            continue
        seen.add(key)
        unique_index.append(item)

    print("DEBUG app_indexer: total apps:", len(unique_index))

    try:
        with open(APP_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(unique_index, f, ensure_ascii=False, indent=2)
        print("DEBUG app_indexer: index saved to", APP_INDEX_PATH)
    except Exception as e:
        print("ERROR app_indexer: failed to save index:", e)

    return unique_index


def load_app_index() -> list[dict]:
    if APP_INDEX_PATH.is_file():
        try:
            with open(APP_INDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            result = []
            for item in data:
                name = str(item.get("name", "")).strip().lower()
                path = str(item.get("path", "")).strip()
                if name and path:
                    result.append({"name": name, "path": path})
            return result
        except Exception:
            return []
    return []
