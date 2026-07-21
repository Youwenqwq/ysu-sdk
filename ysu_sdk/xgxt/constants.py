"""学工系统（综合测评）常量。"""

from __future__ import annotations

XGXT_BASE_URL: str = "https://xgxt.ysu.edu.cn"
XGXT_APP_BASE: str = f"{XGXT_BASE_URL}/xsfw/sys/zhcptybbapp"

# CAS service 入口：authorize 后落在综合测评应用首页。
# 与门户实际跳转一致——注意 CAS 侧登记的 service 是 http 方案。
ZHCP_SERVICE_URL: str = "http://xgxt.ysu.edu.cn/xsfw/sys/zhcptybbapp/*default/index.do"

# 应用标识
APP_NAME: str = "zhcptybbapp"
EMAP_APP_ID: str = "5275772372599202"  # EMAP 数字应用 ID（getAppConfig 的 appId 参数）

# 角色上下文握手端点（与业务 API 不同，在 swpubapp/funauthapp 下）
# 业务 API 要求会话先绑定应用角色（如「学生组」），否则一律 404——与 jwxt 的
# _WEU 门槛同构，只是这里通过显式的角色设置完成。
APP_CONFIG_URL: str = f"{XGXT_BASE_URL}/xsfw/sys/swpubapp/indexmenu/getAppConfig.do"
SET_ROLE_URL: str = f"{XGXT_BASE_URL}/xsfw/sys/swpubapp/userinfo/setXgCommonAppRole.do"
CHANGE_ROLE_URL_TEMPLATE: str = (
    f"{XGXT_BASE_URL}/xsfw/sys/funauthapp/api/changeAppRole/{APP_NAME}/{{role_id}}.do"
)

# API 路径模板（相对 XGXT_APP_BASE，最终 URL 由 _build_api_url 拼出）
API_PATHS = {
    # —— 综测成绩 ——
    "cpxnxq": "modules/evaluationApplyController/getCpxnxq.do",                    # 可查询的测评学年学期列表
    "cj_by_xn": "modules/evaluationApplyController/getEvaluationResultsByXn.do",   # 指定学年学期的综测成绩与排名
    "year_cj_static": "modules/evaluationApplyController/getYearCjStatic.do",      # 各学年学期综测分数总览（我和自己比一比）
    "redar": "modules/evaluationApplyController/getRedar.do",                      # 指标雷达对比（我和别人比一比）
    "zbxx": "modules/zccj/tjsqhqxqzbxx.do",                                        # 指标得分明细分页（加分/扣分/互评等）

    # —— 学业成绩报告（综测成绩页「学业成绩」弹窗） ——
    "five_years": "modules/evaluationBjhpController/getFiveYears.do",              # 学业成绩报告可选学年
    "mr_xn": "modules/evaluationBjhpController/getMrXn.do",                        # 学业成绩报告默认学年
    "xycjbg": "modules/public/xycjbg.do",                                          # 学业成绩报告分页列表
}
