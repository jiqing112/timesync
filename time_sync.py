"""
Windows 时间同步工具 - CLI 版本
自动从 NTP 服务器获取标准时间，与本地时间比较，超过阈值自动同步。
适用于北京时间 (UTC+8)。
"""

import sys
import logging

from ntp_utils import (
    NTP_SERVERS,
    THRESHOLD_SECONDS,
    is_admin,
    run_as_admin,
    get_ntp_time,
    get_local_time,
    set_system_time,
    utc_to_local,
    format_time,
    setup_logging,
)

# 北京时间偏移
UTC_OFFSET_HOURS = 8

logger = logging.getLogger("time_sync")


def wait_exit():
    """等待用户按键退出，非交互环境下直接返回"""
    try:
        input("\n按回车键退出...")
    except EOFError:
        pass


def main():
    setup_logging(level=logging.DEBUG)

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
    ntp_utc, delay = get_ntp_time(timeout=5, verbose=True)
    if ntp_utc is None:
        print()
        print("[ERROR] 无法从任何 NTP 服务器获取时间！")
        print("  请检查网络连接后重试。")
        wait_exit()
        sys.exit(1)

    ntp_beijing = utc_to_local(ntp_utc, UTC_OFFSET_HOURS)
    print(f"    标准时间: {format_time(ntp_beijing)}")
    if delay is not None:
        print(f"    网络延迟: {delay*1000:.0f}ms")
    print()

    # 3. 比较时间差异
    print("[3] 比较时间差异...")
    # 重新获取本地时间以减少网络延迟带来的误差
    local_time = get_local_time()
    diff = abs((local_time - ntp_beijing).total_seconds())
    print(f"    本地时间: {format_time(local_time)}")
    print(f"    标准时间: {format_time(ntp_beijing)}")
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
        print("[!] 修改系统时间需要管理员权限，正在请求提升权限...")
        run_as_admin()

    # 6. 执行同步 - 再次获取 NTP 时间以确保准确
    print("[4] 正在同步系统时间...")
    ntp_utc, delay = get_ntp_time(timeout=5, verbose=True)
    if ntp_utc is None:
        print("[ERROR] 同步前再次获取 NTP 时间失败！")
        wait_exit()
        sys.exit(1)

    success = set_system_time(ntp_utc)
    ntp_beijing = utc_to_local(ntp_utc, UTC_OFFSET_HOURS)
    print()

    if success:
        print(f"  [OK] 系统时间已设置为: {format_time(ntp_beijing)}")
        # 验证同步结果
        new_local = get_local_time()
        new_diff = abs((new_local - ntp_beijing).total_seconds())
        print()
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
