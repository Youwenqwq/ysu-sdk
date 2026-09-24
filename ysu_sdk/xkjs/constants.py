"""ysu_sdk.xkjs 的地址常量。

系统部署在裸 IP + 路径前缀下（无独立域名、无 HTTPS），所有路径都在
``/ysu_xkjs`` 之下；认证经平台 ``/ysu_pt`` 中转。
"""

# 平台（双创管理一体化信息平台）——CAS service 注册在平台侧
PT_BASE_URL = "http://202.206.247.49/ysu_pt"
# 平台的 CAS 票据消费端点（authorize 的 service URL）
PT_CAS_LOGIN_PATH = "/UnifiedAuth/CASLogin"
# 平台 → 子系统桥（创新创业竞赛管理系统的固定 guid）
SUBSYSTEM_BRIDGE_PATH = (
    "/System/Platform/AccessSubsystem/e309020b-113b-405a-8489-62910994b2a7"
)
# 桥接请求需要的 Referer（缺了平台/子系统会拒绝）
PT_HOME_URL = f"{PT_BASE_URL}/System/Home/Index"

# 竞赛管理系统本体
BASE_URL = "http://202.206.247.49/ysu_xkjs"

LOGIN_PATH = "/System/User/Login"
HOME_PATH = "/System/Home/Index"
# 竞赛报名「添加学生」的学生搜索（POST AJAX，返回 HTML 片段）
SEARCH_STUDENT_PATH = "/CompetitionStudent/Apply/SearchStudentPageList"
# 竞赛报名「添加指导教师」的教师搜索（POST AJAX，返回 HTML 片段）
SEARCH_TEACHER_PATH = "/CompetitionStudent/Apply/SearchTeacherPageList"
