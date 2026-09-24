"""在线综合支付平台的只读端点。"""

from __future__ import annotations

BASE_URL = "https://epay.ysu.edu.cn"
ALL_PAY_PATH = "/pay/allPay.html"
INDEX_PATH = "/pay/index.html"
SERVICE_URL = f"{BASE_URL}{ALL_PAY_PATH}"
MAX_HTML_BYTES = 2 * 1024 * 1024
