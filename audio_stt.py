# РАБОТА СО ЗВУКОМ

# audio_stt.py
import sounddevice as sd
from faster_whisper import WhisperModel


# инициализация модели один раз при импорте
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")


def listen(duration: float = 8.0) -> str:
    """Записывает голос и возвращает распознанный текст (ru)."""
    try:
        audio = sd.rec(
            int(duration * 16000),
            samplerate=16000,
            channels=1,
            dtype="float32",
        )
        sd.wait()
    except Exception as e:
        print("Ошибка записи с микрофона:", e)
        return ""

    samples = audio.flatten()

    try:
        segments, info = whisper_model.transcribe(
            samples,
            language="ru",
            beam_size=5,
            vad_filter=False,
            vad_parameters=dict(
                min_silence_duration_ms=1000,  # Дольше ждёт паузу
                speech_pad_ms=400, # Подклеивание хвоста
            ),
        )
    except Exception as e:
        print("Ошибка распознавания Whisper:", e)
        return ""

    parts = [seg.text for seg in segments]
    return " ".join(parts).strip().lower()
