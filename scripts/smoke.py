#!/usr/bin/env python3
"""各模块活网冒烟脚本（手动运行，非自动化测试）。

用法::

    uv run python scripts/smoke.py cas              # 只测 CAS
    uv run python scripts/smoke.py jwxt             # 只测教务
    uv run python scripts/smoke.py xgxt             # 只测学工（综合测评）
    uv run python scripts/smoke.py all --pace 1.5   # 全部，自定义请求间隔
    uv run python scripts/smoke.py dump             # 导出 SDK 能提供的全部数据到 JSON

认证::

    默认读取 ``~/.config/ysu-sdk/cas.json``；文件不存在或已失效时进入
    交互式登录（验证码图片写入 /tmp，MFA 走终端输入），成功后自动保存。

注意::

    cer / xgxt 等域名在 WAF 之后，非浏览器请求突发会触发 RST 乃至 IP 封锁。
    脚本在每组请求之间固定 sleep（``--pace`` 秒，默认 1.0，请勿调太低），
    并且只发送最少量、形态正常的请求。
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ysu_sdk.cas import (
    CASClient,
    CASCredential,
    CASError,
    CaptchaChallenge,
    MFAChallenge,
)

CAPTCHA_PATH = Path("/tmp/ysu_sdk_captcha.png")

_pace_seconds = 1.0


def pace() -> None:
    """请求组之间的固定间隔，避免触发 WAF 风控。"""
    time.sleep(_pace_seconds)


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


# ──────────────────────────────────────────────────────────────────────────── #
# 认证
# ──────────────────────────────────────────────────────────────────────────── #


def _solve_captcha(challenge: CaptchaChallenge) -> str:
    CAPTCHA_PATH.write_bytes(challenge.image_png)
    return input(f"图形验证码已保存到 {CAPTCHA_PATH} ，查看后输入: ").strip()


def _handle_mfa(challenge: MFAChallenge) -> str:
    return input(f"请输入 {challenge.method} 验证码 ({challenge.mobile_hint}): ").strip()


def _interactive_login() -> CASCredential:
    username = input("学号: ").strip()
    password = getpass.getpass("密码: ")
    cred = CASClient().login(
        username,
        password,
        captcha_solver=_solve_captcha,
        mfa_handler=_handle_mfa,
    )
    path = cred.save()
    print(f"登录成功，凭据已保存到 {path}")
    return cred


def build_cas(*, force_login: bool = False) -> CASClient:
    """构造已认证的 CASClient：优先复用本地凭据，失效则交互式登录。"""
    cred = None if force_login else CASCredential.load()
    if cred is None:
        print("未找到本地凭据，进入交互式登录…")
        cred = _interactive_login()
    cas = CASClient(credential=cred)
    if force_login or not cas.is_authenticated():
        if not force_login:
            print("本地凭据已失效，重新登录…")
            cred = _interactive_login()
            cas = CASClient(credential=cred)
    ok("CAS 会话有效")
    return cas


# ──────────────────────────────────────────────────────────────────────────── #
# CAS
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_cas(cas: CASClient) -> None:
    print("== CAS ==")
    # is_authenticated 已在 build_cas 里跑过；这里验证跨 service 出票
    from ysu_sdk.jwxt.constants import JWXT_BASE_URL

    session = cas.authorize(f"{JWXT_BASE_URL}/jwapp/sys/emaphome/portal/index.do")
    jwxt_cookies = [c.name for c in session.cookies if "jwxt.ysu.edu.cn" in (c.domain or "")]
    ok(f"authorize 出票成功，落地 cookie: {sorted(jwxt_cookies)}")
    pace()

    snapshot = cas.credential()
    ok(f"credential 快照含 {len(snapshot.cookies)} 条 CAS 域 cookie")


# ──────────────────────────────────────────────────────────────────────────── #
# JWXT
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_jwxt(cas: CASClient, term: str | None) -> None:
    from ysu_sdk.jwxt import JWXTClient

    print("== JWXT ==")
    jwxt = JWXTClient(cas)

    info = jwxt.query_student_info()
    ok(f"学生信息: {info.name} ({info.student_id}) {info.department}")
    pace()

    grades = jwxt.query_grades(term=term)
    shown = ", ".join(f"{g.course_name}={g.score}" for g in grades[:3])
    ok(f"成绩查询: 共 {len(grades)} 门" + (f"，如 {shown}" if shown else ""))
    pace()

    schedule = jwxt.query_schedule(term=term)
    ok(f"课表查询: 共 {len(schedule)} 门课程")
    pace()

    exams = jwxt.query_exams(term=term)
    ok(f"考试安排: 共 {len(exams)} 场")


# ──────────────────────────────────────────────────────────────────────────── #
# XGXT
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_xgxt(cas: CASClient) -> None:
    from ysu_sdk.xgxt import XGXTClient

    print("== XGXT（综合测评） ==")
    xgxt = XGXTClient(cas)

    terms = xgxt.query_evaluation_terms()
    ok(f"测评学年学期: {[(t.year, t.term) for t in terms]}")
    pace()

    result = xgxt.query_evaluation_result()
    ok(
        f"综测成绩: 总分 {result.total_score}，"
        f"班级 {result.class_rank}/{result.class_size}，"
        f"年级 {result.grade_rank}/{result.grade_size}（{result.year_display}{result.term_display}）"
    )
    pace()

    details = xgxt.query_evaluation_indicators()
    ok(f"指标明细: {[(d.name, d.score) for d in details]}")
    pace()

    radar = xgxt.query_evaluation_radar()
    ok(f"雷达对比: 共 {len(radar)} 项，首项 {radar[0].name if radar else '-'}")
    pace()

    statics = xgxt.query_year_score_statics()
    ok(f"学年总览: {[(s.year_display, s.term_display, s.score or '未出分') for s in statics]}")
    pace()

    years = xgxt.query_academic_report_years()
    page = xgxt.query_academic_report()
    ok(f"学业成绩报告: 默认学年 {years.default_year}，共 {page.total_size} 条")


# ──────────────────────────────────────────────────────────────────────────── #
# 全量数据导出
# ──────────────────────────────────────────────────────────────────────────── #


def _to_jsonable(obj: Any, *, include_raw: bool = False) -> Any:
    """把 dataclass / list / dict 递归转成可 JSON 序列化的结构。

    默认只保留 SDK 封装字段；``include_raw=True`` 时附带接口原始响应
    （每个 dataclass 的 ``raw`` 字段）。
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _to_jsonable(getattr(obj, f.name), include_raw=include_raw)
            for f in dataclass_fields(obj)
            if include_raw or f.name != "raw"
        }
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x, include_raw=include_raw) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v, include_raw=include_raw) for k, v in obj.items()}
    return obj


