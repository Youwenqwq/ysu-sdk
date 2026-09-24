"""费用 SDK 离线协议回归：仅使用合成数据，无凭据、无网络请求。

运行：uv run python scripts/smoke_fees_offline.py [-v]
依赖仅为 SDK 已有依赖；真实客户端通过 requests.Session 的封闭适配器收发，
CAS 仅替换 authorize 边界，水电夹具独立实现密钥派生及 PKCS7 编解码。
"""

from __future__ import annotations

import base64
import json
import unittest
from collections import deque
from collections.abc import Callable
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs

import requests
from Crypto.Cipher import AES
from requests.adapters import BaseAdapter

from ysu_sdk.ecard import EcardBusinessError, EcardClient, EcardProtocolError
from ysu_sdk.ecard import NotLoggedInError as EcardNotLoggedInError
from ysu_sdk.epay import EpayClient, EpayProtocolError
from ysu_sdk.epay import NotLoggedInError as EpayNotLoggedInError
from ysu_sdk.meter import MeterBusinessError, MeterClient, MeterProtocolError


METER_URL = "https://xqh5.17wanxiao.com/smartWaterAndElectricityService/SWAEEncryptServlet"
ECARD_URL = "https://ehall.ysu.edu.cn/publicapp/sys/myyktzd/mySmartCard/loadSmartCardBillMain.do"
HISTORY_URL = "https://epay.ysu.edu.cn/pay/allPay.html"
INDEX_URL = "https://epay.ysu.edu.cn/pay/index.html"
ACCOUNT = "offline-account"
ROOM = "fixture-room-token"


def response(body: Any, *, status: int = 200, url: str = "") -> requests.Response:
    """构造真实 Response；字符串原样传输，其他值编码为 JSON。"""
    result = requests.Response()
    result.status_code = status
    result.url = url
    result.encoding = "utf-8"
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    result._content = text.encode("utf-8")
    return result


class OfflineAdapter(BaseAdapter):
    """严格消费预先声明的请求；任何未知地址、方法或额外重试立即失败。"""

    def __init__(self) -> None:
        super().__init__()
        self.steps: deque[
            tuple[str, str, requests.Response | Callable[[requests.PreparedRequest], requests.Response]]
        ] = deque()

    def expect(
        self,
        method: str,
        url: str,
        reply: requests.Response | Callable[[requests.PreparedRequest], requests.Response],
    ) -> None:
        self.steps.append((method, url, reply))

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        if not self.steps:
            raise AssertionError(f"未声明的离线请求：{request.method} {request.url}")
        method, url, reply = self.steps.popleft()
        if (request.method, request.url) != (method, url):
            raise AssertionError(
                f"离线请求顺序不符：期待 {method} {url}，实际 {request.method} {request.url}"
            )
        result = reply(request) if callable(reply) else reply
        result.request = request
        result.url = result.url or request.url or ""
        return result

    def close(self) -> None:
        pass


class OfflineCAS:
    """仅替代授权边界，保留客户端自身的会话及重试状态机。"""

    def __init__(self) -> None:
        self.authorizations = 0

    def authorize(self, service: str, *, session: requests.Session) -> requests.Session:
        self.authorizations += 1
        return session


class OfflineCase(unittest.TestCase):
    """每例独立会话；移除默认网络适配器，并在 socket 层兜底禁止联网。"""

    def setUp(self) -> None:
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("离线回归禁止网络 I/O"))
            guard.start()
            self.addCleanup(guard.stop)
        self.session = requests.Session()
        self.session.trust_env = False
        for adapter in self.session.adapters.values():
            adapter.close()
        self.session.adapters.clear()
        self.adapter = OfflineAdapter()
        self.session.mount("", self.adapter)
        self.addCleanup(self.session.close)
        self.addCleanup(self.assert_consumed)
        self.cas = OfflineCAS()

    def assert_consumed(self) -> None:
        self.assertEqual(len(self.adapter.steps), 0, "存在未执行的预期协议请求")


