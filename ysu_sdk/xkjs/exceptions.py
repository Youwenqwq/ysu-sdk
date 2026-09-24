"""ysu_sdk.xkjs 的异常类型。"""

from __future__ import annotations


class XkjsError(Exception):
    """创新创业竞赛管理系统 SDK 的基类异常。"""


class XkjsNotLoggedInError(XkjsError):
    """会话未认证或已过期（请求被重定向回登录页）。"""


class XkjsProtocolError(XkjsError):
    """响应与预期不符（非 200、桥接失败、片段中找不到数据表格等）。"""
