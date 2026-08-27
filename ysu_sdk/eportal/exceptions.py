"""ePortal（锐捷校园网认证）SDK 异常体系。"""

from __future__ import annotations


class EPortalError(Exception):
    """ePortal 子包所有异常的基类。"""


class EPortalNetworkError(EPortalError):
    """认证门户不可达：连接被拒、超时等传输层失败。

    最常见的触发原因是当前设备不在校园网内。与 :class:`EPortalProtocolError`
    区分：协议异常指收到了响应但内容不符合预期，本异常指根本没能完成
    HTTP 交换。
    """


class EPortalProtocolError(EPortalError):
    """与认证门户的交互结果与协议预期不符（重定向缺失、字段缺失等）。"""


class EPortalBusinessError(EPortalError):
    """ePortal JSON 接口按协议返回了非 200 业务码，属业务规则拒绝。

    与 :class:`EPortalProtocolError` 区分：协议异常指响应格式不符合预期
    （非 JSON、envelope 残缺等），本异常指响应结构正确但业务码非 200。
    """

    def __init__(self, code: int | None, msg: str | None, url: str) -> None:
        super().__init__(f"ePortal business error from {url}: code={code} msg={msg}")
        self.code = code
        self.msg = msg
        self.url = url


class NeedCaptchaError(EPortalError):
    """登录需要图形验证码但调用方未提供 ``captcha_solver``。"""


class CaptchaFailedError(EPortalError):
    """连续多次提交的验证码均被服务端拒绝。"""


class EPortalAuthError(EPortalError):
    """cas-sso 拒绝了登录（用户名/密码/验证码/账号状态等）。

    通过 :attr:`code` 可编程区分具体原因，常见取值见
    ``ysu_sdk.eportal.constants.LOGIN_ERROR_MESSAGES`` 的键。
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
