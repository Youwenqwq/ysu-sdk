"""17wanxiao 智能水电查询协议常量。"""

from __future__ import annotations

API_URL = (
    "https://xqh5.17wanxiao.com/smartWaterAndElectricityService/SWAEEncryptServlet"
)
CUSTOMER_CODE = "2036"
RANDOM_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 16; PHY110 Build/UKQ1.231108.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 "
    "Mobile Safari/537.36 XWEB/1500047 MMWEBSDK/20260502 MicroMessenger/8.0.72.3100"
)
REFERER = "https://xqh5.17wanxiao.com/userwaterelecmini/index.html"
REQUEST_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": USER_AGENT,
    "Referer": REFERER,
    "Origin": "https://xqh5.17wanxiao.com",
    "X-Requested-With": "com.tencent.mm",
}
