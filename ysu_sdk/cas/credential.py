"""CAS 凭据：仅保留 ``cer.ysu.edu.cn`` 网关路径下的 cookie。

设计要点：

- 持久化时**完整保留** ``name/value/domain/path/secure/expires``，不能用
  ``session.cookies.get_dict()`` —— 那会丢 path 信息且让同名异路径的
  cookie 互相覆盖（如 ``/`` 和 ``/personalInfo`` 上同名的 ``JSESSIONID``）。
- 路径过滤：仅保留 ``path == "/"`` 或 ``path`` 以 ``/authserver`` 开头的
  cookie。其余业务挂载点（如 ``/personalInfo``）的 cookie 是 per-service
  的，不属于 CAS 凭据。
- 文件落盘后 chmod 0o600，避免凭据文件被同机用户读取。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from ysu_sdk._cookie import CookieEntry, collect_cookies, install_cookies
from ysu_sdk.cas.constants import (
    CAS_COOKIE_DOMAIN,
    DEFAULT_CREDENTIAL_PATH,
)


_ALLOWED_PATH_PREFIX: str = "/authserver"


def _is_cas_path(path: str) -> bool:
    """``/`` 或 ``/authserver/...`` 算 CAS 网关路径。"""
    if not path:
        # 没 path 的 cookie 在 requests 里默认按 "/" 处理
        return True
    return path == "/" or path.startswith(_ALLOWED_PATH_PREFIX)


def _is_cas_cookie(c: Any) -> bool:
    return c.domain == CAS_COOKIE_DOMAIN and _is_cas_path(c.path or "")


@dataclass(slots=True)
class CASCredential:
    """CAS 网关凭据：一组 cer.ysu.edu.cn 域上的 cookie。"""

    cookies: list[CookieEntry]

    # ──────────────────────────────────────────────────────────────────── #
    # 与 requests.Session 的互转
    # ──────────────────────────────────────────────────────────────────── #

    @classmethod
    def from_session(cls, session: requests.Session) -> "CASCredential":
        """从 ``session`` 中筛出 CAS 网关 cookie。

        筛选规则：``domain == cer.ysu.edu.cn`` 且 path ∈ {``/``, ``/authserver/...``}。
        """
        return cls(cookies=collect_cookies(session, _is_cas_cookie))

    def apply(self, session: requests.Session) -> None:
        """把凭据中的 cookie **逐条**写入 ``session``，保留 path/domain 等元数据。

        若 ``session`` 上已存在同 name/domain/path 的 cookie，会被覆盖。
        """
        install_cookies(session, self.cookies)

    # ──────────────────────────────────────────────────────────────────── #
    # JSON 序列化
    # ──────────────────────────────────────────────────────────────────── #

    def to_json(self) -> str:
        return json.dumps(
            {"cookies": [c.to_dict() for c in self.cookies]},
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, s: str) -> "CASCredential":
        data = json.loads(s)
        if not isinstance(data, dict) or "cookies" not in data:
            raise ValueError("invalid CASCredential JSON: missing 'cookies'")
        raw_cookies = data["cookies"]
        if not isinstance(raw_cookies, list):
            raise ValueError("invalid CASCredential JSON: 'cookies' must be a list")
        entries = [CookieEntry.from_dict(item) for item in raw_cookies]
        # 历史数据里有些条目可能没 domain，回填到 CAS 网关域上
        entries = [
            e if e.domain else CookieEntry(
                name=e.name,
                value=e.value,
                domain=CAS_COOKIE_DOMAIN,
                path=e.path,
                secure=e.secure,
                expires=e.expires,
            )
            for e in entries
        ]
        return cls(cookies=entries)

    # ──────────────────────────────────────────────────────────────────── #
    # 文件持久化
    # ──────────────────────────────────────────────────────────────────── #

    def save(self, path: Path | None = None) -> Path:
        """写入凭据文件并 chmod 0o600（Windows 下 chmod 是 noop，可接受）。"""
        target = Path(path) if path is not None else DEFAULT_CREDENTIAL_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding="utf-8")
        if sys.platform != "win32":
            try:
                os.chmod(target, 0o600)
            except OSError:
                # 某些文件系统（如 WSL 下挂载的 NTFS）会拒绝 chmod，不致命
                pass
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "CASCredential | None":
        """读取凭据文件。文件不存在返回 ``None``；JSON 异常抛 :class:`ValueError`。"""
        target = Path(path) if path is not None else DEFAULT_CREDENTIAL_PATH
        if not target.exists():
            return None
        return cls.from_json(target.read_text(encoding="utf-8"))
