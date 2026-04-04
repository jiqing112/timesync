"""
Windows 时间同步工具 - GUI 版本
显示当前时间和远程服务器时间，一键同步，支持时区选择
"""

import ctypes
import sys
import datetime
import threading
import ntplib
import subprocess
import tkinter as tk
from tkinter import ttk
from ctypes import wintypes

ctypes.windll.kernel32.FreeConsole()

class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]

kernel32 = ctypes.windll.kernel32
SetSystemTime = kernel32.SetSystemTime
SetSystemTime.argtypes = [ctypes.POINTER(SYSTEMTIME)]
SetSystemTime.restype = wintypes.BOOL

NTP_SERVERS = [
    "ntp.aliyun.com",
    "ntp.tencent.com",
    "cn.pool.ntp.org",
    "ntp.ntsc.ac.cn",
    "time.windows.com",
]

TIMEZONES = [
    ("UTC+8", 8),
    ("UTC+9", 9),
    ("UTC+7", 7),
    ("UTC", 0),
    ("UTC-5", -5),
    ("UTC-8", -8),
]


def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


class TimeSyncGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows 时间同步工具")
        self.root.geometry("400x340")
        self.root.resizable(False, False)
        center_window(self.root, 400, 340)

        self.ntp_time = None
        self.ntp_local_ref = None
        self.time_offset = 8
        self.running = True
        self.syncing = False

        self.setup_ui()
        self.update_local_time()
        self.root.after(500, self.refresh_ntp_time)
        self.root.after(5000, self.periodic_refresh)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="Windows 时间同步", font=("Microsoft YaHei", 14, "bold"))
        title_label.pack(pady=(0, 10))

        time_frame = ttk.LabelFrame(main_frame, text="时间显示", padding="10")
        time_frame.pack(fill=tk.X, pady=5)

        ttk.Label(time_frame, text="本地时间:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.local_time_label = ttk.Label(time_frame, text="--", font=("Consolas", 11))
        self.local_time_label.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(time_frame, text="服务器时间:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ntp_time_label = ttk.Label(time_frame, text="正在获取...", font=("Consolas", 11))
        self.ntp_time_label.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(time_frame, text="时间差异:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.diff_label = ttk.Label(time_frame, text="--", font=("Consolas", 11))
        self.diff_label.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(time_frame, text="时区:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.tz_combo = ttk.Combobox(time_frame, values=[tz[0] for tz in TIMEZONES], state="readonly", width=15)
        self.tz_combo.current(0)
        self.tz_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        self.tz_combo.bind("<<ComboboxSelected>>", self.on_tz_changed)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=12)

        self.sync_btn = ttk.Button(btn_frame, text="一键同步", command=self.sync_time, width=12)
        self.sync_btn.pack(side=tk.LEFT, padx=5)

        self.refresh_btn = ttk.Button(btn_frame, text="刷新时间", command=self.refresh_ntp_time, width=12)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(main_frame, text="正在获取服务器时间...", foreground="blue", font=("Microsoft YaHei", 10))
        self.status_label.pack(pady=5)

    def on_tz_changed(self, event):
        selected = self.tz_combo.get()
        for name, offset in TIMEZONES:
            if name == selected:
                self.time_offset = offset
                break

    def get_local_time(self):
        return datetime.datetime.now()

    def get_ntp_time(self):
        client = ntplib.NTPClient()
        for server in NTP_SERVERS:
            try:
                response = client.request(server, version=3, timeout=3)
                delay = response.delay
                corrected_time = response.tx_time - (delay / 2.0)
                utc_dt = datetime.datetime.fromtimestamp(corrected_time, datetime.timezone.utc)
                return utc_dt.replace(tzinfo=None), delay
            except:
                continue
        return None, None

    def format_time(self, dt):
        if dt is None:
            return "获取失败"
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def update_local_time(self):
        if not self.running:
            return
        local = self.get_local_time()
        self.local_time_label.config(text=self.format_time(local))
        if self.ntp_time and self.ntp_local_ref:
            offset = datetime.timedelta(hours=self.time_offset)
            elapsed = (local - self.ntp_local_ref).total_seconds()
            current_ntp = self.ntp_time + datetime.timedelta(seconds=elapsed) + offset
            self.ntp_time_label.config(text=self.format_time(current_ntp))
            diff = abs((local - current_ntp).total_seconds())
            self.diff_label.config(text=f"{diff:.2f} 秒")
        self.root.after(1000, self.update_local_time)

    def refresh_ntp_time(self):
        self.status_label.config(text="正在获取服务器时间...", foreground="blue")
        self.refresh_btn.config(state=tk.DISABLED)
        self.sync_btn.config(state=tk.DISABLED)

        def worker():
            ntp, delay = self.get_ntp_time()
            local_ref = datetime.datetime.now()
            self.root.after(0, lambda: self.on_ntp_ready(ntp, local_ref, delay))

        threading.Thread(target=worker, daemon=True).start()

    def on_ntp_ready(self, ntp_time, local_ref, delay):
        self.ntp_time = ntp_time
        self.ntp_local_ref = local_ref
        self.refresh_btn.config(state=tk.NORMAL)
        self.sync_btn.config(state=tk.NORMAL)
        if self.ntp_time:
            offset = datetime.timedelta(hours=self.time_offset)
            adjusted = self.ntp_time + offset
            self.ntp_time_label.config(text=self.format_time(adjusted))
            local = self.get_local_time()
            diff = abs((local - adjusted).total_seconds())
            delay_ms = f"{delay*1000:.0f}" if delay else "?"
            self.diff_label.config(text=f"{diff:.2f} 秒 (延迟{delay_ms}ms)")
            self.status_label.config(text="获取成功，正在同步...", foreground="green")
            if ctypes.windll.shell32.IsUserAnAdmin() and not self.syncing:
                self.sync_time()
            else:
                self.status_label.config(text="获取成功", foreground="green")
        else:
            self.ntp_time_label.config(text="获取失败")
            self.status_label.config(text="获取失败，请检查网络", foreground="red")

    def sync_time(self):
        if not self.ntp_time:
            self.status_label.config(text="请先刷新获取服务器时间！", foreground="orange")
            return

        if not ctypes.windll.shell32.IsUserAnAdmin():
            self.status_label.config(text="需要管理员权限！", foreground="red")
            return

        if self.syncing:
            return

        self.syncing = True
        self.sync_btn.config(state=tk.DISABLED)
        self.status_label.config(text="正在同步...", foreground="blue")

        def worker():
            try:
                now = datetime.datetime.now()
                elapsed = (now - self.ntp_local_ref).total_seconds()
                corrected_ntp = self.ntp_time + datetime.timedelta(seconds=elapsed)

                st = SYSTEMTIME()
                st.wYear = corrected_ntp.year
                st.wMonth = corrected_ntp.month
                st.wDay = corrected_ntp.day
                st.wHour = corrected_ntp.hour
                st.wMinute = corrected_ntp.minute
                st.wSecond = corrected_ntp.second
                st.wMilliseconds = corrected_ntp.microsecond // 1000

                if not SetSystemTime(ctypes.byref(st)):
                    raise ctypes.WinError()

                target_time = corrected_ntp + datetime.timedelta(hours=self.time_offset)
                self.root.after(0, lambda: self.on_sync_success(target_time.strftime("%Y-%m-%d %H:%M:%S")))
            except Exception as e:
                self.root.after(0, lambda: self.status_label.config(text=f"同步失败: {str(e)[:20]}", foreground="red"))
            finally:
                self.root.after(0, lambda: setattr(self, 'syncing', False))
                self.root.after(0, lambda: self.sync_btn.config(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def on_sync_success(self, date_str):
        time_str = date_str.split(" ")[1]
        target = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        utc_ntp = target - datetime.timedelta(hours=self.time_offset)
        self.ntp_time = utc_ntp
        self.ntp_local_ref = datetime.datetime.now()
        self.status_label.config(text=f"同步成功！ {date_str} {time_str}", foreground="green")

    def periodic_refresh(self):
        if self.running:
            self.refresh_ntp_time()
        self.root.after(5000, self.periodic_refresh)

    def on_close(self):
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TimeSyncGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
