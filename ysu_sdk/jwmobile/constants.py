"""移动教务（jwmobile）常量。"""

from __future__ import annotations

JWXT_BASE_URL: str = "https://jwxt.ysu.edu.cn"
MOBILE_AUTH_URL: str = f"{JWXT_BASE_URL}/jwmobile/auth/index"
MOBILE_API_BASE: str = f"{JWXT_BASE_URL}/jwmobile/biz/v410"
MOBILE_COOKIE_PATH: str = "/jwmobile"

# 业务接口路径（相对 MOBILE_API_BASE，均为 JSON POST）
API_PATHS = {
    "current_lesson": "lesson/queryCurrentLesson",   # 当前课程及活动列表
    "signin_detail": "signin/detail",                # 签到活动详情
    "signin_status": "signin/querySigninDetail",     # 学生签到状态
    "signin_sign": "signin/sign",                    # 学生签到（写操作）
}