def smoke_dump(cas: CASClient, term: str | None, output: Path, *, include_raw: bool = False) -> None:
    """把 SDK 全部只读方法的数据导出到 JSON 文件。

    尽力而为：单个方法失败（如「未到评教时间」）不中断，记入 ``errors`` 字段。
    会产生较多请求（约 40 个），调用间隔受 ``--pace`` 控制。
    """
    from ysu_sdk.jwxt import JWXTClient
    from ysu_sdk.xgxt import XGXTClient

    dump: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "term": term,
        "cas": {"authenticated": True},
        "jwxt": {},
        "xgxt": {},
        "errors": [],
    }

    def collect(section: str, key: str, fn: Callable[[], Any]) -> Any:
        try:
            value = fn()
        except Exception as exc:  # dump 尽力而为，单个失败不中断
            dump["errors"].append(
                {"method": f"{section}.{key}", "error": f"{type(exc).__name__}: {exc}"}
            )
            print(f"  [SKIP] {section}.{key}: {type(exc).__name__}: {exc}")
            pace()
            return None
        dump[section][key] = _to_jsonable(value, include_raw=include_raw)
        ok(f"{section}.{key}")
        pace()
        return value

    print("== 全量导出 ==")

    # ── JWXT ──
    jwxt = JWXTClient(cas)
    collect("jwxt", "student_info", jwxt.query_student_info)
    grades = collect("jwxt", "grades", lambda: jwxt.query_grades(term=term))
    collect("jwxt", "gpa_stats", jwxt.query_gpa_stats)
    collect("jwxt", "schedule", lambda: jwxt.query_schedule(term=term))
    collect("jwxt", "schedule_experimental", lambda: jwxt.query_schedule_experimental(term=term))
    collect("jwxt", "unscheduled_courses", lambda: jwxt.query_unscheduled_courses(term=term))
    collect("jwxt", "class_periods", jwxt.query_class_periods)
    collect("jwxt", "term_calendar", lambda: jwxt.query_term_calendar(term=term))
    collect("jwxt", "current_week", lambda: jwxt.query_current_week(term=term))
    collect("jwxt", "exams", lambda: jwxt.query_exams(term=term))
    collect("jwxt", "training_plan", jwxt.query_training_plan)
    collect("jwxt", "academic_completion", jwxt.query_academic_completion)
    collect("jwxt", "academic_warnings", jwxt.query_academic_warnings)
    collect("jwxt", "unscheduled_theory_courses", lambda: jwxt.query_unscheduled_theory_courses(term=term))
    collect("jwxt", "adjusted_courses", lambda: jwxt.query_adjusted_courses(term=term))
    collect("jwxt", "overall_adjustments", lambda: jwxt.query_overall_adjustments(term=term))
    collect("jwxt", "courses_on_date", lambda: jwxt.query_courses_on_date(term=term))
    collect("jwxt", "grade_years", jwxt.query_grade_years)
    collect("jwxt", "departments", jwxt.query_departments)
    collect("jwxt", "majors", jwxt.query_majors)
    class_list = collect("jwxt", "class_list", lambda: jwxt.query_class_list(term=term))
    if class_list:
        first_class = class_list[0]
        collect("jwxt", "class_schedule_sample",
                lambda: jwxt.query_class_schedule(first_class.class_id, term=term))
        collect("jwxt", "class_unscheduled_sample",
                lambda: jwxt.query_class_unscheduled_courses(first_class.class_id, term=term))
    collect("jwxt", "campuses", jwxt.query_campuses)
    collect("jwxt", "teaching_buildings", lambda: jwxt.query_teaching_buildings())
    classrooms = collect("jwxt", "classrooms", lambda: jwxt.query_classrooms(term=term, scheduled=True))
    if classrooms:
        first_room = classrooms[0]
        collect("jwxt", "classroom_schedule_sample",
                lambda: jwxt.query_classroom_schedule(first_room.code, term=term))

    # 成绩统计/分布/排名：以第一门成绩为样本，两种口径各调一次
    if grades:
        sample = grades[0]
        if sample.class_id:
            collect("jwxt", "grade_statistics_class",
                    lambda: jwxt.query_grade_statistics(term=term, class_id=sample.class_id))
            collect("jwxt", "grade_distribution_class",
                    lambda: jwxt.query_grade_distribution(term=term, class_id=sample.class_id))
            collect("jwxt", "grade_ranking_class",
                    lambda: jwxt.query_grade_ranking(term=term, class_id=sample.class_id))
        if sample.course_code:
            collect("jwxt", "grade_statistics_course",
                    lambda: jwxt.query_grade_statistics(term=term, course_code=sample.course_code))
            collect("jwxt", "grade_distribution_course",
                    lambda: jwxt.query_grade_distribution(term=term, course_code=sample.course_code))
            collect("jwxt", "grade_ranking_course",
                    lambda: jwxt.query_grade_ranking(term=term, course_code=sample.course_code))

    # 评教：只读部分（提交相关一律不碰）
    eval_types = collect("jwxt", "evaluation_types", lambda: jwxt.query_evaluation_types(term=term))
    if eval_types:
        first_type = eval_types[0]
        pending = collect(
            "jwxt", "evaluation_pending",
            lambda: jwxt.query_pending_evaluations(first_type.code, term=term),
        )
        if pending:
            task = pending[0]
            collect("jwxt", "evaluation_detail_sample",
                    lambda: jwxt.get_evaluation_detail(task.group_no, first_type.code))

    # ── XGXT ──
    xgxt = XGXTClient(cas)
    cp_terms = collect("xgxt", "evaluation_terms", xgxt.query_evaluation_terms) or []
    for t in cp_terms:
        key = f"{t.year}-{t.term}"
        collect("xgxt", f"evaluation_result[{key}]", lambda t=t: xgxt.query_evaluation_result(t.year, t.term))
        collect("xgxt", f"evaluation_indicators[{key}]", lambda t=t: xgxt.query_evaluation_indicators(t.year, t.term))
        collect("xgxt", f"evaluation_radar[{key}]", lambda t=t: xgxt.query_evaluation_radar(t.year, t.term))
    collect("xgxt", "year_score_statics", xgxt.query_year_score_statics)
    report_years = collect("xgxt", "academic_report_years", xgxt.query_academic_report_years)
    if report_years:
        for y in report_years.years:
            collect("xgxt", f"academic_report[{y.year}]",
                    lambda y=y: xgxt.query_academic_report(y.year))

    output.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {output}（{len(dump['errors'])} 个方法被跳过，详见 errors 字段）")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ysu-sdk 各模块活网冒烟（请求间隔默认 1s，勿调太低以免触发 WAF）"
    )
    parser.add_argument("module", choices=["cas", "jwxt", "xgxt", "all", "dump"])
    parser.add_argument("--pace", type=float, default=1.0, metavar="SECONDS",
                        help="每组请求之间的间隔秒数（默认 1.0）")
    parser.add_argument("--term", default=None,
                        help="JWXT 查询的学年学期代码（如 2025-2026-1），默认当前学期")
    parser.add_argument("--login", action="store_true",
                        help="忽略本地凭据，强制交互式登录")
    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="dump 模式的输出文件（默认 ysu_dump_<时间戳>.json）")
    parser.add_argument("--raw", action="store_true",
                        help="dump 模式附带接口原始响应（raw 字段），默认只导出封装字段")
    args = parser.parse_args()

    global _pace_seconds
    _pace_seconds = max(args.pace, 0.0)

    try:
        cas = build_cas(force_login=args.login)
        pace()
        if args.module in ("cas", "all"):
            smoke_cas(cas)
            pace()
        if args.module in ("jwxt", "all"):
            smoke_jwxt(cas, args.term)
            pace()
        if args.module in ("xgxt", "all"):
            smoke_xgxt(cas)
        if args.module == "dump":
            output = Path(args.output) if args.output else Path(
                f"ysu_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            smoke_dump(cas, args.term, output, include_raw=args.raw)
    except CASError as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
