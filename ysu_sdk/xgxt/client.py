"""学工系统客户端：综合测评信息查询业务封装。

基于学工系统（``xgxt.ysu.edu.cn``，EMAP 平台）「综合测评」应用的 API 封装，
当前覆盖「综测成绩」页签下的全部只读查询：测评学年学期、综测成绩与排名、
指标得分明细、雷达对比、学年分数总览、学业成绩报告。
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable, TypeVar

import requests

from ysu_sdk.cas.client import CASClient
from ysu_sdk.xgxt.constants import (
    API_PATHS,
    APP_CONFIG_URL,
    APP_NAME,
    CHANGE_ROLE_URL_TEMPLATE,
    EMAP_APP_ID,
    SET_ROLE_URL,
    XGXT_APP_BASE,
    ZHCP_SERVICE_URL,
)
from ysu_sdk.xgxt.exceptions import (
    NotLoggedInError,
    XGXTBusinessError,
    XGXTProtocolError,
)
from ysu_sdk.xgxt.session import XGXTSession
from ysu_sdk.xgxt.types import (
    AcademicReportEntry,
    AcademicReportPage,
    AcademicReportYear,
    AcademicReportYears,
    EvaluationIndicator,
    EvaluationIndicatorDetail,
    EvaluationRadarItem,
    EvaluationResult,
    EvaluationTerm,
    YearScoreStatic,
)


def _build_api_url(path: str) -> str:
    """拼接完整 API URL。"""
    return f"{XGXT_APP_BASE}/{path}"


def _to_str(val: Any) -> str:
    """把接口返回的标量统一成字符串；``None`` 归一为空串。"""
    if val is None:
        return ""
    return str(val)


def _to_int(val: Any) -> int:
    """把接口返回的数字（可能是 ``int``、数字字符串或空串）统一成 int。"""
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return 0


# ──────────────────────────────────────────────────────────────────────────── #
# 解析器：API 字段名 → 结构化 dataclass
# ──────────────────────────────────────────────────────────────────────────── #


def _parse_term(r: dict[str, Any]) -> EvaluationTerm:
    return EvaluationTerm(
        year=_to_str(r.get("CPXN")),
        term=_to_str(r.get("CPXQ")),
        year_display=_to_str(r.get("CPXN_DISPLAY")),
        term_display=_to_str(r.get("CPXQ_DISPLAY")),
        wid=_to_str(r.get("WID")),
        raw=r,
    )


def _parse_indicator(r: dict[str, Any]) -> EvaluationIndicator:
    return EvaluationIndicator(
        name=_to_str(r.get("ZBMC")),
        score=_to_str(r.get("FS")),
        rank=_to_int(r.get("RK")),
        max_score=_to_str(r.get("ZDZ")),
        category=_to_str(r.get("ZBLB")),
        description=_to_str(r.get("ZBSM")),
        raw=r,
    )


def _parse_result(data: dict[str, Any]) -> EvaluationResult:
    zb_list = data.get("ZBLIST")
    indicators = (
        [_parse_indicator(z) for z in zb_list if isinstance(z, dict)]
        if isinstance(zb_list, list)
        else []
    )
    return EvaluationResult(
        total_score=_to_str(data.get("ZCJ")),
        class_rank=_to_int(data.get("BJPM")),
        class_size=_to_int(data.get("BJRS")),
        grade_rank=_to_int(data.get("ZYNJPM")),
        grade_size=_to_int(data.get("ZYNJRS")),
        year=_to_str(data.get("CPXN")),
        term=_to_str(data.get("CPXQ")),
        year_display=_to_str(data.get("CPXN_DISPLAY")),
        term_display=_to_str(data.get("CPXQ_DISPLAY")),
        show_major_rank=bool(data.get("showZypm")),
        indicators=indicators,
        raw=data,
    )


def _parse_indicator_detail(r: dict[str, Any]) -> EvaluationIndicatorDetail:
    return EvaluationIndicatorDetail(
        name=_to_str(r.get("ZBMC")),
        score=_to_str(r.get("FS")),
        rank=_to_int(r.get("PX")),
        max_score=_to_str(r.get("ZDZ")),
        range_text=_to_str(r.get("FZFW")),
        proportion=_to_str(r.get("BL")),
        category_display=_to_str(r.get("ZBLB_DISPLAY")),
        description=_to_str(r.get("ZBSM")),
        raw=r,
    )


def _parse_radar_item(r: dict[str, Any]) -> EvaluationRadarItem:
    return EvaluationRadarItem(
        name=_to_str(r.get("ZBMC")),
        personal=_to_str(r.get("GR")),
        average=_to_str(r.get("AVG")),
        max_score=_to_str(r.get("MAX")),
        raw=r,
    )


def _parse_year_score_static(r: dict[str, Any]) -> YearScoreStatic:
    return YearScoreStatic(
        year=_to_str(r.get("XNZ")),
        term=_to_str(r.get("XQZ")),
        year_display=_to_str(r.get("XNXSZ")),
        term_display=_to_str(r.get("XQXSZ")),
        score=_to_str(r.get("FS")),
        raw=r,
    )


def _parse_report_year(r: dict[str, Any]) -> AcademicReportYear:
    return AcademicReportYear(
        year=_to_str(r.get("XNZ")),
        year_display=_to_str(r.get("XNXSZ")),
        raw=r,
    )


def _parse_report_entry(r: dict[str, Any]) -> AcademicReportEntry:
    return AcademicReportEntry(
        course_name=_to_str(r.get("KCMC")),
        score=_to_str(r.get("ZCJ")),
        credit=_to_str(r.get("XF")),
        course_nature=_to_str(r.get("KCXZDM")),
        year=_to_str(r.get("XN")),
        term=_to_str(r.get("XQ")),
        raw=r,
    )


_F = TypeVar("_F", bound=Callable[..., Any])


def _with_lazy_reauth(fn: _F) -> _F:
    """业务方法装饰器：默认信任现有 XGXT 会话，过期时回 CAS 拿一次新 ST。

    流程：

    1. 进入前 ``_ensure_authorized()``：session 上已有 xgxt 域 cookie 就跳过；
       没有则走一次 ``cas.authorize``（cold start 路径）。
    2. 执行业务方法。
    3. 若抛 :class:`NotLoggedInError`（HTTP 401/403 或被重定向到 CAS 登录页），
       调用 ``_reauthorize()`` 清掉过期 xgxt cookies 并重新 ``authorize``，
       然后**整段重试**业务方法一次。重试只做一次：再失败就直接抛出。
    """

    @functools.wraps(fn)
    def wrapper(self: "XGXTClient", *args: Any, **kwargs: Any) -> Any:
        self._ensure_authorized()
        try:
            return fn(self, *args, **kwargs)
        except NotLoggedInError:
            self._reauthorize()
            return fn(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class XGXTClient:
    """燕山大学学工系统（综合测评）信息查询客户端。

    依赖 :class:`CASClient` 完成 CAS 认证并持有学工系统 cookie。
    所有查询方法均在 ``self.session`` 上发送请求。

    用法示例::

        cas = CASClient()
        cas.login("username", "password")

        xgxt = XGXTClient(cas)
        result = xgxt.query_evaluation_result()
        print(result.total_score, result.class_rank)
    """

    def __init__(
        self,
        cas_client: CASClient,
        *,
        session: requests.Session | None = None,
        xgxt_session: XGXTSession | None = None,
        timeout: float = 30,
    ) -> None:
        self.cas = cas_client
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self._app_role_ready = False
        if xgxt_session is not None:
            xgxt_session.apply(self.session)
        # 不在此处 ensure_authorized：改为业务方法装饰器在首次调用时按需执行，
        # 避免无意义的 CAS 调用（特别是 ysu-api 等 stateless 调用方）。

    # ──────────────────────────────────────────────────────────────────── #
    # 内部辅助
    # ──────────────────────────────────────────────────────────────────── #

    def _ensure_authorized(self) -> None:
        """确保 session 已携带学工系统 cookie。

        若 ``self.session`` 上已有 ``xgxt.ysu.edu.cn`` 的 cookie 则跳过，
        否则通过 ``CASClient.authorize`` 拿 ST 落盘。
        """
        for c in self.session.cookies:
            if c.domain and "xgxt.ysu.edu.cn" in c.domain:
                break
        else:
            self.cas.authorize(ZHCP_SERVICE_URL, session=self.session)

        self._ensure_app_role()

    def _ensure_app_role(self) -> None:
        """确保会话已绑定综合测评应用的角色上下文（如「学生组」）。

        与 jwxt 的 ``_ensure_weu`` 同构：学工平台的模块 API 要求会话先完成
        角色绑定，否则一律返回 404。绑定流程（与页面前端一致）：

        1. ``getAppConfig`` 拉取应用配置，从 ``HEADER.dropMenu`` 取角色列表；
        2. ``setXgCommonAppRole`` + ``changeAppRole`` 激活角色。

        幂等：本 client 实例内只做一次（``_app_role_ready`` 标记）；服务端
        侧重复激活无害（前端每次进页面都会重走一遍）。
        """
        if self._app_role_ready:
            return
        role_id = self._fetch_active_role_id()
        if role_id is not None:
            self._activate_role(role_id)
        self._app_role_ready = True

    def _fetch_active_role_id(self) -> str | None:
        """从应用配置中取当前激活角色 ID；无角色配置时返回 ``None``。"""
        result = self._raw_post(
            APP_CONFIG_URL,
            params={"appId": EMAP_APP_ID, "appName": APP_NAME},
        )
        header = result.get("HEADER") if isinstance(result, dict) else None
        menu = header.get("dropMenu") if isinstance(header, dict) else None
        if not isinstance(menu, list) or not menu:
            return None
        active = next(
            (r for r in menu if isinstance(r, dict) and r.get("active")),
            menu[0],
        )
        role_id = active.get("id") if isinstance(active, dict) else None
        if not role_id:
            raise XGXTProtocolError(f"getAppConfig 角色项缺少 id: {active!r}")
        return str(role_id)

    def _activate_role(self, role_id: str) -> None:
        """激活指定角色（两步，均为前端实际调用的接口）。"""
        set_result = self._raw_post(
            SET_ROLE_URL,
            data={
                "requestParamStr": json.dumps(
                    {"ROLEID": role_id}, separators=(",", ":")
                )
            },
        )
        if not isinstance(set_result, dict) or set_result.get("returnCode") != "#E000000000000":
            raise XGXTProtocolError(f"setXgCommonAppRole 响应异常: {set_result!r}")

        change_result = self._raw_post(
            CHANGE_ROLE_URL_TEMPLATE.format(role_id=role_id),
        )
        if not isinstance(change_result, dict) or change_result.get("success") is not True:
            raise XGXTProtocolError(f"changeAppRole 响应异常: {change_result!r}")

    def _raw_post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> Any:
        """握手端点专用 POST：不走 ``_post``（这些端点不是 ``code`` envelope）。

        仅做状态码检查与 JSON 解析；会话过期识别仍沿用登录页 HTML 探测。
        """
        try:
            resp = self.session.post(
                url,
                params=params,
                data=data or {},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403):
                raise NotLoggedInError(f"HTTP {exc.response.status_code} from {url}") from exc
            raise XGXTProtocolError(f"HTTP error from {url}: {exc}") from exc
        except requests.RequestException as exc:
            raise XGXTProtocolError(f"request failed for {url}: {exc}") from exc

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type and "authserver/login" in resp.text:
            raise NotLoggedInError("session expired, redirected to CAS login page")

        try:
            return resp.json()
        except (ValueError, TypeError) as exc:
            raise XGXTProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc

    def _reauthorize(self) -> None:
        """显式作废当前 XGXT 会话，重新走 CAS 拿 ST。

        被 :func:`_with_lazy_reauth` 装饰器在捕获 :class:`NotLoggedInError`
        后调用：先清掉 ``xgxt.ysu.edu.cn`` 域上所有可能过期的 cookie，再让
        ``cas.authorize`` 给我们重发一组新 ``JSESSIONID`` / ``_WEU``。

        ``RequestsCookieJar.clear(domain=...)`` 在域不存在时会抛 ``KeyError``，
        这对我们没有意义——目标就是"清空该域"，不存在就当作已清完。
        """
        for domain in ("xgxt.ysu.edu.cn", ".xgxt.ysu.edu.cn"):
            try:
                self.session.cookies.clear(domain=domain)
            except KeyError:
                pass
        self._app_role_ready = False
        self.cas.authorize(ZHCP_SERVICE_URL, session=self.session)

    def session_snapshot(self) -> XGXTSession:
        """从当前 session 提取一份新鲜的 :class:`XGXTSession`。

        供外部调用方（如 ysu-api 的响应阶段中间件）把可能旋转过的 xgxt cookie
        持久化或回传给客户端。
        """
        return XGXTSession.from_session(self.session)

    def _post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        """所有 API 调用的收口：发 POST、检测登录过期、解析 envelope、异常分层。

        Returns:
            解析后的完整响应 JSON（dict）。不同接口的载荷位置不同——
            controller 风格在 ``data`` 字段，EMAP 列表风格在 ``datas`` 字段，
            由调用方按需提取。

        Raises:
            NotLoggedInError: HTTP 401/403，或响应被重定向到 CAS 登录页。
            XGXTProtocolError: 非 JSON 响应、envelope 残缺、网络/HTTP 错误。
            XGXTBusinessError: 响应结构正确但业务 code 非 0。
        """
        url = _build_api_url(path)
        try:
            resp = self.session.post(
                url,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403):
                raise NotLoggedInError(f"HTTP {exc.response.status_code} from {url}") from exc
            raise XGXTProtocolError(f"HTTP error from {url}: {exc}") from exc
        except requests.RequestException as exc:
            raise XGXTProtocolError(f"request failed for {url}: {exc}") from exc

        # 会话过期时 EMAP 可能返回登录页 HTML 而非 JSON
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type and "authserver/login" in resp.text:
            raise NotLoggedInError("session expired, redirected to CAS login page")

        try:
            result: dict[str, Any] = resp.json()
        except (ValueError, TypeError) as exc:
            raise XGXTProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc

        code = result.get("code")
        if code != "0" and code != 0:
            raise XGXTBusinessError(code, result.get("msg"), url)

        return result

    def _post_controller(self, path: str, payload: dict[str, Any]) -> Any:
        """controller 风格接口：请求体为 ``data=<JSON>``，响应取 ``data`` 字段。

        ``evaluationApplyController`` / ``evaluationBjhpController`` 下的接口
        都是这个形状。
        """
        result = self._post(
            path,
            {"data": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        )
        url = _build_api_url(path)
        if "data" not in result:
            raise XGXTProtocolError(f"missing 'data' field in response from {url}")
        return result["data"]

    def _post_rows(
        self, path: str, form: dict[str, str], key: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """EMAP 列表风格接口：纯表单 POST，响应取 ``datas[key].rows``。

        Returns:
            ``(rows, node)`` 二元组——``node`` 是分页节点本身（含
            ``totalSize`` / ``pageNumber`` / ``pageSize``），供需要分页元信息的
            调用方使用。
        """
        result = self._post(path, form)
        url = _build_api_url(path)
        datas = result.get("datas")
        if not isinstance(datas, dict):
            raise XGXTProtocolError(f"missing 'datas' field in response from {url}")
        node = datas.get(key, {})
        if isinstance(node, dict):
            rows = node.get("rows", [])
        elif isinstance(node, list):
            rows, node = node, {}
        else:
            rows, node = [], {}
        if not isinstance(rows, list):
            raise XGXTProtocolError(f"'rows' is not a list in response from {url}")
        return rows, node

    def _resolve_term(self, year: str | None, term: str | None) -> tuple[str, str]:
        """把可选的 ``year`` / ``term`` 归一为具体的 ``(CPXN, CPXQ)``。

        两者都给定则直接使用；任一缺省时查询测评学年学期列表，取第一个
        匹配项（列表按时间倒序，即最新）；都缺省则用最新一组。
        """
        if year is not None and term is not None:
            return str(year), str(term)
        terms = self.query_evaluation_terms()
        for t in terms:
            if (year is None or t.year == str(year)) and (
                term is None or t.term == str(term)
            ):
                return t.year, t.term
        raise ValueError(
            f"未找到匹配的测评学年学期: year={year!r} term={term!r}，"
            "可先调用 query_evaluation_terms() 查看可用值"
        )

    # ──────────────────────────────────────────────────────────────────── #
    # 综测成绩
    # ──────────────────────────────────────────────────────────────────── #

    @_with_lazy_reauth
    def query_evaluation_terms(self) -> list[EvaluationTerm]:
        """查询可查看综测成绩的学年学期列表（按时间倒序，首个为最新）。

        Returns:
            测评学年学期列表；为空表示当前没有可查询的测评批次。
        """
        data = self._post_controller(API_PATHS["cpxnxq"], {})
        rows = data.get("XNXX") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise XGXTProtocolError("getCpxnxq 响应缺少 XNXX 列表")
        return [_parse_term(r) for r in rows if isinstance(r, dict)]

    @_with_lazy_reauth
    def query_evaluation_result(
        self,
        year: str | None = None,
        term: str | None = None,
    ) -> EvaluationResult:
        """查询指定学年学期的综测成绩与班级/年级排名。

        Args:
            year: 测评学年代码（如 ``"2025"``）；缺省时取最新测评批次。
            term: 测评学期代码（``"1"`` / ``"2"``）；缺省时取最新测评批次。

        Returns:
            总分、班级/年级排名及各指标得分。
        """
        cpxn, cpxq = self._resolve_term(year, term)
        data = self._post_controller(
            API_PATHS["cj_by_xn"], {"CPXN": cpxn, "CPXQ": cpxq}
        )
        if not isinstance(data, dict):
            raise XGXTProtocolError("getEvaluationResultsByXn 响应 data 不是对象")
        return _parse_result(data)

    @_with_lazy_reauth
    def query_evaluation_indicators(
        self,
        year: str | None = None,
        term: str | None = None,
        *,
        page_size: int = 100,
        page_number: int = 1,
    ) -> list[EvaluationIndicatorDetail]:
        """查询指定学年学期的指标得分明细（综测成绩页的指标表格）。

        Args:
            year: 测评学年代码；缺省时取最新测评批次。
            term: 测评学期代码；缺省时取最新测评批次。
            page_size: 每页条数。
            page_number: 页码（从 1 开始）。

        Returns:
            指标明细列表（名称、得分、排名、占比、类别等）。
        """
        cpxn, cpxq = self._resolve_term(year, term)
        rows, _ = self._post_rows(
            API_PATHS["zbxx"],
            {
                "XN": cpxn,
                "XQ": cpxq,
                "pageSize": str(page_size),
                "pageNumber": str(page_number),
            },
            "tjsqhqxqzbxx",
        )
        return [_parse_indicator_detail(r) for r in rows]

    @_with_lazy_reauth
    def query_evaluation_radar(
        self,
        year: str | None = None,
        term: str | None = None,
    ) -> list[EvaluationRadarItem]:
        """查询指定学年学期的指标雷达对比（「我和别人比一比」）。

        Args:
            year: 测评学年代码；缺省时取最新测评批次。
            term: 测评学期代码；缺省时取最新测评批次。

        Returns:
            各指标的个人得分、平均得分与满分。
        """
        cpxn, cpxq = self._resolve_term(year, term)
        data = self._post_controller(
            API_PATHS["redar"], {"CPXN": cpxn, "CPXQ": cpxq}
        )
        if not isinstance(data, list):
            raise XGXTProtocolError("getRedar 响应 data 不是数组")
        return [_parse_radar_item(r) for r in data if isinstance(r, dict)]

    @_with_lazy_reauth
    def query_year_score_statics(self) -> list[YearScoreStatic]:
        """查询各学年学期的综测分数总览（「我和自己比一比」）。

        Returns:
            按学年学期排列的分数列表；未出分的学期 ``score`` 为空串。
        """
        data = self._post_controller(API_PATHS["year_cj_static"], {})
        if not isinstance(data, list):
            raise XGXTProtocolError("getYearCjStatic 响应 data 不是数组")
        return [_parse_year_score_static(r) for r in data if isinstance(r, dict)]

    # ──────────────────────────────────────────────────────────────────── #
    # 学业成绩报告（综测成绩页「学业成绩」弹窗）
    # ──────────────────────────────────────────────────────────────────── #

    @_with_lazy_reauth
    def query_academic_report_years(self) -> AcademicReportYears:
        """查询学业成绩报告的可选学年与默认学年。

        Returns:
            学年列表（近五年）与默认学年代码。
        """
        years_raw = self._post_controller(API_PATHS["five_years"], {})
        default_raw = self._post_controller(API_PATHS["mr_xn"], {})
        years = (
            [_parse_report_year(y) for y in years_raw if isinstance(y, dict)]
            if isinstance(years_raw, list)
            else []
        )
        default_year = (
            _to_str(default_raw.get("DQXN")) if isinstance(default_raw, dict) else ""
        )
        return AcademicReportYears(
            years=years,
            default_year=default_year,
            raw={"five_years": years_raw, "mr_xn": default_raw},
        )

    @_with_lazy_reauth
    def query_academic_report(
        self,
        year: str | None = None,
        *,
        page_size: int = 100,
        page_number: int = 1,
    ) -> AcademicReportPage:
        """查询学业成绩报告（按学年分页的课程成绩列表）。

        Args:
            year: 学年代码（如 ``"2024"``）；缺省时用服务端默认学年
                （:meth:`query_academic_report_years` 的 ``default_year``）。
            page_size: 每页条数。
            page_number: 页码（从 1 开始）。

        Returns:
            一页课程成绩及分页元信息。
        """
        if year is None:
            default_raw = self._post_controller(API_PATHS["mr_xn"], {})
            year = _to_str(default_raw.get("DQXN")) if isinstance(default_raw, dict) else ""
            if not year:
                raise XGXTProtocolError("getMrXn 响应缺少 DQXN 字段")
        rows, node = self._post_rows(
            API_PATHS["xycjbg"],
            {
                "XN": str(year),
                "pageSize": str(page_size),
                "pageNumber": str(page_number),
            },
            "xycjbg",
        )
        return AcademicReportPage(
            entries=[_parse_report_entry(r) for r in rows],
            total_size=_to_int(node.get("totalSize")),
            page_number=_to_int(node.get("pageNumber")) or page_number,
            page_size=_to_int(node.get("pageSize")) or page_size,
            raw=node if isinstance(node, dict) else {},
        )
