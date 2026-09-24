"""一卡通余额查询端点。"""

from __future__ import annotations

BASE_URL = "https://ehall.ysu.edu.cn"
SERVICE_PATH = "/publicapp/sys/myyktzd/index.do"
BALANCE_PATH = "/publicapp/sys/myyktzd/mySmartCard/loadSmartCardBillMain.do"
SERVICE_URL = f"{BASE_URL}{SERVICE_PATH}"
BALANCE_URL = f"{BASE_URL}{BALANCE_PATH}"

AJAX_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}
