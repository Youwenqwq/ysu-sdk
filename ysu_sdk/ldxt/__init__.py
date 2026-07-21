"""ysu_sdk.ldxt — 劳动教育实践课程管理平台只读查询。

南京先极科技的 ASP.NET MVC 服务端渲染系统，与 EMAP 技术栈无关：

- 认证：CAS 单点登录（``cas.authorize`` 标准出票流程），会话凭证为
  ``ASP.NET_SessionId`` + forms-auth cookie；
- 数据：整页 GET + 查询字符串过滤，响应为服务端渲染的 HTML 表格，
  用标准库 ``html.parser`` 抽取，不引入第三方解析依赖；
- 导出端点为旧版 OLE2 ``.xls``（二进制），SDK 不使用。

只读接口：

- 劳动记录（时长汇总页列表）：学期/活动/大类/学院/时间/时长/状态；
- 学生学分汇总：累计劳动时长与总学分；
- 活动报名列表：当前可报名活动（报名本身是写操作，不封装）。
"""

from ysu_sdk.ldxt.client import LdxtClient
from ysu_sdk.ldxt.exceptions import (
    LdxtError,
    LdxtNotLoggedInError,
    LdxtProtocolError,
)
from ysu_sdk.ldxt.types import EnrollableActivity, LaborRecord, LaborSummary

__all__ = [
    "EnrollableActivity",
    "LaborRecord",
    "LaborSummary",
    "LdxtClient",
    "LdxtError",
    "LdxtNotLoggedInError",
    "LdxtProtocolError",
]
