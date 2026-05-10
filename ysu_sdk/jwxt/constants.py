"""教务系统常量。"""

from __future__ import annotations

JWXT_BASE_URL: str = "https://jwxt.ysu.edu.cn"
JWXT_APP_BASE: str = f"{JWXT_BASE_URL}/jwapp/sys"

# 各应用入口 ID（即 EMAP appShow.do?id= 的参数，用于触发该应用的 _WEU 下发）
APP_IDS = {
    "cjcx": "d71f7b57b4f348368f06c3e9a2a0988f",                # 成绩查询
    "wdkb": "377b6493556d4f0b86d116ca00cd1b6e",                # 我的课表（理论课）
    "wdkb_sy": "f5bc7667030c4af9b31f212b659a1f62",             # 我的课表（实验课）
    "xsfacx": "9ed0501165cd47209b105356cfa2e17a",              # 培养方案查询
    "xsjbxxgl": "eb858365ce9a44b283b2d365a392ad47",            # 学生基本信息管理
    "xywccx": "2d855fd0484047518ac8087912ca71e0",              # 学业完成查询
    "studentWdksapApp": "b5f84a8ed330481ca1efd1753d95a504",    # 我的考试安排（兼当前学年学期来源）
    "xyyj": "4855b7a54e50498580017c61a1dc94c8",                # 学业预警
    "kcbcx": "74506a67ea1c4bf3bb54eefa6e196779",               # 全校课表查询（未使用）
    "pjapp": "5db54fd366204007af34267396897b24",               # 学生评教
}

# API 路径模板（相对 JWXT_APP_BASE，最终 URL 由 _build_api_url 拼出）
API_PATHS = {
    # —— 成绩查询 ——
    "cjcx": "cjcx/modules/cjcx/xscjcx.do",                                       # 学生成绩
    "cjcx_gpa": "cjcx/modules/cjcx/cxzxfaxfjd.do",                               # 在校学分加权积点（GPA / 学分统计）

    # —— 课表 ——
    "wdkb": "wdkb/modules/xskcb/cxxszhxqkb.do",                                  # 我的课表（理论课，按学年学期）
    "wdkb_wpkc": "wdkb/modules/xskcb/xswpkc.do",                                 # 学生未排课程（未使用）
    "wdkb_dkkc": "wdkb/modules/xskcb/xsdkkc.do",                                 # 学生调课课程（未使用）
    "wdkb_sy": "syxkjg/modules/wdkb/cxxskb.do",                                  # 我的课表（实验课）
    "wdkb_sy_unscheduled": "syxkjg/modules/wdkb/cxxsllsywpk.do",                 # 学生理论实验未排课
    "jc": "wdkb/modules/jshkcb/jc.do",                                           # 节次配置（每节课的起止时间）
    "dqzc": "wdkb/modules/jshkcb/dqzc.do",                                       # 指定日期对应的教学周次与星期
    "cxxljc": "wdkb/modules/xskcb/cxxljc.do",                                    # 学期校历配置（起始日期、总周次、教学周次等）
    "kcbcx": "kcbcx/KbcxController/querybjkb.do",                                # 全校班级课表查询（未使用）

    # —— 学籍 / 培养方案 / 学业 ——
    "xsjbxx": "xsjbxxgl/modules/xsjbxx/cxxsjbxxlb.do",                           # 学生基本信息
    "xywc": "xywccx/modules/xywccx/cxxsscfa.do",                                 # 学业完成（学生所选方案完成情况）
    "pyfa": "xsfacx/modules/pyfacxepg/grpyfacx.do",                              # 个人培养方案（第一步：拿到 PYFADM）
    "pyfa_courses": "jwpubapp/modules/pyfa/kzkccx.do",                           # 培养方案下的课程列表（第二步：传 PYFADM）
    "xyyj": "xyyj/modules/xsxyyjjg/cxxsyjpcjg.do",                               # 学业预警结果

    # —— 考试 ——
    "wdksap": "studentWdksapApp/WdksapController/cxxsksap.do",                   # 我的考试安排
    "wdksap_dqxnxq": "studentWdksapApp/modules/wdksap/dqxnxq.do",                # 当前学年学期代码（被多处复用作为默认 term）

    # —— 学生评教 ——
    "pjlx": "pjapp/api/wdpj/getPjlx.do",                                         # 评教类型及待评数量
    "dpwj": "pjapp/api/wdpj/getDpwj.do",                                         # 待评问卷列表
    "wjtxxx": "pjapp/api/wdpj/getWjtxxx.do",                                     # 问卷题项详情（取题目）
    "calculate_score": "pjapp/api/wdpj/calculateQuestionnaireAnswerScore.do",    # 答案预检 / 计算得分（提交前调用）
    "commit_answer": "pjapp/api/wdpj/commitQuestionnaireAnswer.do",              # 提交评教答案
}
