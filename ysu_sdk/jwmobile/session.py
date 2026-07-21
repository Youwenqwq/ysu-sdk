"""Mobile 会话凭据：``jwxt.ysu.edu.cn`` 域 ``/jwmobile`` 路径上的 cookie。

与 :class:`ysu_sdk.jwxt.JWXTSession` 同域但**不同路径**：移动端会话是
``/jwmobile`` 下的 ``JSESSIONID`` 与 ``Authorization``（JWT），与
``/jwapp`` 的 EMAP 桌面端会话互不通用，因此按路径过滤。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from ysu_sdk._cookie import CookieEntry, collect_cookies, install_cookies


MOBILE_COOKIE_DOMAIN_KEYWORD: str = "jwxt.ysu.edu.cn"
MOBILE_COOKIE_PATH_PREFIX: str = "/jwmobile"


def _is_mobile_cookie(c: Any) -> bool:
    return (
        bool(c.domain)
        and MOBILE_COOKIE_DOMAIN_KEYWORD in c.domain
        and str(c.path or "/").startswith(MOBILE_COOKIE_PATH_PREFIX)
    )


@dataclass(slots=True)
class MobileSession:
    """移动教务会话凭据：/jwmobile 路径上的 cookie 集合。"""

    cookies: list[CookieEntry]

    @classmethod
    def from_session(cls, session: requests.Session) -> "MobileSession":
        """从 ``session`` 中筛出移动端 cookie。"""
        return cls(cookies=collect_cookies(session, _is_mobile_cookie))

    def apply(self, session: requests.Session) -> None:
        """把会话中的 cookie 写入 ``session``，保留 path/domain 等元数据。"""
        install_cookies(session, self.cookies)

    def is_empty(self) -> bool:
        return not self.cookies

    def to_json(self) -> str:
        return json.dumps(
            {"cookies": [c.to_dict() for c in self.cookies]},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "MobileSession":
        data = json.loads(s)
        if not isinstance(data, dict) or "cookies" not in data:
            raise ValueError("invalid MobileSession JSON: missing 'cookies'")
        raw_cookies = data["cookies"]
        if not isinstance(raw_cookies, list):
            raise ValueError("invalid MobileSession JSON: 'cookies' must be a list")
        return cls(cookies=[CookieEntry.from_dict(item) for item in raw_cookies])
