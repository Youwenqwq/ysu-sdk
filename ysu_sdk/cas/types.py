"""数据类型：MFA / Captcha 挑战、第一重登录返回值。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

type MFAMethod = Literal["sms", "cpdaily"]


@dataclass(frozen=True, slots=True)
class CaptchaChallenge:
    """需要用户解决的图形验证码挑战。

    Attributes:
        image_png: PNG 字节流，可直接写入文件或喂给 OCR。
    """

    image_png: bytes


@dataclass(frozen=True, slots=True)
class MFAChallenge:
    """二次认证挑战。

    Attributes:
        method: ``sms`` 或 ``cpdaily``。
        method_code: 服务端字典里对应的数字编码（``"3"`` / ``"5"``），提交时回填。
        mobile_hint: 服务端返回的手机号脱敏文本（如 ``"138****0000"``），用于提示用户。
        username: 与本次挑战绑定的用户名，用于后续提交。
        raw: 服务端返回的原始 JSON，供调试。
    """

    method: MFAMethod
    method_code: str
    mobile_hint: str
    username: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Step1Result:
    """``login_step1`` 的返回值。客户端据此决定下一步：

    - ``authenticated=True``：第一重就完成登录，无需 MFA；
    - ``needs_mfa=True``：需调 :meth:`CASClient.request_mfa_code` 继续。
    """

    authenticated: bool
    needs_mfa: bool
    username: str
