"""在线综合支付平台的 CAS 单点登录只读查询客户端。"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import requests

from ysu_sdk._datetime import to_iso_date, to_iso_datetime
from ysu_sdk._json import parse_loose_json
from ysu_sdk.cas.exceptions import NotAuthenticatedError
from ysu_sdk.epay.constants import (
    ALL_PAY_PATH,
    BASE_URL,
    INDEX_PATH,
    MAX_HTML_BYTES,
    SERVICE_URL,
)
from ysu_sdk.epay.exceptions import EpayProtocolError, NotLoggedInError
from ysu_sdk.epay.types import EpayRecord, EpayStatus

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

_D_MARKER_RE = re.compile(r'''(?:\bD|["']D["'])\s*:\s*\{''')
_LOGIN_PATH_RE = re.compile(r"/(?:authserver/)?login(?:[/.]|$)", re.I)
_LOGIN_FORM_RE = re.compile(
    r'''<form\b[^>]*\b(?:id=["']loginForm["']|action=["'][^"']*authserver)''',
    re.I,
)
_REQUIRED_FIELDS = ("id", "payName", "amountN", "status", "expired", "overTime")


def _extract_data(html: str) -> dict[str, Any]:
    """用括号及引号扫描抽取 D 对象，只解析数据，不执行页面脚本。"""
    if len(html) > MAX_HTML_BYTES or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise EpayProtocolError("支付页面超过 2 MiB，无法安全解析")
    marker = _D_MARKER_RE.search(html)
    if marker is None:
        raise EpayProtocolError("支付页面缺少 D 数据对象")
    start = marker.end() - 1
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(html)):
        char = html[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = parse_loose_json(html[start : index + 1])
                except ValueError as exc:
                    raise EpayProtocolError("支付页面 D 数据无法解析") from exc
                if not isinstance(data, dict):
                    raise EpayProtocolError("支付页面 D 数据不是对象")
                return data
    raise EpayProtocolError("支付页面 D 数据对象不完整")


def _column_index(value: Any) -> int | None:
    """将页面中的 1 基列号转换为数组索引。"""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or not number.is_integer() or number < 1:
        return None
    return int(number) - 1


def _text(raw: dict[str, Any], key: str) -> str:
    """保留原始标量的显示内容，拒绝把损坏的容器字段当成有效状态。"""
    value = raw.get(key)
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise EpayProtocolError(f"支付记录字段格式错误：{key}")
    if isinstance(value, float) and not math.isfinite(value):
        raise EpayProtocolError(f"支付记录字段不是有限数值：{key}")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _parse_records(data: dict[str, Any]) -> list[EpayRecord]:
    """按列映射解析完整记录；额外分页或损坏记录不能视为空账单。"""
    result = data.get("queryResult")
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        raise EpayProtocolError("支付响应缺少有效的 queryResult.rows")
    next_page = result.get("hasNextPage")
    if next_page is True or next_page == 1 or next_page == "1":
        raise EpayProtocolError("支付响应仍有后续分页，暂不支持完整读取")
    if next_page not in (None, False, 0, "0", ""):
        raise EpayProtocolError("支付响应分页标志无效")
    names = result.get("names")
    if not isinstance(names, dict):
        raise EpayProtocolError("支付响应缺少有效的 names 列映射")
    columns = {key: _column_index(value) for key, value in names.items()}
    records: list[EpayRecord] = []
    for row in result["rows"]:
        if not isinstance(row, list):
            raise EpayProtocolError("支付记录行不是数组")
        for key in _REQUIRED_FIELDS:
            index = columns.get(key)
            if index is None or index >= len(row):
                raise EpayProtocolError(f"支付记录缺少必需字段：{key}")
        raw = {
            key: row[index]
            for key, index in columns.items()
            if index is not None and index < len(row)
        }
        record_id = _text(raw, "id").strip()
        pay_name = _text(raw, "payName")
        amount_value = raw["amountN"]
        if (
            not record_id
            or not pay_name.strip()
            or isinstance(amount_value, bool)
            or not isinstance(amount_value, (int, float, str))
            or not str(amount_value).strip()
        ):
            raise EpayProtocolError("支付记录标识、收费名称或金额无效")
        try:
            amount_n = float(amount_value)
        except (ValueError, OverflowError) as exc:
            raise EpayProtocolError("支付记录金额无法解析") from exc
        if not math.isfinite(amount_n):
            raise EpayProtocolError("支付记录金额不是有限数值")
        records.append(
            EpayRecord(
                id=record_id,
                pay_name=pay_name,
                charge_year=_text(raw, "chargeYear"),
                currency_type_show=_text(raw, "currencyTypeShow"),
                amount_n=amount_n,
                amount=_text(raw, "amount"),
                pay_amount=_text(raw, "payAmount"),
                refund_amount=_text(raw, "refundAmount"),
                status=_text(raw, "status"),
                expired=_text(raw, "expired"),
                start_time=to_iso_date(_text(raw, "startTime")),
                over_time=to_iso_datetime(_text(raw, "overTime")),
                raw=raw,
            )
        )
    return records


class EpayClient:
    """支付平台只读客户端；首次查询时通过 CAS 建立独立会话。

    仅查询付款记录，不提供付款、退款或订单变更操作。
    会话过期时重新认证一次，并从历史页面重新开始完整查询。
    """

    def __init__(
        self,
        cas_client: CASClient,
        *,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        self._cas = cas_client
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout
        self._authorized = False

    def _ensure_authorized(self) -> None:
        """懒认证；身份失效转为本模块异常，其他 CAS 异常原样透传。"""
        if self._authorized:
            return
        try:
            self.session = self._cas.authorize(SERVICE_URL, session=self.session)
        except NotAuthenticatedError as exc:
            raise NotLoggedInError("CAS 登录态无效，无法授权支付平台") from exc
        self._authorized = True

    def _fetch_page(self, path: str) -> tuple[dict[str, Any], list[EpayRecord]]:
        """读取页面并检查会话、HTTP 状态及记录完整性。"""
        url = f"{BASE_URL}{path}"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EpayProtocolError(f"支付页面请求失败：{url}") from exc
        html = response.text
        destination = urlsplit(response.url)
        if (
            response.status_code == 401
            or destination.hostname != urlsplit(BASE_URL).hostname
            or _LOGIN_PATH_RE.search(destination.path)
            or _LOGIN_FORM_RE.search(html)
            or "请输入用户名" in html
            or "统一身份认证" in html
        ):
            self._authorized = False
            raise NotLoggedInError(f"支付平台会话已失效：{url}")
        if not 200 <= response.status_code < 300:
            raise EpayProtocolError(f"支付页面返回 HTTP {response.status_code}：{url}")
        data = _extract_data(html)
        return data, _parse_records(data)

    def query_payments(self) -> EpayStatus:
        """依次读取历史与待付款页面，返回去重的全记录和权威待缴列表。

        任一页面无法解析、存在未读取分页或金额无效均抛出协议异常。
        待缴仅取自 index，不从 allPay 的历史未支付记录推断欠费。
        """
        self._ensure_authorized()
        try:
            return self._query_payments()
        except NotLoggedInError:
            self._authorized = False
            self._ensure_authorized()
            return self._query_payments()

    def _query_payments(self) -> EpayStatus:
        """完成双源查询；失败时不保留半次查询结果。"""
        history_data, history = self._fetch_page(ALL_PAY_PATH)
        pending_data, pending = self._fetch_page(INDEX_PATH)
        records: list[EpayRecord] = []
        unpaid: list[EpayRecord] = []
        seen: set[str] = set()
        for record in pending:
            if record.id in seen:
                continue
            seen.add(record.id)
            records.append(record)
            if (
                not record.over_time.strip()
                and record.status.strip() == "1"
                and record.expired.strip() == "0"
            ):
                unpaid.append(record)
        for record in history:
            if record.id not in seen:
                seen.add(record.id)
                records.append(record)
        return EpayStatus(
            records=records,
            unpaid=unpaid,
            raw={"allPay": history_data, "index": pending_data},
        )
