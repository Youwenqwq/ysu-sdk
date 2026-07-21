"""ysu_sdk.scxt — 创新创业学分认定系统只读查询。

与 ldxt 同为南京先极科技的 ASP.NET MVC 服务端渲染系统，但**认证路径
完全不同**：本系统不是直接注册的 CAS service（服务端 CAS 配置甚至残留
``cas.example.com`` 占位符），必须经双创管理一体化信息平台（ysu_pt）中转：

1. ``cas.authorize(ysu_pt/UnifiedAuth/CASLogin)`` —— 平台会话（``.loginAuth``）；
2. GET 平台子系统桥 ``AccessSubsystem/{guid}``（带 Referer）—— 302 出
   access 票据 URL；
3. GET 票据 URL（带 Referer）—— 302 到 LoginRole，ysu_xf 会话就绪。

数据面与 ldxt 同构：整页 GET + HTML 表格（共享 ``ysu_sdk._table`` 解析）。
批次筛选注意：服务端默认只给当前批次（2026），空 BatchID 不等于全部批次，
要全量需遍历批次列表。

只读接口：我的申报记录、学分汇总（认定记录）、学生学分总表、竞赛库、
活动库。申报/审核等写操作不封装。
"""

from ysu_sdk.scxt.client import ScxtClient
from ysu_sdk.scxt.exceptions import (
    ScxtError,
    ScxtNotLoggedInError,
    ScxtProtocolError,
)
from ysu_sdk.scxt.types import (
    CatalogPage,
    Competition,
    CreditBatch,
    CreditDeclaration,
    CreditRecord,
    CreditSummary,
    LibraryActivity,
)

__all__ = [
    "CatalogPage",
    "Competition",
    "CreditBatch",
    "CreditDeclaration",
    "CreditRecord",
    "CreditSummary",
    "LibraryActivity",
    "ScxtClient",
    "ScxtError",
    "ScxtNotLoggedInError",
    "ScxtProtocolError",
]
