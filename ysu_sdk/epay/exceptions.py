"""在线综合支付平台 SDK 异常体系。"""

from __future__ import annotations


class EpayError(Exception):
    """支付查询子包所有异常的基类。"""


class NotLoggedInError(EpayError):
    """未登录或支付平台会话已失效。"""


class EpayProtocolError(EpayError):
    """网络请求失败，或支付响应不符合协议、无法完整读取。"""
