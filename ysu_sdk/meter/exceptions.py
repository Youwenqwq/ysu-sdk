"""智能水电 SDK 异常体系。"""

from __future__ import annotations


class MeterError(Exception):
    """智能水电子包所有异常的基类。"""


class MeterProtocolError(MeterError):
    """网络、HTTP、加密或响应结构不符合协议预期。"""


class MeterBusinessError(MeterError):
    """外层信封返回非零业务码；保留服务端错误码、消息和请求地址。"""

    def __init__(
        self, code: str | int | float | None, msg: str | None, url: str
    ) -> None:
        super().__init__(f"智能水电业务请求失败：{url}，code={code}，msg={msg}")
        self.code = code
        self.msg = msg
        self.url = url
