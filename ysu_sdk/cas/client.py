"""CAS 客户端：登录、MFA、跨 service 出票。"""

from __future__ import annotations

import re
import time
import urllib.parse
from typing import Any, Callable

import requests

from ysu_sdk.cas._crypto import encrypt_password
from ysu_sdk.cas._parser import (
    extract_error_message,
    extract_hidden_fields,
    is_ip_frozen,
    is_reauth_page,
)
from ysu_sdk.cas.constants import (
    AUTH_INDEX_URL,
    AUTH_LOGIN_URL,
    CER_BASE_URL,
    CHECK_CAPTCHA_URL,
    DEFAULT_LOGIN_SERVICE,
    GET_CAPTCHA_URL,
    MFA_METHOD_TO_AUTH_CODE_TYPE,
    MFA_METHOD_TO_CODE,
    REAUTH_SEND_CODE_URL,
    REAUTH_SUBMIT_URL,
    REAUTH_TYPE_URL,
)
from ysu_sdk.cas.credential import CASCredential
from ysu_sdk.cas.exceptions import (
    CASNetworkError,
    CASProtocolError,
    IPBlockedError,
    LoginFailedError,
    MFAFailedError,
    MFARequiredError,
    NeedCaptchaError,
    NotAuthenticatedError,
)
from ysu_sdk.cas.types import (
    CaptchaChallenge,
    MFAChallenge,
    MFAMethod,
    Step1Result,
)


_TICKET_RE = re.compile(r"ticket=(ST-[^&\s]+)")


