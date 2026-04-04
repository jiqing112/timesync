"""
Windows 时间同步工具
自动从 NTP 服务器获取标准时间，与本地时间比较，超过阈值自动同步。
适用于北京时间 (UTC+8)。
"""

import ctypes
import sys
import datetime
import ntplib
import subprocess


def wait_exit():
    """等待用户按键退出，非交互环境下直接返回"""
    try:
        input("\n按回车键退出...")
    except EOFError:
        pass


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

# 北京时间时区偏移（UTC+8）
BEIJING_UTC_OFFSET = datetime.timedelta(hours=8)


def is_admin() -> bool:
    """检查当前是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新启动本脚本"""
    print("[!] 修改系统时间需要管理员权限，正在请求提升权限...")
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)


def get_local_time() -> datetime.datetime:
    """获取本地系统时间（北京时间）"""
    return datetime.datetime.now()


def get_ntp_time() -> datetime.datetime | None:
    """
    从 NTP 服务器获取标准 UTC 时间，转换为北京时间。
    依次尝试多个服务器，直到成功。
    """
    client = ntplib.NTPClient()
    for server in NTP_SERVERS:
        try:
            print(f"  正在连接 NTP 服务器: {server} ...")
            response = client.request(server, version=3, timeout=5)
            utc_time = datetime.datetime.fromtimestamp(response.tx_time, tz=datetime.timezone.utc)
            beijing_time = utc_time + BEIJING_UTC_OFFSET
            beijing_time = beijing_time.replace(tzinfo=None)  # 转为 naive 以便与本地时间比较
            print(f"  [OK] 成功从 {server} 获取时间")
            return beijing_time
        except Exception as e:
            print(f"  [FAIL] {server} 连接失败: {e}")
            continue
    return None


def set_system_time(target_time: datetime.datetime):
    """
    使用 w32tm 命令或 Windows API 设置系统时间。
    需要管理员权限。
    """
    # 方法：使用 Windows date 和 time 命令
    date_str = target_time.strftime("%Y-%m-%d")
    time_str = target_time.strftime("%H:%M:%S")

    try:
        # 使用 PowerShell 设置系统时间（更可靠）
        ps_cmd = f"Set-Date -Date '{date_str} {time_str}'"
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  [OK] 系统时间已设置为: {date_str} {time_str}")
            return True
        else:
            print(f"  [FAIL] 设置时间失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  [FAIL] 设置时间时发生异常: {e}")
        return False


def format_time(dt: datetime.datetime) -> str:
    """格式化时间为易读字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def main():
    print("=" * 56)
    print("       Windows 时间同步工具 (北京时间 UTC+8)")
    print("=" * 56)
    print()

    # 1. 获取本地时间
    print("[1] 读取本地系统时间...")
    local_time = get_local_time()
    print(f"    本地时间: {format_time(local_time)}")
    print()

    # 2. 获取 NTP 服务器时间
    print("[2] 从 NTP 服务器获取标准时间...")
    ntp_time = get_ntp_time()
    if ntp_time is None:
        print()
        print("[ERROR] 无法从任何 NTP 服务器获取时间！")
        print("  请检查网络连接后重试。")
        wait_exit()
        sys.exit(1)

    print(f"    标准时间: {format_time(ntp_time)}")
    print()

    # 3. 比较时间差异
    print("[3] 比较时间差异...")
    # 重新获取本地时间以减少网络延迟带来的误差
    local_time = get_local_time()
    diff = abs((local_time - ntp_time).total_seconds())
    print(f"    本地时间: {format_time(local_time)}")
    print(f"    标准时间: {format_time(ntp_time)}")
    print(f"    时间差异: {diff:.3f} 秒")
    print(f"    同步阈值: {THRESHOLD_SECONDS} 秒")
    print()

    # 4. 判断是否需要同步
    if diff <= THRESHOLD_SECONDS:
        print("[OK] 本地时间与标准时间差异在阈值范围内，无需同步。")
        wait_exit()
        return

    print(f"[!] 时间差异超过阈值 ({diff:.3f}s > {THRESHOLD_SECONDS}s)，需要同步！")
    print()

    # 5. 检查管理员权限
    if not is_admin():
        run_as_admin()

    # 6. 执行同步
    print("[4] 正在同步系统时间...")
    # 再次获取 NTP 时间以确保准确
    ntp_time = get_ntp_time()
    if ntp_time is None:
        print("[ERROR] 同步前再次获取 NTP 时间失败！")
        wait_exit()
        sys.exit(1)

    success = set_system_time(ntp_time)
    print()

    if success:
        # 验证同步结果
        new_local = get_local_time()
        new_diff = abs((new_local - ntp_time).total_seconds())
        print("[5] 同步验证:")
        print(f"    同步后本地时间: {format_time(new_local)}")
        print(f"    同步后时间差异: {new_diff:.3f} 秒")
        if new_diff <= THRESHOLD_SECONDS:
            print("    [OK] 时间同步成功！")
        else:
            print("    [WARN] 同步后差异仍较大，请手动检查。")
    else:
        print("[ERROR] 时间同步失败，请尝试手动同步或检查权限。")

    wait_exit()


if __name__ == "__main__":
    main()
