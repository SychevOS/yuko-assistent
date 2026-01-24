from datetime import datetime
from pathlib import Path
import traceback


class Logger:
    def __init__(self, log_file: str = "yuko_logs.txt"):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self.log_file = self.log_dir / log_file

        if not self.log_file.exists():
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("=== Yuko Assistant Logs ===\n")
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")

    def _write(self, message: str):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        self._write(log_message)

    def info(self, message: str):
        self.log(message, level="INFO")

    def warning(self, message: str):
        self.log(message, level="WARNING")

    def error(self, message: str):
        self.log(message, level="ERROR")

    def exception(self, message: str):
        tb = traceback.format_exc()
        full = f"{message}\n{tb}"
        self.log(full, level="ERROR")


logger = Logger()
