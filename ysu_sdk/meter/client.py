"""17wanxiao 智能水电只读客户端；凭据为学工号，不依赖 CAS。"""

from __future__ import annotations

import base64
import json
import math
import secrets
import time
from typing import Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from ysu_sdk._datetime import to_iso_date, to_iso_datetime
from ysu_sdk.meter.constants import (
    API_URL,
    CUSTOMER_CODE,
    RANDOM_ALPHABET,
    REQUEST_HEADERS,
)
from ysu_sdk.meter.exceptions import MeterBusinessError, MeterProtocolError
from ysu_sdk.meter.types import (
    DayUse,
    MeterDevice,
    MeterOverview,
    MeterRoom,
    MonthUse,
    RechargeRecord,
)


def _derive_key(timestamp: str, random_str: str) -> bytes:
    """时间戳奇数取前六位、偶数取后六位，再拼十位随机串。"""
    if (
        len(timestamp) < 6
        or not timestamp.isascii()
        or not timestamp.isdigit()
        or len(random_str) != 10
        or not random_str.isascii()
    ):
        raise ValueError("智能水电密钥参数格式错误")
    part = timestamp[:6] if int(timestamp[-1]) % 2 else timestamp[-6:]
    return (part + random_str).encode("ascii")


def _invalid_constant(value: str) -> Any:
    """拒绝标准 JSON 不支持的 NaN 和 Infinity。"""
    raise ValueError(f"非法 JSON 数值：{value}")


