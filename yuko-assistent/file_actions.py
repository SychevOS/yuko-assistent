import os
from pathlib import Path

from send2trash import send2trash  # pip install send2trash
from Logger import logger

USER_HOME = Path.home()

ALLOWED_ROOTS = [
    USER_HOME / "Desktop",
    USER_HOME / "Documents",
    USER_HOME / "Downloads",
    USER_HOME / "Pictures",
    USER_HOME / "Videos",
    USER_HOME / "Music",
    USER_HOME / "OneDrive",
    USER_HOME,  # Разрешить поиск по всему домашнему каталогу пользователя
]

FORBIDDEN_PREFIXES = [
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("C:/ProgramData"),
    USER_HOME / "AppData",
]


def _normalize(path: Path) -> Path:
    return path.expanduser().resolve()


def _is_under(root: Path, path: Path) -> bool:
    root = _normalize(root)
    path = _normalize(path)
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_allowed(path: Path) -> bool:
    path = _normalize(path)

    for fb in FORBIDDEN_PREFIXES:
        if _is_under(fb, path):
            return False

    return any(_is_under(root, path) for root in ALLOWED_ROOTS)


def search_file(query: str, max_results: int = 10):
    query = query.strip().lower()
    results: list[Path] = []

    for root in ALLOWED_ROOTS:
        root = _normalize(root)
        if not root.exists():
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            depth = Path(dirpath).relative_to(root).parts
            if len(depth) > 10:  # Увеличена глубина поиска
                dirnames[:] = []
                continue

            for name in filenames:
                if query in name.lower():
                    p = Path(dirpath) / name
                    if _is_allowed(p):
                        results.append(p)
                        if len(results) >= max_results:
                            return results
    if not results:
        logger.log(f"Файлы по запросу '{query}' не найдены в разрешенных папках", "WARNING")
    return results


def open_file(path_str: str):
    path = _normalize(Path(path_str))
    if not path.exists():
        logger.log(f"Файл не найден: {path}", "ERROR")
        raise FileNotFoundError(path)
    if not _is_allowed(path):
        logger.log(f"Попытка открыть запрещенный файл: {path}", "ERROR")
        raise PermissionError("Path is outside allowed user folders")
    logger.log(f"Открыт файл: {path}", "INFO")
    os.startfile(str(path))


def show_in_explorer(path_str: str):
    path = _normalize(Path(path_str))
    if not path.exists():
        raise FileNotFoundError(path)
    if not _is_allowed(path):
        raise PermissionError("Path is outside allowed user folders")

    if path.is_dir():
        os.startfile(str(path))
        return

    import subprocess
    subprocess.Popen(
        ["explorer", "/select,", str(path)],
        shell=True,
    )


def delete_file(path_str: str):
    path = _normalize(Path(path_str))
    if not path.exists():
        raise FileNotFoundError(path)
    if not _is_allowed(path):
        raise PermissionError("Path is outside allowed user folders")
    send2trash(str(path))
