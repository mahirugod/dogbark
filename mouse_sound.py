"""
鼠标左键点击 → 播放音效（GUI 配置 + 后台监听）
零第三方依赖，纯 Windows API + tkinter + winsound
支持 MP3 / WAV（MCI + winsound），不弹窗、不卡鼠标
"""
import ctypes
import atexit
import configparser
import os
import shutil
import sys
import time
import winsound
import threading

# windowed 模式（PyInstaller --windowed）下 stdout/stderr 为 None，print 会崩溃
if getattr(sys, "frozen", False):
    _log_path = os.path.join(os.path.dirname(sys.executable), "debug.log")
    try:
        _f = open(_log_path, "w", encoding="utf-8")
        sys.stdout = _f
        sys.stderr = _f
    except Exception:
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201

# MCI 常量
MCI_FROM_ID = 0x19
MCI_TO_ID = 0x18


def _mci_send(cmd: str) -> int:
    out = ctypes.create_string_buffer(256)
    result = winmm.mciSendStringW(cmd, out, 256, 0)
    return result


def _mci_play(path: str) -> bool:
    """通过 MCI 播放音频文件，返回是否成功"""
    if not os.path.isfile(path):
        print(f"[mouse-sound] 文件不存在: {path}", file=sys.stderr)
        return False

    escaped = path.replace('"', '\\"')

    # 先关闭之前可能还在播放的实例
    _mci_send("close mouse_sound")

    # open（不带 type，让系统自动识别）
    r = _mci_send(f'open "{escaped}" alias mouse_sound')
    if r != 0:
        print(f"[mouse-sound] MCI open 失败 (code={r}): {path}", file=sys.stderr)
        return False

    time.sleep(0.05)

    # play from start
    r = _mci_send("play mouse_sound")
    if r != 0:
        print(f"[mouse-sound] MCI play 失败 (code={r})", file=sys.stderr)
        _mci_send("close mouse_sound")
        return False

    print("[mouse-sound] MCI 播放已触发", file=sys.stderr)
    return True


class App:
    def __init__(self):
        self.audio_file = ""
        self.hook_handle = None
        self._callback_ref = None
        self._running = False
        self._last_play_time = 0.0
        self._click_count = 0
        self._play_thread = None

    def load_config(self, path):
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        self.audio_file = cp.get("sound", "audio_file", fallback="").strip()

    def save_config(self, path):
        cp = configparser.ConfigParser()
        cp["core"] = {}
        cp["sound"] = {"audio_file": self.audio_file}
        with open(path, "w", encoding="utf-8") as f:
            cp.write(f)

    # ── 播放 ─────────────────────────────────────────────────────────
    def _play(self, audio_path):
        """
        快速播放：MCI 为主，winsound 兜底。
        内置 100ms 节流防卡死。
        """
        now = time.monotonic()
        if now - self._last_play_time < 0.1:
            return
        self._last_play_time = now

        if not audio_path or not os.path.isfile(audio_path):
            print("[mouse-sound] 未找到音效文件，使用系统 Beep", file=sys.stderr)
            winsound.Beep(800, 80)
            return

        # 在新线程里播放，不阻塞钩子
        t = threading.Thread(target=self._do_play, args=(audio_path,), daemon=True)
        t.start()

    def _do_play(self, audio_path):
        ext = os.path.splitext(audio_path)[1].lower()

        # MCI 支持 MP3 和 WAV
        if ext in (".mp3", ".wav"):
            if _mci_play(audio_path):
                return

        # WAV 走 winsound
        if ext == ".wav":
            try:
                winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                print("[mouse-sound] winsound 播放已触发", file=sys.stderr)
                return
            except Exception as e:
                print(f"[mouse-sound] winsound 失败: {e}", file=sys.stderr)

        # 最终兜底
        winsound.Beep(800, 80)

    def _play_safe(self):
        try:
            self._play(self.audio_file)
        except Exception as e:
            print(f"[mouse-sound] 播放失败: {e}", file=sys.stderr)

    def _test(self):
        self._do_play(self.audio_file)

    # ── 钩子 ─────────────────────────────────────────────────────────
    def _mouse_proc(self, nCode, wParam, lParam):
        try:
            if nCode >= 0 and wParam == WM_LBUTTONDOWN:
                self._click_count += 1
                self._play_safe()
        except Exception:
            pass
        try:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
        except Exception:
            return 0

    def install_hook(self):
        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p
        ]
        user32.CallNextHookEx.restype = ctypes.c_long

        self._callback_ref = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_void_p,
        )(self._mouse_proc)
        self.hook_handle = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._callback_ref, None, 0,
        )
        if not self.hook_handle:
            raise RuntimeError("SetWindowsHookExW 失败")
        print(f"[mouse-sound] 钩子已安装  句柄={self.hook_handle}")

    def uninstall_hook(self):
        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None
            print("[mouse-sound] 钩子已卸载")

    def start(self):
        if self._running:
            return
        self._running = True
        self.install_hook()
        print("[mouse-sound] 监听已启动")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self.uninstall_hook()
        # 关闭 MCI 资源，避免退出时残留句柄占用临时音效文件
        _mci_send("close mouse_sound")
        print("[mouse-sound] 监听已停止")

    def test_sound(self):
        self._test()


