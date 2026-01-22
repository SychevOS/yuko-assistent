# 1. Установи Python 3.11+ с python.org (галка "Add Python to PATH").
# 2. Установи Ollama:
#   - скачай с https://ollama.com
#   - поставь и перезапусти компьютер.
# 3. Открой папку с Юко и запусти install_yuko.ps1 (ПКМ → Запуск с PowerShell).
# 4. Запуск Юко: run_yuko.bat

# Ставить на global среду
# pip install faster-whisper sounddevice numpy groq python-dotenv send2trash
# py -3.11 -m venv .venv_whisper.\.venv_whisper\Scripts\activate
# python main.py

# Загрузка обновы
# git add .
# git commit -m "Чё поменяли"
# git push -u origin master

# ВЗАИМОДЕЙСТВИЯ С ВЕТВЯМИ
# git checkout -b название(создаём ветку)
# git branch(посмотреть где находимся и др ветки)
# git push -u origin NAME(отправить ветку на гит)
# git checkout master (переключение на основную)

# ДЛЯ КЛОНИРОВАНИЯ ПРОЕКТА
# git clone https://github.com/SychevOS/yuko-assistent



<!-- 
main.py
Главный цикл. Слушает голос, получает текст, определяет интент, либо выполняет команду, либо спрашивает ИИ.
​

audio_stt.py
Запись с микрофона и распознавание речи (Whisper). Одна ключевая функция listen().
​

intents.py
Понимание команд и действия:
решает, что хотел пользователь (analyze);
выполняет простые команды (браузер, калькулятор, Discord, Steam и т.п.);
парсит спец‑теги из ответа ИИ и исполняет их.
​

ai_client.py
Общение с локальной моделью (будет через Ollama). Одна важная функция ask_ai().
​

words_config.py
Словари ключевых слов: как распознать выход, браузер, приложения, имя Юко и т.д.

app_launcher.py
Запуск приложений по имени (launch_app("discord") и другие).
​

file_actions.py
Операции с файлами: поиск, открыть, показать в проводнике, удалить.
​

Папка yuko_data/ (+ models/, temp/)
Рабочие данные и модели.
-->