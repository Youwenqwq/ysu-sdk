"""劳动教育实践课程管理平台的只读查询客户端。"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar
from urllib.parse import urlsplit

import requests

from ysu_sdk._datetime import to_iso_datetime
from ysu_sdk._table import TableData, parse_tables
from ysu_sdk.ldxt.constants import (
    BASE_URL,
    DEFAULT_PAGE_SIZE,
    ENROLL_PATH,
    HOME_PATH,
    LOGIN_PATH,
    SSO_PATH,
    SUMMARY_PATH,
    SUMMARY_QUERY_PATH,
)
from ysu_sdk.ldxt.exceptions import LdxtNotLoggedInError, LdxtProtocolError
from ysu_sdk.ldxt.types import EnrollableActivity, LaborRecord, LaborSummary

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

P = ParamSpec("P")
R = TypeVar("R")


def _to_float(val: str) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _split_time_range(text: str) -> tuple[str, str]:
    """把 ``2024-09-28 08:00 至 2024-09-28 12:00`` 拆成起止并归一。"""
    parts = [p.strip() for p in text.split("至", 1)]
    start = to_iso_datetime(parts[0]) if parts else ""
    end = to_iso_datetime(parts[1]) if len(parts) > 1 else ""
    return start, end


def _col_map(headers: list[str]) -> dict[str, int]:
    return {h: i for i, h in enumerate(headers) if h}


def _cell(row: list[str], cols: dict[str, int], name: str) -> str:
    idx = cols.get(name)
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


class LdxtClient:
    """劳动教育实践课程管理平台（ldxt.ysu.edu.cn）的只读查询客户端。

    南京先极科技的 ASP.NET MVC 系统：CAS 单点登录 + 服务端渲染 HTML
    表格。与 EMAP 系子包（jwxt/xgxt）无共享代码。

    Example:
        ```python
        from ysu_sdk.cas import CASClient, CASCredential
        from ysu_sdk.ldxt import LdxtClient

        cas = CASClient(credential=CASCredential.load())
        ldxt = LdxtClient(cas)

        for record in ldxt.query_labor_records():
            print(record.term, record.name, record.hours, record.status)
        print(ldxt.query_labor_summary().total_hours)
        ```
    """

    def __init__(
        self,
        cas_client: CASClient,
        timeout: float | tuple[float, float] | None = None,
    ) -> None:
        self._cas = cas_client
        self.timeout = timeout if timeout is not None else cas_client.timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            }
        )
        self._authorized = False

    # ──────────────────────────────────────────────────────────────────── #
    # 认证与底层请求
    # ──────────────────────────────────────────────────────────────────── #

    def _ensure_authorized(self) -> None:
        """懒认证：首次业务请求时完成 SSO 握手建立 ASP.NET 会话。

        三步握手（浏览器实测）：

        1. ``cas.authorize(UnifiedAuthenticationLogin)`` —— 出票、服务端
           验票并种 ``.DotNetCasClientAuth`` cookie；
        2. ``POST UnifiedAuthenticationLogin`` —— 服务端确认登录，返回
           JSON ``{Success:true, Data:{Url:"/System/User/LoginRole"}}``；
        3. GET 返回的角色落地 URL —— 写入角色上下文，会话就绪。
        """
        if self._authorized:
            return
        self.session = self._cas.authorize(
            f"{BASE_URL}{SSO_PATH}", session=self.session
        )
        url = f"{BASE_URL}{SSO_PATH}"
        try:
            resp = self.session.post(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LdxtProtocolError(f"request failed for {url}: {exc}") from exc
        try:
            result: dict[str, Any] = resp.json()
        except (ValueError, TypeError) as exc:
            raise LdxtProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc
        if not result.get("Success"):
            raise LdxtNotLoggedInError(
                f"SSO finalize rejected: {result.get('Message')!r}"
            )
        data = result.get("Data")
        next_path = data.get("Url") if isinstance(data, dict) else None
        # 落地页本身可能是角色选择页（LoginRole），只要未被踢回登录页即就绪
        self._get_page(next_path or HOME_PATH)
        self._authorized = True

    def _get_page(self, path: str, params: dict[str, Any] | None = None) -> str:
        """GET 一个服务端渲染页面；被踢回登录页时抛 :class:`LdxtNotLoggedInError`。"""
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LdxtProtocolError(f"request failed for {url}: {exc}") from exc
        if urlsplit(resp.url).path.rstrip("/") == LOGIN_PATH:
            raise LdxtNotLoggedInError(f"redirected to login page: {url}")
        if resp.status_code >= 400:
            raise LdxtProtocolError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    def _get_table(self, path: str, params: dict[str, Any] | None = None) -> TableData:
        """GET 页面并抽取第一张顶层表格。"""
        html = self._get_page(path, params)
        tables = parse_tables(html)
        if not tables:
            raise LdxtProtocolError(f"no data table found in page: {path}")
        return tables[0]

    @staticmethod
    def _with_reauth(func: Callable[P, R]) -> Callable[P, R]:
        """会话过期时重新认证一次并重试（与 jwmobile 同一模式）。"""

        @wraps(func)
        def wrapper(self: LdxtClient, *args: P.args, **kwargs: P.kwargs) -> R:
            self._ensure_authorized()
            try:
                return func(self, *args, **kwargs)
            except LdxtNotLoggedInError:
                self._authorized = False
                self._ensure_authorized()
                return func(self, *args, **kwargs)

        return wrapper

    # ──────────────────────────────────────────────────────────────────── #
    # 劳动记录
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_labor_records(
        self,
        term_code: str = "",
        batch_id: str = "",
        category_code1: str = "",
        category_code2: str = "",
        grade: str = "",
        org_teacher: str = "",
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[LaborRecord]:
        """查询本人劳动记录（时长汇总页的「劳动列表」）。

        过滤参数为厂商内部代码，原样透传；默认全部为空即查询全部记录，
        每页取最大档（200 条）避免翻页。
        """
        table = self._get_table(
            SUMMARY_PATH,
            params={
                "AscSortKey": "",
                "DescSortKey": "",
                "TermCode": term_code,
                "BatchID": batch_id,
                "CategoryCode1": category_code1,
                "CategoryCode2": category_code2,
                "Grade": grade,
                "OrgTeacher": org_teacher,
                "PageSize": page_size,
            },
        )
        cols = _col_map(table.headers)
        name_idx = cols.get("活动名称")
        records: list[LaborRecord] = []
        for row, badges in zip(table.rows, table.badges):
            start, end = _split_time_range(_cell(row, cols, "活动时间"))
            enroll_type = ""
            if name_idx is not None and name_idx < len(badges):
                enroll_type = "".join(badges[name_idx])
            records.append(
                LaborRecord(
                    term=_cell(row, cols, "学期"),
                    name=_cell(row, cols, "活动名称"),
                    enroll_type=enroll_type,
                    category=_cell(row, cols, "活动大类"),
                    department=_cell(row, cols, "所属学院"),
                    time_start=start,
                    time_end=end,
                    teacher=_cell(row, cols, "组织老师"),
                    hours=_to_float(_cell(row, cols, "劳动时长")),
                    student=_cell(row, cols, "学生"),
                    status=_cell(row, cols, "状态"),
                    raw=dict(zip(table.headers, row)),
                )
            )
        return records

    # ──────────────────────────────────────────────────────────────────── #
    # 学生学分汇总
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_labor_summary(self) -> LaborSummary:
        """查询本人劳动学分汇总（累计时长/总学分）。"""
        table = self._get_table(SUMMARY_QUERY_PATH)
        cols = _col_map(table.headers)
        if not table.rows:
            raise LdxtProtocolError("no summary row found in page")
        row = table.rows[0]
        return LaborSummary(
            student_id=_cell(row, cols, "学生学号"),
            name=_cell(row, cols, "学生姓名"),
            department=_cell(row, cols, "学院"),
            major=_cell(row, cols, "专业"),
            class_name=_cell(row, cols, "班级"),
            grade=_cell(row, cols, "年级"),
            schooling=_cell(row, cols, "学制"),
            total_hours=_to_float(_cell(row, cols, "劳动时长")),
            total_credits=_to_float(_cell(row, cols, "总学分")),
            raw=dict(zip(table.headers, row)),
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 活动报名列表
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_enrollable_activities(self) -> list[EnrollableActivity]:
        """查询活动报名列表（当前可见的可报名/历史活动）。

        报名、上传佐证材料是写操作，SDK 不封装。
        """
        table = self._get_table(ENROLL_PATH)
        cols = _col_map(table.headers)
        activities: list[EnrollableActivity] = []
        for row in table.rows:
            start, end = _split_time_range(_cell(row, cols, "活动时间"))
            enroll_start, enroll_end = _split_time_range(_cell(row, cols, "报名时间"))
            activities.append(
                EnrollableActivity(
                    name=_cell(row, cols, "活动名称"),
                    category=_cell(row, cols, "活动大类"),
                    time_start=start,
                    time_end=end,
                    location=_cell(row, cols, "活动地点"),
                    hours=_to_float(_cell(row, cols, "劳动时长")),
                    description=_cell(row, cols, "活动说明"),
                    department=_cell(row, cols, "所属学院"),
                    enroll_start=enroll_start,
                    enroll_end=enroll_end,
                    is_enrolled=_cell(row, cols, "是否报名") == "是",
                    operation=_cell(row, cols, "操作"),
                    raw=dict(zip(table.headers, row)),
                )
            )
        return activities
