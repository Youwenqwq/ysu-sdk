"""移动教务客户端：课程签到业务封装。

基于移动教务（``jwxt.ysu.edu.cn/jwmobile``）的独立 biz 接口封装。
与桌面端 EMAP（jwxt 子包）**完全解耦**：认证走 CAS SSO 落地 JSESSIONID
后，从跳转链中捕获 JWT 存为 ``Authorization`` cookie，此后所有业务
调用都是 JSON POST 到 ``/jwmobile/biz/v410``。

本包唯一的写操作是 :meth:`MobileClient.sign`（学生本人签到）。
"""

from __future__ import annotations

import functools
import json
import re
from typing import Any, Callable, TypeVar
from urllib.parse import unquote, urljoin

import requests
from requests.cookies import create_cookie

from ysu_sdk._datetime import to_iso_datetime
from ysu_sdk.cas.client import CASClient
from ysu_sdk.jwmobile.constants import (
    API_PATHS,
    JWXT_BASE_URL,
    MOBILE_API_BASE,
    MOBILE_AUTH_URL,
    MOBILE_COOKIE_PATH,
)
from ysu_sdk.jwmobile.exceptions import (
    MobileBusinessError,
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

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_SUCCESS_CODES = {"200", 200, "0", 0}


# ──────────────────────────────────────────────────────────────────────────── #
# 解析器：API 字段名 → 结构化 dataclass
# ──────────────────────────────────────────────────────────────────────────── #


def _to_int(val: Any) -> int:
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return 0


def _opt_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    return _to_int(val)


def _opt_str(val: Any) -> str | None:
    if val is None or val == "":
        return None
    return str(val)


def _parse_lesson_activity(raw: dict[str, Any]) -> LessonActivity:
    create_time = _opt_str(raw.get("createTime"))
    return LessonActivity(
        activity_id=str(raw.get("activityId") or ""),
        type=_opt_int(raw.get("type")),
        status=_opt_int(raw.get("status")),
        title=_opt_str(raw.get("title")),
        icon=_opt_str(raw.get("icon")),
        sign_type=str(raw.get("signType") or ""),
        sign_clazz=str(raw.get("signClazz") or ""),
        is_end=bool(raw.get("isEnd")),
        is_creator=bool(raw.get("isCreator")),
        create_time=to_iso_datetime(create_time) if create_time else None,
        raw=raw,
    )


def _parse_current_lesson(raw: dict[str, Any]) -> CurrentLesson:
    activities = raw.get("activityList")
    return CurrentLesson(
        lesson_id=_opt_str(raw.get("lessonId")),
        activities=(
            [_parse_lesson_activity(a) for a in activities if isinstance(a, dict)]
            if isinstance(activities, list)
            else []
        ),
        raw=raw,
    )


def _parse_signin_detail(raw: dict[str, Any]) -> SigninActivityDetail:
    return SigninActivityDetail(
        activity_id=str(raw.get("activityId") or ""),
        duration=_to_int(raw.get("duration")),
        start_time=to_iso_datetime(raw.get("startTime")),
        end_time=to_iso_datetime(raw.get("endTime")),
        left_seconds=_to_int(raw.get("leftSeconds")),
        signin_type=_to_int(raw.get("signinType")),
        raw=raw,
    )


def _parse_signin_status(raw: dict[str, Any]) -> SigninStatus:
    return SigninStatus(
        sign_status=_to_int(raw.get("signStatus")),
        attendance_status=_to_int(raw.get("attendanceStatus")),
        sign_order=_to_int(raw.get("signOrder")),
        signin_type=_to_int(raw.get("signinType")),
        raw=raw,
    )


_F = TypeVar("_F", bound=Callable[..., Any])


def _with_mobile_reauth(fn: _F) -> _F:
    """业务方法装饰器：信任现有 Authorization cookie，过期时重走一次 SSO。

    1. 进入前 ``_ensure_authorized()``：已有 Authorization cookie 则跳过；
       没有则走 CAS authorize + JWT 捕获（cold start 路径）。
    2. 业务方法抛 :class:`MobileNotLoggedInError`（HTTP 401/403 或 envelope
       ``code=401``）时，``_reauthorize()`` 清掉移动端 cookie 重新认证，
       整段重试一次。再失败直接抛出。
    """

    @functools.wraps(fn)
    def wrapper(self: "MobileClient", *args: Any, **kwargs: Any) -> Any:
        self._ensure_authorized()
        try:
            return fn(self, *args, **kwargs)
        except MobileNotLoggedInError:
            self._reauthorize()
            return fn(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class MobileClient:
    """燕山大学移动教务（课程签到）客户端。

    依赖 :class:`CASClient` 完成 CAS 认证；与 jwxt 子包互不依赖。
    所有业务方法均在 ``self.session`` 上发送请求。

    用法示例::

        cas = CASClient()
        cas.login("username", "password")

        mobile = MobileClient(cas)
        lesson = mobile.query_current_lesson(
            teach_class_id="202520262041S007601",
            teach_class_type="1",
            schedule_id="...",
            week=15,
            week_day=2,
            start_node=7,
            end_node=8,
        )
        for act in lesson.activities:
            detail = mobile.query_signin_detail(act.activity_id)
            status = mobile.sign(act.activity_id)
    """

    def __init__(
        self,
        cas_client: CASClient,
        *,
        session: requests.Session | None = None,
        mobile_session: MobileSession | None = None,
        timeout: float = 30,
    ) -> None:
        self.cas = cas_client
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        if mobile_session is not None:
            mobile_session.apply(self.session)

    # ──────────────────────────────────────────────────────────────────── #
    # 认证
    # ──────────────────────────────────────────────────────────────────── #

    def _has_auth_cookie(self) -> bool:
        for c in self.session.cookies:
            if (
                c.name == "Authorization"
                and c.value
                and c.domain
                and "jwxt.ysu.edu.cn" in c.domain
            ):
                return True
        return False

    def _capture_mobile_token(self) -> str:
        """从认证跳转链中捕获移动端 JWT（``token=`` 参数）。

        前置：CAS SSO 已完成（session 上已有 JSESSIONID）。此时再次请求
        认证入口会直接 302 到携带 ``token=`` 的地址，手动跟随提取即可。
        """
        url = MOBILE_AUTH_URL
        for _ in range(5):
            try:
                resp = self.session.get(
                    url, allow_redirects=False, timeout=self.timeout
                )
            except requests.RequestException as exc:
                raise MobileProtocolError(f"mobile token capture failed: {exc}") from exc

            location = resp.headers.get("Location", "")
            if location:
                # token 可能出现在 query 或 fragment（SPA 路由）中
                m = re.search(r"[?&]token=([^&#]+)", location)
                if m:
                    return unquote(m.group(1))
                if resp.status_code in _REDIRECT_STATUSES:
                    url = urljoin(url, location)
                    continue
            break
        raise MobileProtocolError("failed to obtain mobile JWT token from redirect chain")

    def _ensure_authorized(self) -> None:
        """确保 session 已持有移动端 ``Authorization`` cookie（JWT）。

        没有则走完整认证：CAS authorize 落地 JSESSIONID → 捕获 JWT →
        以 cookie 形式写回 session。
        """
        if self._has_auth_cookie():
            return

        self.cas.authorize(MOBILE_AUTH_URL, session=self.session)
        token = self._capture_mobile_token()
        self.session.cookies.set_cookie(
            create_cookie(
                name="Authorization",
                value=token,
                domain="jwxt.ysu.edu.cn",
                path=MOBILE_COOKIE_PATH,
                secure=True,
            )
        )

    def _reauthorize(self) -> None:
        """作废当前移动端会话，重新走 CAS + JWT 捕获。"""
        for domain in ("jwxt.ysu.edu.cn", ".jwxt.ysu.edu.cn"):
            try:
                self.session.cookies.clear(domain=domain)
            except KeyError:
                pass
        self._ensure_authorized()

    def session_snapshot(self) -> MobileSession:
        """从当前 session 提取一份新鲜的 :class:`MobileSession`。"""
        return MobileSession.from_session(self.session)

    # ──────────────────────────────────────────────────────────────────── #
    # 请求收口
    # ──────────────────────────────────────────────────────────────────── #

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """所有业务调用的收口：JSON POST + envelope 解析 + 异常分层。

        envelope 约定：``{"code": 200, "data": {...}}``；``code`` 为
        200/0 视为成功，401 视为会话过期，其余为业务拒绝。
        """
        url = f"{MOBILE_API_BASE}/{path}"
        try:
            resp = self.session.post(
                url,
                json=body,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MobileProtocolError(f"request failed for {url}: {exc}") from exc

        if resp.status_code in (401, 403):
            raise MobileNotLoggedInError(f"HTTP {resp.status_code} from {url}")
        if resp.status_code >= 400:
            raise MobileProtocolError(f"HTTP {resp.status_code} from {url}")

        try:
            result: dict[str, Any] = resp.json()
        except (ValueError, TypeError) as exc:
            raise MobileProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc

        code = result.get("code")
        if code in (401, "401"):
            raise MobileNotLoggedInError(
                str(result.get("msg") or f"mobile API authentication failed: {url}")
            )
        if code not in _SUCCESS_CODES:
            raise MobileBusinessError(
                code if isinstance(code, (str, int)) else None,
                result.get("msg") if isinstance(result.get("msg"), str) else None,
                url,
            )

        data = result.get("data")
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        return {"_value": data}

    # ──────────────────────────────────────────────────────────────────── #
    # 课程与活动
    # ──────────────────────────────────────────────────────────────────── #

    @_with_mobile_reauth
    def query_current_lesson(
        self,
        *,
        teach_class_id: str,
        teach_class_type: str,
        schedule_id: str,
        week: int,
        week_day: int,
        start_node: int,
        end_node: int,
    ) -> CurrentLesson:
        """查询当前课程及其活动列表（``lesson/queryCurrentLesson``）。

        Args:
            teach_class_id: 教学班标识（理论课取 ``JXBID``，实验课取 ``SYXZDM``）。
            teach_class_type: 教学班类型（``JXBLX``，通常 ``"1"``）。
            schedule_id: 课表 ID（``KBID``）。
            week: 教学周次。
            week_day: 星期几（1-7）。
            start_node: 起始节次。
            end_node: 结束节次。

        Returns:
            课程 ID 与活动列表（签到等活动）。
        """
        data = self._post(
            API_PATHS["current_lesson"],
            {
                "teachClassId": teach_class_id,
                "teachClassType": teach_class_type,
                "scheduleId": schedule_id,
                "week": week,
                "weekDay": week_day,
                "startNode": start_node,
                "endNode": end_node,
            },
        )
        return _parse_current_lesson(data)

    def query_current_lesson_for_course(
        self,
        course: CourseLike,
        week: int,
        *,
        week_day: int | None = None,
    ) -> CurrentLesson:
        """以课程对象查询当前课程活动（解析 ``teachClassId`` 的便捷方法）。

        封装移动端接口的标识解析规则：``class_type == "1"`` 时
        ``teachClassId`` 取教学班 ID，否则取实验性质代码。``course``
        只需满足 :class:`CourseLike`（jwxt 的 ``Course`` 天然满足）。

        Args:
            course: 课程对象（如 :meth:`JWXTClient.query_schedule` 的结果）。
            week: 教学周次。
            week_day: 星期几；为 ``None`` 则用 ``course.week_day``。
        """
        class_type = course.class_type or "1"
        teach_class_id = (
            course.class_id if class_type == "1" else course.experiment_type_code
        )
        if not teach_class_id or not course.schedule_id:
            raise ValueError(
                "课程对象缺少移动端所需标识（class_id/schedule_id），"
                "请使用 query_schedule_experimental 等含完整字段的课表来源"
            )
        return self.query_current_lesson(
            teach_class_id=teach_class_id,
            teach_class_type=class_type,
            schedule_id=course.schedule_id,
            week=week,
            week_day=week_day if week_day is not None else course.week_day,
            start_node=course.start_section,
            end_node=course.end_section,
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 用户信息
    # ──────────────────────────────────────────────────────────────────── #

    @_with_mobile_reauth
    def query_user_info(self) -> MobileUserInfo:
        """查询移动端用户信息（``GET biz/user/info``，含头像 URL）。

        该端点为 GET 且字段在顶层（无 ``data`` 包装），与 v410 业务
        接口形态不同，单独处理。
        """
        url = f"{JWXT_BASE_URL}/jwmobile/biz/user/info"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise MobileProtocolError(f"request failed for {url}: {exc}") from exc
        if resp.status_code in (401, 403):
            raise MobileNotLoggedInError(f"HTTP {resp.status_code} from {url}")
        if resp.status_code >= 400:
            raise MobileProtocolError(f"HTTP {resp.status_code} from {url}")
        try:
            result: dict[str, Any] = resp.json()
        except (ValueError, TypeError) as exc:
            raise MobileProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc
        code = result.get("code")
        if code in (401, "401"):
            raise MobileNotLoggedInError(f"user info authentication failed: {url}")
        if code not in _SUCCESS_CODES:
            raise MobileBusinessError(
                code if isinstance(code, (str, int)) else None,
                result.get("msg") if isinstance(result.get("msg"), str) else None,
                url,
            )
        return MobileUserInfo(
            name=str(result.get("xm") or ""),
            student_id=str(result.get("xh") or ""),
            class_name=str(result.get("className") or ""),
            major=str(result.get("zymc") or ""),
            department=str(result.get("yxmc") or ""),
            grade=str(result.get("xznj") or ""),
            avatar_url=str(result.get("avatar") or ""),
            raw=result,
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 签到
    # ──────────────────────────────────────────────────────────────────── #

    @_with_mobile_reauth
    def query_signin_detail(
        self,
        activity_id: str,
        *,
        title: str = "签到",
    ) -> SigninActivityDetail:
        """查询签到活动详情（``signin/detail``）：时长、起止时间、剩余秒数。"""
        data = self._post(
            API_PATHS["signin_detail"],
            {"activityId": activity_id, "title": title},
        )
        return _parse_signin_detail(data)

    @_with_mobile_reauth
    def query_signin_status(
        self,
        activity_id: str,
        *,
        title: str = "签到",
    ) -> SigninStatus:
        """查询当前学生的签到状态（``signin/querySigninDetail``）。"""
        data = self._post(
            API_PATHS["signin_status"],
            {"activityId": activity_id, "title": title},
        )
        return _parse_signin_status(data)

    @_with_mobile_reauth
    def sign(
        self,
        activity_id: str,
        *,
        accuracy: float = 0,
        latitude: float = 0,
        longitude: float = 0,
        code: str | None = None,
    ) -> SigninStatus:
        """学生签到（``signin/sign``，**写操作**）。

        Args:
            activity_id: 签到活动 ID。
            accuracy: 定位精度（米）。
            latitude: 纬度。
            longitude: 经度。
            code: 签到码（数字签/手势签时必填）。

        Returns:
            签到后的状态（与 :meth:`query_signin_status` 同构）。
        """
        body: dict[str, Any] = {
            "activityId": activity_id,
            "accuracy": accuracy,
            "latitude": latitude,
            "longitude": longitude,
        }
        if code is not None:
            body["code"] = code
        data = self._post(API_PATHS["signin_sign"], body)
        return _parse_signin_status(data)
