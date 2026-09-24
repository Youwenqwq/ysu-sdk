"""创新创业竞赛管理系统的学生/教师查询客户端。"""

from __future__ import annotations

import html as _html
import re
from functools import wraps
from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar
from urllib.parse import urlsplit

import requests

from ysu_sdk.xkjs.constants import (
    BASE_URL,
    HOME_PATH,
    LOGIN_PATH,
    PT_BASE_URL,
    PT_CAS_LOGIN_PATH,
    PT_HOME_URL,
    SEARCH_STUDENT_PATH,
    SEARCH_TEACHER_PATH,
    SUBSYSTEM_BRIDGE_PATH,
)
from ysu_sdk.xkjs.exceptions import XkjsNotLoggedInError, XkjsProtocolError
from ysu_sdk.xkjs.types import Page, Student, Teacher

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

P = ParamSpec("P")
R = TypeVar("R")

_PAGER_RE = re.compile(r"共(\d+)页(\d+)条记录，当前显示：第\s*(\d+)\s*页")
_ROW_RE = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.S | re.I)
_ROW_ID_RE = re.compile(r'id="choose-teacher-([0-9a-fA-F-]{36})"')
_ROW_USER_RE = re.compile(r'data-value="([^"]*)"')
_CELL_RE = re.compile(r'data-name="([^"]+)"[^>]*data-value="([^"]*)"', re.S)
_MODE_RE = re.compile(r'data-command="choose"[^>]*data-mode="([^"]+)"')


def _parse_pager(html: str) -> tuple[int, int, int]:
    """解析 ``共1页1条记录，当前显示：第 1 页`` → (页数, 条数, 当前页)。

    无结果时服务端不渲染分页条，返回 ``(0, 0, 1)``。
    """
    m = _PAGER_RE.search(html)
    if not m:
        return 0, 0, 1
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _parse_rows(html: str) -> list[tuple[dict[str, str], str, bool]]:
    """从搜索结果 HTML 片段抽取数据行 → (单元格键值对, 行 id, 是否已选中)。

    每行 ``<tr>`` 的 ``data-value`` 是内部 UserID，各 ``<td>`` 带
    ``data-name``/``data-value`` 键值对；空结果行（``c-data-empty``）
    没有任何 ``data-name``，自然被跳过。学生表与教师表结构同构，
    仅列集合不同。
    """
    rows: list[tuple[dict[str, str], str, bool]] = []
    for attrs, body in _ROW_RE.findall(html):
        cells = {
            name: _html.unescape(value) for name, value in _CELL_RE.findall(body)
        }
        if not cells:
            continue
        id_m = _ROW_ID_RE.search(attrs)
        user_m = _ROW_USER_RE.search(attrs)
        if "UserID" not in cells and user_m:
            cells["UserID"] = _html.unescape(user_m.group(1))
        mode_m = _MODE_RE.search(body)
        selected = bool(mode_m and mode_m.group(1) == "remove")
        rows.append((cells, id_m.group(1) if id_m else "", selected))
    return rows


def _parse_students(html: str) -> list[Student]:
    return [
        Student(
            user_id=cells.get("UserID", ""),
            name=cells.get("UserName", ""),
            account=cells.get("UserAccount", ""),
            college=cells.get("XueYuanName", ""),
            major=cells.get("ZhuanYeName", ""),
            selected=selected,
            raw={"row_id": row_id, "cells": cells},
        )
        for cells, row_id, selected in _parse_rows(html)
    ]


def _parse_teachers(html: str) -> list[Teacher]:
    return [
        Teacher(
            user_id=cells.get("UserID", ""),
            name=cells.get("UserName", ""),
            account=cells.get("UserAccount", ""),
            college=cells.get("XueYuanName", ""),
            selected=selected,
            raw={"row_id": row_id, "cells": cells},
        )
        for cells, row_id, selected in _parse_rows(html)
    ]


