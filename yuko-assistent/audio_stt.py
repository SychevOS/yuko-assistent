# audio_stt.py
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# инициализация модели один раз при импорте
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

def is_silence(samples: np.ndarray, energy_threshold: float = 1e-4) -> bool:
    """
    Грубый чек тишины: среднеквадратичная энергия ниже порога.
    Если тишина — даже не дёргаем модель.
    """
    if samples.size == 0:
        return True
    rms = np.sqrt(np.mean(samples ** 2))
    return rms < energy_threshold

def listen(duration: float = 5.0) -> str:
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

    # 1) Отсекаем тишину/минимальный шум
    if is_silence(samples):
        # можно залогировать, если нужно дебажить
        # print("DEBUG: тишина, STT пропускаем")
        return ""

    try:
        segments, info = whisper_model.transcribe(
            samples,
            language="ru",
            beam_size=5,
            vad_filter=True,  # 2) включаем VAD, пусть он режет тишину внутри
            vad_parameters=dict(
                min_silence_duration_ms=800,
                speech_pad_ms=200,
            ),
        )
    except Exception as e:
        print("Ошибка распознавания Whisper:", e)
        return ""

    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    text = " ".join(parts).strip().lower()

    # 3) Отбрасываем короткие/подозрительные фразы
    if not text:
        return ""
    # меньше 5 символов / 1-2 слов — считаем шумом
    if len(text) < 5 or len(text.split()) < 2:
        return ""

    return text
