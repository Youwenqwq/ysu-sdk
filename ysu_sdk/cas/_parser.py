"""HTML 解析辅助：提取 hidden 字段、识别 reauth/IP 冻结/错误页。

改用 BeautifulSoup 处理多 <form> 场景——各登录模式（userNameLogin / dynamicLogin / fidoLogin / qrLogin）
拥有独立 <form>，且字段名（execution、lt 等）在不同 form 间重复。正则难以可靠切分 form 边界；
BS 提供结构化的 form 遍历与选择器，维护成本更低。
"""

from __future__ import annotations

from bs4 import BeautifulSoup

_REAUTH_KEYWORDS: tuple[str, ...] = (
    "reAuthCheck",
    "Multifactor",
    "reAuthType",
    "二次认证",
)

_IP_FROZEN_KEYWORDS: tuple[str, ...] = (
    "IP freeze",
    "has been blocked",
    "IP被冻结",
)

_ERROR_SELECTORS: tuple[str, ...] = (
    "#showErrorTip",
    ".form-errorTip",
    ".help-block",
    ".reauth_error_submit",
)


def extract_hidden_fields(html: str, *, cllt: str | None = None) -> dict[str, str]:
    """提取页面里 ``<input type=hidden>`` 的 name(优先)或 id → value 映射。

    若给出 *cllt*，则只在 ``<input name="cllt" value="...">`` 匹配该值的
    ``<form>`` 内部抓取。这样可区分不同登录模式（userNameLogin / dynamicLogin
    等）各自的 hidden 字段，避免同名字段跨 form 互相覆盖。
    """
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form") or [soup]

    if cllt is not None:
        forms = [
            f
            for f in forms
            if (cllt_inp := f.find("input", attrs={"name": "cllt"})) is not None
            and cllt_inp.get("value") == cllt
        ]

    fields: dict[str, str] = {}
    for container in forms:
        for inp in container.find_all("input"):
            if inp.get("type", "").lower() != "hidden":
                continue
            key = inp.get("name") or inp.get("id")
            if not key:
                continue
            fields[key] = inp.get("value", "")
    return fields


def is_reauth_page(html: str) -> bool:
    """是否为二次认证（MFA）页面。"""
    return any(k in html for k in _REAUTH_KEYWORDS)


def is_ip_frozen(html: str) -> bool:
    """是否为 IP 被冻结提示页。"""
    return any(k in html for k in _IP_FROZEN_KEYWORDS)


def extract_error_message(html: str) -> str | None:
    """从登录页提取后端给出的错误提示，找不到返回 ``None``。"""
    soup = BeautifulSoup(html, "html.parser")
    for selector in _ERROR_SELECTORS:
        el = soup.select_one(selector)
        if el is not None and (text := el.get_text(strip=True)):
            return text
    return None
