"""
Простой логгер для Yuko Assistant
Создает файл логов при запуске программы
"""

import os
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_file="yuko_logs.txt"):
        # Создаем папку logs если нет
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        # Полный путь к файлу логов
        self.log_file = self.log_dir / log_file

        # Создаем файл при первом запуске
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Yuko Assistant Logs ===\n")
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")

        print(f"📝 Логирование: {self.log_file}")

    def log(self, message: str, level: str = "INFO"):
        """Записать сообщение в лог"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}\n"

        # Записываем в файл
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)

        # Также выводим в консоль
        print(f"[{level}] {message}")

    def log_command(self, command: str, success: bool = True):
        """Записать команду пользователя"""
        status = "✅ УСПЕХ" if success else "❌ ОШИБКА"
        self.log(f"Команда: '{command}' - {status}")

    def log_voice(self, text: str):
        """Записать распознанную речь"""
        self.log(f"Распознано: '{text}'", "VOICE")

    def log_error(self, error: str):
        """Записать ошибку"""
        self.log(f"Ошибка: {error}", "ERROR")

    def log_app(self, app_name: str, path: str = ""):
        """Записать запуск приложения"""
        if path:
            self.log(f"Запуск приложения: {app_name} -> {path}")
        else:
            self.log(f"Запуск приложения: {app_name}")

    def log_ai(self, request: str, response: str = ""):
        """Записать запрос/ответ ИИ"""
        if response:
            self.log(f"ИИ: '{request[:50]}...' -> '{response[:50]}...'", "AI")
        else:
            self.log(f"Запрос к ИИ: '{request}'", "AI")

# Создаем логгер
logger = Logger()