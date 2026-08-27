"""cas-sso 登录页与 portal 跳转的 HTML 解析。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ysu_sdk.eportal.exceptions import EPortalProtocolError

_JS_REDIRECT_RE = re.compile(r"location\.href\s*=\s*'([^']+)'")


def extract_js_redirect(html: str) -> str | None:
    """从 ``location.href='...'`` 形式的 JS 跳转页中提取目标 URL。"""
    m = _JS_REDIRECT_RE.search(html)
    return m.group(1) if m else None


@dataclass(frozen=True, slots=True)
class LoginMaterial:
    """cas-sso 登录页内嵌的一次性材料。

    Attributes:
        croypto: Base64 编码的 AES-ECB key，加密密码与 ``captcha_payload`` 用。
        execution: 表单 ``execution`` 字段（页面 ``#login-page-flowkey``）。
    """

    croypto: str
    execution: str


def extract_login_material(html: str) -> LoginMaterial:
    """从 cas-sso 登录页 HTML 提取 ``croypto`` 与 ``execution``。

    两者都藏在 ``display:none`` 的 ``<p>`` 里且无 ``name`` 属性，只能按
    ``id`` 提取。每次渲染页面都会轮换，登录失败重试时必须重新抓取。

    Raises:
        EPortalProtocolError: 页面中找不到任一字段。
    """
    soup = BeautifulSoup(html, "html.parser")
    croypto_el = soup.find("p", id="login-croypto")
    flowkey_el = soup.find("p", id="login-page-flowkey")
    if croypto_el is None or flowkey_el is None:
        raise EPortalProtocolError(
            "cas-sso login page missing login-croypto/login-page-flowkey"
        )
    croypto = croypto_el.get_text(strip=True)
    execution = flowkey_el.get_text(strip=True)
    if not croypto or not execution:
        raise EPortalProtocolError("cas-sso login page has empty croypto/flowkey")
    return LoginMaterial(croypto=croypto, execution=execution)


def extract_login_error_code(html: str) -> str | None:
    """从登录结果页提取错误码（``#login-error-msg > span`` 的数字文本）。

    成功重定向走掉时页面里不会有该元素；返回 ``None`` 表示未发现错误标记。
    """
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find("div", id="login-error-msg")
    if el is None:
        return None
    span = el.find("span")
    if span is None:
        return None
    code = span.get_text(strip=True)
    return code or None