class CASClient:
    """燕山大学统一身份认证（CAS）网关客户端。

    所有需要登录态的方法都依赖 ``self.session`` 中持有的 ``CASTGC``
    cookie。通过 :meth:`authorize` 可以把这份凭据用到任意 service URL
    上，从而拿到该业务系统的 per-service cookie。
    """

    def __init__(
        self,
        credential: CASCredential | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        if credential is not None:
            credential.apply(self.session)

    # ──────────────────────────────────────────────────────────────────── #
    # 状态
    # ──────────────────────────────────────────────────────────────────── #

    def is_authenticated(self) -> bool:
        """判断当前 session 是否仍持有有效 TGC。

        实现：``GET /authserver/index.do``，``allow_redirects=False``。
        - 302 到登录页 → ``False``；
        - 200 或 302 到非登录页 → ``True``。

        Raises:
            CASNetworkError: 网关不可达（连接被拒、超时、被 WAF 重置等）。
                不会把传输层失败误报为「未认证」。
        """
        try:
            resp = self.session.get(
                AUTH_INDEX_URL,
                allow_redirects=False,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise CASNetworkError(f"CAS gateway unreachable: {exc}") from exc
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            return "/authserver/login" not in location
        return resp.status_code == 200

    def credential(self) -> CASCredential:
        """从当前 session 提取一份新鲜的 :class:`CASCredential`。"""
        return CASCredential.from_session(self.session)

    # ──────────────────────────────────────────────────────────────────── #
    # 一次性登录（交互式 / 阻塞式）
    # ──────────────────────────────────────────────────────────────────── #

    def login(
        self,
        username: str,
        password: str,
        *,
        captcha_solver: Callable[[CaptchaChallenge], str] | None = None,
        mfa_handler: Callable[[MFAChallenge], str] | None = None,
        mfa_method: MFAMethod = "cpdaily",
    ) -> CASCredential:
        """完成一次完整登录。两个回调都是同步的，会阻塞到调用方返回字符串为止。

        Raises:
            NeedCaptchaError: 需要图形验证码但未提供 ``captcha_solver``。
            MFARequiredError: 需要 MFA 但未提供 ``mfa_handler``。
            LoginFailedError: 用户名/密码错误。
            IPBlockedError: 当前 IP 被冻结。
            MFAFailedError: MFA 验证码错误或过期。
        """
        captcha_str = ""
        captcha = self.fetch_captcha(username)
        if captcha is not None:
            if captcha_solver is None:
                raise NeedCaptchaError("server requires a captcha but no solver was provided")
            captcha_str = captcha_solver(captcha)

        step1 = self.login_step1(username, password, captcha=captcha_str)

        if step1.authenticated:
            return self.credential()

        if step1.needs_mfa:
            if mfa_handler is None:
                raise MFARequiredError("server requires MFA but no handler was provided")
            challenge = self.request_mfa_code(username, method=mfa_method)
            code = mfa_handler(challenge)
            if not code or not code.strip():
                raise MFAFailedError("empty MFA code")
            return self.submit_mfa_code(challenge, code.strip())

        raise CASProtocolError("login_step1 returned an ambiguous result")

    # ──────────────────────────────────────────────────────────────────── #
    # 编程式分步入口
    # ──────────────────────────────────────────────────────────────────── #

    def fetch_captcha(self, username: str) -> CaptchaChallenge | None:
        """如果服务端要求验证码则抓取图片，否则返回 ``None``。"""
        try:
            resp = self.session.get(
                CHECK_CAPTCHA_URL,
                params={"username": username},
                timeout=min(self.timeout, 10),
            )
            data = resp.json()
        except (requests.RequestException, ValueError):
            return None

        if not data.get("isNeed", False):
            return None

        img_resp = self.session.get(
            GET_CAPTCHA_URL,
            params={"_": int(time.time() * 1000)},
            timeout=min(self.timeout, 10),
        )
        img_resp.raise_for_status()
        return CaptchaChallenge(image_png=img_resp.content)

    def login_step1(
        self,
        username: str,
        password: str,
        *,
        captcha: str | None = None,
    ) -> Step1Result:
        """提交第一重凭据，返回结构化结果。

        Raises:
            NeedCaptchaError: 服务端拒绝缺失/错误的验证码。
            IPBlockedError: 当前 IP 被冻结。
            LoginFailedError: 用户名 / 密码错误。
            CASProtocolError: 登录页结构与预期不符。
        """
        html = self._get_login_page()
        fields = extract_hidden_fields(html, cllt="userNameLogin")
        execution = fields.get("execution")
        salt = fields.get("pwdEncryptSalt")
        if not execution:
            raise CASProtocolError("login page missing 'execution' field")
        if not salt:
            raise CASProtocolError("login page missing 'pwdEncryptSalt' field")

        encrypted = encrypt_password(password, salt)
        data = {
            "username": username,
            "password": encrypted,
            "captcha": captcha or "",
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": execution,
        }
        encoded_service = urllib.parse.quote(DEFAULT_LOGIN_SERVICE, safe="")
        login_url = (
            f"{AUTH_LOGIN_URL}?service={encoded_service}"
            f"&_={int(time.time() * 1000)}"
        )
        resp = self.session.post(
            login_url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": CER_BASE_URL,
                "Referer": f"{AUTH_LOGIN_URL}?service={encoded_service}",
            },
            allow_redirects=False,
            timeout=self.timeout,
        )
        return self._classify_step1_response(resp, username)

    def request_mfa_code(
        self,
        username: str,
        method: MFAMethod = "cpdaily",
    ) -> MFAChallenge:
        """切换 MFA 类型并请求一次性验证码。"""
        type_code = MFA_METHOD_TO_CODE[method]
        encoded_service = urllib.parse.quote(DEFAULT_LOGIN_SERVICE, safe="")
        referer = (
            f"{CER_BASE_URL}/authserver/reAuthCheck/reAuthLoginView.do"
            f"?isMultifactor=true&service={encoded_service}"
        )

        # 1. 切换 reAuthType
        self.session.post(
            REAUTH_TYPE_URL,
            data={
                "isMultifactor": "true",
                "reAuthType": type_code,
                "service": DEFAULT_LOGIN_SERVICE,
            },
            headers={
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=min(self.timeout, 15),
        )

        # 2. 请求验证码
        auth_code_type = MFA_METHOD_TO_AUTH_CODE_TYPE[method]
        resp = self.session.post(
            REAUTH_SEND_CODE_URL,
            data={
                "userName": username,
                "authCodeTypeName": auth_code_type,
            },
            headers={
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=min(self.timeout, 15),
        )
        try:
            result: dict[str, Any] = resp.json()
        except ValueError as exc:
            raise CASProtocolError(
                f"reauth send-code returned non-JSON: {resp.text[:200]!r}"
            ) from exc

        res = result.get("res", "")
        msg = result.get("returnMessage", "")

        if res in ("success", "cpdaily_success", "wechat_success"):
            return MFAChallenge(
                method=method,
                method_code=type_code,
                mobile_hint=str(result.get("mobile", "")),
                username=username,
                raw=result,
            )
        if res == "code_time_fail":
            raise MFAFailedError(f"send too frequent: {msg}")
        raise CASProtocolError(f"unexpected reauth send-code response: res={res!r} msg={msg!r}")

    def submit_mfa_code(
        self,
        challenge: MFAChallenge,
        code: str,
    ) -> CASCredential:
        """提交 MFA 验证码。成功返回最新凭据，失败抛 :class:`MFAFailedError`。"""
        encoded_service = urllib.parse.quote(DEFAULT_LOGIN_SERVICE, safe="")
        referer = (
            f"{CER_BASE_URL}/authserver/reAuthCheck/reAuthLoginView.do"
            f"?isMultifactor=true&service={encoded_service}"
        )
        data = {
            "service": DEFAULT_LOGIN_SERVICE,
            "reAuthType": challenge.method_code,
            "isMultifactor": "true",
            "dynamicCode": code,
            "password": "",
            "uuid": "",
            "answer1": "",
            "answer2": "",
            "otpCode": "",
        }
        resp = self.session.post(
            REAUTH_SUBMIT_URL,
            data=data,
            allow_redirects=False,
            timeout=self.timeout,
            headers={
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        # 3xx：跟随重定向，最终是否落到非登录页决定成败
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            try:
                follow = self.session.get(
                    location, timeout=self.timeout, allow_redirects=True
                )
                if "/authserver/login" not in follow.url:
                    return self.credential()
            except requests.RequestException:
                # 跟随失败但 Location 已能证明 ST 已派发
                if "ticket=" in location and "/authserver/login" not in location:
                    return self.credential()

        # 200：先看 JSON 错误码，再看显式 HTML 错误标记
        if resp.status_code == 200:
            try:
                result = resp.json()
                code_field = result.get("code") or result.get("res")
                if code_field in ("reAuth_failed", "reAuth_unauthorized"):
                    raise MFAFailedError(f"server rejected MFA code: {result}")
            except ValueError:
                pass

            text = resp.text
            if any(
                marker in text
                for marker in ("reauth_error_submit", "reAuth_failed", "reAuth_unauthorized")
            ):
                if "reAuth_success" not in text and "loginSuccess" not in text:
                    raise MFAFailedError("MFA page reported failure")

        # 兜底：再触发一次 CAS 登录看看是否已经认证
        if self.is_authenticated():
            return self.credential()

        raise MFAFailedError("MFA submission did not produce a valid session")

    # ──────────────────────────────────────────────────────────────────── #
    # 跨 service 出票
    # ──────────────────────────────────────────────────────────────────── #

    def authorize(
        self,
        service_url: str,
        *,
        session: requests.Session | None = None,
    ) -> requests.Session:
        """凭已有的 TGC 给 ``service_url`` 出票，并把 ST 落到目标 session 上。

        - ``session=None``：新建一个 :class:`requests.Session`（推荐 —— 隔离不同
          业务的 cookie）；
        - ``session=existing``：把 ST / per-service cookie 落到给定 session 上。

        ``authorize()`` 返回前会把目标 session 上回流的 CAS 域 cookie（如服务端
        轮换的 ``happyVoyage``）同步回 ``self.session``，让 :class:`CASClient`
        内部凭据始终是最新的。

        Raises:
            NotAuthenticatedError: 缺少 TGC 或服务端把请求踢回了登录页。
            CASProtocolError: 重定向链与预期不符。
        """
        target = session if session is not None else requests.Session()

        # 把 cer 域上的 cookie 同步过去 —— 否则目标 session 没 TGC 拿不到 ST
        CASCredential.from_session(self.session).apply(target)

        encoded = urllib.parse.quote(service_url, safe="")
        url = f"{AUTH_LOGIN_URL}?service={encoded}"
        try:
            resp = target.get(url, allow_redirects=True, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CASProtocolError(f"authorize redirect chain failed: {exc}") from exc

        # 落地页要么就是 service_url 本身，要么至少不能是 CAS 登录页
        if "/authserver/login" in resp.url:
            raise NotAuthenticatedError(
                "CAS bounced back to login page; TGC missing or expired"
            )

        # 把目标 session 上的 cer cookie（含轮换后的 happyVoyage）回流到 self.session
        CASCredential.from_session(target).apply(self.session)

        return target

    def get_service_ticket(self, service_url: str) -> str:
        """更底层：仅从 302 ``Location`` 头里解析出 ST。

        一般用户不需要直接调这个；用 :meth:`authorize` 即可。

        Raises:
            CASProtocolError: 没拿到 302 或 Location 里不含 ticket。
            NotAuthenticatedError: 服务端 302 回了登录页。
        """
        encoded = urllib.parse.quote(service_url, safe="")
        url = f"{AUTH_LOGIN_URL}?service={encoded}"
        resp = self.session.get(url, allow_redirects=False, timeout=self.timeout)

        if resp.status_code not in (301, 302, 303, 307, 308):
            raise CASProtocolError(
                f"expected redirect from CAS, got status {resp.status_code}"
            )

        location = resp.headers.get("Location", "")
        if "/authserver/login" in location:
            raise NotAuthenticatedError(
                "CAS redirected back to login page; TGC missing or expired"
            )

        m = _TICKET_RE.search(location)
        if not m:
            raise CASProtocolError(f"no ST ticket in Location header: {location!r}")
        return m.group(1)

    # ──────────────────────────────────────────────────────────────────── #
    # 内部辅助
    # ──────────────────────────────────────────────────────────────────── #

    def _get_login_page(self) -> str:
        """拉取 CAS 登录页 HTML（使用 stub service URL）。"""
        resp = self.session.get(
            AUTH_LOGIN_URL,
            params={"service": DEFAULT_LOGIN_SERVICE},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.text

    def _classify_step1_response(
        self,
        resp: requests.Response,
        username: str,
    ) -> Step1Result:
        """把第一重提交的响应翻译成 :class:`Step1Result`。"""
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")

            if "reAuthCheck" in location or "isMultifactor" in location:
                # MFA 入口；跟随一次让 session 落地到 reauth 页面
                self.session.get(location, timeout=self.timeout)
                return Step1Result(authenticated=False, needs_mfa=True, username=username)

            if DEFAULT_LOGIN_SERVICE in location or "ticket=" in location:
                # 直接拿到 ST，跟随一次完成 service 端落地
                self.session.get(location, timeout=self.timeout)
                return Step1Result(authenticated=True, needs_mfa=False, username=username)

            # 其他重定向：跟随后再判断
            try:
                follow = self.session.get(location, timeout=self.timeout)
            except requests.RequestException as exc:
                raise CASProtocolError(f"failed to follow redirect: {exc}") from exc

            if DEFAULT_LOGIN_SERVICE in follow.url or "ticket=" in follow.url:
                return Step1Result(authenticated=True, needs_mfa=False, username=username)
            if is_reauth_page(follow.text):
                return Step1Result(authenticated=False, needs_mfa=True, username=username)

            raise CASProtocolError(
                f"unrecognized redirect chain after first-factor: {follow.url}"
            )

        if resp.status_code == 200:
            text = resp.text
            if is_ip_frozen(text):
                raise IPBlockedError("IP 被认证网关冻结，请稍后再试或联系管理员")
            if is_reauth_page(text):
                return Step1Result(authenticated=False, needs_mfa=True, username=username)
            error = extract_error_message(text)
            if error:
                # 服务端常用同一个 element 提示 "需要验证码" 与 "用户名密码错"，
                # 关键词区分一下
                if "验证码" in error or "captcha" in error.lower():
                    raise NeedCaptchaError(error)
                raise LoginFailedError(error)
            raise LoginFailedError("first-factor authentication failed (no error message extracted)")

        raise CASProtocolError(f"unexpected status code from CAS: {resp.status_code}")
