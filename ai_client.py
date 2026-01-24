# ai_client.py
import requests
from Logger import logger

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen2.5:7b-instruct"

SYSTEM_PROMPT = (
    "Ты локальный голосовой ассистент Юко на русском языке."
    "Отвечай не слишком развёрнуто без просьбы пользователя"
    "Ты девушка"
    "Ты доброжелательная и общительная"
    "При вопросе о создателе упоминаешь, что его зовут Финн"
    "Если нужно выполнить действие на ПК, используй спец-теги в квадратных скобках, например: "
    "[OPEN_BROWSER], [YOUTUBE_SEARCH:запрос], [WEB_SEARCH:запрос], [SEARCH_FILE:имя]."
)


def ask_ai(message: str) -> str:
    """
    Отправляет запрос в локальную модель Qwen через Ollama и возвращает текст ответа.
    """
    message = (message or "").strip()
    if not message:
        return "Не совсем поняла запрос, попробуй переформулировать."

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "stream": False,
        "options": {
            "temperature": 0.4,
            "top_p": 0.9,
            "num_predict": 256,
        },
    }

    try:
        logger.info(f"AI_HTTP_REQUEST: url={OLLAMA_URL}, model={MODEL_NAME}, msg='{message}'")
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("AI_HTTP_ERROR: ошибка обращения к локальной модели через Ollama")
        return "У меня проблема с локальной моделью, попробуй позже."

    try:
        content = data["message"]["content"]
    except Exception:
        logger.exception("AI_PARSE_ERROR: не смогла прочитать ответ модели")
        return "Не смогла прочитать ответ модели."

    reply = (content or "").strip()
    logger.info(f"AI_REPLY_RAW: '{reply[:200]}'")
    return reply