def meter_key(timestamp: str, random_string: str) -> bytes:
    """按服务端协议独立派生 AES-128 密钥，不调用 SDK 私有函数。"""
    digits = timestamp[:6] if int(timestamp) % 2 else timestamp[-6:]
    return (digits + random_string).encode("ascii")


def meter_encrypted(envelope: dict[str, Any], timestamp: str) -> requests.Response:
    """使用独立的响应时间戳、随机串及手工 PKCS7 填充。"""
    random_string = "ABCDEFGHIJ"
    clear = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    padding = 16 - len(clear) % 16
    cipher = AES.new(meter_key(timestamp, random_string), AES.MODE_ECB)
    encrypted = cipher.encrypt(clear + bytes([padding]) * padding)
    return response({
        "timestamp": timestamp,
        "randomStr": random_string,
        "encryptData": base64.b64encode(encrypted).decode("ascii"),
    })


class MeterOfflineTests(OfflineCase):
    """真实四类水电查询、独立双向加密及错误边界。"""

    def setUp(self) -> None:
        super().setUp()
        for target, value in (
            ("ysu_sdk.meter.client.time.time", 1760000000.002),
            ("ysu_sdk.meter.client.secrets.choice", "Z"),
        ):
            fixed = patch(target, return_value=value)
            fixed.start()
            self.addCleanup(fixed.stop)
        self.client = MeterClient(ACCOUNT, session=self.session)

    def exchange(
        self,
        command: str,
        params: dict[str, str],
        body: dict[str, Any],
        *,
        response_timestamp: str = "1761234567891",
    ) -> None:
        def handle(request: requests.PreparedRequest) -> requests.Response:
            form = parse_qs(request.body.decode() if isinstance(request.body, bytes) else request.body)
            self.assertEqual(form["method"], [command])
            timestamp = form["timestamp"][0]
            random_string = form["randomStr"][0]
            self.assertRegex(timestamp, r"^[0-9]+$")
            self.assertRegex(random_string, r"^[0-9A-Z]{10}$")
            cipher = AES.new(meter_key(timestamp, random_string), AES.MODE_ECB)
            padded = cipher.decrypt(base64.b64decode(form["encryptData"][0], validate=True))
            padding = padded[-1]
            self.assertTrue(1 <= padding <= 16, "请求 PKCS7 填充长度无效")
            self.assertEqual(padded[-padding:], bytes([padding]) * padding)
            envelope = json.loads(padded[:-padding].decode("utf-8"))
            self.assertEqual(envelope["customercode"], "2036")
            self.assertEqual(envelope["command"], "OWNWaterElecService")
            self.assertEqual(envelope["method"], command)
            self.assertEqual(json.loads(envelope["param"]), {
                "cmd": command, "timestamp": timestamp, "account": ACCOUNT, **params,
            })
            self.assertNotEqual(meter_key(timestamp, random_string), meter_key(response_timestamp, "ABCDEFGHIJ"))
            return meter_encrypted({"code_": 0, "body": json.dumps(body)}, response_timestamp)

        self.adapter.expect("POST", METER_URL, handle)

    def test_room_even_request_odd_response(self) -> None:
        """偶数请求密钥与不同的奇数响应密钥均可互通。"""
        self.exchange("getbindroom", {}, {
            "result": "0", "roomfullname": "离线楼_示例房间", "roomverify": ROOM,
            "account_num": "fixture-meter-account",
        })
        room = self.client.query_room()
        self.assertIsNotNone(room)
        self.assertEqual((room.room_full_name, room.room_verify, room.account_num), (
            "离线楼_示例房间", ROOM, "fixture-meter-account",
        ))

    def test_overview_odd_request_even_response(self) -> None:
        """反向奇偶组合解密，并保留电表、月用量及线路描述。"""
        self.exchange("h5_getstuindexpage", {"roomverify": ROOM}, {
            "result": 0, "roomfullname": "离线楼_示例房间", "roomnum": "示例房间",
            "modlist": [{
                "devicename": "照明电表", "odd": "12.5", "todayuse": "0.75", "price": "0.5",
                "monthuselist": [{"yearmonth": "2026.08", "monthuse": "18.25"}],
                "linestatus": [{"desc": "正常供电"}, {"desc": "次要线路"}],
            }],
        }, response_timestamp="1761234567892")
        with patch("ysu_sdk.meter.client.time.time", return_value=1760000000.003):
            overview = self.client.query_overview(ROOM)
        self.assertIsNotNone(overview)
        self.assertEqual(overview.room_num, "示例房间")
        self.assertEqual([
            (m.device_name, m.remaining, m.today_use, m.price, m.line_desc)
            for m in overview.meters
        ], [("照明电表", 12.5, 0.75, 0.5, "正常供电")])
        self.assertEqual([(m.month, m.use) for m in overview.meters[0].month_use], [("2026.08", 18.25)])

    def test_daily_account_business_and_dates(self) -> None:
        """日用量请求必须携带账号、业务类型与完整日期区间。"""
        self.exchange("gettimeusedetail", {
            "roomverify": ROOM, "businesstype": "0", "startdate": "2026-08-01", "enddate": "2026-08-02",
        }, {"result": "0", "dayuselist": [
            {"date": "2026.08.01", "use": "0.25"}, {"date": "2026-08-02", "use": 0},
        ]})
        days = self.client.query_daily_use(ROOM, "2026-08-01", "2026-08-02")
        self.assertEqual([(day.date, day.use) for day in days], [("2026-08-01", 0.25), ("2026-08-02", 0.0)])

    def test_recharges_flatten_groups_and_normalize_times(self) -> None:
        """充值明细按月及月内顺序拍平，零元补电不伪造付款金额。"""
        self.exchange("h5_getrechargelist", {"roomverify": ROOM}, {"result": 0, "list": [
            {"dayrechargelist": [
                {"daytime": "2026-08-02 09:10:11", "name": "充值", "sumbuy": "20", "sumbuyfare": "10"},
                {"daytime": "2026-08-01 08:00:00", "name": "补电", "sumbuy": "2", "sumbuyfare": "0"},
            ]},
            {"dayrechargelist": []},
            {"dayrechargelist": [
                {"daytime": "2026-07-31 12:00:00", "name": "充值", "sumbuy": 10, "sumbuyfare": 5},
            ]},
        ]})
        records = self.client.query_recharges(ROOM)
        self.assertEqual([(r.time, r.name, r.amount, r.fare) for r in records], [
            ("2026-08-02T09:10:11", "充值", 20.0, 10.0),
            ("2026-08-01T08:00:00", "补电", 2.0, 0.0),
            ("2026-07-31T12:00:00", "充值", 10.0, 5.0),
        ])

    def test_no_binding_does_not_invent_room(self) -> None:
        """未绑定业务码与缺失查询凭据都不是虚构的空房间。"""
        for body in ({"result": "-20003"}, {"result": "0", "roomfullname": "无凭据房间"}):
            with self.subTest(body=body):
                self.exchange("getbindroom", {}, body)
                self.assertIsNone(self.client.query_room())

    def test_outer_rejection_does_not_retry_or_parse_body(self) -> None:
        """外层拒绝优先于损坏业务体，保留错误码且不重试。"""
        self.adapter.expect("POST", METER_URL, meter_encrypted({
            "code_": 503, "message_": "离线模拟业务拒绝", "body": "不是 JSON",
        }, "1761234567891"))
        with self.assertRaises(MeterBusinessError) as caught:
            self.client.query_room()
        self.assertEqual((caught.exception.code, caught.exception.msg), (503, "离线模拟业务拒绝"))

    def test_corrupt_ciphertext_is_protocol_error_without_retry(self) -> None:
        """无效 Base64 和有效 Base64 的非整块密文均不得降级为空绑定。"""
        for ciphertext in ("%%%", base64.b64encode(b"short").decode("ascii")):
            with self.subTest(ciphertext=ciphertext):
                self.adapter.expect("POST", METER_URL, response({
                    "timestamp": "1761234567891", "randomStr": "ABCDEFGHIJ", "encryptData": ciphertext,
                }))
                with self.assertRaises(MeterProtocolError):
                    self.client.query_room()