class XkjsClient:
    """创新创业竞赛管理系统（202.206.247.49/ysu_xkjs）的查询客户端。

    与 scxt 同为先极科技 ASP.NET MVC 系统，认证路径完全一致：必须经
    ysu_pt 平台中转（本系统未直接注册为 CAS service），仅桥接 guid
    不同。数据面是 POST AJAX + HTML 片段（不是整页 GET）。

    Example:
        ```python
        from ysu_sdk.cas import CASClient, CASCredential
        from ysu_sdk.xkjs import XkjsClient

        xkjs = XkjsClient(CASClient(credential=CASCredential.load()))

        page = xkjs.search_students(name="张三")
        for s in page.items:
            print(s.name, s.account, s.college, s.major)

        for t in xkjs.search_teachers(name="李四").items:
            print(t.name, t.account, t.college)
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
        """懒认证：平台出票 → 子系统桥 → 票据落地，三步建立 ysu_xkjs 会话。

        桥接与票据请求都必须带平台主页 Referer，否则平台拒绝出票、
        子系统报「访问参数获取失败」。
        """
        if self._authorized:
            return
        self.session = self._cas.authorize(
            f"{PT_BASE_URL}{PT_CAS_LOGIN_PATH}", session=self.session
        )
        referer = {"Referer": PT_HOME_URL}
        bridge_url = f"{PT_BASE_URL}{SUBSYSTEM_BRIDGE_PATH}"
        try:
            resp = self.session.get(
                bridge_url, allow_redirects=False, headers=referer,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise XkjsProtocolError(f"request failed for {bridge_url}: {exc}") from exc
        ticket_url = resp.headers.get("Location", "")
        if resp.status_code not in (301, 302) or "authserver/access" not in ticket_url:
            raise XkjsProtocolError(
                f"subsystem bridge did not issue access ticket: "
                f"{resp.status_code} -> {ticket_url!r}"
            )
        try:
            resp = self.session.get(
                ticket_url, allow_redirects=False, headers=referer,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise XkjsProtocolError(f"access ticket consumption failed: {exc}") from exc
        if resp.status_code not in (301, 302):
            raise XkjsNotLoggedInError(
                f"access ticket rejected: {resp.status_code} {resp.text[:120]!r}"
            )
        # 完整跟随票据落地链（LoginRole），再访问主页初始化服务端会话状态
        landing = resp.headers.get("Location", "")
        if landing:
            self._get_page_abs(requests.compat.urljoin(ticket_url, landing))
        self._get_page_abs(f"{BASE_URL}{HOME_PATH}")
        self._authorized = True

    def _get_page_abs(self, url: str) -> str:
        """GET 绝对 URL（认证流程内部用，不做登录页检测）。"""
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise XkjsProtocolError(f"request failed for {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise XkjsProtocolError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    def _post_fragment(self, path: str, data: dict[str, str]) -> str:
        """POST 一个 AJAX 片段端点；被踢回登录页时抛
        :class:`XkjsNotLoggedInError`。"""
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.post(
                url,
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise XkjsProtocolError(f"request failed for {url}: {exc}") from exc
        if urlsplit(resp.url).path.rstrip("/").endswith(LOGIN_PATH):
            raise XkjsNotLoggedInError(f"redirected to login page: {url}")
        if resp.status_code >= 400:
            raise XkjsProtocolError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    @staticmethod
    def _with_reauth(func: Callable[P, R]) -> Callable[P, R]:
        """会话过期时重新认证一次并重试。"""

        @wraps(func)
        def wrapper(self: XkjsClient, *args: P.args, **kwargs: P.kwargs) -> R:
            self._ensure_authorized()
            try:
                return func(self, *args, **kwargs)
            except XkjsNotLoggedInError:
                self._authorized = False
                self._ensure_authorized()
                return func(self, *args, **kwargs)

        return wrapper

    # ──────────────────────────────────────────────────────────────────── #
    # 学生查询
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def search_students(
        self,
        name: str = "",
        account: str = "",
        college_code: str = "",
        major_code: str = "",
        grade: str = "",
        page_index: int = 1,
    ) -> Page[Student]:
        """按条件搜索学生（竞赛报名「添加学生」的数据源）。

        各条件为空表示不限制。``college_code``/``major_code`` 是服务端
        编码（页面下拉框的 value），不是名称。
        """
        html = self._post_fragment(
            SEARCH_STUDENT_PATH,
            data={
                "PageIndex": str(page_index),
                "XueYuanCode": college_code,
                "ZhuanYeCode": major_code,
                "UserName": name,
                "UserAccount": account,
                "Grade": grade,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        page_count, total, current = _parse_pager(html)
        return Page(
            items=_parse_students(html),
            page_count=page_count,
            total_records=total,
            page_index=current,
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 教师查询
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def search_teachers(
        self,
        name: str = "",
        account: str = "",
        college_code: str = "",
        page_index: int = 1,
    ) -> Page[Teacher]:
        """按条件搜索教师（竞赛报名「添加指导教师」的数据源）。

        各条件为空表示不限制。``college_code`` 是服务端编码（页面下拉框
        的 value），不是名称。教师搜索无专业/年级条件。
        """
        html = self._post_fragment(
            SEARCH_TEACHER_PATH,
            data={
                "PageIndex": str(page_index),
                "XueYuanCode": college_code,
                "UserName": name,
                "UserAccount": account,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        page_count, total, current = _parse_pager(html)
        return Page(
            items=_parse_teachers(html),
            page_count=page_count,
            total_records=total,
            page_index=current,
        )
