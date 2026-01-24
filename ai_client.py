# ai_client.py
import requests

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
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Юко: ошибка обращения к модели: {e}")
        return "У меня проблема с локальной моделью, попробуй позже."

    try:
        content = data["message"]["content"]
    except Exception:
        return "Не смогла прочитать ответ модели."

    return (content or "").strip()