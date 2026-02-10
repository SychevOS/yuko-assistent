"""
Простейшее текстовое ядро для GUI Юко.
Потом сюда можно будет подложить реальный пайплайн.
"""


class YukoCore:
    def __init__(self):
        self._status = "online"

    def get_status(self):
        """
        Возвращает (status, message) для GUI.
        status: "online" / "offline" / "error" / "demo"
        """
        if self._status == "online":
            return "online", "Юко онлайн. Ядро загружено (демо-режим)."
        else:
            return self._status, "Ядро в неизвестном состоянии."

    def process_text_request(self, text: str) -> str:
        """
        Обрабатывает текстовый запрос и возвращает ответ.
        Сейчас просто эхоит запрос.
        """
        text = text.strip()
        if not text:
            return "Я не получила текста для обработки."
        return f"[ДЕМО] Ты написал: «{text}». Реальное ядро пока не подключено."
