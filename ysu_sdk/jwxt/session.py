"""JWXT 会话凭据：一组 ``jwxt.ysu.edu.cn`` 域上的 cookie。

与 :class:`ysu_sdk.cas.CASCredential` 形状相同，但语义不同：

- **CASCredential** 是 *长寿命* 的 CAS 网关 TGC，可以用来反复给不同 service 出 ST。
- **JWXTSession** 是 *短寿命* 的 per-service cookies（``JSESSIONID`` / ``_WEU`` /
  ``route`` 等），过期后业务调用会被踢回 CAS 登录页，由 :class:`JWXTClient`
  的懒回退机制自动重新 ``authorize`` 落地新的 cookie。

设计要点：

- 过滤规则：``c.domain`` 包含 ``jwxt.ysu.edu.cn``（兼容 ``.jwxt.ysu.edu.cn``）。
- 不做文件持久化：调用方（ysu-api / ysu-mcp-server）自行决定如何在客户端 ↔
  服务端之间运输（Header、本地文件等）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from ysu_sdk._cookie import CookieEntry, collect_cookies, install_cookies


JWXT_COOKIE_DOMAIN_KEYWORD: str = "jwxt.ysu.edu.cn"


def _is_jwxt_cookie(c: Any) -> bool:
    return bool(c.domain) and JWXT_COOKIE_DOMAIN_KEYWORD in c.domain


@dataclass(slots=True)
class JWXTSession:
    """教务系统会话凭据：一组 jwxt.ysu.edu.cn 域上的 cookie。"""

    cookies: list[CookieEntry]

    # ──────────────────────────────────────────────────────────────────── #
    # 与 requests.Session 的互转
    # ──────────────────────────────────────────────────────────────────── #

    @classmethod
    def from_session(cls, session: requests.Session) -> "JWXTSession":
        """从 ``session`` 中筛出教务系统 cookie。"""
        return cls(cookies=collect_cookies(session, _is_jwxt_cookie))

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
    def from_json(cls, s: str) -> "JWXTSession":
        data = json.loads(s)
        if not isinstance(data, dict) or "cookies" not in data:
            raise ValueError("invalid JWXTSession JSON: missing 'cookies'")
        raw_cookies = data["cookies"]
        if not isinstance(raw_cookies, list):
            raise ValueError("invalid JWXTSession JSON: 'cookies' must be a list")
        return cls(cookies=[CookieEntry.from_dict(item) for item in raw_cookies])
