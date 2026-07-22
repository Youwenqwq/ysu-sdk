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
    "kcbcx": "74506a67ea1c4bf3bb54eefa6e196779",               # 全校课表查询
    "bkbl": "d4145d3276744d9da8bf609da4702ae8",                # 补考与结业生考试办理
    "pjapp": "5db54fd366204007af34267396897b24",               # 学生评教
}

# 全校课表应用首页（代码表端点的 Referer 校验值）
KCBCX_INDEX_URL: str = f"{JWXT_APP_BASE}/kcbcx/*default/index.do"

# API 路径模板（相对 JWXT_APP_BASE，最终 URL 由 _build_api_url 拼出）
API_PATHS = {
    # —— 成绩查询 ——
    "cjcx": "cjcx/modules/cjcx/xscjcx.do",                                       # 学生成绩
    "cjcx_gpa": "cjcx/modules/cjcx/cxzxfaxfjd.do",                               # 在校学分加权积点（GPA / 学分统计）
    "jxbcjtjcx": "cjcx/modules/cjcx/jxbcjtjcx.do",                               # 成绩统计（教学班/课程总体的最高分、最低分、平均分）
    "jxbcjfbcx": "cjcx/modules/cjcx/jxbcjfbcx.do",                               # 成绩分布（教学班/课程总体的等级人数分布）
    "jxbxspmcx": "cjcx/modules/cjcx/jxbxspmcx.do",                               # 学生成绩排名（教学班内 / 课程总体）

    # —— 课表 ——
    "wdkb": "wdkb/modules/xskcb/cxxszhxqkb.do",                                  # 我的课表（理论课，按学年学期）
    "wdkb_wpkc": "wdkb/modules/xskcb/xswpkc.do",                                 # 学生未排课程（理论课表口径）
    "wdkb_dkkc": "wdkb/modules/xskcb/xsdkkc.do",                                 # 学生调课课程
    "ztdkjl": "wdkb/modules/jshkcb/cxztdkjl.do",                                 # 整体调课记录
    "wdkb_sy": "syxkjg/modules/wdkb/cxxskb.do",                                  # 我的课表（实验课）
    "wdkb_sy_unscheduled": "syxkjg/modules/wdkb/cxxsllsywpk.do",                 # 学生理论实验未排课
    "jc": "wdkb/modules/jshkcb/jc.do",                                           # 节次配置（每节课的起止时间）
    "dqzc": "wdkb/modules/jshkcb/dqzc.do",                                       # 指定日期对应的教学周次与星期
    "cxxljc": "wdkb/modules/xskcb/cxxljc.do",                                    # 学期校历配置（起始日期、总周次、教学周次等）
    "kcbcx": "kcbcx/KbcxController/querybjkb.do",                                # 全校班级课表（requestParamStr 风格）
    "kcbcx_tk": "kcbcx/KbcxController/querybjkbtk.do",                           # 班级课表调课记录
    "kcbcx_wpk": "kcbcx/KbcxController/querybjkbwpk.do",                          # 班级课表未排课
    "bjcx": "kcbcx/modules/bjkcb/bjcx.do",                                        # 班级列表（级联筛选：年级/院系/专业）
    "jscx": "kcbcx/modules/jskcb/jscx.do",                                        # 教室列表（querySetting 风格筛选）
    "jaskb": "kcbcx/KbcxController/queryjaskb.do",                                # 教室课表
    "jaskb_tk": "kcbcx/KbcxController/queryjaskbtk.do",                           # 教室课表调课记录

    # —— 代码表（级联筛选的字典数据源；绝对路径，不随 JWXT_APP_BASE 拼接） ——
    "code_nj": "/jwapp/code/c1e19f4d-94e0-464f-bb7b-d70d0517150c.do",            # 年级
    "code_yxdm": "/jwapp/code/49a86828-aef9-4a48-b26f-01149dac72d7.do",          # 院系
    "code_zydm": "/jwapp/code/87a9226a-6e44-44cc-9743-c081a8f9cb9b.do",          # 专业（otherFields.YXDM 为父级院系）
    "code_xxxq": "/jwapp/code/83a986fc-e677-400e-99a4-c7bb39c2ca35.do",          # 校区
    "code_jxldm": "/jwapp/code/82101c45-a7d3-414d-988b-24744db9f5ea.do",         # 教学楼

    # —— 学籍 / 培养方案 / 学业 ——
    "xsjbxx": "xsjbxxgl/modules/xsjbxx/cxxsjbxxlb.do",                           # 学生基本信息
    "xywc": "xywccx/modules/xywccx/cxxsscfa.do",                                 # 学业完成（学生所选方案完成情况）
    "pyfa": "xsfacx/modules/pyfacxepg/grpyfacx.do",                              # 个人培养方案（第一步：拿到 PYFADM）
    "pyfa_courses": "jwpubapp/modules/pyfa/kzkccx.do",                           # 培养方案下的课程列表（第二步：传 PYFADM）
    "xyyj": "xyyj/modules/xsxyyjjg/cxxsyjpcjg.do",                               # 学业预警结果

    # —— 考试 ——
    "wdksap": "studentWdksapApp/WdksapController/cxxsksap.do",                   # 我的考试安排
    "wdksap_dqxnxq": "studentWdksapApp/modules/wdksap/dqxnxq.do",                # 当前学年学期代码（被多处复用作为默认 term）

    # —— 补考办理 ——
    "bkxtcs": "bkbl/modules/bkbm/cxxtcs.do",                                     # 补考报名学年学期参数
    "bkkspc": "bkbl/modules/bkbm/cxbkkspc.do",                                   # 补考考试批次
    "bkbmmx": "bkbl/modules/bkbm/cxbkbmmx.do",                                   # 补考报名明细（可报名/已报名课程）
    "xgksrwxs": "bkbl/modules/bkbm/xgksrwxs.do",                                 # 补考报名/取消报名（写，结果以 extParams 为准）

    # —— 学生评教 ——
    "pjlx": "pjapp/api/wdpj/getPjlx.do",                                         # 评教类型及待评数量
    "dpwj": "pjapp/api/wdpj/getDpwj.do",                                         # 待评问卷列表
    "wjtxxx": "pjapp/api/wdpj/getWjtxxx.do",                                     # 问卷题项详情（取题目）
    "calculate_score": "pjapp/api/wdpj/calculateQuestionnaireAnswerScore.do",    # 答案预检 / 计算得分（提交前调用）
    "commit_answer": "pjapp/api/wdpj/commitQuestionnaireAnswer.do",              # 提交评教答案
}
