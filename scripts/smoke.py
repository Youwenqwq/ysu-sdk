#!/usr/bin/env python3
"""各模块活网冒烟脚本（手动运行，非自动化测试）。

用法::

    uv run python scripts/smoke.py cas              # 只测 CAS
    uv run python scripts/smoke.py jwxt             # 只测教务
    uv run python scripts/smoke.py xgxt             # 只测学工（综合测评）
    uv run python scripts/smoke.py meter --account <学工号>  # 无需 CAS
    uv run python scripts/smoke.py ecard            # 一卡通余额
    uv run python scripts/smoke.py epay             # 缴费历史与官方待缴
    uv run python scripts/smoke.py all --account <学工号> --pace 1.5
    uv run python scripts/smoke.py dump --account <学工号>  # 全量 JSON
    uv run python scripts/smoke.py dump --sections ecard,epay -o fees.json
    uv run python scripts/smoke.py dump --sections meter --account <学工号>
    uv run python scripts/smoke_fees_offline.py      # 无网络的协议回归

认证::

    默认读取 ``~/.config/ysu-sdk/cas.json``；文件不存在或已失效时进入
    交互式登录（验证码图片写入 /tmp，MFA 走终端输入），成功后自动保存。
    meter 以及仅导出 meter 时不读取 CAS 凭据、不触发登录。
    包含 meter 的模式必须提供 --account；用电区间默认截至今天的近 30 天，
    可通过 --start-date / --end-date 指定。仅查询本人或已获授权的账号。

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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from ysu_sdk.cas import (
    CASClient,
    CASCredential,
    CASError,
    CaptchaChallenge,
    MFAChallenge,
)
from ysu_sdk.ecard import EcardError
from ysu_sdk.epay import EpayError
from ysu_sdk.meter import MeterError

CAPTCHA_PATH = Path("/tmp/ysu_sdk_captcha.png")
DUMP_SECTIONS = {"jwxt", "xgxt", "ldxt", "scxt", "meter", "ecard", "epay"}

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
# 移动教务（课程签到）
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_mobile(cas: CASClient) -> None:
    from ysu_sdk.jwxt import JWXTClient
    from ysu_sdk.jwmobile import MobileClient

    print("== 移动教务（jwmobile） ==")
    mobile = MobileClient(cas)
    mobile._ensure_authorized()
    ok("移动端认证（JWT 捕获）")
    pace()

    jwxt = JWXTClient(cas)
    cw = jwxt.query_current_week()
    ok(f"当前周次: 第{cw.week}周 周{cw.weekday}")
    pace()

    today = jwxt.query_courses_on_date()
    if not today:
        ok("今天无课（假期），跳过课程活动查询")
        return
    for c in today[:3]:
        lesson = mobile.query_current_lesson_for_course(c, cw.week)
        ok(f"{c.name}: 活动数={len(lesson.activities)}")
        pace()


# ──────────────────────────────────────────────────────────────────────────── #
# 劳动教育（ldxt）
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_ldxt(cas: CASClient) -> None:
    from ysu_sdk.ldxt import LdxtClient

    print("== 劳动教育系统（ldxt） ==")
    ldxt = LdxtClient(cas)

    records = ldxt.query_labor_records()
    total = sum(r.hours or 0 for r in records)
    ok(f"劳动记录: {len(records)} 条, 时长合计={total}h")
    pace()

    summary = ldxt.query_labor_summary()
    ok(f"学分汇总: {summary.name} 时长={summary.total_hours}h 学分={summary.total_credits}")
    pace()

    acts = ldxt.query_enrollable_activities()
    ok(f"活动报名列表: {len(acts)} 条")


# ──────────────────────────────────────────────────────────────────────────── #
# 双创学分（scxt）
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_scxt(cas: CASClient) -> None:
    from ysu_sdk.scxt import ScxtClient

    print("== 创新创业学分认定系统（scxt） ==")
    scxt = ScxtClient(cas)

    decls = scxt.query_credit_declarations()
    ok(f"申报记录: {len(decls)} 条, 分值合计={sum(d.score or 0 for d in decls)}")
    pace()

    summary = scxt.query_credit_summary()
    ok(f"学分汇总: {summary.name} 总学分={summary.total_credits} 成绩={summary.grade}")
    pace()

    records = scxt.query_all_credit_records()
    ok(f"全部认定记录: {len(records)} 条")
    pace()

    comps = scxt.query_competitions()
    ok(f"竞赛库: {comps.total_records} 条 {comps.total_pages} 页")


# ──────────────────────────────────────────────────────────────────────────── #
# 空调电费、一卡通与缴费（全部只读）
# ──────────────────────────────────────────────────────────────────────────── #


def smoke_meter(account: str, start_date: str, end_date: str) -> None:
    from ysu_sdk.meter import MeterClient

    print("== 空调电费（meter） ==")
    meter = MeterClient(account)
    room = meter.query_room()
    if room is None:
        ok("未绑定房间或缺少房间查询凭据，跳过后续用电查询")
        return
    ok(f"绑定房间: {room.room_full_name}")
    pace()

    overview = meter.query_overview(room.room_verify)
    if overview is None:
        print("  [SKIP] 电表概览不可用（内层业务 result 非零）")
    else:
        ok(f"电表概览: {len(overview.meters)} 路")
        for device in overview.meters:
            print(f"    {device.device_name}: 剩余={device.remaining}度 "
                  f"今日={device.today_use}度 电价={device.price}元/度 {device.line_desc}")
            for month in device.month_use:
                print(f"      {month.month}: {month.use}度")
    pace()

    daily = meter.query_daily_use(room.room_verify, start_date, end_date)
    ok(f"日用量 {start_date} 至 {end_date}: {len(daily)} 条，"
       f"合计={sum(day.use for day in daily):.2f}度")
    pace()

    recharges = meter.query_recharges(room.room_verify)
    ok(f"充值历史（只读）: {len(recharges)} 条，"
       f"电量={sum(record.amount for record in recharges):.2f}度，"
       f"金额={sum(record.fare for record in recharges):.2f}元")


def smoke_ecard(cas: CASClient) -> None:
    from ysu_sdk.ecard import EcardClient

    print("== 一卡通（ecard） ==")
    balance = EcardClient(cas).query_balance()
    if balance is None:
        ok("暂无一卡通余额数据（不代表零余额）")
        return
    ok(f"余额={balance.balance:.2f}元 卡号={balance.card_num} "
       f"有效期={balance.available_date} 状态={balance.card_status_name}")
    print(f"    可用月份: {', '.join(balance.months)}")


def smoke_epay(cas: CASClient) -> None:
    from ysu_sdk.epay import EpayClient

    print("== 缴费信息（epay） ==")
    payments = EpayClient(cas).query_payments()
    ok(f"付款记录: {len(payments.records)} 条")
    for record in payments.records:
        print(f"    {record.pay_name}: {record.amount_n:.2f}元 "
              f"状态={record.record_status} 完成时间={record.over_time or '无'}")
    ok(f"官方待缴: {len(payments.unpaid)} 笔，"
       f"合计={sum(record.amount_n for record in payments.unpaid):.2f}元")
    for record in payments.unpaid:
        print(f"    待缴: {record.pay_name} {record.amount_n:.2f}元")


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


def smoke_dump(
    cas: CASClient | None,
    term: str | None,
    output: Path,
    *,
    account: str | None,
    start_date: str,
    end_date: str,
    include_raw: bool = False,
    sections: set[str] | None = None,
) -> None:
    """把 SDK 全部只读方法的数据导出到 JSON 文件。

    尽力而为：单个方法失败（如「未到评教时间」）不中断，记入 ``errors`` 字段。
    请求数量取决于所选板块，调用间隔受 ``--pace`` 控制。
    """
    from ysu_sdk.jwxt import JWXTClient
    from ysu_sdk.ldxt import LdxtClient
    from ysu_sdk.scxt import ScxtClient
    from ysu_sdk.xgxt import XGXTClient
    from ysu_sdk.ecard import EcardClient
    from ysu_sdk.epay import EpayClient
    from ysu_sdk.meter import MeterClient

    dump: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "term": term,
        "cas": {"authenticated": True if cas is not None else None},
        "jwxt": {},
        "xgxt": {},
        "ldxt": {},
        "scxt": {},
        "meter": {},
        "ecard": {},
        "epay": {},
        "errors": [],
    }

    def collect(section: str, key: str, fn: Callable[[], Any]) -> Any:
        if sections is not None and section not in sections:
            return None
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
    if sections is None or "jwxt" in sections:
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
        collect("jwxt", "makeup_exam_batches", lambda: jwxt.query_makeup_exam_batches())
        collect("jwxt", "makeup_exam_courses", lambda: jwxt.query_makeup_exam_courses())
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
    if sections is None or "xgxt" in sections:
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

    # ── Ldxt（劳动教育）──
    if sections is None or "ldxt" in sections:
        ldxt = LdxtClient(cas)
        collect("ldxt", "labor_records", ldxt.query_labor_records)
        collect("ldxt", "labor_summary", ldxt.query_labor_summary)
        collect("ldxt", "enrollable_activities", ldxt.query_enrollable_activities)

    # ── Scxt（双创学分）──
    if sections is None or "scxt" in sections:
        scxt = ScxtClient(cas)
        collect("scxt", "credit_declarations", scxt.query_credit_declarations)
        collect("scxt", "credit_summary", scxt.query_credit_summary)
        collect("scxt", "credit_batches", scxt.query_credit_batches)
        collect("scxt", "credit_records_all", scxt.query_all_credit_records)
        collect("scxt", "competitions_page1", scxt.query_competitions)
        collect("scxt", "activities_page1", scxt.query_activities)

    # ── 空调电费 ──
    if sections is None or "meter" in sections:
        if not account:
            raise ValueError("空调电费查询需要提供学工号")
        meter = MeterClient(account)
        dump["meter"]["date_range"] = {"start_date": start_date, "end_date": end_date}
        room = collect("meter", "room", meter.query_room)
        if room is not None:
            collect("meter", "overview", lambda: meter.query_overview(room.room_verify))
            collect("meter", "daily_use",
                    lambda: meter.query_daily_use(room.room_verify, start_date, end_date))
            collect("meter", "recharges", lambda: meter.query_recharges(room.room_verify))

    # ── 一卡通与缴费 ──
    if sections is None or "ecard" in sections:
        ecard = EcardClient(cas)
        collect("ecard", "balance", ecard.query_balance)
    if sections is None or "epay" in sections:
        epay = EpayClient(cas)
        collect("epay", "payments", epay.query_payments)

    output.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {output}（{len(dump['errors'])} 个方法被跳过，详见 errors 字段）")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ysu-sdk 各模块活网冒烟（请求间隔默认 1s，勿调太低以免触发 WAF）"
    )
    parser.add_argument("module", choices=[
        "cas", "jwxt", "xgxt", "mobile", "ldxt", "scxt",
        "meter", "ecard", "epay", "all", "dump",
    ])
    parser.add_argument("--pace", type=float, default=1.0, metavar="SECONDS",
                        help="每组请求之间的间隔秒数（默认 1.0）")
    parser.add_argument("--term", default=None,
                        help="JWXT 查询的学年学期代码（如 2025-2026-1），默认当前学期")
    parser.add_argument("--login", action="store_true",
                        help="忽略本地凭据，强制交互式登录")
    parser.add_argument("--account", default=None, metavar="ID",
                        help="空调电费查询的学工号（meter、all 或包含 meter 的 dump 必填）")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                        help="日用量起始日期（默认结束日期前 29 天）")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                        help="日用量结束日期（默认今天）")
    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="dump 模式的输出文件（默认 ysu_dump_<时间戳>.json）")
    parser.add_argument("--raw", action="store_true",
                        help="dump 模式附带接口原始响应（raw 字段），默认只导出封装字段")
    parser.add_argument("--sections", default=None, metavar="LIST",
                        help="dump 板块，逗号分隔：jwxt,xgxt,ldxt,scxt,meter,ecard,epay（默认全部）")
    args = parser.parse_args()
    sections = None
    if args.module == "dump" and args.sections is not None:
        sections = {s.strip() for s in args.sections.split(",") if s.strip()}
        if not sections or sections - DUMP_SECTIONS:
            parser.error("--sections 必须是有效板块列表：" + ",".join(sorted(DUMP_SECTIONS)))
    needs_meter = args.module in ("meter", "all") or (
        args.module == "dump" and (sections is None or "meter" in sections)
    )
    account = args.account.strip() if args.account else None
    if needs_meter and not account:
        parser.error("包含 meter 的查询必须提供 --account <学工号>")
    end_date = args.end_date or date.today()
    start_date = args.start_date or end_date - timedelta(days=29)
    if start_date > end_date:
        parser.error("--start-date 不能晚于 --end-date")
    requires_cas = args.module != "meter" and not (
        args.module == "dump" and sections == {"meter"}
    )

    global _pace_seconds
    _pace_seconds = max(args.pace, 0.0)

    try:
        cas = build_cas(force_login=args.login) if requires_cas else None
        if requires_cas:
            pace()
        if args.module in ("cas", "all"):
            smoke_cas(cas)
            pace()
        if args.module in ("jwxt", "all"):
            smoke_jwxt(cas, args.term)
            pace()
        if args.module in ("xgxt", "all"):
            smoke_xgxt(cas)
            pace()
        if args.module in ("mobile", "all"):
            smoke_mobile(cas)
            pace()
        if args.module in ("ldxt", "all"):
            smoke_ldxt(cas)
            pace()
        if args.module in ("scxt", "all"):
            smoke_scxt(cas)
            pace()
        if needs_meter and args.module != "dump":
            smoke_meter(account, start_date.isoformat(), end_date.isoformat())
            pace()
        if args.module in ("ecard", "all"):
            smoke_ecard(cas)
            pace()
        if args.module in ("epay", "all"):
            smoke_epay(cas)
            pace()
        if args.module == "dump":
            output = Path(args.output) if args.output else Path(
                f"ysu_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            smoke_dump(
                cas, args.term, output, account=account,
                start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                include_raw=args.raw, sections=sections,
            )
    except (CASError, MeterError, EcardError, EpayError) as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
