"""共享的日期/时间格式归一助手。

学校各系统接口的日期写法不一致（至少四种：``YYYY-MM-DD``、
``YYYY-MM-DD HH:MM:SS``、``YYYY.MM.DD HH:MM:SS``、复合展示串），
jwxt 与 jwmobile 两个子包都需要归一，提到这里避免重复。

约定见 AGENTS.md「Conventions」：日期 ``YYYY-MM-DD``，日期时间
RFC3339（``YYYY-MM-DDTHH:MM:SS``），未识别格式原样透传。
"""

from __future__ import annotations

import re
from typing import Any

_ISO_DATE_RE = re.compile(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$")
_ISO_DATETIME_RE = re.compile(
    r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})[T ](\d{1,2}):(\d{2}):(\d{2})$"
)


def to_iso_date(val: Any) -> str:
    """把已知日期格式归一为 ``YYYY-MM-DD``；未识别的原样透传。"""
    s = str(val or "").strip()
    m = _ISO_DATE_RE.match(s)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return str(val or "")


def to_iso_datetime(val: Any) -> str:
    """把已知日期时间格式归一为 RFC3339（``YYYY-MM-DDTHH:MM:SS``）。

    未识别的格式原样透传——字符串契约下「偶尔不统一」不等于数据丢失。
    """
    s = str(val or "").strip()
    m = _ISO_DATETIME_RE.match(s)
    if m:
        y, mo, d, h, mi, se = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{mi}:{se}"
    return str(val or "")
