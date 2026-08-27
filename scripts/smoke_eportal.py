#!/usr/bin/env python3
"""ePortal（校园网认证）活网冒烟脚本（手动运行，非自动化测试）。

**必须在校园网内运行**（典型场景：未认证的宿舍网设备/容器），且目标设备
应当是「未认证」状态才有完整的登录路径可测。

用法::

    uv run python scripts/smoke_eportal.py status    # 查询在线状态
    uv run python scripts/smoke_eportal.py offline   # 离线状态 + 异常路径（不需要凭据）
    uv run python scripts/smoke_eportal.py login <学工号> <密码> [服务名]
    uv run python scripts/smoke_eportal.py logout

验证码人工识别：脚本把 PNG 的 base64 打印在两行标记之间，解码查看::

    base64 -d cap.b64 > cap.png

识别结果写入 ``/tmp/captcha_answer.txt``（一行文本）后脚本自动继续。

若设备存在未完成的认证流程（redirect.jsp 302 到占位 IP、NAS 劫持不应答），
可用环境变量指定仍在有效期内的流程 sessionId 直接续上::

    EPORTAL_RESUME_SESSION=<sessionId> uv run python scripts/smoke_eportal.py login ...

注意：未认证设备的 HTTP 流量会被 NAS 劫持评估，短时间多次触发会被丢包
（ReadTimeout），恢复时间未知。请顺序运行各模式，不要并发。
"""

from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

from ysu_sdk.eportal import (
    CaptchaFailedError,
    EPortalClient,
    NeedCaptchaError,
    OnlineStatus,
)

ANSWER_PATH = Path("/tmp/captcha_answer.txt")
RESUME_SESSION = os.environ.get("EPORTAL_RESUME_SESSION")


def patch_resume(client: EPortalClient) -> None:
    """测试辅助：跳过 redirect.jsp，复用仍在有效期内的流程会话。"""
    if not RESUME_SESSION:
        return
    client._fetch_session_info = lambda: {  # type: ignore[method-assign]
        "sessionId": RESUME_SESSION,
        "customPageId": "7f27e840a0f445a599be2b2aa2224af4",
        "mode": "history",
        "nasIp": "10.11.1.200",
        "userIp": "10.20.75.212",
        "ssid": "Ruijie",
    }
    print(f"[resume] 复用流程会话 {RESUME_SESSION}")


def show(status: OnlineStatus) -> None:
    print(
        f"online={status.online} username={status.username} "
        f"service={status.service} ip={status.user_ip} mac={status.user_mac} "
        f"message={status.message}"
    )


def manual_solver(png: bytes) -> str:
    print("-----CAPTCHA-BEGIN-----", flush=True)
    print(base64.b64encode(png).decode(), flush=True)
    print("-----CAPTCHA-END-----", flush=True)
    print(f"识别后执行: echo '<答案>' > {ANSWER_PATH}", flush=True)
    ANSWER_PATH.unlink(missing_ok=True)
    for _ in range(180):
        if ANSWER_PATH.exists():
            code = ANSWER_PATH.read_text().strip()
            ANSWER_PATH.unlink(missing_ok=True)
            if code:
                return code
        time.sleep(1)
    raise TimeoutError("180 秒内未提供验证码答案")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    client = EPortalClient(timeout=15)

    if mode == "status":
        show(client.get_status())
        return

    if mode == "logout":
        client.logout()
        print("logout ok")
        show(client.get_status())
        return

    if mode == "offline":
        print("--- 1. get_status（期望离线） ---")
        show(client.get_status())

        print("--- 2. 无 solver 登录（期望 NeedCaptchaError） ---")
        patch_resume(client)
        try:
            client.login("probe_no_such_user_zz9", "WrongPassword123")
            print("!! 意外成功")
        except NeedCaptchaError as e:
            print("OK NeedCaptchaError:", e)

        print("--- 3. 垃圾 solver 登录（期望 CaptchaFailedError） ---")
        client2 = EPortalClient(timeout=15)
        patch_resume(client2)
        try:
            client2.login(
                "probe_no_such_user_zz9",
                "WrongPassword123",
                captcha_solver=lambda png: "zzzz",
                max_captcha_attempts=2,
            )
            print("!! 意外成功")
        except CaptchaFailedError as e:
            print("OK CaptchaFailedError:", e)
        return

    if mode == "login":
        username, password = sys.argv[2], sys.argv[3]
        service = sys.argv[4] if len(sys.argv) > 4 else "校园网"
        patch_resume(client)
        status = client.login(
            username, password, service=service, captcha_solver=manual_solver
        )
        print("login ok:")
        show(status)
        return

    print(f"unknown mode: {mode}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
