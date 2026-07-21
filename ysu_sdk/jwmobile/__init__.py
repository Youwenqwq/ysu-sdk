"""移动教务（课程签到）子包公开 API。"""

from ysu_sdk.jwmobile.client import MobileClient
from ysu_sdk.jwmobile.exceptions import (
    MobileBusinessError,
    MobileError,
    MobileNotLoggedInError,
    MobileProtocolError,
)
from ysu_sdk.jwmobile.session import MobileSession
from ysu_sdk.jwmobile.types import (
    CourseLike,
    CurrentLesson,
    LessonActivity,
    MobileUserInfo,
    SigninActivityDetail,
    SigninStatus,
)

__all__ = [
    "MobileClient",
    "MobileSession",
    "MobileError",
    "MobileNotLoggedInError",
    "MobileProtocolError",
    "MobileBusinessError",
    "CourseLike",
    "CurrentLesson",
    "LessonActivity",
    "MobileUserInfo",
    "SigninActivityDetail",
    "SigninStatus",
]
