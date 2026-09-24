"""ysu_sdk.xkjs — 创新创业竞赛管理系统学生/教师查询。

与 scxt 同为南京先极科技的 ASP.NET MVC 系统，**认证路径完全一致**：
本系统不是直接注册的 CAS service，必须经双创管理一体化信息平台
（ysu_pt）中转：

1. ``cas.authorize(ysu_pt/UnifiedAuth/CASLogin)`` —— 平台会话；
2. GET 平台子系统桥 ``AccessSubsystem/{guid}``（带 Referer）—— 302 出
   access 票据 URL；
3. GET 票据 URL（带 Referer）—— 302 到 LoginRole，ysu_xkjs 会话就绪。

数据面与 scxt 不同：学生/教师搜索是 POST AJAX 端点，返回 HTML 片段
（``<table>`` 的 ``<td>`` 带 ``data-name``/``data-value`` 键值对），
而非整页渲染。

只读接口：学生搜索、教师搜索。报名/审核等写操作不封装。
"""

from ysu_sdk.xkjs.client import XkjsClient
from ysu_sdk.xkjs.exceptions import (
    XkjsError,
    XkjsNotLoggedInError,
    XkjsProtocolError,
)
from ysu_sdk.xkjs.types import Page, Student, Teacher

__all__ = [
    "Page",
    "Student",
    "Teacher",
    "XkjsClient",
    "XkjsError",
    "XkjsNotLoggedInError",
    "XkjsProtocolError",
]
