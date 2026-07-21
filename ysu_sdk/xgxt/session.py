"""XGXT 会话凭据：一组 ``xgxt.ysu.edu.cn`` 域上的 cookie。

与 :class:`ysu_sdk.jwxt.JWXTSession` 形状相同，语义也一致：

- 短寿命的 per-service cookies（``JSESSIONID`` / ``_WEU`` / WAF 的 ``nS_*`` 等），
  过期后业务调用会被踢回 CAS 登录页，由 :class:`XGXTClient` 的懒回退机制
  自动重新 ``authorize`` 落地新的 cookie。

过滤规则：``c.domain`` 包含 ``xgxt.ysu.edu.cn``（兼容 ``.xgxt.ysu.edu.cn``）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from ysu_sdk._cookie import CookieEntry, collect_cookies, install_cookies


XGXT_COOKIE_DOMAIN_KEYWORD: str = "xgxt.ysu.edu.cn"


def _is_xgxt_cookie(c: Any) -> bool:
    return bool(c.domain) and XGXT_COOKIE_DOMAIN_KEYWORD in c.domain


@dataclass(slots=True)
class XGXTSession:
    """学工系统会话凭据：一组 xgxt.ysu.edu.cn 域上的 cookie。"""

    cookies: list[CookieEntry]

    # ──────────────────────────────────────────────────────────────────── #
    # 与 requests.Session 的互转
    # ──────────────────────────────────────────────────────────────────── #

    @classmethod
    def from_session(cls, session: requests.Session) -> "XGXTSession":
        """从 ``session`` 中筛出学工系统 cookie。"""
        return cls(cookies=collect_cookies(session, _is_xgxt_cookie))

    def apply(self, session: requests.Session) -> None:
        """把会话中的 cookie 写入 ``session``，保留 path/domain 等元数据。"""
        install_cookies(session, self.cookies)

    def is_empty(self) -> bool:
        return not self.cookies

    # ──────────────────────────────────────────────────────────────────── #
    # JSON 序列化
    # ──────────────────────────────────────────────────────────────────── #

    def to_json(self) -> str:
        return json.dumps(
            {"cookies": [c.to_dict() for c in self.cookies]},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "XGXTSession":
        data = json.loads(s)
        if not isinstance(data, dict) or "cookies" not in data:
            raise ValueError("invalid XGXTSession JSON: missing 'cookies'")
        raw_cookies = data["cookies"]
        if not isinstance(raw_cookies, list):
            raise ValueError("invalid XGXTSession JSON: 'cookies' must be a list")
        return cls(cookies=[CookieEntry.from_dict(item) for item in raw_cookies])
