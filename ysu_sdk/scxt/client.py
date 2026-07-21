"""创新创业学分认定系统的只读查询客户端。"""

from __future__ import annotations

import re
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar
from urllib.parse import urlsplit

import requests

from ysu_sdk._table import TableData, parse_tables
from ysu_sdk.scxt.constants import (
    ACTIVITY_PATH,
    BASE_URL,
    COMPETITION_PATH,
    DECLARE_PATH,
    DEFAULT_PAGE_SIZE,
    HOME_PATH,
    LOGIN_PATH,
    PT_BASE_URL,
    PT_CAS_LOGIN_PATH,
    PT_HOME_URL,
    SUBSYSTEM_BRIDGE_PATH,
    SUMMARY_PATH,
    SUMMARY_QUERY_PATH,
)
from ysu_sdk.scxt.exceptions import ScxtNotLoggedInError, ScxtProtocolError
from ysu_sdk.scxt.types import (
    CatalogPage,
    Competition,
    CreditBatch,
    CreditDeclaration,
    CreditRecord,
    CreditSummary,
    LibraryActivity,
)

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

P = ParamSpec("P")
R = TypeVar("R")

_PAGER_RE = re.compile(r"共(\d+)页(\d+)条记录，当前显示：第\s*(\d+)\s*页")
_BATCH_SELECT_RE = re.compile(
    r'<select[^>]*name="BatchID"[^>]*>(.*?)</select>', re.S | re.I
)
_OPTION_RE = re.compile(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', re.S | re.I)


def _to_float(val: str) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _col_map(headers: list[str]) -> dict[str, int]:
    return {h: i for i, h in enumerate(headers) if h}


def _cell(row: list[str], cols: dict[str, int], name: str) -> str:
    idx = cols.get(name)
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def _parse_pager(html: str) -> tuple[int, int, int]:
    """解析 ``共73页1448条记录，当前显示：第 1 页`` → (页数, 条数, 当前页)。"""
    m = _PAGER_RE.search(html)
    if not m:
        return 1, 0, 1
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class ScxtClient:
    """创新创业学分认定系统（202.206.247.49/ysu_xf）的只读查询客户端。

    与 ldxt 同为先极科技 ASP.NET MVC 系统，但认证必须经 ysu_pt 平台
    中转（本系统未直接注册为 CAS service）。表格解析共享
    :mod:`ysu_sdk._table`。

    Example:
        ```python
        from ysu_sdk.cas import CASClient, CASCredential
        from ysu_sdk.scxt import ScxtClient

        scxt = ScxtClient(CASClient(credential=CASCredential.load()))

        for d in scxt.query_credit_declarations():
            print(d.item_name, d.score, d.status)
        print(scxt.query_credit_summary().total_credits)
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
        """懒认证：平台出票 → 子系统桥 → 票据落地，三步建立 ysu_xf 会话。

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
            raise ScxtProtocolError(f"request failed for {bridge_url}: {exc}") from exc
        ticket_url = resp.headers.get("Location", "")
        if resp.status_code not in (301, 302) or "authserver/access" not in ticket_url:
            raise ScxtProtocolError(
                f"subsystem bridge did not issue access ticket: "
                f"{resp.status_code} -> {ticket_url!r}"
            )
        try:
            resp = self.session.get(
                ticket_url, allow_redirects=False, headers=referer,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ScxtProtocolError(f"access ticket consumption failed: {exc}") from exc
        if resp.status_code not in (301, 302):
            raise ScxtNotLoggedInError(
                f"access ticket rejected: {resp.status_code} {resp.text[:120]!r}"
            )
        # 完整跟随票据落地链（LoginRole），再访问主页——服务端会话状态经
        # 主页初始化后，列表页才会渲染完整列（否则缺「成绩」等列）
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
            raise ScxtProtocolError(f"request failed for {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise ScxtProtocolError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    def _get_page(self, path: str, params: dict[str, Any] | None = None) -> str:
        """GET 一个服务端渲染页面；被踢回登录页时抛 :class:`ScxtNotLoggedInError`。"""
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ScxtProtocolError(f"request failed for {url}: {exc}") from exc
        if urlsplit(resp.url).path.rstrip("/") == LOGIN_PATH:
            raise ScxtNotLoggedInError(f"redirected to login page: {url}")
        if resp.status_code >= 400:
            raise ScxtProtocolError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    def _get_table(self, path: str, params: dict[str, Any] | None = None) -> tuple[TableData, str]:
        """GET 页面并返回（第一张顶层表格, 原始 HTML）。"""
        html = self._get_page(path, params)
        tables = parse_tables(html)
        if not tables:
            raise ScxtProtocolError(f"no data table found in page: {path}")
        return tables[0], html

    @staticmethod
    def _with_reauth(func: Callable[P, R]) -> Callable[P, R]:
        """会话过期时重新认证一次并重试。"""

        @wraps(func)
        def wrapper(self: ScxtClient, *args: P.args, **kwargs: P.kwargs) -> R:
            self._ensure_authorized()
            try:
                return func(self, *args, **kwargs)
            except ScxtNotLoggedInError:
                self._authorized = False
                self._ensure_authorized()
                return func(self, *args, **kwargs)

        return wrapper

    # ──────────────────────────────────────────────────────────────────── #
    # 批次
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_credit_batches(self) -> list[CreditBatch]:
        """查询学分认定批次列表（申报页 ``BatchID`` 下拉框）。

        学分汇总页服务端**默认只给当前批次**，要查全部记录需按批次遍历。
        """
        html = self._get_page(DECLARE_PATH)
        m = _BATCH_SELECT_RE.search(html)
        if not m:
            raise ScxtProtocolError("BatchID select not found on declare page")
        batches: list[CreditBatch] = []
        for value, text in _OPTION_RE.findall(m.group(1)):
            name = re.sub(r"\s+", " ", text).strip()
            if value and name and "请选择" not in name:
                batches.append(
                    CreditBatch(batch_id=value, name=name,
                                raw={"value": value, "text": name})
                )
        return batches

    # ──────────────────────────────────────────────────────────────────── #
    # 申报记录
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_credit_declarations(
        self, batch_id: str = "", item_name: str = ""
    ) -> list[CreditDeclaration]:
        """查询我的学分申报记录（默认服务端当前批次口径）。"""
        table, _ = self._get_table(
            DECLARE_PATH, params={"BatchID": batch_id, "ItemName": item_name}
        )
        cols = _col_map(table.headers)
        declarations: list[CreditDeclaration] = []
        for row in table.rows:
            declarations.append(
                CreditDeclaration(
                    item_name=_cell(row, cols, "项目名称"),
                    category_major=_cell(row, cols, "认定大类"),
                    category_minor=_cell(row, cols, "认定小类"),
                    award_level=_cell(row, cols, "获奖等级或排名"),
                    score=_to_float(_cell(row, cols, "分值")),
                    applicant=_cell(row, cols, "学分申请人"),
                    batch=_cell(row, cols, "所属批次"),
                    status=_cell(row, cols, "状态"),
                    operation=_cell(row, cols, "操作"),
                    raw=dict(zip(table.headers, row)),
                )
            )
        return declarations

    # ──────────────────────────────────────────────────────────────────── #
    # 学分汇总（认定记录）
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_credit_records(
        self,
        batch_id: str = "",
        item_name: str = "",
        year: str = "",
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[CreditRecord]:
        """查询学分汇总（认定记录）。

        注意：``batch_id=""`` 时服务端只返回**当前批次**的记录，
        查全部批次请用 :meth:`query_all_credit_records`。
        """
        table, _ = self._get_table(
            SUMMARY_PATH,
            params={
                "AscSortKey": "",
                "DescSortKey": "",
                "BatchID": batch_id,
                "ManagerID": "",
                "CategoryCode1": "",
                "CategoryCode2": "",
                "CategoryCode3": "",
                "ItemName": item_name,
                "Grade": "",
                "GetCGYear": year,
                "IsGuiDang": "",
                "PageSize": page_size,
            },
        )
        cols = _col_map(table.headers)
        records: list[CreditRecord] = []
        for row in table.rows:
            records.append(
                CreditRecord(
                    item_name=_cell(row, cols, "项目名称"),
                    year=_cell(row, cols, "取得成果年份"),
                    category_major=_cell(row, cols, "认定大类"),
                    category_minor=_cell(row, cols, "认定小类"),
                    award_level=_cell(row, cols, "获奖等级或排名"),
                    reference_score=_to_float(_cell(row, cols, "参照分值")),
                    actual_score=_to_float(_cell(row, cols, "实际分值")),
                    grade=_cell(row, cols, "成绩"),
                    applicant=_cell(row, cols, "学分申请人"),
                    class_name=_cell(row, cols, "所属班级"),
                    department=_cell(row, cols, "所属学院"),
                    batch=_cell(row, cols, "所属批次"),
                    status=_cell(row, cols, "状态"),
                    raw=dict(zip(table.headers, row)),
                )
            )
        return records

    def query_all_credit_records(self) -> list[CreditRecord]:
        """遍历全部批次查询认定记录（每批次一次请求，顺序发出）。"""
        records: list[CreditRecord] = []
        for batch in self.query_credit_batches():
            records.extend(self.query_credit_records(batch_id=batch.batch_id))
        return records

    # ──────────────────────────────────────────────────────────────────── #
    # 学生学分汇总
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_credit_summary(self) -> CreditSummary:
        """查询本人学分总表（总学分/成绩）。"""
        table, _ = self._get_table(SUMMARY_QUERY_PATH)
        cols = _col_map(table.headers)
        if not table.rows:
            raise ScxtProtocolError("no summary row found in page")
        row = table.rows[0]
        return CreditSummary(
            student_id=_cell(row, cols, "账号"),
            name=_cell(row, cols, "用户名"),
            department=_cell(row, cols, "学院"),
            major=_cell(row, cols, "专业"),
            class_name=_cell(row, cols, "班级"),
            grade_year=_cell(row, cols, "年级"),
            grade=_cell(row, cols, "成绩"),
            total_credits=_to_float(_cell(row, cols, "总学分")),
            raw=dict(zip(table.headers, row)),
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 竞赛库 / 活动库
    # ──────────────────────────────────────────────────────────────────── #

    @_with_reauth
    def query_competitions(
        self,
        item_code: str = "",
        item_name: str = "",
        is_enable: str = "",
        page_index: int = 1,
    ) -> CatalogPage[Competition]:
        """查询竞赛库（分页，每页固定 20 条，共千余条）。

        ``is_enable`` 为厂商代码（``是``/``否`` 对应值原样透传），
        分页信息在返回的 :class:`CatalogPage` 上。
        """
        table, html = self._get_table(
            COMPETITION_PATH,
            params={
                "ItemCode": item_code,
                "ItemName": item_name,
                "IsEnable": is_enable,
                "pageIndex": page_index,
            },
        )
        total_pages, total_records, current = _parse_pager(html)
        cols = _col_map(table.headers)
        items = [
            Competition(
                code=_cell(row, cols, "竞赛编码"),
                name=_cell(row, cols, "竞赛名称"),
                category_major=_cell(row, cols, "认定大类"),
                category_minor=_cell(row, cols, "认定小类"),
                is_enabled=_cell(row, cols, "是否启用") == "是",
                status=_cell(row, cols, "状态"),
                raw=dict(zip(table.headers, row)),
            )
            for row in table.rows
        ]
        return CatalogPage(
            items=items,
            page_index=current,
            total_pages=total_pages,
            total_records=total_records,
        )

    @_with_reauth
    def query_activities(
        self, name: str = "", page_index: int = 1
    ) -> CatalogPage[LibraryActivity]:
        """查询活动库（分页，每页固定 20 条）。"""
        table, html = self._get_table(
            ACTIVITY_PATH,
            params={"HuoDongName": name, "pageIndex": page_index},
        )
        total_pages, total_records, current = _parse_pager(html)
        cols = _col_map(table.headers)
        items = [
            LibraryActivity(
                name=_cell(row, cols, "活动名称"),
                organizer=_cell(row, cols, "举办单位"),
                category=_cell(row, cols, "活动类别"),
                detail=_cell(row, cols, "详情"),
                raw=dict(zip(table.headers, row)),
            )
            for row in table.rows
        ]
        return CatalogPage(
            items=items,
            page_index=current,
            total_pages=total_pages,
            total_records=total_records,
        )