def cleanup_meipass():
    """打包环境退出时，主动删除 PyInstaller 临时解压目录（_MEIPASS）。
    该目录是 Python 进程启动时生成的，关闭程序后系统会自行清理，
    但这里显式删除可立即释放磁盘空间。"""
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass or not os.path.isdir(meipass):
        return
    # 等 MCI 线程释放句柄
    time.sleep(0.15)
    try:
        shutil.rmtree(meipass, ignore_errors=True)
        print(f"[mouse-sound] 已清理临时解压目录: {meipass}")
    except Exception as e:
        print(f"[mouse-sound] 清理临时目录失败: {e}")


# ── GUI ───────────────────────────────────────────────────────────────
def run_gui(app: App, config_path: str):
    import tkinter as tk
    from tkinter import ttk, filedialog

    root = tk.Tk()
    root.overrideredirect(True)          # 无边框
    root.resizable(False, False)
    root.configure(bg="#1a1a24")

    # 样式 —— 大狗叫主题（深色 + 琥珀/棕色调，贴合"大狗"氛围）
    style = ttk.Style()
    style.theme_use("clam")
    bg = "#1a1a24"
    fg = "#f2e9d8"
    accent = "#f5a623"
    sub = "#8a8577"
    card = "#232333"
    title_bg = "#101018"                # 自定义标题栏底色

    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=card)
    style.configure("Title.TLabel", font=("Microsoft YaHei", 20, "bold"),
                    foreground=accent, background=bg)
    style.configure("Sub.TLabel", font=("Microsoft YaHei", 9),
                    foreground=sub, background=bg)
    style.configure("TLabel", font=("Microsoft YaHei", 10),
                    foreground=fg, background=bg)
    style.configure("Val.TLabel", font=("Consolas", 10),
                    foreground=accent, background=bg)
    style.configure("Entry.TLabel", font=("Consolas", 8),
                    foreground=sub, background=bg)
    style.configure("TEntry", font=("Consolas", 10),
                    fieldbackground=card, foreground=fg)
    style.configure("TButton", font=("Microsoft YaHei", 10),
                    foreground=fg, background="#3a3a50")
    style.map("TButton", foreground=[("active", fg)],
              background=[("active", "#4a4a60")])
    style.configure("Accent.TButton", font=("Microsoft YaHei", 11, "bold"),
                    foreground="#1a1a24", background=accent)
    style.map("Accent.TButton", background=[("active", "#ffb840")])
    # 自定义标题栏样式
    style.configure("TitleBar.TFrame", background=title_bg)
    style.configure("TitleBar.TLabel", font=("Microsoft YaHei", 10, "bold"),
                    foreground=accent, background=title_bg)
    style.configure("Close.TLabel", font=("Microsoft YaHei", 12, "bold"),
                    foreground=sub, background=title_bg, cursor="hand2")
    style.map("Close.TLabel", foreground=[("active", "#e06c75")])

    status_var = tk.StringVar(value="未运行")
    path_var = tk.StringVar(value=app.audio_file)
    event_count_var = tk.StringVar(value="0")

    def update_status():
        if app._running:
            status_var.set("🐶 监听中")
        else:
            status_var.set("未运行")
        event_count_var.set(str(app._click_count))

    def pick_file():
        p = filedialog.askopenfilename(
            title="选择音效文件",
            filetypes=[
                ("音频文件", "*.mp3 *.wav"),
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("所有文件", "*.*"),
            ],
        )
        if p:
            path_var.set(p)
            app.audio_file = p

    def on_test():
        app.audio_file = path_var.get().strip()
        app.test_sound()

    def on_toggle():
        if app._running:
            app.stop()
            toggle_btn.config(text="🐕 开始叫")
            toggle_btn.config(style="Accent.TButton")
        else:
            app.audio_file = path_var.get().strip()
            # 仅当用户选了自定义文件时才保存配置
            if "_MEI" not in app.audio_file:
                app.save_config(config_path)
            app.start()
            toggle_btn.config(text="🔇 停止叫")
            toggle_btn.config(style="TButton")
        update_status()

    def on_exit():
        app.stop()
        # 不保存内置临时音效路径（每次运行 _MEIPASS 不同）
        if app.audio_file and "_MEI" not in app.audio_file:
            app.save_config(config_path)
        root.destroy()
        # 程序退出时主动清理 PyInstaller 临时解压目录
        cleanup_meipass()

    # ── 自定义标题栏（无边框窗口需要自己画，且支持拖动）──
    titlebar = tk.Frame(root, bg=title_bg, cursor="fleur")
    titlebar.pack(fill="x", side="top")
    tk.Label(
        titlebar, text="🐶 大狗叫", font=("Microsoft YaHei", 10, "bold"),
        fg=accent, bg=title_bg,
    ).pack(side="left", padx=(12, 0), pady=6)
    close_lbl = tk.Label(
        titlebar, text="✕", font=("Microsoft YaHei", 12, "bold"),
        fg=sub, bg=title_bg, cursor="hand2",
    )
    close_lbl.pack(side="right", padx=6, pady=2)
    close_lbl.bind("<Button-1>", lambda e: on_exit())
    close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg="#e06c75"))
    close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg=sub))

    # 拖动窗口：鼠标在标题栏上按下并拖动即可移动窗口
    _drag = {"x": 0, "y": 0}
    def _drag_start(e):
        _drag["x"] = e.x_root - root.winfo_x()
        _drag["y"] = e.y_root - root.winfo_y()
    def _drag_move(e):
        root.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
    for w in (titlebar,):
        w.bind("<Button-1>", _drag_start)
        w.bind("<B1-Motion>", _drag_move)

    # 主框架
    main = ttk.Frame(root, padding=(24, 18))
    main.pack(fill="both", expand=True)
    main.columnconfigure(0, weight=1)

    # 副标题
    ttk.Label(main, text="鼠标左键一点，大狗就叫", style="Sub.TLabel").grid(
        row=0, column=0, sticky="w", pady=(2, 10)
    )

    # 音效文件
    ttk.Label(main, text="音效文件", style="TLabel").grid(
        row=1, column=0, sticky="w", pady=(0, 4)
    )
    entry_row = ttk.Frame(main)
    entry_row.grid(row=2, column=0, sticky="ew")
    ttk.Entry(entry_row, textvariable=path_var, width=28).pack(
        side="left", fill="x", expand=True
    )
    ttk.Button(entry_row, text="浏览", command=pick_file, width=6).pack(
        side="left", padx=(8, 0)
    )
    ttk.Label(main, textvariable=path_var, style="Entry.TLabel").grid(
        row=3, column=0, sticky="w", pady=(4, 10)
    )

    # 状态
    ttk.Label(main, text="运行状态", style="TLabel").grid(
        row=4, column=0, sticky="w", pady=(0, 4)
    )
    status_frame = ttk.Frame(main)
    status_frame.grid(row=5, column=0, sticky="ew")
    ttk.Label(status_frame, textvariable=status_var, style="Val.TLabel").pack(
        side="left"
    )
    ttk.Label(status_frame, text="  ·  左键次数: ", style="Sub.TLabel").pack(side="left")
    ttk.Label(status_frame, textvariable=event_count_var, style="Val.TLabel").pack(
        side="left"
    )

    # 按钮
    btn_row = ttk.Frame(main)
    btn_row.grid(row=6, column=0, sticky="ew", pady=(14, 0))
    toggle_btn = ttk.Button(
        btn_row, text="🐕 开始叫", command=on_toggle, width=12, style="Accent.TButton"
    )
    toggle_btn.pack(side="left")
    ttk.Button(btn_row, text="试听", command=on_test, width=8).pack(side="left", padx=(10, 0))
    ttk.Button(btn_row, text="退出", command=on_exit, width=6).pack(side="right")

    # 提示
    ttk.Label(
        main,
        text="支持 MP3 / WAV · 不弹窗 · 不卡鼠标",
        style="Sub.TLabel",
        justify="left",
    ).grid(row=7, column=0, sticky="w", pady=(10, 0))

    # Esc 关闭；无边框后 WM_DELETE_WINDOW 不再生效，保留以防系统快捷键
    root.bind("<Escape>", lambda e: on_exit())
    root.protocol("WM_DELETE_WINDOW", on_exit)
    root.update_idletasks()

    # 初始居中
    w, h = 320, 290
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    # 定时刷新计数
    def refresh_count():
        update_status()
        root.after(200, refresh_count)

    refresh_count()
    root.mainloop()


