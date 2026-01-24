"""
Простой логгер для Yuko Assistant
Создает файл логов при запуске программы
"""

from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_file="yuko_logs.txt"):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self.log_file = self.log_dir / log_file

        if not self.log_file.exists():
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("=== Yuko Assistant Logs ===\n")
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message)


logger = Logger()