class EcardOfflineTests(OfflineCase):
    """一卡通金额、响应优先级与有限重授权。"""

    def setUp(self) -> None:
        super().setUp()
        self.client = EcardClient(self.cas, session=self.session)

    def balance_reply(self, body: Any, *, status: int = 200, url: str = "") -> None:
        self.adapter.expect("POST", ECARD_URL, response(body, status=status, url=url))

    def test_top_level_precedence_and_datas_fallback(self) -> None:
        """顶层零余额优先于 datas，缺失顶层时使用嵌套字段。"""
        self.balance_reply({
            "code": 200, "status": 200, "remining": "0.00", "cardnum": "top-card",
            "availdate": "2029-08-31", "cardstatusname": "在用", "yearMonths": ["2026-09", "2026-08"],
            "datas": {"KNYE": 99, "KH": "nested-card", "KYXQ": "2028-01-01", "MC": "挂失"},
        })
        top = self.client.query_balance()
        self.assertIsNotNone(top)
        self.assertEqual((top.balance, top.card_num, top.available_date, top.card_status_name),
                         (0.0, "top-card", "2029-08-31", "在用"))
        self.assertEqual(top.months, ["2026-09", "2026-08"])
        self.balance_reply({
            "remining": None, "id": "not-the-card", "datas": {
                "KNYE": " -2.50 ", "KH": "nested-card", "KYXQ": "2028-01-01", "MC": "挂失",
            },
        })
        nested = self.client.query_balance()
        self.assertIsNotNone(nested)
        self.assertEqual((nested.balance, nested.card_num, nested.available_date, nested.card_status_name),
                         (-2.5, "nested-card", "2028-01-01", "挂失"))
        self.assertEqual(self.cas.authorizations, 1)

    def test_no_card_is_not_zero_or_malformed_response(self) -> None:
        """有有效期但无余额返回 None，无法识别的响应不能伪装成无卡。"""
        self.balance_reply({"code": 200, "datas": {}, "availdate": "2029-08-31"})
        self.assertIsNone(self.client.query_balance())
        self.balance_reply({"message": "离线损坏响应"})
        with self.assertRaises(EcardProtocolError):
            self.client.query_balance()
        self.assertEqual(self.cas.authorizations, 1)

    def test_invalid_balances_do_not_fall_back_or_retry(self) -> None:
        """损坏顶层金额不回退到正常 datas；拒绝布尔值与非有限值。"""
        for value in ("unavailable", True, 1e309, "1e3"):
            with self.subTest(value=value):
                self.balance_reply({"remining": value, "datas": {"KNYE": 25}})
                with self.assertRaises(EcardProtocolError):
                    self.client.query_balance()
        self.assertEqual(self.cas.authorizations, 1)

    def test_business_rejection_is_not_expiry_or_balance(self) -> None:
        """拒绝码与 success=false 均保留为业务错误，不使用随附余额或重授权。"""
        for body, code in (
            ({"code": 500, "msg": "离线业务拒绝", "remining": "18.55"}, 500),
            ({"code": 200, "success": False, "msg": "离线业务拒绝", "remining": "18.55"}, 200),
        ):
            with self.subTest(code=code):
                self.balance_reply(body)
                with self.assertRaises(EcardBusinessError) as caught:
                    self.client.query_balance()
                self.assertEqual((caught.exception.code, caught.exception.msg), (code, "离线业务拒绝"))
        self.assertEqual(self.cas.authorizations, 1)

    def test_expiry_reauthorizes_once_then_returns_new_balance(self) -> None:
        """JSON 过期码优先于余额，重授权后只采用新余额。"""
        self.balance_reply({"code": "401", "remining": "999"})
        self.balance_reply('{code:200, datas:{KNYE:"18.55", KH:"fixture-card"}}')
        balance = self.client.query_balance()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.balance, 18.55)
        self.assertEqual(self.cas.authorizations, 2)

    def test_repeated_expiry_stops_after_one_retry(self) -> None:
        """HTTP 过期后仍返回登录页时抛认证错误，禁止第三次尝试。"""
        self.balance_reply({}, status=401)
        self.balance_reply('<html><form>请输入用户名</form></html>')
        with self.assertRaises(EcardNotLoggedInError):
            self.client.query_balance()
        self.assertEqual(self.cas.authorizations, 2)


