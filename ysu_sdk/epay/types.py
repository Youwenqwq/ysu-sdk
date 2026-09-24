"""在线综合支付平台的付款记录与查询结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EpayRecordStatus = Literal["paid", "unpaid", "closed", "expired", "unknown"]


@dataclass(frozen=True, slots=True)
class EpayRecord:
    """一条付款记录，金额单位为元。

    ``amount_n`` 为数值；``amount``、``pay_amount``、``refund_amount``
    保留服务端显示字符串（包括千分位）。``status`` 保留原始状态码。
    ``start_time`` 为日期，``over_time`` 为归一化的付款完成时间。
    ``raw`` 按页面 ``names`` 映射保留全部原始列，不归一化日期或金额。
    """

    id: str = ""
    pay_name: str = ""
    charge_year: str = ""
    currency_type_show: str = ""
    amount_n: float = 0.0
    amount: str = ""
    pay_amount: str = ""
    refund_amount: str = ""
    status: str = ""
    expired: str = ""
    start_time: str = ""
    over_time: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def record_status(self) -> EpayRecordStatus:
        """按完成时间、过期标志、状态码的优先级归一化付款状态。"""
        if self.over_time.strip():
            return "paid"
        if self.expired.strip() == "1":
            return "expired"
        status = self.status.strip()
        if status == "0":
            return "closed"
        if status == "1" and self.expired.strip() == "0":
            return "unpaid"
        return "unknown"


@dataclass(frozen=True, slots=True)
class EpayStatus:
    """完整付款查询结果；请求失败时抛异常，不返回伪造的空账单。

    ``records`` 合并待付款与历史记录，同 ID 以待付款页面为准。
    ``unpaid`` 仅来自待付款页面，满足完成时间为空、状态为 1、过期为 0。
    ``raw`` 的 ``allPay`` 和 ``index`` 分别保存两个页面的原始 D 对象。
    """

    records: list[EpayRecord] = field(default_factory=list)
    unpaid: list[EpayRecord] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
