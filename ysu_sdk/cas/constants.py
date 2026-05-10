"""常量：URL、字符集、MFA 类型映射、默认凭据路径。"""

from __future__ import annotations

from pathlib import Path

CER_BASE_URL: str = "https://cer.ysu.edu.cn"
AUTH_LOGIN_URL: str = f"{CER_BASE_URL}/authserver/login"
AUTH_INDEX_URL: str = f"{CER_BASE_URL}/authserver/index.do"
CHECK_CAPTCHA_URL: str = f"{CER_BASE_URL}/authserver/checkNeedCaptcha.htl"
GET_CAPTCHA_URL: str = f"{CER_BASE_URL}/authserver/getCaptcha.htl"
REAUTH_TYPE_URL: str = f"{CER_BASE_URL}/authserver/reAuthCheck/changeReAuthType.do"
REAUTH_SEND_CODE_URL: str = (
    f"{CER_BASE_URL}/authserver/dynamicCode/getDynamicCodeByReauth.do"
)
REAUTH_SUBMIT_URL: str = f"{CER_BASE_URL}/authserver/reAuthCheck/reAuthSubmit.do"

# 登录时给 CAS 的 stub service —— 用 cer 自身的页面，避免拉进任何业务系统
DEFAULT_LOGIN_SERVICE: str = f"{CER_BASE_URL}/personalInfo/personCenter/index.html"

# 前端 AES 加密使用的字符集
AES_CHARS: str = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"

# 仅暴露经实测的两种 MFA
MFA_METHOD_TO_CODE: dict[str, str] = {"sms": "3", "cpdaily": "5"}
MFA_METHOD_TO_AUTH_CODE_TYPE: dict[str, str] = {
    "sms": "reAuthDynamicCodeType",
    "cpdaily": "reAuthCpdailyDynamicCodeType",
}

# CAS 网关 cookie 所在的根域；持久化时按该域过滤
CAS_COOKIE_DOMAIN: str = "cer.ysu.edu.cn"

# 凭据持久化默认位置
DEFAULT_CREDENTIAL_PATH: Path = Path.home() / ".config" / "ysu-sdk" / "cas.json"
