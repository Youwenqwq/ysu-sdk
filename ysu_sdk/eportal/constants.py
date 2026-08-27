"""常量：URL、服务别名、登录错误码映射。"""

from __future__ import annotations

AUTH_BASE_URL: str = "https://auth1.ysu.edu.cn"

# —— ePortal 门户流程 ——
PORTAL_REDIRECT_URL: str = f"{AUTH_BASE_URL}/eportal/redirect.jsp?mode=history"
GET_ONLINE_USER_INFO_URL: str = f"{AUTH_BASE_URL}/eportal/adaptor/getOnlineUserInfo"
CURRENT_NODE_URL: str = f"{AUTH_BASE_URL}/eportal/workFlow/getCurrentNode"
SERVICE_SELECTION_URL: str = f"{AUTH_BASE_URL}/eportal/network/serviceSelection"
SERVICE_LOGIN_URL: str = f"{AUTH_BASE_URL}/eportal/network/serviceLogin"
USER_ONLINE_URL: str = f"{AUTH_BASE_URL}/eportal/network/userOnline"
ACCOUNT_INFO_URL: str = f"{AUTH_BASE_URL}/eportal/operator/getAccountInfo"
OFFLINE_URL: str = f"{AUTH_BASE_URL}/eportal/network/offline"

# —— cas-sso 登录页（锐捷内嵌的统一认证，非 cer 网关）——
CAS_SSO_LOGIN_URL: str = f"{AUTH_BASE_URL}/cas-sso/login"
# CAS 委托认证入口（页面上的「统一身份认证」外部提供者）
CLIENTREDIRECT_URL: str = (
    f"{AUTH_BASE_URL}/cas-sso/clientredirect?client_name=sidadapter"
)
CAPTCHA_COUNT_URL: str = (
    f"{AUTH_BASE_URL}/cas-sso/api/protected/user/captchaCount/validate"
)
# 验证码图片地址由 captchaCount 响应的 captchaUrl 给出（相对 /cas-sso/），
# 实测为 api/captcha/generate/DEFAULT?captchaModeType=1
CAS_SSO_PREFIX: str = f"{AUTH_BASE_URL}/cas-sso/"

DEFAULT_SERVICE: str = "校园网"

# 服务英文别名 → 服务端服务名（供不便输入中文的调用方使用）
SERVICE_ALIASES: dict[str, str] = {
    "campus": "校园网",
    "unicom": "中国联通",
    "telecom": "中国电信",
    "mobile": "中国移动",
}

# cas-sso 登录失败页 ``#login-error-msg`` 中的数字错误码 → 含义。
# 码表从前端 js（this.codeArray1）提取；只收录 UsernamePassword 流程会遇到的。
LOGIN_ERROR_MESSAGES: dict[str, str] = {
    "1320007": "需要输入验证码或验证码错误",
    "1030007": "需要输入验证码或验证码错误",
    "1030027": "用户名或密码错误",
    "1030031": "用户名或密码错误",
    "1030028": "账号已锁定，请稍后再试",
    "1410040": "用户名无效",
    "1410041": "用户名无效",
}

# 与验证码相关的错误码：提交后可换一张验证码重试
CAPTCHA_ERROR_CODES: frozenset[str] = frozenset({"1320007", "1030007"})

DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)
