"""一卡通 SDK 异常体系。"""

from __future__ import annotations


class EcardError(Exception):
    """一卡通子包所有异常的基类。"""


class NotLoggedInError(EcardError):
    """CAS 未认证或一卡通会话已过期。"""


class EcardProtocolError(EcardError):
    """请求失败或响应格式与一卡通协议不符。"""


class EcardBusinessError(EcardError):
    """服务端返回有效响应，但拒绝余额查询；不属于会话过期。"""

    def __init__(
        self, code: str | int | float | None, msg: str | None, url: str
    ) -> None:
        super().__init__(f"一卡通业务请求被拒绝：{url}，code={code}，msg={msg}")
        self.code = code
        self.msg = msg
        self.url = url
