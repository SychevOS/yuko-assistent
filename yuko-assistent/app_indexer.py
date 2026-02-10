# app_indexer.py
"""
Универсальный индексер приложений для Юко.

Собирает .exe из:
- реестра (Uninstall)
- меню Пуск
- Program Files / Program Files (x86)
- %LOCALAPPDATA%
- %APPDATA%

Фильтрует мусор по глубине, размеру и имени.
Результат кладёт в app_index.json:
[
  {"name": "...", "path": "...", "source": "...", "variants": [...]},
  ...
]
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any

import winreg

from Logger import logger
from transcription import RussianTranscriber

BASE_DIR = Path(__file__).parent
APP_INDEX_PATH = BASE_DIR / "app_index.json"


# ---------- общие утилиты ----------

def _is_good_exe(path: Path) -> bool:
    """
    Очень грубый фильтр .exe:
    - существует
    - размер > 200 КБ (отсекаем мелкий мусор)
    """
    try:
        if not path.is_file():
            return False
        if path.suffix.lower() != ".exe":
            return False
        if path.stat().st_size < 200 * 1024:
            return False
        return True
    except Exception:
        return False


def _make_entry(name: str, path: Path, source: str) -> Dict[str, Any]:
    norm_name = name.strip()
    variants = RussianTranscriber.normalize_app_name(norm_name)
    return {
        "name": norm_name,
        "path": str(path),
        "source": source,
        "variants": variants,
    }


# ---------- скан реестра ----------

def _scan_registry_apps() -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []

    uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for root, subkey in uninstall_roots:
        try:
            with winreg.OpenKey(root, subkey) as hkey:
                for i in range(0, winreg.QueryInfoKey(hkey)[0]):
                    try:
                        sk_name = winreg.EnumKey(hkey, i)
                        with winreg.OpenKey(hkey, sk_name) as sk:
                            try:
                                display_name, _ = winreg.QueryValueEx(sk, "DisplayName")
                            except OSError:
                                continue
                            try:
                                install_location, _ = winreg.QueryValueEx(sk, "InstallLocation")
                            except OSError:
                                install_location = ""

                            if not display_name:
                                continue

                            candidate = None
                            if install_location:
                                p = Path(install_location)
                                if p.is_dir():
                                    exe_name = display_name.split()[0] + ".exe"
                                    candidate = p / exe_name

                            if candidate and _is_good_exe(candidate):
                                apps.append(_make_entry(display_name, candidate, "registry"))
                    except OSError:
                        continue
        except OSError:
            continue

    logger.info(f"app_indexer: registry apps: {len(apps)}")
    return apps


# ---------- скан меню Пуск ----------

def _scan_start_menu() -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []
    start_menu_paths = []

    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        start_menu_paths.append(Path(programdata) / "Microsoft/Windows/Start Menu/Programs")

    appdata = os.environ.get("APPDATA")
    if appdata:
        start_menu_paths.append(Path(appdata) / "Microsoft/Windows/Start Menu/Programs")

    for base in start_menu_paths:
        if not base.is_dir():
            continue
        for lnk in base.rglob("*.lnk"):
            try:
                name = lnk.stem
                target = lnk  # ярлык; запускаем через os.startfile
                apps.append(_make_entry(name, target, "start_menu"))
            except Exception:
                continue

    logger.info(f"app_indexer: start menu apps: {len(apps)}")
    return apps


# ---------- скан Program Files ----------

def _scan_program_files() -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []

    pf_paths = []
    pf = os.environ.get("ProgramFiles")
    if pf:
        pf_paths.append(Path(pf))
    pf86 = os.environ.get("ProgramFiles(x86)")
    if pf86:
        pf_paths.append(Path(pf86))

    for base in pf_paths:
        if not base.is_dir():
            continue
        # ограничим глубину: 3 уровня
        for root, dirs, files in os.walk(base):
            depth = Path(root).relative_to(base).parts
            if len(depth) > 3:
                dirs[:] = []
                continue
            for fname in files:
                if not fname.lower().endswith(".exe"):
                    continue
                path = Path(root) / fname
                if not _is_good_exe(path):
                    continue
                name = fname[:-4]
                apps.append(_make_entry(name, path, "program_files"))

    logger.info(f"app_indexer: pf apps: {len(apps)}")
    return apps


# ---------- универсальный скан AppData ----------

def _scan_appdata() -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []

    roots: List[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata))
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata))

    preferred_dirs = [
        "Discord",
        "Telegram Desktop",
        "anydesk",
        "WhatsApp",
        "OBS Studio",
        "Steam",
        "Battle.net",
    ]

    for root in roots:
        if not root.is_dir():
            continue

        for sub in root.iterdir():
            try:
                if not sub.is_dir():
                    continue

                is_preferred = any(p.lower() in sub.name.lower() for p in preferred_dirs)
                if not is_preferred:
                    if sub.name.lower().startswith(("microsoft", "adobe", "google", "mozilla", "temp")):
                        continue

                for r, dirs, files in os.walk(sub):
                    depth = Path(r).relative_to(sub).parts
                    if len(depth) > 3:
                        dirs[:] = []
                        continue
                    for fname in files:
                        if not fname.lower().endswith(".exe"):
                            continue
                        path = Path(r) / fname
                        if not _is_good_exe(path):
                            continue
                        name = fname[:-4]
                        apps.append(_make_entry(name, path, "appdata"))
            except Exception:
                continue

    logger.info(f"app_indexer: appdata apps: {len(apps)}")
    return apps


# ---------- объединение и сохранение ----------

def build_app_index() -> List[Dict[str, Any]]:
    logger.info("app_indexer: scanning registry...")
    reg_apps = _scan_registry_apps()

    logger.info("app_indexer: scanning start menu...")
    start_apps = _scan_start_menu()

    logger.info("app_indexer: scanning Program Files...")
    pf_apps = _scan_program_files()

    logger.info("app_indexer: scanning AppData...")
    ad_apps = _scan_appdata()

    all_apps = reg_apps + start_apps + pf_apps + ad_apps
    logger.info(f"app_indexer: total apps (raw): {len(all_apps)}")

    seen = set()
    unique_apps: List[Dict[str, Any]] = []
    for app in all_apps:
        key = (app["name"].lower(), app["path"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique_apps.append(app)

    logger.info(f"app_indexer: total apps (unique): {len(unique_apps)}")

    try:
        with open(APP_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(unique_apps, f, ensure_ascii=False, indent=2)
        logger.info(f"app_indexer: index saved to {APP_INDEX_PATH}")
    except Exception:
        logger.error("app_indexer: failed to save index")

    return unique_apps


def load_app_index() -> List[Dict[str, Any]]:
    if not APP_INDEX_PATH.is_file():
        return []
    try:
        with open(APP_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.error("app_indexer: failed to load index")
        return []
