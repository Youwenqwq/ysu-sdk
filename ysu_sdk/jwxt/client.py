"""教务系统客户端：信息查询业务封装。

基于 EMAP 平台 API 封装，所有查询方法均返回结构化数据类型。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from ysu_sdk.cas.client import CASClient
from ysu_sdk.jwxt.constants import APP_IDS, API_PATHS, JWXT_APP_BASE, JWXT_BASE_URL
from ysu_sdk.jwxt.exceptions import JWXTBusinessError, JWXTProtocolError, NotLoggedInError
from ysu_sdk.jwxt.types import (
    AcademicCompletion,
    AcademicWarning,
    Course,
    EvaluationAnswer,
    EvaluationDetail,
    EvaluationTask,
    EvaluationType,
    Exam,
    GPAStats,
    Grade,
    Question,
    QuestionOption,
    StudentInfo,
    TrainingPlan,
)

logger = logging.getLogger("ysu_sdk.jwxt")


def _build_api_url(path: str) -> str:
    """拼接完整 API URL。"""
    return f"{JWXT_APP_BASE}/{path}"


def _emap_post(
    session: requests.Session,
    url: str,
    data: dict[str, str] | None = None,
    *,
    timeout: float = 30,
) -> dict[str, Any]:
    """发送 EMAP 风格的 POST 请求并解析响应。

    Args:
        session: 已携带 cookie 的 requests.Session。
        url: 目标 API URL。
        data: 请求表单数据。
        timeout: 请求超时秒数。

    Returns:
        响应 JSON 中的 ``datas`` 字典。

    Raises:
        NotLoggedInError: 响应被重定向到登录页或返回未登录标记。
        JWXTBusinessError: 响应结构正确但业务 code 非 0（业务规则拒绝）。
        JWXTProtocolError: 响应格式异常（非 JSON、envelope 残缺等）。
    """
    if data is None:
        data = {}

    resp = session.post(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=timeout,
    )
    resp.raise_for_status()

    # EMAP 有时在session过期时返回登录页HTML而非JSON
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type and "authserver/login" in resp.text:
        raise NotLoggedInError("session expired, redirected to CAS login page")

    try:
        result: dict[str, Any] = resp.json()
    except (ValueError, TypeError) as exc:
        raise JWXTProtocolError(f"non-JSON response from {url}: {resp.text[:200]!r}") from exc

    code = result.get("code")
    if code != "0" and code != 0:
        raise JWXTBusinessError(code, result.get("msg"), url)

    return result.get("datas", {})


def _extract_rows(datas: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """从 EMAP 响应 datas 中提取 rows 数组。"""
    node = datas.get(key, {})
    if isinstance(node, dict):
        return node.get("rows", [])
    if isinstance(node, list):
        return node
    return []


_TRUTHY_TOKENS: frozenset[str] = frozenset({"1", "是", "true", "True"})


def _to_bool(val: Any) -> bool:
    """把 EMAP 常见的真/假表示（``"1"`` / ``"是"`` / ``"true"`` 等）转成 bool。

    ``None``、空串、其它任何字符串都视为 ``False``。
    """
    return str(val) in _TRUTHY_TOKENS


# 实验/未排课接口共享的 KBLB 取值映射。
_COURSE_CATEGORY_TO_KBLB: dict[str, str] = {
    "all": "0",
    "theory": "1",
    "experiment": "2",
}


class JWXTClient:
    """燕山大学教务系统信息查询客户端。

    依赖 :class:`CASClient` 完成 CAS 认证并持有教务系统 cookie。
    所有查询方法均在 ``self.session`` 上发送请求。

    用法示例::

        cas = CASClient()
        cas.login("username", "password")

        jwxt = JWXTClient(cas)
        grades = jwxt.query_grades()
        schedule = jwxt.query_schedule()
    """

    def __init__(
        self,
        cas_client: CASClient,
        *,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        self.cas = cas_client
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        # 把 CAS 凭据同步到本 session，再authorize到教务系统
        self._ensure_authorized()

    # ──────────────────────────────────────────────────────────────────── #
    # 内部辅助
    # ──────────────────────────────────────────────────────────────────── #

    def _ensure_authorized(self) -> None:
        """确保 session 已携带教务系统 cookie。

        若 ``self.session`` 上已有 ``jwxt.ysu.edu.cn`` 的 cookie 则跳过，
        否则通过 ``CASClient.authorize`` 拿 ST 落盘。
        """
        for c in self.session.cookies:
            if c.domain and "jwxt.ysu.edu.cn" in c.domain:
                return

        service = f"{JWXT_BASE_URL}/jwapp/sys/emaphome/portal/index.do"
        self.cas.authorize(service, session=self.session)

    def _ensure_weu(self, app_id: str) -> None:
        """访问应用首页以刷新 ``_WEU`` 权限 token。

        EMAP 平台为每个应用签发独立的 ``_WEU``，直接调用 API 时若 token
        不对应目标应用会返回 404。通过访问 ``appShow.do`` 可令服务端
        下发正确的 ``_WEU``。
        """
        url = f"{JWXT_BASE_URL}/jwapp/sys/emaphome/appShow.do"
        try:
            resp = self.session.get(
                url,
                params={"id": app_id},
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=self.timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
        except requests.RequestException:
            # appShow 可能 302 跳转，允许失败；只要 _WEU 被刷新即可
            pass

    def _post(
        self,
        path: str,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """``_emap_post`` 的快捷封装，自动拼接 URL 并处理异常。"""
        url = _build_api_url(path)
        try:
            return _emap_post(self.session, url, data, timeout=self.timeout)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403):
                raise NotLoggedInError(f"HTTP {exc.response.status_code} from {url}") from exc
            raise JWXTProtocolError(f"HTTP error from {url}: {exc}") from exc
        except requests.RequestException as exc:
            raise JWXTProtocolError(f"request failed for {url}: {exc}") from exc

    def _get_current_term(self, app_id: str, path_key: str) -> str:
        """查询当前学年学期代码（如 ``2025-2026-2``）。"""
        self._ensure_weu(app_id)
        datas = self._post(API_PATHS[path_key])
        rows = _extract_rows(datas, path_key.rsplit("_", 1)[-1])
        if not rows:
            raise JWXTProtocolError("current term query returned empty result")
        term = str(rows[0].get("DM") or "")
        if not term:
            raise JWXTProtocolError("current term query returned empty DM")
        return term

    # ──────────────────────────────────────────────────────────────────── #
    # 成绩查询
    # ──────────────────────────────────────────────────────────────────── #

    def query_grades(
        self,
        *,
        term: str | None = None,
        course_name: str | None = None,
        page_size: int = 100,
        page_number: int = 1,
    ) -> list[Grade]:
        """查询学生成绩。

        Args:
            term: 学年学期，如 ``"2025-2026-1"``；为 ``None`` 则查询全部。
            course_name: 按课程名模糊匹配；为 ``None`` 则不筛选。
            page_size: 每页条数，默认 100（一般一次取完）。
            page_number: 页码，从 1 开始。

        Returns:
            成绩列表，按学期降序排列。
        """
        self._ensure_weu(APP_IDS["cjcx"])

        query: list[dict[str, Any]] = []
        if term:
            query.append({
                "name": "XNXQDM",
                "value": term,
                "linkOpt": "and",
                "builder": "m_value_equal",
            })
        if course_name:
            query.append({
                "name": "XSKCM",
                "value": course_name,
                "linkOpt": "and",
                "builder": "include",
            })

        # 前端默认携带的固定过滤条件：有效成绩、不显示最高成绩
        query.extend([
            {
                "name": "SFYX",
                "caption": "是否有效",
                "linkOpt": "AND",
                "builderList": "cbl_m_List",
                "builder": "m_value_equal",
                "value": "1",
                "value_display": "是",
            },
            {
                "name": "SHOWMAXCJ",
                "caption": "显示最高成绩",
                "linkOpt": "AND",
                "builderList": "cbl_String",
                "builder": "equal",
                "value": 0,
                "value_display": "否",
            },
            {
                "name": "BY1",
                "caption": "备用1",
                "linkOpt": "AND",
                "builderList": "cbl_m_List",
                "builder": "equal",
                "value": "1",
            },
        ])

        data = {
            "querySetting": json.dumps(query, ensure_ascii=False),
            "pageSize": str(page_size),
            "pageNumber": str(page_number),
            "*order": "-XNXQDM,-KCH,-KXH",
        }
        datas = self._post(API_PATHS["cjcx"], data)
        rows = _extract_rows(datas, "xscjcx")
        return [_parse_grade(r) for r in rows]

    def query_gpa_stats(
        self,
        *,
        student_id: str | None = None,
    ) -> GPAStats:
        """查询学分绩点统计。

        Args:
            student_id: 学号；为 ``None`` 则自动查询当前登录学生信息。

        Returns:
            :class:`GPAStats`
        """
        if student_id is None:
            student_id = self.query_student_info().student_id

        self._ensure_weu(APP_IDS["cjcx"])

        # 服务端要求把同一个学号塞 6 个等价字段
        data = {f"XH{i}": student_id for i in range(1, 7)}
        datas = self._post(API_PATHS["cjcx_gpa"], data)
        rows = _extract_rows(datas, "cxzxfaxfjd")
        if not rows:
            raise JWXTProtocolError("query_gpa_stats returned empty result")
        return _parse_gpa_stats(rows[0])

    # ──────────────────────────────────────────────────────────────────── #
    # 课表查询
    # ──────────────────────────────────────────────────────────────────── #

    def query_schedule(
        self,
        *,
        term: str | None = None,
    ) -> list[Course]:
        """查询学生整学期课表。

        Args:
            term: 学年学期，如 ``"2025-2026-1"``；为 ``None`` 则查询当前学期。

        Returns:
            课程列表。
        """
        self._ensure_weu(APP_IDS["wdkb"])

        if term is None:
            term = self._get_current_term(APP_IDS["studentWdksapApp"], "wdksap_dqxnxq")

        datas = self._post(API_PATHS["wdkb"], {"XNXQDM": term})
        rows = _extract_rows(datas, "cxxszhxqkb")
        return [_parse_course(r) for r in rows]

    def query_schedule_experimental(
        self,
        *,
        term: str | None = None,
        student_id: str | None = None,
        course_category: str = "all",
    ) -> list[Course]:
        """查询学生课表（实验选课结果）。

        该接口比 ``query_schedule`` 返回更完整的课表信息，
        包含理论课与实验课。差异字段（如 ``YPSJDD``、``SYXZMC`` 等）
        可通过每条记录的 ``raw`` 字典获取。

        Args:
            term: 学年学期；为 ``None`` 则查询当前学期。
            student_id: 学号；为 ``None`` 则自动查询当前登录学生信息。
            course_category: 课表类别，``"all"`` 全部、``"theory"`` 理论、
                ``"experiment"`` 实验。

        Returns:
            课程列表。
        """
        return self._query_courses_by_kblb(
            path_key="wdkb_sy",
            row_key="cxxskb",
            term=term,
            student_id=student_id,
            course_category=course_category,
        )

    def query_unscheduled_courses(
        self,
        *,
        term: str | None = None,
        student_id: str | None = None,
        course_category: str = "all",
    ) -> list[Course]:
        """查询学生理论/实验未排课列表。

        返回尚未安排具体时间地点的课程。

        Args:
            term: 学年学期；为 ``None`` 则查询当前学期。
            student_id: 学号；为 ``None`` 则自动查询当前登录学生信息。
            course_category: 课表类别，``"all"`` 全部、``"theory"`` 理论、
                ``"experiment"`` 实验。

        Returns:
            未排课课程列表。
        """
        return self._query_courses_by_kblb(
            path_key="wdkb_sy_unscheduled",
            row_key="cxxsllsywpk",
            term=term,
            student_id=student_id,
            course_category=course_category,
        )

    def _query_courses_by_kblb(
        self,
        *,
        path_key: str,
        row_key: str,
        term: str | None,
        student_id: str | None,
        course_category: str,
    ) -> list[Course]:
        """实验选课/未排课接口的共用实现。

        二者共享 ``XNXQDM/XH/KBLB`` 的请求体与 ``wdkb_sy`` 的 ``_WEU``，仅 API
        路径与 ``_extract_rows`` 的 key 不同。
        """
        if term is None:
            term = self._get_current_term(
                APP_IDS["studentWdksapApp"], "wdksap_dqxnxq"
            )
        if student_id is None:
            student_id = self.query_student_info().student_id

        self._ensure_weu(APP_IDS["wdkb_sy"])

        kblb = _COURSE_CATEGORY_TO_KBLB.get(course_category, "0")
        datas = self._post(API_PATHS[path_key], {
            "XNXQDM": term,
            "XH": student_id,
            "KBLB": kblb,
        })
        rows = _extract_rows(datas, row_key)
        return [_parse_course(r) for r in rows]

    # ──────────────────────────────────────────────────────────────────── #
    # 考试安排
    # ──────────────────────────────────────────────────────────────────── #

    def query_exams(
        self,
        *,
        term: str | None = None,
    ) -> list[Exam]:
        """查询我的考试安排。

        Args:
            term: 学年学期；为 ``None`` 则查询当前学期。

        Returns:
            考试安排列表。
        """
        self._ensure_weu(APP_IDS["studentWdksapApp"])

        if term is None:
            term = self._get_current_term(APP_IDS["studentWdksapApp"], "wdksap_dqxnxq")

        param: dict[str, Any] = {
            "XNXQDM": term,
            "*order": "-KSRQ,-KSSJMS",
        }
        datas = self._post(API_PATHS["wdksap"], {
            "requestParamStr": json.dumps(param, ensure_ascii=False),
        })
        rows = _extract_rows(datas, "cxxsksap")
        return [_parse_exam(r) for r in rows]

    # ──────────────────────────────────────────────────────────────────── #
    # 学生基本信息
    # ──────────────────────────────────────────────────────────────────── #

    def query_student_info(self) -> StudentInfo:
        """查询当前登录学生的基本信息。

        Returns:
            :class:`StudentInfo`
        """
        self._ensure_weu(APP_IDS["xsjbxxgl"])

        data = {
            "querySetting": json.dumps([], ensure_ascii=False),
            "pageSize": "12",
            "pageNumber": "1",
        }
        datas = self._post(API_PATHS["xsjbxx"], data)
        rows = _extract_rows(datas, "cxxsjbxxlb")
        if not rows:
            raise JWXTProtocolError("query_student_info returned empty result")
        return _parse_student_info(rows[0])

    # ──────────────────────────────────────────────────────────────────── #
    # 培养方案
    # ──────────────────────────────────────────────────────────────────── #

    def query_training_plan(
        self,
        *,
        page_size: int = 500,
        page_number: int = 1,
    ) -> list[TrainingPlan]:
        """查询个人培养方案课程列表。

        内部先查询 ``grpyfacx`` 获取培养方案代码 ``PYFADM``，
        再调用 ``kzkccx`` 获取课程明细。

        Args:
            page_size: 每页条数，默认 500。
            page_number: 页码。

        Returns:
            培养方案课程列表。
        """
        self._ensure_weu(APP_IDS["xsfacx"])

        # 第一步：获取个人培养方案代码
        datas = self._post(API_PATHS["pyfa"])
        rows = _extract_rows(datas, "grpyfacx")
        if not rows:
            raise JWXTProtocolError("query_training_plan: no training plan found")
        pyfadm = str(rows[0].get("PYFADM") or "")
        if not pyfadm:
            raise JWXTProtocolError("query_training_plan: PYFADM is empty")

        # 第二步：获取培养方案课程列表
        datas = self._post(API_PATHS["pyfa_courses"], {
            "PYFADM": pyfadm,
            "pageSize": str(page_size),
            "pageNumber": str(page_number),
        })
        course_rows = _extract_rows(datas, "kzkccx")
        return [_parse_training_plan(r) for r in course_rows]

    # ──────────────────────────────────────────────────────────────────── #
    # 学业完成查询
    # ──────────────────────────────────────────────────────────────────── #

    def query_academic_completion(self) -> AcademicCompletion:
        """查询学业完成情况。

        Returns:
            :class:`AcademicCompletion`
        """
        self._ensure_weu(APP_IDS["xywccx"])

        datas = self._post(API_PATHS["xywc"], {"SCLBDM": "04", "*order": "-CZSJ"})
        rows = _extract_rows(datas, "cxxsscfa")
        if not rows:
            raise JWXTProtocolError("query_academic_completion returned empty result")
        return _parse_academic_completion(rows[0])

    # ──────────────────────────────────────────────────────────────────── #
    # 学业预警
    # ──────────────────────────────────────────────────────────────────── #

    def query_academic_warnings(self) -> list[AcademicWarning]:
        """查询学业预警结果。

        Returns:
            预警列表。
        """
        self._ensure_weu(APP_IDS["xyyj"])

        datas = self._post(API_PATHS["xyyj"])
        rows = _extract_rows(datas, "cxxsyjpcjg")
        return [_parse_academic_warning(r) for r in rows]

    # ──────────────────────────────────────────────────────────────────── #
    # 评教
    # ──────────────────────────────────────────────────────────────────── #

    def query_evaluation_types(
        self,
        *,
        term: str | None = None,
    ) -> list[EvaluationType]:
        """查询评教类型及待评数量。

        Args:
            term: 学年学期代码，如 ``"2025-2026-2"``；为 ``None`` 则查询当前学期。

        Returns:
            评教类型列表，包含类型名称、代码及待评数量。
        """
        self._ensure_weu(APP_IDS["pjapp"])

        if term is None:
            term = self._get_current_term(
                APP_IDS["studentWdksapApp"], "wdksap_dqxnxq"
            )

        datas = self._post(API_PATHS["pjlx"], {"XNXQDM": term})
        rows = _extract_rows(datas, "getPjlx")
        return [_parse_evaluation_type(r) for r in rows]

    def query_pending_evaluations(
        self,
        eval_type: str,
        *,
        term: str | None = None,
    ) -> list[EvaluationTask]:
        """查询指定类型的待评教任务列表。

        Args:
            eval_type: 评教类型代码，如 ``"01"``（学生评教）或 ``"07"``（随堂调查）。
            term: 学年学期代码；为 ``None`` 则查询当前学期。

        Returns:
            待评教任务列表。
        """
        self._ensure_weu(APP_IDS["pjapp"])

        if term is None:
            term = self._get_current_term(
                APP_IDS["studentWdksapApp"], "wdksap_dqxnxq"
            )

        query = [{
            "name": "XNXQDM",
            "builder": "m_value_equal",
            "linkOpt": "AND",
            "value": term,
        }]
        datas = self._post(API_PATHS["dpwj"], {
            "PJLXDM": eval_type,
            "querySetting": json.dumps(query, ensure_ascii=False),
        })
        rows = _extract_rows(datas, "getDpwj")
        return [_parse_evaluation_task(r) for r in rows]

    def get_evaluation_detail(
        self,
        group_no: str,
        eval_type: str,
        *,
        sequence: int = 1,
    ) -> EvaluationDetail:
        """获取评教问卷详情。

        Args:
            group_no: 分组标识（``GROUPNO``）。
            eval_type: 评教类型代码。
            sequence: 评教次序，默认 1。

        Returns:
            :class:`EvaluationDetail`，包含题目列表及教师信息。
        """
        self._ensure_weu(APP_IDS["pjapp"])

        datas = self._post(API_PATHS["wjtxxx"], {
            "GROUPNO": group_no,
            "PJLXDM": eval_type,
            "XUH": str(sequence),
        })
        raw = datas.get("getWjtxxx")
        if not raw:
            raise JWXTProtocolError("get_evaluation_detail returned empty result")
        return _parse_evaluation_detail(raw)

    def calculate_evaluation_score(
        self,
        group_no: str,
        wjid: str,
        eval_type: str,
        answers: list[EvaluationAnswer],
        *,
        teacher_relation_id: str = "",
        course_name: str = "",
        teacher_name: str = "",
        sequence: int = 1,
    ) -> dict[str, Any]:
        """计算评教答案得分（预检）。

        在正式提交前调用，可验证答案格式并获取预估得分。

        Args:
            group_no: 分组标识。
            wjid: 问卷ID。
            eval_type: 评教类型代码。
            answers: 答案列表。
            teacher_relation_id: 评教关系ID（``PJGXID``）。
            course_name: 课程名称。
            teacher_name: 教师姓名。
            sequence: 评教次序。

        Returns:
            服务端返回的得分信息字典。
        """
        del group_no, eval_type  # 当前服务端实现不需要这两个字段，签名保留向前兼容
        self._ensure_weu(APP_IDS["pjapp"])

        return self._post(
            API_PATHS["calculate_score"],
            _evaluation_form_data(
                wjid=wjid,
                answers=answers,
                teacher_relation_id=teacher_relation_id,
                course_name=course_name,
                teacher_name=teacher_name,
                sequence=sequence,
            ),
        )

    def submit_evaluation(
        self,
        group_no: str,
        wjid: str,
        eval_type: str,
        answers: list[EvaluationAnswer],
        *,
        teacher_relation_id: str = "",
        course_name: str = "",
        teacher_name: str = "",
        sequence: int = 1,
    ) -> None:
        """提交评教答案。

        这是 SDK 中唯一的"写操作"接口，提交后不可修改。

        Args:
            group_no: 分组标识。
            wjid: 问卷ID。
            eval_type: 评教类型代码。
            answers: 答案列表。
            teacher_relation_id: 评教关系ID（``PJGXID``）。
            course_name: 课程名称。
            teacher_name: 教师姓名。
            sequence: 评教次序。

        Raises:
            JWXTBusinessError: 服务端拒绝（如已超出评教时间、答案不完整）。
            JWXTProtocolError: 响应格式异常。
        """
        del group_no, eval_type  # 当前服务端实现不需要这两个字段，签名保留向前兼容
        self._ensure_weu(APP_IDS["pjapp"])

        # _post 已确保 code == "0"；到达此处即视为提交成功
        self._post(
            API_PATHS["commit_answer"],
            _evaluation_form_data(
                wjid=wjid,
                answers=answers,
                teacher_relation_id=teacher_relation_id,
                course_name=course_name,
                teacher_name=teacher_name,
                sequence=sequence,
            ),
        )


# ──────────────────────────────────────────────────────────────────────── #
# 解析辅助函数
# ──────────────────────────────────────────────────────────────────────── #


def _parse_grade(raw: dict[str, Any]) -> Grade:
    zcj = raw.get("ZCJ")
    score = str(zcj) if zcj is not None else str(raw.get("XSZCJMC") or "")

    return Grade(
        course_name=str(raw.get("XSKCM") or raw.get("KCM") or ""),
        course_code=str(raw.get("XSKCH") or raw.get("KCH") or ""),
        score=score,
        grade_level=str(raw.get("XSZCJMC") or ""),
        grade_point=str(raw.get("XFJD") or ""),
        credit=str(raw.get("XF") or ""),
        hours=str(raw.get("XS") or ""),
        term=str(raw.get("XNXQDM") or ""),
        course_type=str(raw.get("KCXZDM_DISPLAY") or raw.get("KCXZDM") or ""),
        course_category=str(raw.get("KCLBDM_DISPLAY") or ""),
        exam_type=str(raw.get("KSLXDM_DISPLAY") or raw.get("KSLXDM") or ""),
        study_mode=str(raw.get("XDFSDM_DISPLAY") or ""),
        is_major=_to_bool(raw.get("SFZX")),
        is_retake=str(raw.get("CXCKDM_DISPLAY") or ""),
        grade_level_type=str(raw.get("XSDJCJLXDM_DISPLAY") or ""),
        department=str(raw.get("KKDWDM_DISPLAY") or ""),
        is_pass=_to_bool(raw.get("SFJG")),
        is_valid=_to_bool(raw.get("SFYX")),
        special_reason=str(raw.get("TSYYDM_DISPLAY") or ""),
        is_degree_course=_to_bool(raw.get("SFZGKC")),
        project_name=str(raw.get("TYXMDM_DISPLAY") or ""),
        raw=raw,
    )


def _parse_gpa_stats(raw: dict[str, Any]) -> GPAStats:
    return GPAStats(
        plan_name=str(raw.get("PYFAMC") or ""),
        study_type=str(raw.get("FAXDLX_DISPLAY") or ""),
        required_credit_earned=str(raw.get("BXKHDXF") or ""),
        elective_credit_earned=str(raw.get("XXKHDXF") or ""),
        degree_credit_earned=str(raw.get("XWKHDXF") or ""),
        required_credit_failed=str(raw.get("BXKBJGXF") or ""),
        gpa_initial=str(raw.get("PPJDCX") or ""),
        gpa_highest=str(raw.get("PPJDZG") or ""),
        required_gpa_highest=str(raw.get("BXKPPJD") or ""),
        degree_gpa_initial=str(raw.get("XWKPJJDCX") or ""),
        degree_gpa_highest=str(raw.get("XWKPJJDZG") or ""),
        weighted_avg=str(raw.get("JQPJF") or ""),
        arithmetic_avg=str(raw.get("SSPJF") or ""),
        degree_weighted_avg=str(raw.get("XWKJQPJF") or ""),
        raw=raw,
    )


def _parse_course(raw: dict[str, Any]) -> Course:
    return Course(
        name=str(raw.get("KCM") or ""),
        code=str(raw.get("KCH") or ""),
        teacher=str(raw.get("SKJS") or raw.get("JSMC") or ""),
        classroom=str(raw.get("JASMC") or ""),
        week_day=int(raw.get("SKXQ") or raw.get("XQ") or 0),
        start_section=int(raw.get("KSJC") or 0),
        end_section=int(raw.get("JSJC") or 0),
        weeks=str(raw.get("ZCMC") or ""),
        credit=str(raw.get("XF") or ""),
        course_type=str(raw.get("KCXZDM") or ""),
        raw=raw,
    )


def _parse_exam(raw: dict[str, Any]) -> Exam:
    return Exam(
        name=str(raw.get("KCM") or ""),
        exam_name=str(raw.get("KSMC") or ""),
        exam_date=str(raw.get("KSRQ") or ""),
        exam_time=str(raw.get("KSSJMS") or raw.get("KSSJ") or ""),
        exam_location=str(raw.get("JASMC") or ""),
        seat_number=str(raw.get("ZWH") or ""),
        raw=raw,
    )


def _parse_student_info(raw: dict[str, Any]) -> StudentInfo:
    return StudentInfo(
        name=str(raw.get("XM") or ""),
        name_pinyin=str(raw.get("XMPY") or ""),
        student_id=str(raw.get("XH") or ""),
        gender=str(raw.get("XBDM_DISPLAY") or ""),
        nation=str(raw.get("MZDM_DISPLAY") or ""),
        nationality=str(raw.get("GJDQDM_DISPLAY") or ""),
        department=str(raw.get("YXDM_DISPLAY") or ""),
        major=str(raw.get("ZYDM_DISPLAY") or raw.get("RXZY_DISPLAY") or ""),
        class_name=str(raw.get("BJMC") or raw.get("RXBJ_DISPLAY") or ""),
        grade_level=str(raw.get("XZNJ_DISPLAY") or ""),
        enrollment_date=str(raw.get("RXNY") or ""),
        expected_graduation=str(raw.get("YJBYRQ") or ""),
        education_level=str(raw.get("PYCCDM_DISPLAY") or ""),
        campus=str(raw.get("XXXQDM_DISPLAY") or ""),
        student_status=str(raw.get("XJZTDM_DISPLAY") or ""),
        discipline=str(raw.get("XKMLDM_DISPLAY") or ""),
        study_duration=str(raw.get("XZ") or ""),
        foreign_language=str(raw.get("WYYZDM_DISPLAY") or ""),
        raw=raw,
    )


def _parse_training_plan(raw: dict[str, Any]) -> TrainingPlan:
    kcxzdm = str(raw.get("KCXZDM") or "")
    return TrainingPlan(
        course_name=str(raw.get("KCM") or ""),
        course_code=str(raw.get("KCH") or ""),
        credit=str(raw.get("XF") or ""),
        course_type=str(raw.get("KCXZDM") or ""),
        required=kcxzdm in ("01", "1", "必修"),
        term=str(raw.get("XNXQ") or raw.get("JHXNXQ") or ""),
        course_group=str(raw.get("KZM") or ""),
        raw=raw,
    )


def _parse_academic_completion(raw: dict[str, Any]) -> AcademicCompletion:
    return AcademicCompletion(
        plan_name=str(raw.get("PYFAMC") or ""),
        total_required=str(raw.get("YQXF") or ""),
        completed=str(raw.get("WCXF") or ""),
        elective=str(raw.get("XKXF") or ""),
        passed=_to_bool(raw.get("JSSFTG")),
        raw=raw,
    )


def _parse_academic_warning(raw: dict[str, Any]) -> AcademicWarning:
    return AcademicWarning(
        warning_type=str(raw.get("SCJLMC") or ""),
        warning_level=str(raw.get("YJJB") or ""),
        description=str(raw.get("BZ") or ""),
        term=str(raw.get("SCPCMC") or ""),
        raw=raw,
    )


def _parse_evaluation_type(raw: dict[str, Any]) -> EvaluationType:
    return EvaluationType(
        name=str(raw.get("PJLXMC") or ""),
        code=str(raw.get("PJLXDM") or ""),
        count=int(raw.get("NUMBER") or 0),
        raw=raw,
    )


def _parse_evaluation_task(raw: dict[str, Any]) -> EvaluationTask:
    return EvaluationTask(
        wid=str(raw.get("WID") or ""),
        wjid=str(raw.get("WJID") or ""),
        name=str(raw.get("MC") or ""),
        course_name=str(raw.get("KCM") or ""),
        teacher_name=str(raw.get("XM") or raw.get("SKDX") or ""),
        teacher_id=str(raw.get("JSH") or ""),
        term=str(raw.get("XNXQDM") or ""),
        term_name=str(raw.get("XNXQMC") or ""),
        eval_type=str(raw.get("PJLXDM") or ""),
        eval_type_name=str(raw.get("PJLXMC") or ""),
        category=str(raw.get("PJLBDM") or ""),
        category_name=str(raw.get("PJLBMC") or ""),
        start_time=str(raw.get("KSSJ") or ""),
        end_time=str(raw.get("JSSJ") or ""),
        sequence=int(raw.get("XUH") or 1),
        class_name=str(raw.get("BJMC") or ""),
        group_no=str(raw.get("GROUPNO") or ""),
        raw=raw,
    )


def _parse_evaluation_detail(raw: dict[str, Any]) -> EvaluationDetail:
    questions = []
    for q_raw in raw.get("questionList", []):
        options = []
        for opt_raw in q_raw.get("questionOptions", []):
            options.append(QuestionOption(
                wid=str(opt_raw.get("WID") or ""),
                text=str(opt_raw.get("MC") or ""),
                score=float(opt_raw.get("FZ") or 0),
                score_ratio=float(opt_raw.get("FZBL") or 0),
                question_id=str(opt_raw.get("TMID") or ""),
                raw=opt_raw,
            ))
        options.sort(key=lambda o: o.raw.get("PX", 0))
        questions.append(Question(
            tmid=str(q_raw.get("TMID") or ""),
            wjid=str(q_raw.get("WJID") or ""),
            text=str(q_raw.get("MC") or ""),
            question_type=str(q_raw.get("TX") or ""),
            max_score=float(q_raw.get("ZF") or 0),
            order=int(q_raw.get("PX") or 0),
            options=options,
            raw=q_raw,
        ))
    questions.sort(key=lambda q: (q.raw.get("PX", 0), q.tmid))

    return EvaluationDetail(
        wjid=str(raw.get("WJID") or ""),
        name=str(raw.get("WJMC") or ""),
        deadline=str(raw.get("JZRQ") or ""),
        questions=questions,
        teachers=raw.get("teachers", []),
        raw=raw,
    )


def _build_answer_payload(answer: EvaluationAnswer, wjid: str) -> dict[str, Any]:
    """将 EvaluationAnswer 转换为服务端要求的 DA 格式。"""
    if answer.question_type == "02" or answer.text:
        return {
            "WJID": wjid,
            "TMID": answer.tmid,
            "TX": answer.question_type or "02",
            "DA": answer.text,
        }
    if len(answer.option_ids) == 1:
        return {
            "WJID": wjid,
            "TMID": answer.tmid,
            "TX": answer.question_type or "01",
            "DA": {"TMXXID": answer.option_ids[0], "FJXX": ""},
        }
    return {
        "WJID": wjid,
        "TMID": answer.tmid,
        "TX": answer.question_type or "07",
        "DA": [{"TMXXID": oid, "FJXX": ""} for oid in answer.option_ids],
    }


# 旁听信息（FJTXXX）的固定 stub —— 学生评教接口不消费这些字段，但服务端校验
# 必须存在；保留与抓包一致的取值。
_EVALUATION_FJTXXX_STUB: dict[str, Any] = {
    "SKRS": None, "TKFJ": None, "TKYJ": None, "TKSJ": None,
    "SJSKJS": None, "SDXSS": None, "CDZTS": None, "TKNR": None,
    "TKZC": "10", "TKXQ": "0", "TKKSJC": "1", "TKJSJC": "1",
    "WID": None,
}


def _evaluation_form_data(
    *,
    wjid: str,
    answers: list[EvaluationAnswer],
    teacher_relation_id: str,
    course_name: str,
    teacher_name: str,
    sequence: int,
) -> dict[str, str]:
    """评教 ``calculate_score`` / ``commit_answer`` 共用的表单体。

    两个接口的 ``requestParamStr`` 内容完全一致，仅 URL 不同。
    """
    da_list = [_build_answer_payload(a, wjid) for a in answers]
    payload = {
        "DF": None,
        "PJZT": "0",
        "DA": da_list,
        "PJGXID": teacher_relation_id,
        "KCM": course_name,
        "XM": teacher_name,
        "XUH": sequence,
        "FJTXXX": dict(_EVALUATION_FJTXXX_STUB),
        "WJID": wjid,
        "questionAnswers": json.dumps(da_list, ensure_ascii=False),
    }
    return {"requestParamStr": json.dumps([payload], ensure_ascii=False)}
