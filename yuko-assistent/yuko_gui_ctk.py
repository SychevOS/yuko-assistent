import customtkinter as ctk
import threading
import time
from datetime import datetime
from PIL import Image, ImageTk  # для GIF-анимации глаз


# ===== ГЛОБАЛЬНОЕ =====


try:
    from yuko_core_example import YukoCore
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    print("⚠️ Модуль ядра не найден. Работаю в демо-режиме.")


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")



# ===== SPLASH =====


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, core_init_callback=None, on_done=None):
        super().__init__(parent)
        self.core_init_callback = core_init_callback
        self.on_done = on_done

        self.title("Юко")
        self.geometry("640x380")
        self.resizable(False, False)
        self.overrideredirect(True)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (640 // 2)
        y = (self.winfo_screenheight() // 2) - (380 // 2)
        self.geometry(f"640x380+{x}+{y}")

        main = ctk.CTkFrame(self, fg_color="#050514", corner_radius=0)
        main.pack(fill="both", expand=True)

        aura_left = ctk.CTkFrame(main, fg_color="#251046", corner_radius=300)
        aura_left.place(relx=0.0, rely=0.1, relwidth=0.5, relheight=0.6)

        aura_right = ctk.CTkFrame(main, fg_color="#1f1033", corner_radius=300)
        aura_right.place(relx=0.4, rely=0.0, relwidth=0.6, relheight=0.7)

        title = ctk.CTkLabel(
            main,
            text="ЮКО",
            font=("Segoe UI", 46, "bold"),
            text_color="#f5f3ff",
        )
        title.place(relx=0.08, rely=0.18)

        subtitle = ctk.CTkLabel(
            main,
            text="Персональный ИИ‑ассистент",
            font=("Segoe UI", 14),
            text_color="#a78bfa",
        )
        subtitle.place(relx=0.08, rely=0.34)

        self.status_label = ctk.CTkLabel(
            main,
            text="Запуск интерфейса...",
            font=("Segoe UI", 12),
            text_color="#a1a1aa",
        )
        self.status_label.place(relx=0.08, rely=0.58)

        self.progress = ctk.CTkProgressBar(
            main,
            width=420,
            height=10,
            corner_radius=5,
            fg_color="#18122b",
            progress_color="#c084fc",
        )
        self.progress.place(relx=0.08, rely=0.65)
        self.progress.set(0)

        self.load_sequence()

    def load_sequence(self):
        def step1():
            self.status_label.configure(text="Инициализация модулей...")
            self.progress.set(0.25)
            self.after(450, step2)

        def step2():
            self.status_label.configure(text="Подключение ядра (если доступно)...")
            self.progress.set(0.55)
            if self.core_init_callback:
                threading.Thread(target=self.core_init_callback, daemon=True).start()
            self.after(600, step3)

        def step3():
            self.status_label.configure(text="Подготовка интерфейса...")
            self.progress.set(0.8)
            self.after(450, step4)

        def step4():
            self.status_label.configure(text="Готово.")
            self.progress.set(1.0)
            self.after(400, self.close_splash)

        step1()

    def close_splash(self):
        try:
            if self.on_done:
                self.on_done()
        finally:
            self.destroy()



# ===== ГЛАВНОЕ ОКНО =====


class YukoGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.colors = {
            "bg_dark": "#030112",
            "bg_medium": "#0b061b",
            "bg_light": "#18122b",
            "accent": "#c084fc",
            "accent_soft": "#7c3aed",
            "danger": "#ff375f",
            "text_primary": "#f5f3ff",
            "text_secondary": "#a78bfa",
            "moon": "#e5defc",
        }

        self.title("Юко — ИИ ассистент")
        self.geometry("1150x720")
        self.minsize(960, 640)
        self.configure(fg_color=self.colors["bg_dark"])

        self.is_listening = False
        self.core = None
        self.core_status = "offline"
        self.current_screen = "chat"

        self.bg_canvas = None
        self.eyes_label = None
        self.eyes_frames = []
        self.eyes_frame_index = 0

        self._create_background()
        self._create_base_layout()
        self._create_eyes_gif()
        self.create_screens()
        self.center_window()

    # --- фон ---

    def _create_background(self):
        self.bg_canvas = ctk.CTkCanvas(
            self,
            bg=self.colors["bg_dark"],
            highlightthickness=0,
            bd=0,
        )
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.bg_canvas.create_oval(
            -220, 220, 260, 780,
            fill="#1e1b4b",
            outline="",
        )
        self.bg_canvas.create_oval(
            820, -180, 1350, 420,
            fill="#3b0764",
            outline="",
        )
        self.bg_canvas.lower("all")

    # --- базовый каркас: топ-бар + основной контейнер ---

    def _create_base_layout(self):
        # TOP BAR
        self.top_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors["bg_dark"],
            corner_radius=0,
            height=80,
        )
        self.top_frame.pack(side="top", fill="x")

        underline = ctk.CTkFrame(
            self.top_frame,
            fg_color="#1e1b4b",
            height=2,
            corner_radius=0,
        )
        underline.pack(side="bottom", fill="x")

        header_left = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        header_left.pack(side="left", padx=24, pady=14)

        icon_label = ctk.CTkLabel(
            header_left,
            text="🌙",
            font=("Segoe UI Emoji", 26),
        )
        icon_label.pack(side="left", padx=(0, 10))

        # вместо текстовых надписей — только глаза по центру top_frame
        header_right = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        header_right.pack(side="right", padx=24)

        self.chat_tab_btn = ctk.CTkButton(
            header_right,
            text="Чат",
            width=90,
            height=32,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            text_color=self.colors["bg_dark"],
            font=("Segoe UI", 11),
            command=lambda: self.show_screen("chat"),
        )
        self.chat_tab_btn.pack(side="right", padx=(0, 10))

        self.settings_btn = ctk.CTkButton(
            header_right,
            text="Настройки",
            width=110,
            height=32,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["accent_soft"],
            text_color=self.colors["text_primary"],
            font=("Segoe UI", 11),
            command=lambda: self.show_screen("settings"),
        )
        self.settings_btn.pack(side="right", padx=(0, 10))

        # MAIN CONTAINER
        self.main_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.main_container.pack(side="top", fill="both", expand=True)

    # --- глаза (анимированный GIF) ---

    def _create_eyes_gif(self):
        """
        Использует файл eyes_blink.gif в той же папке, что и скрипт.
        Если файла нет или он не читается — просто ничего не рисуем.
        """
        try:
            img = Image.open("eyes_blink.gif")
        except Exception:
            return

        self.eyes_frames = []
        try:
            while True:
                frame = img.copy()
                frame = frame.convert("RGBA")
                frame = frame.resize((260, 80), Image.LANCZOS)
                tk_frame = ImageTk.PhotoImage(frame)
                self.eyes_frames.append(tk_frame)
                img.seek(len(self.eyes_frames))
        except EOFError:
            pass

        if not self.eyes_frames:
            return

        # глаза в шапке, по центру
        self.eyes_label = ctk.CTkLabel(
            self.top_frame,
            text="",
            fg_color="transparent",
        )
        self.eyes_label.place(relx=0.5, rely=0.05, anchor="n")
        self._animate_eyes()

    def _animate_eyes(self):
        if not self.eyes_frames or not self.eyes_label:
            return
        frame = self.eyes_frames[self.eyes_frame_index]
        self.eyes_label.configure(image=frame)
        self.eyes_frame_index = (self.eyes_frame_index + 1) % len(self.eyes_frames)
        self.after(80, self._animate_eyes)

    # --- ядро ---

    def initialize_core(self):
        try:
            if CORE_AVAILABLE:
                self.core = YukoCore()
                status, message = self.core.get_status()
                self.core_status = status
                self.after(0, lambda: self.update_status(f"● {message}"))
                self.after(0, lambda: self.add_action_log(f"Ядро: {message}"))
            else:
                self.core_status = "demo"
                self.after(
                    0,
                    lambda: self.update_status("● Демо режим (ядро не подключено)"),
                )
                self.after(0, lambda: self.add_action_log("Работа в демо-режиме"))
        except Exception as e:
            self.core_status = "error"
            err_text = str(e)
            self.after(
                0,
                lambda err=err_text: self.update_status(f"● Ошибка: {err}"),
            )
            self.after(
                0,
                lambda err=err_text: self.add_action_log(
                    f"Ошибка инициализации: {err}"
                ),
            )

    # --- геометрия ---

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # --- экраны ---

    def create_screens(self):
        # Два экрана: чат и настройки
        self.chat_screen = ctk.CTkFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
        )
        self.chat_screen.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.settings_screen = ctk.CTkFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
        )
        self.settings_screen.place(relx=0, rely=0, relwidth=1, relheight=1)

        # --- chat_screen ---

        self.chat_frame = ctk.CTkFrame(
            self.chat_screen,
            fg_color=self.colors["bg_medium"],
            corner_radius=16,
        )
        self.chat_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(24, 12),
            pady=24,
        )

        # статус перетащу сюда, под заголовок диалога
        header_row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=18, pady=(16, 6))

        chat_header = ctk.CTkLabel(
            header_row,
            text="Диалог",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors["text_primary"],
        )
        chat_header.pack(side="left", anchor="w")

        self.status_indicator = ctk.CTkLabel(
            header_row,
            text="● Готова",
            font=("Segoe UI", 11),
            text_color=self.colors["text_secondary"],
        )
        self.status_indicator.pack(side="right", anchor="e")

        chat_sub = ctk.CTkLabel(
            self.chat_frame,
            text="Сообщения и ответы ассистента.",
            font=("Segoe UI", 11),
            text_color=self.colors["text_secondary"],
        )
        chat_sub.pack(padx=18, anchor="w")

        self.chat_display = ctk.CTkTextbox(
            self.chat_frame,
            fg_color=self.colors["bg_dark"],
            corner_radius=12,
            font=("Consolas", 12),
            text_color=self.colors["text_primary"],
            wrap="word",
        )
        self.chat_display.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self.chat_display.configure(state="disabled")

        self.input_frame = ctk.CTkFrame(
            self.chat_frame,
            fg_color=self.colors["bg_light"],
            corner_radius=14,
            height=72,
        )
        self.input_frame.pack(fill="x", padx=16, pady=(0, 16))
        self.input_frame.pack_propagate(False)

        self.input_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Сообщение для Юко...",
            height=40,
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["accent"],
            border_width=1,
            font=("Segoe UI", 11),
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(14, 10), pady=16)
        self.input_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            width=46,
            height=40,
            fg_color=self.colors["accent"],
            hover_color="#a855f7",
            text_color=self.colors["bg_dark"],
            font=("Segoe UI", 18, "bold"),
            command=self.send_message,
        )
        self.send_btn.pack(side="left", padx=(0, 8))

        self.voice_btn = ctk.CTkButton(
            self.input_frame,
            text="🎙",
            width=46,
            height=40,
            fg_color=self.colors["bg_medium"],
            hover_color=self.colors["accent_soft"],
            font=("Segoe UI", 18),
            command=self.toggle_voice,
        )
        self.voice_btn.pack(side="left", padx=(0, 14))

        self.history_frame = ctk.CTkFrame(
            self.chat_screen,
            width=320,
            fg_color=self.colors["bg_medium"],
            corner_radius=16,
        )
        self.history_frame.pack(side="right", fill="both", padx=(12, 24), pady=24)
        self.history_frame.pack_propagate(False)

        history_header = ctk.CTkLabel(
            self.history_frame,
            text="История",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors["text_primary"],
        )
        history_header.pack(pady=(16, 4), padx=18, anchor="w")

        history_sub = ctk.CTkLabel(
            self.history_frame,
            text="Логи запросов и действий.",
            font=("Segoe UI", 10),
            text_color=self.colors["text_secondary"],
        )
        history_sub.pack(padx=18, anchor="w")

        self.history_display = ctk.CTkTextbox(
            self.history_frame,
            fg_color=self.colors["bg_dark"],
            corner_radius=12,
            font=("Consolas", 10),
            text_color=self.colors["text_secondary"],
            wrap="word",
        )
        self.history_display.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.history_display.configure(state="disabled")

        self.add_system_message("Привет, я Юко. Пиши, что нужно.")

        # --- settings_screen ---

        settings_inner = ctk.CTkFrame(
            self.settings_screen,
            fg_color=self.colors["bg_medium"],
            corner_radius=16,
        )
        settings_inner.pack(fill="both", expand=True, padx=24, pady=24)

        settings_header = ctk.CTkLabel(
            settings_inner,
            text="Настройки",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors["text_primary"],
        )
        settings_header.pack(pady=(18, 4), padx=20, anchor="w")

        settings_sub = ctk.CTkLabel(
            settings_inner,
            text="Параметры моделей, голоса и системы.",
            font=("Segoe UI", 11),
            text_color=self.colors["text_secondary"],
        )
        settings_sub.pack(padx=20, anchor="w")

        core_status_label = ctk.CTkLabel(
            settings_inner,
            text=f"Статус ядра: {self.core_status}",
            font=("Segoe UI", 12),
            text_color=self.colors["text_secondary"],
        )
        core_status_label.pack(padx=20, pady=(16, 8), anchor="w")

        model_label = ctk.CTkLabel(
            settings_inner,
            text="Модель ответа:",
            font=("Segoe UI", 12),
            text_color=self.colors["text_primary"],
        )
        model_label.pack(padx=20, pady=(20, 4), anchor="w")

        self.model_combo = ctk.CTkComboBox(
            settings_inner,
            values=["Локальная", "Облачная", "Демо"],
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["accent"],
            button_color=self.colors["accent_soft"],
            text_color=self.colors["text_primary"],
            font=("Segoe UI", 11),
        )
        self.model_combo.set("Демо")
        self.model_combo.pack(padx=20, anchor="w")

        self.show_screen("chat")

    # --- переключение экранов ---

    def show_screen(self, name: str):
        self.current_screen = name

        if name == "chat":
            self.chat_screen.lift()
            self.chat_tab_btn.configure(
                fg_color=self.colors["accent"],
                text_color=self.colors["bg_dark"],
            )
            self.settings_btn.configure(
                fg_color=self.colors["bg_light"],
                text_color=self.colors["text_primary"],
            )
        else:
            self.settings_screen.lift()
            self.chat_tab_btn.configure(
                fg_color=self.colors["bg_light"],
                text_color=self.colors["text_primary"],
            )
            self.settings_btn.configure(
                fg_color=self.colors["accent"],
                text_color=self.colors["bg_dark"],
            )

    # --- чат ---

    def add_message(self, sender, message, color=None):
        self.chat_display.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M")

        if color is None:
            color = self.colors["accent"] if sender == "Юко" else self.colors["moon"]

        self.chat_display.insert("end", f"[{timestamp}] ", "timestamp")
        self.chat_display.insert("end", f"{sender}: ", "sender")
        self.chat_display.insert("end", f"{message}\n\n", "message")

        self.chat_display.tag_config(
            "timestamp",
            foreground=self.colors["text_secondary"],
        )
        self.chat_display.tag_config(
            "sender",
            foreground=color,
        )
        self.chat_display.tag_config(
            "message",
            foreground=self.colors["text_primary"],
        )

        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def add_system_message(self, message):
        self.add_message("Юко", message, self.colors["accent"])

    def add_user_message(self, message):
        self.add_message("Ты", message, self.colors["moon"])

    def add_action_log(self, action):
        self.history_display.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_display.insert("end", f"[{timestamp}] {action}\n", "log")
        self.history_display.tag_config("log", foreground=self.colors["text_secondary"])
        self.history_display.see("end")
        self.history_display.configure(state="disabled")

    def send_message(self):
        message = self.input_entry.get().strip()
        if not message:
            return
        self.add_user_message(message)
        self.add_action_log(f"Отправлено: {message[:30]}...")
        self.input_entry.delete(0, "end")
        self.process_message(message)

    def process_message(self, message):
        self.update_status("● Обработка сообщения...")

        def worker():
            try:
                if self.core and self.core_status == "online":
                    response = self.core.process_text_request(message)
                else:
                    time.sleep(1)
                    response = (
                        f"[ДЕМО] Получен текст: '{message}'. "
                        f"Подключи ядро, чтобы был настоящий ответ."
                    )
                self.after(0, lambda: self.add_system_message(response))
                self.after(0, lambda: self.add_action_log("Ответ получен"))
            except Exception as e:
                err = f"Ошибка: {e}"
                self.after(0, lambda: self.add_system_message(err))
                self.after(0, lambda: self.add_action_log(f"Ошибка: {e}"))
            finally:
                self.after(0, lambda: self.update_status("● Готова"))

        threading.Thread(target=worker, daemon=True).start()

    # --- голос ---

    def toggle_voice(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.voice_btn.configure(fg_color=self.colors["accent"])
            self.update_status("🎙 Голосовой режим включен")
            self.add_action_log("Голосовой ввод включен")
        else:
            self.voice_btn.configure(fg_color=self.colors["bg_medium"])
            self.update_status("● Готова")
            self.add_action_log("Голосовой ввод выключен")

    # --- статус ---

    def update_status(self, status):
        self.status_indicator.configure(text=status)
        if "Готова" in status:
            self.status_indicator.configure(text_color=self.colors["accent"])
        elif "🎙" in status:
            self.status_indicator.configure(text_color=self.colors["accent"])
        elif "Ошибка" in status or "offline" in status.lower():
            self.status_indicator.configure(text_color=self.colors["danger"])
        else:
            self.status_indicator.configure(
                text_color=self.colors["text_secondary"]
            )



# ===== ТОЧКА ВХОДА =====


def main():
    app = YukoGUI()

    def safe_init_core():
        try:
            app.initialize_core()
        except Exception as e:
            print("Core init error:", e)

    app.withdraw()

    def on_splash_done():
        app.deiconify()
        app.update()
        app.center_window()

    SplashScreen(app, core_init_callback=safe_init_core, on_done=on_splash_done)

    app.mainloop()


if __name__ == "__main__":
    main()