def _json_object(text: str) -> dict[str, Any]:
    """解码协议中的 JSON 对象，不把无效信封当成空结果。"""
    value = json.loads(text, parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("智能水电响应必须是 JSON 对象")
    return value


def _raw_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _raw_num(value: Any) -> float:
    """兼容服务端数字/字符串混发；无效或非有限值按上游规则归零。"""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """允许省略空列表，但拒绝将错误类型的明细静默转换为空列表。"""
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise MeterProtocolError(f"智能水电响应字段 {key} 必须是对象列表")
    return value


class MeterClient:
    """智能水电查询客户端；仅查询绑定、余额、用量及充值历史。

    account 为学工号。每次请求使用独立随机密钥，响应按自身时间戳和
    随机串解密，不复用请求密钥，也不建立 CAS 登录会话。
    """

    def __init__(
        self,
        account: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        self.account = account
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout

    def query_room(self) -> MeterRoom | None:
        """查询学工号绑定房间；未绑定或缺少房间查询凭据时返回 None。"""
        data = self._call("getbindroom", {"account": self.account})
        if _raw_str(data["result"]) != "0":
            return None
        room_verify = _raw_str(data.get("roomverify"))
        if not room_verify:
            return None
        return MeterRoom(
            room_full_name=_raw_str(data.get("roomfullname")),
            room_verify=room_verify,
            account_num=_raw_str(data.get("account_num")),
            raw=data,
        )

    def query_overview(self, room_verify: str) -> MeterOverview | None:
        """查询宿舍电表概览；内层业务结果非零时返回 None。"""
        data = self._call(
            "h5_getstuindexpage",
            {"roomverify": room_verify, "account": self.account},
        )
        if _raw_str(data["result"]) != "0":
            return None
        meters = []
        for meter in _rows(data, "modlist"):
            lines = _rows(meter, "linestatus")
            meters.append(
                MeterDevice(
                    device_name=_raw_str(meter.get("devicename")),
                    remaining=_raw_num(meter.get("odd")),
                    today_use=_raw_num(meter.get("todayuse")),
                    price=_raw_num(meter.get("price")),
                    month_use=[
                        MonthUse(
                            month=_raw_str(month.get("yearmonth")),
                            use=_raw_num(month.get("monthuse")),
                            raw=month,
                        )
                        for month in _rows(meter, "monthuselist")
                    ],
                    line_desc=_raw_str(lines[0].get("desc")) if lines else "",
                    raw=meter,
                )
            )
        return MeterOverview(
            room_full_name=_raw_str(data.get("roomfullname")),
            room_num=_raw_str(data.get("roomnum")),
            meters=meters,
            raw=data,
        )

    def query_daily_use(
        self, room_verify: str, start_date: str, end_date: str
    ) -> list[DayUse]:
        """查询日期区间内的日用电量；日期参数格式为 YYYY-MM-DD。"""
        data = self._call(
            "gettimeusedetail",
            {
                "roomverify": room_verify,
                "businesstype": "0",
                "startdate": start_date,
                "enddate": end_date,
                "account": self.account,
            },
        )
        if _raw_str(data["result"]) != "0":
            return []
        return [
            DayUse(
                date=to_iso_date(_raw_str(day.get("date"))),
                use=_raw_num(day.get("use")),
                raw=day,
            )
            for day in _rows(data, "dayuselist")
        ]

    def query_recharges(self, room_verify: str) -> list[RechargeRecord]:
        """查询充值历史；按服务端月份和月内顺序拍平，不执行充值。"""
        data = self._call(
            "h5_getrechargelist",
            {"roomverify": room_verify, "account": self.account},
        )
        if _raw_str(data["result"]) != "0":
            return []
        return [
            RechargeRecord(
                time=to_iso_datetime(_raw_str(record.get("daytime"))),
                name=_raw_str(record.get("name")),
                amount=_raw_num(record.get("sumbuy")),
                fare=_raw_num(record.get("sumbuyfare")),
                raw=record,
            )
            for month in _rows(data, "list")
            for record in _rows(month, "dayrechargelist")
        ]

    def _call(self, command: str, params: dict[str, str]) -> dict[str, Any]:
        """统一处理 AES-128-ECB/PKCS7 信封、HTTP 及业务错误。"""
        timestamp = str(int(time.time() * 1000))
        random_str = "".join(secrets.choice(RANDOM_ALPHABET) for _ in range(10))
        envelope = {
            "param": json.dumps(
                {"cmd": command, **params, "timestamp": timestamp},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "customercode": CUSTOMER_CODE,
            "method": command,
            "command": "OWNWaterElecService",
        }
        plaintext = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        encrypted = AES.new(_derive_key(timestamp, random_str), AES.MODE_ECB).encrypt(
            pad(plaintext, AES.block_size)
        )
        try:
            response = self.session.post(
                API_URL,
                data={
                    "encryptData": base64.b64encode(encrypted).decode("ascii"),
                    "randomStr": random_str,
                    "timestamp": timestamp,
                    "method": command,
                },
                headers=REQUEST_HEADERS,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise MeterProtocolError(f"智能水电请求失败：{API_URL}") from exc
        if response.status_code != 200:
            raise MeterProtocolError(f"智能水电接口返回 HTTP {response.status_code}")
        try:
            payload = _json_object(response.text)
            encrypted_data = payload.get("encryptData")
            response_random = payload.get("randomStr")
            response_timestamp = payload.get("timestamp")
            if (
                not isinstance(encrypted_data, str)
                or not isinstance(response_random, str)
                or isinstance(response_timestamp, bool)
                or not isinstance(response_timestamp, (str, int))
            ):
                raise ValueError("智能水电加密响应缺少有效密钥或密文")
            response_key = _derive_key(str(response_timestamp), response_random)
            ciphertext = base64.b64decode(encrypted_data, validate=True)
            plaintext = unpad(
                AES.new(response_key, AES.MODE_ECB).decrypt(ciphertext),
                AES.block_size,
            )
            plain = _json_object(plaintext.decode("utf-8"))
            code = plain.get("code_")
            if (
                isinstance(code, bool)
                or not isinstance(code, (str, int, float))
                or (isinstance(code, str) and not code.strip())
            ):
                raise ValueError("智能水电响应缺少有效 code_")
            numeric_code = float(code)
            if not math.isfinite(numeric_code):
                raise ValueError("智能水电响应 code_ 不是有限数值")
            if numeric_code != 0:
                raise MeterBusinessError(
                    int(numeric_code) if numeric_code.is_integer() else numeric_code,
                    _raw_str(plain["message_"])
                    if plain.get("message_") is not None
                    else "查询失败",
                    API_URL,
                )
            body = plain.get("body")
            if not isinstance(body, str):
                raise ValueError("智能水电响应缺少 JSON 字符串 body")
            data = _json_object(body)
            result = data.get("result")
            if not isinstance(result, (str, int, float, bool)):
                raise ValueError("智能水电业务响应缺少有效 result")
            return data
        except (ValueError, TypeError, OverflowError) as exc:
            raise MeterProtocolError(f"智能水电响应格式或解密失败：{exc}") from exc
