"""AES-CBC 密码加密，与认证网关前端兼容。

加密流程（前端原版）：

1. 密码前面拼接 64 字节随机前缀，规避明文短串特征；
2. 以登录页返回的 ``pwdEncryptSalt`` 为 AES key（UTF-8）；
3. 16 字节随机串作为 IV（UTF-8）；
4. AES-CBC + PKCS7 padding；
5. 输出 Base64。
"""

from __future__ import annotations

import base64
import secrets

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ysu_sdk.cas.constants import AES_CHARS
from ysu_sdk.cas.exceptions import CASProtocolError

_VALID_AES_KEY_BYTES: frozenset[int] = frozenset({16, 24, 32})


def _random_string(length: int) -> str:
    """从 :data:`AES_CHARS` 中随机取 *length* 个字符。

    使用 ``secrets`` 而非 ``random`` —— 加密上下文里随机性应当不可预测，
    即便前端用的是 ``Math.random()``，本地实现没必要照搬其弱随机。
    """
    return "".join(secrets.choice(AES_CHARS) for _ in range(length))


def encrypt_password(password: str, salt: str) -> str:
    """与认证网关前端等价的 AES-CBC 加密。

    Args:
        password: 用户原始密码。
        salt: 登录页 ``pwdEncryptSalt`` 字段，用作 AES key。
              字节长度必须 ∈ {16, 24, 32}，否则视为协议异常。

    Returns:
        Base64 编码后的密文字符串，可直接作为表单 ``password`` 字段提交。

    Raises:
        CASProtocolError: salt 字节长度不符合 AES 要求。
    """
    key_bytes = salt.encode("utf-8")
    if len(key_bytes) not in _VALID_AES_KEY_BYTES:
        raise CASProtocolError(
            f"unexpected pwdEncryptSalt length: {len(key_bytes)} bytes"
            f" (expected one of {sorted(_VALID_AES_KEY_BYTES)})"
        )

    data = _random_string(64) + password
    iv = _random_string(16).encode("utf-8")
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")
