"""
Автоматический установщик всех зависимостей для Юко AI
Запускай этот файл ПЕРЕД первым запуском main.py
"""

import sys
import subprocess
import os
from pathlib import Path

# Список всех необходимых пакетов
REQUIRED_PACKAGES = [
    "sounddevice",
    "numpy",
    "groq",
    "send2trash",
    "requests",
    "python-dotenv"
]

def print_header(text):
    """Красивый заголовок"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    print(f"🐍 Python версия: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ ОШИБКА: Нужен Python 3.8 или новее!")
        print("   Скачай с https://www.python.org/downloads/")
        return False
    
    print("✅ Версия Python подходит")
    return True

def check_pip():
    """Проверка наличия pip"""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✅ pip установлен")
        return True
    except:
        print("❌ pip не найден!")
        print("   Установи командой: python -m ensurepip --upgrade")
        return False

def upgrade_pip():
    """Обновление pip до последней версии"""
    print("\n📦 Обновляю pip...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✅ pip обновлён")
        return True
    except Exception as e:
        print(f"⚠️  Не удалось обновить pip: {e}")
        return False

def is_package_installed(package_name):
    """Проверка установлен ли пакет"""
    try:
        __import__(package_name.replace("-", "_"))
        return True
    except ImportError:
        return False

def install_package(package_name, quiet=True):
    """Установка одного пакета"""
    print(f"📥 Устанавливаю {package_name}...", end=" ", flush=True)
    
    cmd = [sys.executable, "-m", "pip", "install", package_name]
    
    if quiet:
        cmd.append("-q")
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    else:
        stdout = None
        stderr = None
    
    try:
        subprocess.check_call(cmd, stdout=stdout, stderr=stderr)
        print("✅")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def install_all_packages(packages, optional=False):
    """Установка списка пакетов"""
    success_count = 0
    failed = []

    print(f"\n📦 Установка обязательных пакетов ({len(packages)} шт.)...")
    
    for pkg in packages:
        # Проверяем, может уже установлен
        check_name = pkg.replace("-", "_")
        if is_package_installed(check_name):
            print(f"⏭️  {pkg} уже установлен")
            success_count += 1
            continue
        
        if install_package(pkg):
            success_count += 1
        else:
            failed.append(pkg)
    
    print(f"\n📊 Результат: {success_count}/{len(packages)} успешно")
    
    if failed and not optional:
        print(f"❌ Не удалось установить: {', '.join(failed)}")
        return False
    
    return True

def create_env_template():
    """Создание шаблона .env файла"""
    env_path = Path(".env")
    
    if env_path.exists():
        print("⏭️  Файл .env уже существует")
        return
    
    template = """# Конфигурация для Юко AI
# Получи ключ на https://console.groq.com/keys

GROQ_API_KEY=your_groq_api_key_here

# Если нужна OpenAI вместо Groq:
# OPENAI_API_KEY=your_openai_key_here
"""
    
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(template)
        print("✅ Создан шаблон .env файла")
        print("   ⚠️  Не забудь добавить свой GROQ_API_KEY!")
    except Exception as e:
        print(f"⚠️  Не удалось создать .env: {e}")

def create_requirements_txt():
    """Создание requirements.txt для будущего"""
    req_path = Path("requirements.txt")
    
    content = "\n".join(REQUIRED_PACKAGES)
    
    try:
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ Создан requirements.txt")
    except Exception as e:
        print(f"⚠️  Не удалось создать requirements.txt: {e}")

def check_audio_devices():
    """Проверка доступности аудиоустройств"""
    print("\n🔊 Проверка аудиоустройств...")
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        
        if input_devices:
            print(f"✅ Найдено {len(input_devices)} устройств ввода (микрофонов)")
            for i, dev in enumerate(input_devices, 1):
                print(f"   {i}. {dev['name']}")
        else:
            print("⚠️  Микрофоны не найдены!")
            print("   Проверь подключение микрофона")
        
    except Exception as e:
        print(f"⚠️  Не удалось проверить аудио: {e}")

def main():
    """Главная функция установки"""
    print_header("🤖 УСТАНОВЩИК ЗАВИСИМОСТЕЙ ДЛЯ ЮКО AI")
    
    # 1. Проверка Python
    if not check_python_version():
        return False
    
    # 2. Проверка pip
    if not check_pip():
        return False
    
    # 3. Обновление pip
    upgrade_pip()
    
    # 4. Установка обязательных пакетов
    if not install_all_packages(REQUIRED_PACKAGES):
        print("\n❌ Критическая ошибка при установке пакетов!")
        return False
    
    # 6. Создание конфиг файлов
    print_header("📝 СОЗДАНИЕ КОНФИГУРАЦИОННЫХ ФАЙЛОВ")
    create_env_template()
    create_requirements_txt()
    
    # 7. Проверка аудио
    check_audio_devices()
    
    # 8. Финальное сообщение
    print_header("✅ УСТАНОВКА ЗАВЕРШЕНА")
    print("""
Что дальше:
1. Открой файл .env и добавь свой GROQ_API_KEY
   (получить можно на https://console.groq.com/keys)
   
2. Проверь, что микрофон подключен и работает

3. Запусти main.py командой:
   python main.py
   
4. Скажи "Юко привет" для проверки

🎉 Удачи!
    """)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n❌ Установка завершилась с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)