# 故意打乱列顺序，并保留一个未使用列，防止解析器误用固定位置或零基下标。
EPAY_COLUMNS = {
    "payName": 1, "unused": 2, "expired": 3, "amountN": 4, "id": 5,
    "overTime": 6, "status": 7, "startTime": 8, "amount": 9,
}


def payment_row(
    identity: Any,
    name: str = "离线费用",
    amount: Any = "10.00",
    *,
    status: str = "1",
    expired: str = "0",
    paid_at: str = "",
) -> list[Any]:
    """合成付款行，不包含真实身份信息。"""
    return [name, "无关列", expired, amount, identity, paid_at, status, "2026-08-01", "10.00"]


def payment_page(
    rows: list[list[Any]], *, columns: dict[str, Any] | None = None, has_next: Any = 0,
) -> requests.Response:
    """真正的 HTML D 对象，混用未加引号的键与 JSON 字符串。"""
    names = EPAY_COLUMNS if columns is None else columns
    name_text = ",".join(f"{name}:{json.dumps(index)}" for name, index in names.items())
    data = (
        "{queryResult:{names:{" + name_text + "},rows:"
        + json.dumps(rows, ensure_ascii=False) + ",hasNextPage:" + json.dumps(has_next) + "}}"
    )
    return response('<html><script>var $E={D : ' + data + ',other:{ignored:true}};</script></html>')


