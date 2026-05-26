"""
Windows 时间同步工具 - GUI 版本
显示当前时间和远程服务器时间，一键同步，支持时区选择
"""

import ctypes
import datetime
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ntp_utils import (
    is_admin,
    get_ntp_time,
    get_local_time,
    set_system_time,
    setup_logging,
    THRESHOLD_SECONDS,
)

ctypes.windll.kernel32.FreeConsole()

logger = logging.getLogger("time_sync")

TIMEZONES = [
    ("UTC+8", 8),
    ("UTC+9", 9),
    ("UTC+7", 7),
    ("UTC", 0),
    ("UTC-5", -5),
    ("UTC-8", -8),
]

# NTP 自动刷新间隔（毫秒），5 秒
NTP_REFRESH_INTERVAL_MS = 5_000


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

        self.ntp_time = None          # UTC naive datetime
        self.ntp_local_ref = None     # 获取 NTP 时间时的本地时间快照
        self.ntp_delay = None         # 网络延迟（秒）
        self.time_offset = 8          # 时区偏移（小时）
        self.running = True
        self.syncing = False

        self.setup_ui()
        self.update_local_time()
        self.root.after(500, self.refresh_ntp_time)
        self.root.after(NTP_REFRESH_INTERVAL_MS, self.periodic_refresh)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame, text="Windows 时间同步",
            font=("Microsoft YaHei", 14, "bold")
        )
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
        self.tz_combo = ttk.Combobox(
            time_frame, values=[tz[0] for tz in TIMEZONES],
            state="readonly", width=15
        )
        self.tz_combo.current(0)
        self.tz_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        self.tz_combo.bind("<<ComboboxSelected>>", self.on_tz_changed)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=12)

        self.sync_btn = ttk.Button(btn_frame, text="一键同步", command=self.sync_time, width=12)
        self.sync_btn.pack(side=tk.LEFT, padx=5)

        self.refresh_btn = ttk.Button(btn_frame, text="刷新时间", command=self.refresh_ntp_time, width=12)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(
            main_frame, text="正在获取服务器时间...",
            foreground="blue", font=("Microsoft YaHei", 10)
        )
        self.status_label.pack(pady=5)

    def on_tz_changed(self, event):
        selected = self.tz_combo.get()
        for name, offset in TIMEZONES:
            if name == selected:
                self.time_offset = offset
                break

    def format_time(self, dt):
        if dt is None:
            return "获取失败"
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _get_current_ntp_local(self) -> datetime.datetime | None:
        """根据 NTP 快照和本地时间流逝，推算当前的 NTP 本地时间"""
        if self.ntp_time is None or self.ntp_local_ref is None:
            return None
        offset = datetime.timedelta(hours=self.time_offset)
        elapsed = (get_local_time() - self.ntp_local_ref).total_seconds()
        return self.ntp_time + datetime.timedelta(seconds=elapsed) + offset

    def update_local_time(self):
        if not self.running:
            return
        local = get_local_time()
        self.local_time_label.config(text=self.format_time(local))

        current_ntp = self._get_current_ntp_local()
        if current_ntp is not None:
            self.ntp_time_label.config(text=self.format_time(current_ntp))
            diff = abs((local - current_ntp).total_seconds())
            self.diff_label.config(text=f"{diff:.2f} 秒")

        self.root.after(1000, self.update_local_time)

    def refresh_ntp_time(self):
        self.status_label.config(text="正在获取服务器时间...", foreground="blue")
        self.refresh_btn.config(state=tk.DISABLED)
        self.sync_btn.config(state=tk.DISABLED)

        def worker():
            ntp, delay = get_ntp_time(timeout=3)
            local_ref = get_local_time()
            self.root.after(0, lambda: self.on_ntp_ready(ntp, local_ref, delay))

        threading.Thread(target=worker, daemon=True).start()

    def on_ntp_ready(self, ntp_time, local_ref, delay):
        self.ntp_time = ntp_time
        self.ntp_local_ref = local_ref
        self.ntp_delay = delay
        self.refresh_btn.config(state=tk.NORMAL)
        self.sync_btn.config(state=tk.NORMAL)

        if self.ntp_time is not None:
            offset = datetime.timedelta(hours=self.time_offset)
            adjusted = self.ntp_time + offset
            self.ntp_time_label.config(text=self.format_time(adjusted))

            local = get_local_time()
            diff = abs((local - adjusted).total_seconds())
            delay_ms = f"{delay * 1000:.0f}" if delay else "?"
            self.diff_label.config(text=f"{diff:.2f} 秒 (延迟{delay_ms}ms)")
            logger.info("NTP time synced, diff=%.2f sec", diff)

            if is_admin():
                if diff > THRESHOLD_SECONDS:
                    self.status_label.config(text=f"差异 {diff:.2f}s > {THRESHOLD_SECONDS}s, 正在自动同步...", foreground="orange")
                    logger.info("Time diff %.2f > threshold %.2f, auto syncing...", diff, THRESHOLD_SECONDS)
                    self.sync_time()
                else:
                    self.status_label.config(text=f"时间差异 {diff:.2f}s, 无需同步", foreground="green")
            else:
                self.status_label.config(text="获取成功 (需管理员权限同步)", foreground="blue")
        else:
            self.ntp_time_label.config(text="获取失败")
            self.status_label.config(text="获取失败，请检查网络", foreground="red")
            logger.warning("NTP time fetch failed")

    def sync_time(self):
        if self.ntp_time is None:
            self.status_label.config(text="请先刷新获取服务器时间！", foreground="orange")
            return

        if not is_admin():
            self.status_label.config(text="需要管理员权限！", foreground="red")
            return

        if self.syncing:
            return

        self.syncing = True
        self.sync_btn.config(state=tk.DISABLED)
        self.status_label.config(text="正在同步...", foreground="blue")

        def worker():
            try:
                ntp_ref = self.ntp_time
                local_ref = self.ntp_local_ref
                if ntp_ref is None or local_ref is None:
                    return
                now = get_local_time()
                elapsed = (now - local_ref).total_seconds()
                corrected_utc = ntp_ref + datetime.timedelta(seconds=elapsed)

                success = set_system_time(corrected_utc)

                if success:
                    local_time = corrected_utc + datetime.timedelta(hours=self.time_offset)
                    time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
                    self.root.after(0, lambda: self.on_sync_success(corrected_utc, time_str))
                else:
                    self.root.after(0, lambda: self.status_label.config(
                        text="同步失败，请检查权限", foreground="red"
                    ))
            except Exception as e:
                logger.error("同步异常: %s", e)
                self.root.after(0, lambda: self.status_label.config(
                    text=f"同步失败: {str(e)[:30]}", foreground="red"
                ))
            finally:
                self.root.after(0, self._finish_sync)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_sync(self):
        self.syncing = False
        self.sync_btn.config(state=tk.NORMAL)

    def on_sync_success(self, utc_time, display_str):
        # 更新 NTP 参考点，使后续时间推算基于新的基准
        self.ntp_time = utc_time
        self.ntp_local_ref = get_local_time()
        self.status_label.config(text=f"同步成功！{display_str}", foreground="green")
        logger.info("时间同步成功: %s", display_str)

    def periodic_refresh(self):
        if not self.running:
            return  # 窗口已关闭，不再调度
        self.refresh_ntp_time()
        self.root.after(NTP_REFRESH_INTERVAL_MS, self.periodic_refresh)

    def on_close(self):
        if self.syncing:
            if not messagebox.askyesno("确认", "正在同步时间，确定要退出吗？"):
                return
        self.running = False
        self.root.destroy()


def main():
    setup_logging(level=logging.INFO)
    root = tk.Tk()
    app = TimeSyncGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
