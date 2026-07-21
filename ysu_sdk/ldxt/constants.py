"""ysu_sdk.ldxt 的地址常量。"""

BASE_URL = "https://ldxt.ysu.edu.cn"

# 登录页（未认证请求会被 302 到这里）
LOGIN_PATH = "/System/User/Login"
# CAS 单点登录端点（authorize 的 service URL，也是登录确认 POST 的目标）
SSO_PATH = "/About/UnifiedAuthenticationLogin"
# 主页（角色落地 URL 缺失时的后备）
HOME_PATH = "/System/Home/Index"
# 时长汇总（劳动记录列表）
SUMMARY_PATH = "/XueFen/Summary"
# 学生学分汇总
SUMMARY_QUERY_PATH = "/XueFen/SummaryQuery/Index"
# 活动报名列表
ENROLL_PATH = "/XueFen/Enroll/Index"

# 列表页可选每页 20/50/100/200，默认拉最大档避免翻页
DEFAULT_PAGE_SIZE = 200
