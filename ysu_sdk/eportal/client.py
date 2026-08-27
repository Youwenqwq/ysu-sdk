"""ePortal（锐捷校园网认证）客户端：登录、登出、在线状态查询。

目标系统是 ``auth1.ysu.edu.cn`` 的锐捷 ePortal，与 CAS 网关（cer）无关：
认证走的是 portal 内嵌的 cas-sso 页面（AES-ECB 加密，key 内嵌于页面），
全程只需要校园网内网可达，不依赖统一身份认证的 TGC。

完整登录流程（与浏览器一致）：

1. ``GET /eportal/redirect.jsp?mode=history`` —— 302 到占位 IP，NAS 劫持后
   JS 跳转到 ``/eportal/index.jsp?wlanuserip=<加密参数>``，再 302 到
   ``portal-main?sessionId=...``，从落地 URL 解析会话参数；
2. ``GET /cas-sso/login?...`` —— 拿到登录页内嵌的 ``croypto``（AES key）
   与 ``execution``（flowkey）；
3. ``GET /cas-sso/api/protected/user/captchaCount/validate`` —— 查询该账号
   是否需要图形验证码（需 CSRF 头，见 :func:`_make_csrf_headers`）；
4. 需要时 ``GET captchaUrl`` 取 PNG，交给 ``captcha_solver`` 回调；
5. ``POST /cas-sso/login`` 提交表单；失败时页面重渲染并携带数字错误码
   （``#login-error-msg``），成功后 302 链上会出现 ``auth-success``/``ticket=``；
6. 查 ``userOnline``：未在线则流程停在服务选择节点，走
   ``serviceSelection`` → ``serviceLogin`` 完成准入后复查 ``userOnline``。
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse
from typing import TYPE_CHECKING, Any, Callable

import requests

if TYPE_CHECKING:
    from ysu_sdk.cas import CASClient

from ysu_sdk.eportal._crypto import aes_ecb_encrypt
from ysu_sdk.eportal._parser import (
    LoginMaterial,
    extract_js_redirect,
    extract_login_error_code,
    extract_login_material,
)
from ysu_sdk.eportal.constants import (
    CAPTCHA_COUNT_URL,
    CAPTCHA_ERROR_CODES,
    CAS_SSO_LOGIN_URL,
    CAS_SSO_PREFIX,
    CLIENTREDIRECT_URL,
    DEFAULT_SERVICE,
    DEFAULT_USER_AGENT,
    GET_ONLINE_USER_INFO_URL,
    LOGIN_ERROR_MESSAGES,
    OFFLINE_URL,
    PORTAL_REDIRECT_URL,
    SERVICE_ALIASES,
    SERVICE_LOGIN_URL,
    SERVICE_SELECTION_URL,
    USER_ONLINE_URL,
)
from ysu_sdk.eportal.exceptions import (
    CaptchaFailedError,
    EPortalAuthError,
    EPortalBusinessError,
    EPortalNetworkError,
    EPortalProtocolError,
    NeedCaptchaError,
)
from ysu_sdk.eportal.types import OnlineStatus

_CSRF_CHARS: str = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
)


def _make_csrf_headers() -> dict[str, str]:
    """生成 ``/api/protected/`` 端点要求的 Csrf-Key / Csrf-Value 头。

    规则逆向自前端 js：``Csrf-Key`` 为 32 位随机串 ``a``，
    ``Csrf-Value = MD5(s[:n/2] + s + s[n/2:])``，其中 ``s = Base64(a)``。
    """
    key = "".join(secrets.choice(_CSRF_CHARS) for _ in range(32))
    s = base64.b64encode(key.encode()).decode()
    half = len(s) // 2
    value = hashlib.md5((s[:half] + s + s[half:]).encode()).hexdigest()
    return {"Csrf-Key": key, "Csrf-Value": value}


class EPortalClient:
    """锐捷 ePortal 校园网认证客户端。

    仅在校园网内可用；所有方法在门户不可达时抛 :class:`EPortalNetworkError`，
    不会把网络故障误报为「离线」。

    客户端持有独立的 ``requests.Session``（门户会在上面落 ``JSESSIONID``
    （``/eportal``）与 ``SESSION``（``/cas-sso/``）两个 cookie，验证码图片
    与登录提交都依赖后者）。
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        # NAS 劫持页对非浏览器特征的请求直接丢包（实测仅带 User-Agent 不够，
        # 需要完整的 Accept/Accept-Language），这里补齐默认头
        self.session.headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8",
        )
        self.session.headers.setdefault("Accept-Language", "zh-CN,zh;q=0.9")
        self.timeout = timeout

    # ──────────────────────────────────────────────────────────────────── #
    # 公开 API
    # ──────────────────────────────────────────────────────────────────── #

    def get_status(self) -> OnlineStatus:
        """查询当前设备的在线状态（无需认证凭据）。

        注意 ``getOnlineUserInfo`` 按 ``sessionId`` 出记录：**无效 sessionId
        会返回一条伪造的离线记录**（``result="fail"``），因此本方法必须先经
        portal 入口拿到一个真实流程会话。副作用：设备离线时每次调用都会在
        portal 侧创建一个流程会话（与浏览器打开认证页的行为一致）。

        Raises:
            EPortalNetworkError: 门户不可达（多半是不在校园网内），或设备
                离线且 NAS 劫持不应答。
            EPortalProtocolError: 响应不符合 envelope 预期。
        """
        session_info = self._fetch_session_info()
        return self._query_status(session_info["sessionId"])

    def _query_status(self, session_id: str) -> OnlineStatus:
        """用真实流程 sessionId 查询在线状态。"""
        params = {"sessionId": session_id, "_": str(int(time.time() * 1000))}
        data = self._get_json(GET_ONLINE_USER_INFO_URL, params=params)
        info = data.get("portalOnlineUserInfo")
        if not isinstance(info, dict):
            raise EPortalProtocolError(
                f"getOnlineUserInfo missing portalOnlineUserInfo: {data!r}"
            )
        # 离线时 result="fail" 且 redirectUrl 非空；在线时 result="success"
        online = info.get("result") == "success" or bool(info.get("userName"))
        return OnlineStatus(
            online=online,
            username=info.get("userName") or None,
            service=info.get("realServiceName") or info.get("service") or None,
            user_ip=info.get("userIp") or None,
            user_mac=info.get("userMac") or None,
            message=info.get("message") or None,
            raw=info,
        )

    def login(
        self,
        username: str,
        password: str,
        *,
        service: str = DEFAULT_SERVICE,
        captcha_solver: Callable[[bytes], str] | None = None,
        max_captcha_attempts: int = 3,
    ) -> OnlineStatus:
        """完成一次完整的校园网认证登录；已在线时直接返回当前状态。

        Args:
            username: 准入账号（学工号）。
            password: 密码。
            service: 网络服务名（``"校园网"`` / ``"中国联通"`` / …），
                也接受 ``SERVICE_ALIASES`` 里的英文别名（``"campus"`` 等）。
            captcha_solver: 图形验证码回调，入参为 PNG 字节流，返回识别结果。
                当前服务端对所有账号强制验证码，不提供时抛
                :class:`NeedCaptchaError`。
            max_captcha_attempts: 验证码识别错误时的最大重试次数（每次都会
                重新抓取登录页与验证码）。

        Returns:
            登录校验通过后的 :class:`OnlineStatus`。

        Raises:
            NeedCaptchaError: 需要验证码但未提供 ``captcha_solver``。
            CaptchaFailedError: 连续 ``max_captcha_attempts`` 次验证码被拒。
            EPortalAuthError: 认证被服务端拒绝（密码错误、账号锁定等），
                具体原因见 ``code`` 与异常消息。
            EPortalBusinessError: 准入流程接口返回业务拒绝。
            EPortalNetworkError / EPortalProtocolError: 传输或协议异常。
        """
        session_info = self._fetch_session_info()
        session_id = session_info["sessionId"]
        status = self._query_status(session_id)
        if status.online:
            return status
        service = SERVICE_ALIASES.get(service, service)

        captcha_code = ""
        for attempt in range(max_captcha_attempts):
            login_url, material = self._fetch_login_material(session_info)
            required, captcha_url = self._captcha_required(username)
            if required:
                if captcha_solver is None:
                    raise NeedCaptchaError(
                        "服务端要求图形验证码，请提供 captcha_solver 回调"
                    )
                captcha_code = captcha_solver(self._fetch_captcha(captcha_url))
            try:
                self._submit_login(
                    login_url, material, username, password, captcha_code
                )
                break
            except EPortalAuthError as exc:
                if (
                    exc.code in CAPTCHA_ERROR_CODES
                    and captcha_solver is not None
                    and attempt + 1 < max_captcha_attempts
                ):
                    continue
                if exc.code in CAPTCHA_ERROR_CODES and captcha_solver is not None:
                    raise CaptchaFailedError(
                        f"连续 {max_captcha_attempts} 次验证码均被拒绝"
                    ) from exc
                raise
        else:
            # 理论上到不了（循环内非验证码错误都会直接 raise），防御一下
            raise EPortalProtocolError("login attempts exhausted unexpectedly")

        return self._finish_admission(session_id, service)

    def login_via_cas(
        self, cas: CASClient, *, service: str = DEFAULT_SERVICE
    ) -> OnlineStatus:
        """通过统一身份认证（CAS 委托）完成校园网认证。

        与 :meth:`login` 的差别仅在身份验证一跳：走登录页上的
        「统一身份认证」外部提供者（``clientredirect?client_name=sidadapter``），
        跳转到 CAS 网关认证后带 ticket 回跳。持有有效 TGC（如
        ``CASClient(credential=CASCredential.load())``）时全程**免密、
        免验证码**；TGC 失效则由 :meth:`CASClient.login` 之类的调用方先行
        补齐（本方法不处理 CAS 侧登录）。

        Args:
            cas: 已认证的 :class:`CASClient`（持有有效 TGC）。
            service: 网络服务名，同 :meth:`login`。

        Returns:
            登录校验通过后的 :class:`OnlineStatus`。

        Raises:
            NotAuthenticatedError: ``cas`` 未持有有效 TGC。
            EPortalAuthError / EPortalBusinessError: 准入阶段被拒。
            EPortalNetworkError / EPortalProtocolError: 传输或协议异常。
        """
        session_info = self._fetch_session_info()
        session_id = session_info["sessionId"]
        status = self._query_status(session_id)
        if status.online:
            return status
        service = SERVICE_ALIASES.get(service, service)

        # GET 登录页：把流程会话绑定到 SESSION cookie（委托认证依赖此绑定）
        self._request("GET", self._cas_sso_login_url(session_info))

        # clientredirect → cer CAS 登录 URL（service 参数即回跳地址）
        resp = self._request("GET", CLIENTREDIRECT_URL, allow_redirects=False)
        location = resp.headers.get("Location", "")
        if "/authserver/login" not in location:
            raise EPortalProtocolError(
                f"clientredirect did not point to CAS login: {location!r}"
            )
        service_url = urllib.parse.parse_qs(
            urllib.parse.urlparse(location).query
        ).get("service", [""])[0]
        if not service_url:
            raise EPortalProtocolError(
                f"CAS login URL missing service param: {location!r}"
            )

        # 用 cas 侧的 TGC 出票；ticket 消费与流程推进都落在本 session 上
        st = cas.get_service_ticket(service_url)
        sep = "&" if "?" in service_url else "?"
        final = self._request("GET", f"{service_url}{sep}ticket={st}")

        # 回跳后的页面可能用 JS 跳转继续流程（auth-success 等），手动跟随
        for _ in range(5):
            target = extract_js_redirect(final.text)
            if target is None:
                break
            final = self._request("GET", urllib.parse.urljoin(final.url, target))

        return self._finish_admission(session_id, service)

    def logout(self) -> None:
        """登出当前设备；已离线时为 no-op。

        Raises:
            EPortalBusinessError: 服务端拒绝下线。
            EPortalNetworkError / EPortalProtocolError: 传输或协议异常。
        """
        session_info = self._fetch_session_info()
        status = self._query_status(session_info["sessionId"])
        if not status.online:
            return
        self._post_json(OFFLINE_URL, {"sessionId": session_info["sessionId"]})

    # ──────────────────────────────────────────────────────────────────── #
    # 准入收尾（login / login_via_cas 共用）
    # ──────────────────────────────────────────────────────────────────── #

    def _finish_admission(self, session_id: str, service: str) -> OnlineStatus:
        """cas-sso 认证完成后的准入收尾。

        认证成功后流程通常停在服务选择节点：先查 ``userOnline``，未在线则走
        ``serviceSelection`` → ``serviceLogin`` 完成准入；少数账号可能随
        重定向链自动完成准入，则跳过服务选择。
        """
        online_data = self._post_json(USER_ONLINE_URL, {"sessionId": session_id})
        if not (isinstance(online_data, dict) and online_data.get("online")):
            self._post_json(SERVICE_SELECTION_URL, {"sessionId": session_id})
            login_data = self._post_json(
                SERVICE_LOGIN_URL, {"sessionId": session_id, "service": service}
            )
            if isinstance(login_data, dict):
                auth_result = login_data.get("authResult")
                if auth_result == "fail":
                    raise EPortalAuthError(
                        f"准入失败: {login_data.get('authMessage', '未知原因')}"
                    )
                if auth_result is not None and auth_result != "success":
                    raise EPortalProtocolError(
                        f"unexpected authResult from serviceLogin: {auth_result!r}"
                    )
            online_data = self._post_json(
                USER_ONLINE_URL, {"sessionId": session_id}
            )
            if not (
                isinstance(online_data, dict) and online_data.get("online")
            ):
                raise EPortalAuthError(
                    f"登录校验失败: "
                    f"{online_data.get('message', '认证后用户不在线')}"
                )

        return self._query_status(session_id)

    # ──────────────────────────────────────────────────────────────────── #
    # 门户会话
    # ──────────────────────────────────────────────────────────────────── #

    def _fetch_session_info(self) -> dict[str, str]:
        """跟随 portal 跳转链，解析 ``portal-main`` 落地 URL 上的会话参数。

        手动跟随 30x 与 ``location.href=`` 形式的 JS 跳转。注意两种已知
        异常情况：

        - 设备存在未完成的认证流程时，``redirect.jsp`` 会 302 到占位 IP
          （如 ``http://124.124.124.124``），依赖 NAS 劫持该请求重新带回
          portal 页面；若 NAS 不应答（限速惩罚等），抛
          :class:`EPortalNetworkError`。
        - 设备已在线时落地 URL 仍含 ``sessionId``（多一个
          ``userOnline=true``），正常解析即可。
        """
        url = PORTAL_REDIRECT_URL
        for _ in range(10):
            try:
                resp = self._request("GET", url, allow_redirects=False)
            except EPortalNetworkError as exc:
                raise EPortalNetworkError(
                    f"portal redirect chain broken at {url}: {exc}. "
                    "若目标是占位 IP（如 124.124.124.124），说明设备存在未完成"
                    "的认证流程且 NAS 未应答劫持请求——稍后在浏览器访问任意 "
                    "HTTP 页面触发认证页，或等流程会话过期后重试"
                ) from exc
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if not location:
                    raise EPortalProtocolError(
                        f"redirect without Location from {url}"
                    )
                url = urllib.parse.urljoin(url, location)
                continue
            target = extract_js_redirect(resp.text)
            if target is None:
                break
            url = urllib.parse.urljoin(url, target)
        else:
            raise EPortalProtocolError("portal redirect chain too long")

        if "portal-main" not in url:
            raise EPortalProtocolError(
                f"portal redirect did not land on portal-main: {url}"
            )
        params = {
            k: v[0]
            for k, v in urllib.parse.parse_qs(
                urllib.parse.urlparse(url).query
            ).items()
        }
        if not params.get("sessionId"):
            raise EPortalProtocolError(
                f"portal-main URL missing sessionId: {url}"
            )
        return params

    def _cas_sso_login_url(self, session_info: dict[str, str]) -> str:
        """构造携带流程会话参数的 cas-sso 登录页 URL。"""
        query = urllib.parse.urlencode(
            {
                "flowSessionId": session_info.get("sessionId", ""),
                "customPageId": session_info.get("customPageId", ""),
                "preview": "false",
                "appType": "normal",
                "language": "zh-CN",
                "mode": session_info.get("mode", ""),
                "timer": str(int(time.time() * 1000)),
                "nasIp": session_info.get("nasIp", ""),
                "userIp": session_info.get("userIp", ""),
                "ssid": session_info.get("ssid", ""),
            }
        )
        return f"{CAS_SSO_LOGIN_URL}?{query}"

    def _fetch_login_material(
        self, session_info: dict[str, str]
    ) -> tuple[str, LoginMaterial]:
        """GET cas-sso 登录页，返回（登录 URL, 页面内嵌材料）。

        副作用：建立 ``SESSION`` cookie（path ``/cas-sso/``）并把流程会话
        绑定到它——CAS 委托认证依赖这个绑定。
        """
        login_url = self._cas_sso_login_url(session_info)
        resp = self._request("GET", login_url)
        return login_url, extract_login_material(resp.text)

    # ──────────────────────────────────────────────────────────────────── #
    # cas-sso 登录提交
    # ──────────────────────────────────────────────────────────────────── #

    def _captcha_required(self, username: str) -> tuple[bool, str | None]:
        """查询该账号是否需要图形验证码，返回（是否需要, 验证码图片 URL）。"""
        data = self._get_json(
            CAPTCHA_COUNT_URL,
            params={"userName": username},
            headers=_make_csrf_headers(),
        )
        if not isinstance(data, dict):
            raise EPortalProtocolError(f"unexpected captchaCount data: {data!r}")
        return bool(data.get("captchaInvisible")), data.get("captchaUrl") or None

    def _fetch_captcha(self, captcha_url: str | None) -> bytes:
        """下载验证码 PNG（绑定当前 session 的 ``SESSION`` cookie）。"""
        if not captcha_url:
            captcha_url = "api/captcha/generate/DEFAULT?captchaModeType=1"
        url = urllib.parse.urljoin(CAS_SSO_PREFIX, captcha_url)
        resp = self._request("GET", url)
        if not resp.content.startswith(b"\x89PNG"):
            raise EPortalProtocolError(
                f"captcha response is not a PNG (len={len(resp.content)})"
            )
        return resp.content

    def _submit_login(
        self,
        login_url: str,
        material: LoginMaterial,
        username: str,
        password: str,
        captcha_code: str,
    ) -> None:
        """提交 cas-sso 登录表单；失败时按页面错误码抛 :class:`EPortalAuthError`。"""
        form = {
            "username": username,
            "type": "UsernamePassword",
            "_eventId": "submit",
            "geolocation": "",
            "execution": material.execution,
            "captcha_code": captcha_code,
            "croypto": material.croypto,
            "password": aes_ecb_encrypt(material.croypto, password),
            "captcha_payload": aes_ecb_encrypt(material.croypto, "{}"),
        }
        resp = self._request(
            "POST", f"{login_url}&accept-language=zh-CN", data=form
        )
        if self._login_succeeded(resp):
            return
        code = extract_login_error_code(resp.text)
        if code is not None:
            raise EPortalAuthError(
                LOGIN_ERROR_MESSAGES.get(code, f"登录被拒绝（错误码 {code}）"),
                code=code,
            )
        raise EPortalProtocolError(
            f"cas-sso login result page has neither success redirect nor error code"
            f" (final URL: {resp.url})"
        )

    @staticmethod
    def _login_succeeded(resp: requests.Response) -> bool:
        """成功标志：302 链（含最终 URL）中出现 ``auth-success`` 或 ``ticket=``。"""
        candidates = [r.url for r in resp.history] + [resp.url]
        candidates += [
            r.headers.get("Location", "") for r in resp.history
        ]
        return any(
            "auth-success" in u or "ticket=" in u for u in candidates
        )

    # ──────────────────────────────────────────────────────────────────── #
    # HTTP 出口（envelope 解包与异常分层的唯一入口）
    # ──────────────────────────────────────────────────────────────────── #

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise EPortalNetworkError(
                f"ePortal unreachable (not on campus network?): {exc}"
            ) from exc
        return resp

    def _unwrap_json(self, resp: requests.Response, url: str) -> Any:
        """解包 ePortal JSON envelope：``{"code": 200, "message": ..., "data": ...}``。"""
        try:
            payload = resp.json()
        except ValueError as exc:
            raise EPortalProtocolError(
                f"non-JSON response from {url}: {resp.text[:200]!r}"
            ) from exc
        if not isinstance(payload, dict) or "code" not in payload:
            raise EPortalProtocolError(
                f"malformed envelope from {url}: {payload!r}"
            )
        code = payload.get("code")
        if code != 200:
            raise EPortalBusinessError(code, payload.get("message"), url)
        return payload.get("data")

    def _get_json(self, url: str, **kwargs: Any) -> Any:
        return self._unwrap_json(self._request("GET", url, **kwargs), url)

    def _post_json(self, url: str, payload: dict[str, Any]) -> Any:
        resp = self._request("POST", url, json=payload)
        return self._unwrap_json(resp, url)
