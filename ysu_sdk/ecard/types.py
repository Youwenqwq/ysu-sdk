"""一卡通余额查询的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EcardBalance:
    """一卡通余额信息。

    Attributes:
        balance: 余额（元），允许零和负数。
        card_num: 卡号。
        available_date: 有效期（YYYY-MM-DD），未识别格式原样保留。
        card_status_name: 卡状态名，如「在用」「挂失」。
        months: 服务端提供的可用月份列表，如「2026-09」。
        raw: 完整原始响应对象。
    """

    balance: float
    card_num: str = ""
    available_date: str = ""
    card_status_name: str = ""
    months: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
