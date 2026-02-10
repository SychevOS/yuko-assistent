# setup.py
"""
Автоустановка всего нужного для Юко (faster-whisper + Ollama) в текущий .venv.

Запуск (в корне проекта, в активном .venv):
    python setup.py
"""
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "yuko_data"
MODELS_DIR = DATA_DIR / "models"

REQUIRED_DIRS = [DATA_DIR, MODELS_DIR]

# МИНИМАЛЬНЫЙ набор, без openai-whisper, torch и прочего мусора
EXTRA_DEPS = [
    "ollama",   # чтобы python-код мог дергать Ollama
]

def run(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    return subprocess.call(cmd)

def ensure_dirs():
    print("\n=== Проверка директорий ===")
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[OK] dir: {d}")

def install_python_deps():
    """
    Ставит зависимости только из requirements.txt + EXTRA_DEPS
    в текущий интерпретатор (sys.executable).
    """
    print("\n=== Установка Python-зависимостей ===")
    print(f"[INFO] Текущий Python: {sys.executable}")

    req = BASE_DIR / "yuko-assistent" / "requirements.txt"
    if req.is_file():
        print("[INFO] Найден requirements.txt, ставлю из него")
        code = run([sys.executable, "-m", "pip", "install", "-r", str(req)])
        if code != 0:
            print("[WARN] pip install -r requirements.txt завершился с ошибкой")
    else:
        print("[WARN] requirements.txt не найден, пропускаю установку из файла")

    if EXTRA_DEPS:
        print("[INFO] Ставлю дополнительные пакеты (только реально нужные):")
        for pkg in EXTRA_DEPS:
            code = run([sys.executable, "-m", "pip", "install", pkg])
            if code != 0:
                print(f"[WARN] не удалось поставить {pkg}, продолжаем")

def ensure_whisper_models():
    """
    Ты используешь faster-whisper. Он сам скачает модели при первом запуске.
    Никаких лишних скачиваний тут не делаем, только информируем.
    """
    print("\n=== Проверка моделей Whisper ===")
    try:
        import faster_whisper  # type: ignore
        _ = faster_whisper
        print("[OK] faster-whisper установлен, модели докачаются при первом запуске")
    except ImportError:
        print("[WARN] faster-whisper не установлен (проверь requirements.txt)")

def ensure_ollama_model(model_name: str = "qwen2.5:7b-instruct"):
    """
    Проверяет наличие модели в локальном Ollama и при отсутствии — докачивает.
    Требует запущенный ollama serve.
    """
    print(f"\n=== Проверка модели Ollama '{model_name}' ===")

    try:
        import ollama  # импорт здесь, после install_python_deps
    except ImportError:
        print("[WARN] Модуль 'ollama' не установлен, пропускаю проверку модели")
        return

    try:
        ollama.show(model_name)
        print(f"[OK] Ollama модель '{model_name}' уже есть")
    except Exception:
        print(f"[NEED] тяну Ollama модель '{model_name}'")
        try:
            ollama.pull(model_name)
            print(f"[OK] Ollama модель '{model_name}' скачана")
        except Exception as e:
            print(f"[ERROR] не удалось скачать модель '{model_name}': {e}")

def main():
    print("=== SETUP YUKO ASSISTANT (faster-whisper + Ollama) ===")
    print(f"Проект: {BASE_DIR}")
    print(f"Python: {sys.executable}")

    ensure_dirs()
    install_python_deps()
    ensure_whisper_models()
    ensure_ollama_model("qwen2.5:7b-instruct")

    print("\n=== Готово ===")
    print("Можно запускать Юко:")
    print("    python yuko-assistent/main.py")

if __name__ == "__main__":
    main()
