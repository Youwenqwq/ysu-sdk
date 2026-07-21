"""ysu_sdk.scxt 的地址常量。

系统部署在裸 IP + 路径前缀下（无独立域名、无 HTTPS），所有路径都在
``/ysu_xf`` 之下；认证经平台 ``/ysu_pt`` 中转。
"""

# 平台（双创管理一体化信息平台）——CAS service 注册在平台侧
PT_BASE_URL = "http://202.206.247.49/ysu_pt"
# 平台的 CAS 票据消费端点（authorize 的 service URL）
PT_CAS_LOGIN_PATH = "/UnifiedAuth/CASLogin"
# 平台 → 子系统桥（双创学分认定系统的固定 guid）
SUBSYSTEM_BRIDGE_PATH = (
    "/System/Platform/AccessSubsystem/e3090712-0609-404a-ade1-6a76ad8d90b1"
)
# 桥接请求需要的 Referer（缺了平台/子系统会拒绝）
PT_HOME_URL = f"{PT_BASE_URL}/System/Home/Index"

# 学分认定系统本体
BASE_URL = "http://202.206.247.49/ysu_xf"

LOGIN_PATH = "/System/User/Login"
HOME_PATH = "/System/Home/Index"
DECLARE_PATH = "/XueFen/Declare/Index"  # 我的申报记录
SUMMARY_PATH = "/XueFen/Summary"  # 学分汇总（认定记录，按批次过滤）
SUMMARY_QUERY_PATH = "/XueFen/SummaryQuery/Index"  # 学生学分汇总
COMPETITION_PATH = "/JingSai/Declare/Index"  # 竞赛库
ACTIVITY_PATH = "/HuoDongKu/Declare/Index"  # 活动库

DEFAULT_PAGE_SIZE = 200
