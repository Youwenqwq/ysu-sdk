"""CAS SDK 异常体系。"""

from __future__ import annotations


class CASError(Exception):
    """CAS 子包所有异常的基类。"""


class NeedCaptchaError(CASError):
    """登录需要图形验证码但调用方未提供。"""


class IPBlockedError(CASError):
    """当前 IP 被认证网关临时冻结。"""


class LoginFailedError(CASError):
    """用户名或密码错误（或后端在第一重就判定登录失败）。"""


class MFARequiredError(CASError):
    """第一重通过但服务端要求继续二次认证。

    供 ``login()`` 在没有 ``mfa_handler`` 时抛出；若使用编程式分步流程，
    应改为检查 :class:`Step1Result.needs_mfa`。
    """


class MFAFailedError(CASError):
    """MFA 验证码错误、过期或被服务端拒绝。"""


class NotAuthenticatedError(CASError):
    """未持有有效 TGC 时调用了需要登录态的方法（如 :meth:`authorize`）。"""


class CASProtocolError(CASError):
    """与认证网关的交互结果与协议预期不符（重定向缺失、字段缺失等）。"""
