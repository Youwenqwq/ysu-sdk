"""移动教务 SDK 异常体系。"""

from __future__ import annotations


class MobileError(Exception):
    """移动教务子包所有异常的基类。"""


class MobileNotLoggedInError(MobileError):
    """未登录或移动端会话（Authorization token）过期。"""


class MobileProtocolError(MobileError):
    """与移动教务的交互结果与协议预期不符。"""


class MobileBusinessError(MobileError):
    """服务端按协议返回了非成功业务码，属业务规则拒绝。

    通过 :attr:`code` 与 :attr:`msg` 可编程区分具体业务原因
    （如不在签到时间范围内）。
    """

    def __init__(self, code: str | int | None, msg: str | None, url: str) -> None:
        super().__init__(f"mobile business error from {url}: code={code} msg={msg}")
        self.code = code
        self.msg = msg
        self.url = url
