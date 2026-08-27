"""AES-ECB 加密，与 cas-sso 登录页前端兼容。

cas-sso 登录页在 ``#login-croypto`` 中内嵌 Base64 编码的 AES key，
前端用它对密码和 ``captcha_payload`` 做 AES-ECB + PKCS7 加密（CryptoJS
``AES.encrypt(text, Base64.parse(croypto), {mode: ECB})``），输出 Base64。

注意这与 CAS 网关（``ysu_sdk.cas._crypto``）的 AES-CBC 是两套不同的加密，
不要混用。
"""

from __future__ import annotations

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ysu_sdk.eportal.exceptions import EPortalProtocolError

_VALID_AES_KEY_BYTES: frozenset[int] = frozenset({16, 24, 32})


def aes_ecb_encrypt(croypto_b64: str, plaintext: str) -> str:
    """以页面内嵌的 ``croypto`` 为 key 做 AES-ECB 加密。

    Args:
        croypto_b64: 登录页 ``#login-croypto`` 的 Base64 文本，
                     解码后字节长度必须 ∈ {16, 24, 32}。
        plaintext: 待加密明文（密码或 ``"{}"``）。

    Returns:
        Base64 编码后的密文字符串。

    Raises:
        EPortalProtocolError: croypto 不是合法 Base64 或 key 长度不符。
    """
    try:
        key = base64.b64decode(croypto_b64, validate=True)
    except ValueError as exc:
        raise EPortalProtocolError(f"invalid croypto (not base64): {croypto_b64!r}") from exc
    if len(key) not in _VALID_AES_KEY_BYTES:
        raise EPortalProtocolError(
            f"unexpected croypto key length: {len(key)} bytes"
            f" (expected one of {sorted(_VALID_AES_KEY_BYTES)})"
        )
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")
