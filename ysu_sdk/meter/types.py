"""智能水电查询的数据类型；raw 保留对应层级的原始响应字段。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MeterRoom:
    """学工号绑定的宿舍电表户；room_verify 用于后续查询。"""

    room_full_name: str = ""
    room_verify: str = ""
    account_num: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class MonthUse:
    """月度用电量（度）；month 保留上游年月格式，如 2026.08。"""

    month: str = ""
    use: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class MeterDevice:
    """一路电表；remaining、today_use 单位为度，price 单位为元/度。"""

    device_name: str = ""
    remaining: float = 0.0
    today_use: float = 0.0
    price: float = 0.0
    month_use: list[MonthUse] = field(default_factory=list)
    line_desc: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class MeterOverview:
    """绑定宿舍及其各路电表的用电概览。"""

    room_full_name: str = ""
    room_num: str = ""
    meters: list[MeterDevice] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class DayUse:
    """每日用电量（度）；date 归一为 YYYY-MM-DD，未知格式原样保留。"""

    date: str = ""
    use: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class RechargeRecord:
    """历史充值记录；amount 为度、fare 为元，补电等非支付记录金额为零。

    time 归一为 RFC3339；未识别的时间格式原样保留。
    """

    time: str = ""
    name: str = ""
    amount: float = 0.0
    fare: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