def main():
    # 兼容 PyInstaller 单文件打包：
    #   - 内置音效（dog_bark.mp3）随 exe 打包，运行时在临时解压目录里
    #   - config.ini 放在 exe 同级目录，用户可直接查看/修改
    if getattr(sys, "frozen", False):
        # 打包环境：资源解压目录 & 配置/默认音效目录
        resource_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        config_dir = os.path.dirname(os.path.abspath(sys.executable))
        bundled_default = os.path.join(resource_dir, "dog_bark.mp3")
        default_audio = bundled_default if os.path.isfile(bundled_default) else ""
    else:
        resource_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = resource_dir
        default_audio = os.path.join(resource_dir, "dog_bark.mp3")

    config_path = os.path.join(config_dir, "config.ini")
    app = App()
    app.load_config(config_path)
    # 若配置为空或文件不存在，优先使用内置默认音效
    if not app.audio_file or not os.path.isfile(app.audio_file):
        if default_audio and os.path.isfile(default_audio):
            app.audio_file = default_audio

    if len(sys.argv) > 1 and sys.argv[1] == "--headless":
        # 后台无 GUI 模式
        print(f"[大狗叫] 音效: {app.audio_file or '系统默认提示音(Beep)'}")
        print("[大狗叫] 监听中，按 Ctrl+C 退出")
        try:
            app.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[大狗叫] 正在退出…")
        finally:
            app.stop()
            cleanup_meipass()
    else:
        # 注册全局退出兜底：即使 GUI 没调 cleanup_meipass，进程退出时也清理
        atexit.register(cleanup_meipass)
        run_gui(app, config_path)


if __name__ == "__main__":
    main()
