"""解析学校接口返回的未加引号键名 JSON，不执行 JavaScript。"""

from __future__ import annotations

import json
import re
from typing import Any

_MAX_LENGTH = 2 * 1024 * 1024
# Consume quoted strings intact so key-like text inside values stays untouched.
_TOKEN = re.compile(r'"(?:[^"\\]|\\[\s\S])*"|([{\[,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)')


def _quote_key(match: re.Match[str]) -> str:
    if match[1] is None:
        return match[0]
    return f'{match[1]}"{match[2]}"{match[3]}'


def _reject_constant(value: str) -> Any:
    raise ValueError(f"JSON 含非标准数值：{value}")


def parse_loose_json(text: str) -> Any:
    """接受标准 JSON 或未加引号的 ASCII 键名；无效或超过 2 MiB 时抛 ValueError。"""
    if not isinstance(text, str) or len(text) > _MAX_LENGTH:
        raise ValueError("JSON 响应过大或不是字符串")
    try:
        return json.loads(_TOKEN.sub(_quote_key, text), parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("JSON 响应嵌套过深") from exc
