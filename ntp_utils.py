"""
NTP 时间同步工具 - 公共模块
提供 NTP 时间获取、系统时间设置、管理员权限检查等共享功能。
"""

import ctypes
import sys
import datetime
import logging
import subprocess
import ntplib
from ctypes import wintypes

logger = logging.getLogger("time_sync")

# ============== 配置 ==============
# NTP 服务器列表（按优先级排序）
NTP_SERVERS = [
    "ntp.aliyun.com",       # 阿里云 NTP
    "ntp.tencent.com",      # 腾讯云 NTP
    "cn.pool.ntp.org",      # 中国 NTP 池
    "ntp.ntsc.ac.cn",       # 中国国家授时中心
    "time.windows.com",     # 微软 NTP
]

# 时间差异阈值（秒），超过此值则自动同步
THRESHOLD_SECONDS = 2.0


# ============== Windows API 定义 ==============
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


_kernel32 = ctypes.windll.kernel32
_SetSystemTime = _kernel32.SetSystemTime
_SetSystemTime.argtypes = [ctypes.POINTER(SYSTEMTIME)]
_SetSystemTime.restype = wintypes.BOOL


# ============== 管理员权限 ==============
def is_admin() -> bool:
    """检查当前是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新启动本脚本"""
    logger.info("正在请求提升管理员权限...")
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        subprocess.list2cmdline(sys.argv),  # 安全转义参数，防止命令注入
        None, 1
    )
    sys.exit(0)


# ============== NTP 时间获取 ==============
def get_ntp_time(timeout: int = 5, verbose: bool = False) -> tuple[datetime.datetime | None, float | None]:
    """
    从 NTP 服务器获取标准 UTC 时间。
    返回 (utc_naive_datetime, delay_seconds) 或 (None, None)。

    包含网络延迟补偿。
    """
    client = ntplib.NTPClient()
    for server in NTP_SERVERS:
        try:
            if verbose:
                print(f"  正在连接 NTP 服务器: {server} ...")
            logger.debug("连接 NTP 服务器: %s", server)

            response = client.request(server, version=3, timeout=timeout)
            delay = response.delay
            # 使用延迟补偿修正时间
            corrected_time = response.tx_time - (delay / 2.0)
            utc_dt = datetime.datetime.fromtimestamp(corrected_time, datetime.timezone.utc)
            utc_naive = utc_dt.replace(tzinfo=None)

            if verbose:
                print(f"  [OK] 成功从 {server} 获取时间 (延迟 {delay*1000:.0f}ms)")
            logger.info("从 %s 获取时间成功, 延迟 %.1fms", server, delay * 1000)
            return utc_naive, delay
        except Exception as e:
            if verbose:
                print(f"  [FAIL] {server} 连接失败: {e}")
            logger.warning("NTP 服务器 %s 连接失败: %s", server, e)
            continue
    return None, None


def utc_to_local(utc_time: datetime.datetime, offset_hours: int = 8) -> datetime.datetime:
    """将 UTC 时间转换为指定时区的本地时间"""
    return utc_time + datetime.timedelta(hours=offset_hours)


# ============== 系统时间设置 ==============
def set_system_time(utc_time: datetime.datetime) -> bool:
    """
    使用 Windows API (SetSystemTime) 设置系统时间。
    参数 utc_time 必须是 UTC 时间（naive datetime）。
    需要管理员权限。
    """
    st = SYSTEMTIME()
    st.wYear = utc_time.year
    st.wMonth = utc_time.month
    st.wDay = utc_time.day
    st.wHour = utc_time.hour
    st.wMinute = utc_time.minute
    st.wSecond = utc_time.second
    st.wMilliseconds = utc_time.microsecond // 1000

    if _SetSystemTime(ctypes.byref(st)):
        logger.info("系统时间已设置为 (UTC): %s", utc_time.strftime("%Y-%m-%d %H:%M:%S"))
        return True
    else:
        error = ctypes.WinError()
        logger.error("设置系统时间失败: %s", error)
        return False


# ============== 辅助函数 ==============
def format_time(dt: datetime.datetime) -> str:
    """格式化时间为易读字符串（精确到毫秒）"""
    if dt is None:
        return "获取失败"
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_local_time() -> datetime.datetime:
    """获取本地系统时间"""
    return datetime.datetime.now()


def setup_logging(level=logging.INFO, log_file: str | None = None):
    """配置日志系统"""
    handlers = []
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # 文件输出（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers)
