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


class CASNetworkError(CASError):
    """认证网关不可达：连接被拒、超时、被 WAF 重置等传输层失败。

    与 :class:`CASProtocolError` 区分：协议异常指收到了响应但内容不符合
    预期，本异常指根本没能完成 HTTP 交换。调用方应据此区分「网关/网络
    故障」与「凭据失效」——例如 WAF 封禁 IP 时抛的就是本异常。
    """


class CASProtocolError(CASError):
    """与认证网关的交互结果与协议预期不符（重定向缺失、字段缺失等）。"""