class EpayOfflineTests(OfflineCase):
    """HTML 解码、双源付款语义与整次查询重启。"""

    def setUp(self) -> None:
        super().setUp()
        self.client = EpayClient(self.cas, session=self.session)

    def test_html_strings_columns_and_status_precedence(self) -> None:
        """字符串内的键样文本、括号、转义引号及尾反斜杠不破坏 D 提取。"""
        name = '离线费用 {status:1, nested:{x:2}} "引号" \\'
        self.adapter.expect("GET", HISTORY_URL, payment_page([]))
        self.adapter.expect("GET", INDEX_URL, payment_page([
            payment_row("paid", name, "10000", status="0", expired="1", paid_at="2026-08-02 09:10:11"),
            payment_row("expired", status="0", expired="1"),
            payment_row("closed", status="0"),
            payment_row("unknown", status="9"),
            payment_row("uncertain", expired=""),
            payment_row("pending", amount="12.50"),
        ]))
        result = self.client.query_payments()
        self.assertEqual([(r.id, r.record_status) for r in result.records], [
            ("paid", "paid"), ("expired", "expired"), ("closed", "closed"),
            ("unknown", "unknown"), ("uncertain", "unknown"), ("pending", "unpaid"),
        ])
        paid = result.records[0]
        self.assertEqual((paid.pay_name, paid.amount_n, paid.start_time, paid.over_time), (
            name, 10000.0, "2026-08-01", "2026-08-02T09:10:11",
        ))
        self.assertEqual([(r.id, r.amount_n) for r in result.unpaid], [("pending", 12.5)])

    def test_index_first_dedupe_and_authoritative_unpaid(self) -> None:
        """index 首条同 ID 优先；历史独有的未支付记录不计为欠费。"""
        self.adapter.expect("GET", HISTORY_URL, payment_page([
            payment_row("history-only", amount="900"),
            payment_row("shared", "历史已缴版本", paid_at="2026-08-01 12:00:00"),
        ]))
        self.adapter.expect("GET", INDEX_URL, payment_page([
            payment_row("shared", "当前待缴版本", "25"),
            payment_row("shared", "重复已缴版本", "999", paid_at="2026-08-02 12:00:00"),
        ]))
        result = self.client.query_payments()
        self.assertEqual([(r.id, r.pay_name, r.amount_n) for r in result.records], [
            ("shared", "当前待缴版本", 25.0), ("history-only", "离线费用", 900.0),
        ])
        self.assertEqual([(r.id, r.amount_n) for r in result.unpaid], [("shared", 25.0)])

    def test_invalid_identity_and_amount_reject_without_retry(self) -> None:
        """空标识、空名称、无效金额、布尔金额及非有限金额不是有效账单。"""
        for row in (
            payment_row(" "), payment_row("fixture", " "), payment_row("fixture", amount="损坏"),
            payment_row("fixture", amount=True), payment_row("fixture", amount="Infinity"),
        ):
            with self.subTest(row=row):
                self.adapter.expect("GET", HISTORY_URL, payment_page([row]))
                with self.assertRaises(EpayProtocolError):
                    self.client.query_payments()
        self.assertEqual(self.cas.authorizations, 1)

    def test_missing_status_and_invalid_column_reject_without_retry(self) -> None:
        """缺少状态列不能推断欠费；零基映射不能当作合法一基列。"""
        missing = {name: index for name, index in EPAY_COLUMNS.items() if name != "status"}
        for columns in (missing, {**EPAY_COLUMNS, "id": 0}):
            with self.subTest(columns=columns):
                self.adapter.expect("GET", HISTORY_URL, payment_page([payment_row("fixture")], columns=columns))
                with self.assertRaises(EpayProtocolError):
                    self.client.query_payments()
        self.assertEqual(self.cas.authorizations, 1)

    def test_incomplete_pagination_rejects_even_empty_page(self) -> None:
        """后续分页与未知分页标志都不能被当作完整的空账单。"""
        for next_page in (1, "unknown"):
            with self.subTest(next_page=next_page):
                self.adapter.expect("GET", HISTORY_URL, payment_page([], has_next=next_page))
                with self.assertRaises(EpayProtocolError):
                    self.client.query_payments()
        self.assertEqual(self.cas.authorizations, 1)

    def test_missing_html_data_and_http_rejection_do_not_retry(self) -> None:
        """格式错误与 HTTP 拒绝不是认证过期，不触发整次重试。"""
        for reply in (response("<html>离线损坏页面</html>"), response("离线服务拒绝", status=503)):
            with self.subTest(status=reply.status_code):
                self.adapter.expect("GET", HISTORY_URL, reply)
                with self.assertRaises(EpayProtocolError):
                    self.client.query_payments()
        self.assertEqual(self.cas.authorizations, 1)

    def test_index_expiry_restarts_whole_query(self) -> None:
        """index 过期后重新读取历史，不能把旧半次结果混入新会话。"""
        self.adapter.expect("GET", HISTORY_URL, payment_page([payment_row("stale-history")]))
        self.adapter.expect("GET", INDEX_URL, response(
            "<html>sign in</html>", url="https://auth.ysu.edu.cn/authserver/login",
        ))
        self.adapter.expect("GET", HISTORY_URL, payment_page([
            payment_row("fresh-history", paid_at="2026-08-01 12:00:00"),
        ]))
        self.adapter.expect("GET", INDEX_URL, payment_page([payment_row("fresh-pending", amount="30")]))
        result = self.client.query_payments()
        self.assertEqual([r.id for r in result.records], ["fresh-pending", "fresh-history"])
        self.assertEqual([(r.id, r.amount_n) for r in result.unpaid], [("fresh-pending", 30.0)])
        self.assertEqual(self.cas.authorizations, 2)

    def test_repeated_index_expiry_stops_after_one_restart(self) -> None:
        """第二次查询仍过期时直接抛认证错误，禁止无限重启。"""
        for _ in range(2):
            self.adapter.expect("GET", HISTORY_URL, payment_page([]))
            self.adapter.expect("GET", INDEX_URL, response("会话过期", status=401))
        with self.assertRaises(EpayNotLoggedInError):
            self.client.query_payments()
        self.assertEqual(self.cas.authorizations, 2)


if __name__ == "__main__":
    unittest.main()
