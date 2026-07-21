"""ysu_sdk.scxt 的异常类型。"""

from __future__ import annotations


class ScxtError(Exception):
    """双创学分认定系统 SDK 的基类异常。"""


class ScxtNotLoggedInError(ScxtError):
    """会话未认证或已过期（请求被重定向回登录页）。"""


class ScxtProtocolError(ScxtError):
    """响应与预期不符（非 200、桥接失败、页面中找不到数据表格等）。"""
