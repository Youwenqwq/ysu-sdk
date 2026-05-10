"""教务系统 SDK 异常体系。"""

from __future__ import annotations


class JWXTError(Exception):
    """教务系统子包所有异常的基类。"""


class NotLoggedInError(JWXTError):
    """未登录或会话过期时调用需要登录态的方法。"""


class JWXTProtocolError(JWXTError):
    """与教务系统的交互结果与协议预期不符。"""


class JWXTBusinessError(JWXTError):
    """服务端按协议返回了非零业务码（如「未到评教时间」），属业务规则拒绝。

    与 :class:`JWXTProtocolError` 区分：协议异常指响应格式不符合预期
    （非 JSON、envelope 残缺等），本异常指响应结构正确但业务码非零。
    通过 :attr:`code` 与 :attr:`msg` 可编程区分具体业务原因。
    """

    def __init__(self, code: str | int | None, msg: str | None, url: str) -> None:
        super().__init__(f"EMAP business error from {url}: code={code} msg={msg}")
        self.code = code
        self.msg = msg
        self.url = url
