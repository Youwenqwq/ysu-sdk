"""一卡通余额的 CAS 单点登录只读客户端。"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import requests

from ysu_sdk._datetime import to_iso_date
from ysu_sdk._json import parse_loose_json
from ysu_sdk.cas.exceptions import NotAuthenticatedError
from ysu_sdk.ecard.constants import AJAX_HEADERS, BALANCE_PATH, BALANCE_URL, SERVICE_URL
from ysu_sdk.ecard.exceptions import (
    EcardBusinessError,
    EcardProtocolError,
    NotLoggedInError,
)
from ysu_sdk.ecard.types import EcardBalance

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

_BALANCE_RE = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
_LOGIN_RE = re.compile(r"authserver|reAuthCheck|isMultifactor|身份认证|请输入用户名", re.I)


def _str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value)


def _coalesce(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _parse_balance(body: dict[str, Any]) -> EcardBalance | None:
    datas = body.get("datas")
    if not isinstance(datas, dict):
        datas = {}
    value = _coalesce(body.get("remining"), datas.get("KNYE"))
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise EcardProtocolError("一卡通余额不是有效金额")
    if isinstance(value, str) and _BALANCE_RE.fullmatch(value.strip()) is None:
        raise EcardProtocolError("一卡通余额不是有效金额")
    try:
        balance = float(value)
    except (ValueError, OverflowError) as exc:
        raise EcardProtocolError("一卡通余额不是有效金额") from exc
    if not math.isfinite(balance):
        raise EcardProtocolError("一卡通余额不是有限金额")
    months = body.get("yearMonths")
    return EcardBalance(
        balance=balance,
        card_num=_str(_coalesce(body.get("cardnum"), datas.get("KH"), body.get("id"))),
        available_date=to_iso_date(_str(_coalesce(body.get("availdate"), datas.get("KYXQ")))),
        card_status_name=_str(_coalesce(body.get("cardstatusname"), datas.get("MC"))),
        months=[text for month in months if (text := _str(month))] if isinstance(months, list) else [],
        raw=body,
    )


class EcardClient:
    """通过独立会话查询 ehall 一卡通余额，不提供充值或交易接口。

    首次查询时使用已有 CAS 凭据建立一卡通会话；余额接口报告会话过期时，
    重新授权并且仅重试一次。CAS 的其他错误保留原异常类型。
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
        """首次业务请求或会话失效后懒执行 CAS 授权。"""
        if self._authorized:
            return
        try:
            self.session = self._cas.authorize(SERVICE_URL, session=self.session)
        except NotAuthenticatedError as exc:
            raise NotLoggedInError("CAS 尚未登录或认证已过期") from exc
        self._authorized = True

    def _request_balance(self) -> dict[str, Any]:
        """按 AJAX 协议读取余额，分别识别会话、业务与协议异常。"""
        try:
            response = self.session.post(
                BALANCE_URL,
                headers=AJAX_HEADERS,
                allow_redirects=False,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EcardProtocolError("一卡通余额请求失败") from exc
        status = response.status_code
        if 300 <= status < 400 or status in (401, 403):
            raise NotLoggedInError("一卡通会话已过期")
        if not 200 <= status < 300:
            raise EcardProtocolError(f"一卡通接口返回 HTTP {status}")
        if response.url:
            try:
                final_url = urlsplit(response.url)
                if not final_url.scheme or not final_url.netloc:
                    raise ValueError("响应地址不是绝对 URL")
                port = final_url.port
            except ValueError as exc:
                raise EcardProtocolError("一卡通响应 URL 格式无效") from exc
            if (
                final_url.scheme != "https"
                or final_url.hostname != "ehall.ysu.edu.cn"
                or port not in (None, 443)
                or final_url.path != BALANCE_PATH
            ):
                raise NotLoggedInError("一卡通响应离开了余额查询端点")
        text = response.text
        if _LOGIN_RE.search(text):
            raise NotLoggedInError("一卡通响应要求重新登录")
        try:
            body = parse_loose_json(text)
        except ValueError as exc:
            raise EcardProtocolError("一卡通响应不是有效 JSON") from exc
        if not isinstance(body, dict):
            raise EcardProtocolError("一卡通响应必须是 JSON 对象")
        for key in ("code", "status"):
            code = body.get(key)
            if code is None:
                continue
            if isinstance(code, bool) or not isinstance(code, (str, int, float)):
                raise EcardProtocolError("一卡通响应状态码格式无效")
            if isinstance(code, float) and not math.isfinite(code):
                raise EcardProtocolError("一卡通响应状态码不是有限数值")
            if code in (401, "401", 403, "403"):
                raise NotLoggedInError("一卡通会话已过期")
            if code not in (200, "200"):
                raise EcardBusinessError(
                    code, _str(_coalesce(body.get("msg"), body.get("message"))) or None, BALANCE_URL
                )
        if body.get("success") is False:
            raise EcardBusinessError(
                _coalesce(body.get("code"), body.get("status")),
                _str(_coalesce(body.get("msg"), body.get("message"))) or None,
                BALANCE_URL,
            )
        if (
            "datas" not in body
            and "remining" not in body
            and body.get("code") not in (200, "200")
            and body.get("status") not in (200, "200")
        ):
            raise EcardProtocolError("无法识别一卡通余额响应结构")
        return body

    def query_balance(self) -> EcardBalance | None:
        """查询一卡通余额；缺少余额返回 None，真实零余额仍返回余额对象。

        金额字符串必须是十进制定点数（可带正负号及首尾空白）；布尔值、
        空串、非有限金额及科学记数法字符串均为协议错误。
        """
        retried = False
        while True:
            self._ensure_authorized()
            try:
                return _parse_balance(self._request_balance())
            except NotLoggedInError:
                self._authorized = False
                if retried:
                    raise
                retried = True
