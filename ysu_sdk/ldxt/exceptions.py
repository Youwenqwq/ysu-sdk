"""ysu_sdk.ldxt 的异常类型。

沿用 SDK 的三段式分层：``LdxtError`` 是基类，未登录/会话失效与
协议解析失败分别独立成类，方便上层区分「重新认证」与「页面结构变了」。
"""

from __future__ import annotations


class LdxtError(Exception):
    """劳动教育系统 SDK 的基类异常。"""


class LdxtNotLoggedInError(LdxtError):
    """会话未认证或已过期（请求被重定向回登录页）。"""


class LdxtProtocolError(LdxtError):
    """响应与预期不符（非 200、页面中找不到数据表格等）。"""
