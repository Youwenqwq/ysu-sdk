"""共享的 cookie 序列化助手。

CAS 凭据与 JWXT 会话都要把 ``requests.Session`` 上的 cookie 序列化成 JSON
再恢复 —— 形状一模一样，只是过滤规则不同。把通用部分提到这里，避免两边重复。

约束：完整保留 ``name/value/domain/path/secure/expires``。不要用
``session.cookies.get_dict()`` —— 那会丢 path 信息且让同名异路径的 cookie 互相
覆盖（如 ``/`` 和 ``/personalInfo`` 上同名的 ``JSESSIONID``）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

import requests
from requests.cookies import create_cookie


@dataclass(frozen=True, slots=True)
class CookieEntry:
    """单条 cookie 的可序列化表示。"""

    name: str
    value: str
    domain: str
    path: str
    secure: bool
    expires: int | None  # epoch seconds；None 表示会话级

    @classmethod
    def from_cookie(cls, c: Any) -> "CookieEntry":
        """从 ``requests`` 的 cookie 对象构造。"""
        return cls(
            name=c.name,
            value=c.value or "",
            domain=c.domain or "",
            path=c.path or "/",
            secure=bool(c.secure),
            expires=int(c.expires) if c.expires is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CookieEntry":
        return cls(
            name=str(d["name"]),
            value=str(d.get("value", "")),
            domain=str(d.get("domain", "")),
            path=str(d.get("path", "/")),
            secure=bool(d.get("secure", False)),
            expires=(int(d["expires"]) if d.get("expires") is not None else None),
        )

    def install(self, session: requests.Session) -> None:
        """写入 ``session``，保留 path/domain 等元数据。同 name/domain/path 的会被覆盖。"""
        session.cookies.set_cookie(
            create_cookie(
                name=self.name,
                value=self.value,
                domain=self.domain,
                path=self.path,
                secure=self.secure,
                expires=self.expires,
            )
        )


CookiePredicate = Callable[[Any], bool]


def collect_cookies(
    session: requests.Session, predicate: CookiePredicate
) -> list[CookieEntry]:
    """从 ``session`` 中筛出满足 ``predicate`` 的 cookie。"""
    return [CookieEntry.from_cookie(c) for c in session.cookies if predicate(c)]


def install_cookies(session: requests.Session, entries: list[CookieEntry]) -> None:
    """把 entries 批量写入 ``session``。"""
    for entry in entries:
        entry.install(session)
