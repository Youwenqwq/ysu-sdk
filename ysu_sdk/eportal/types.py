"""数据类型：在线状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class OnlineStatus:
    """当前设备的校园网在线状态。

    Attributes:
        online: 是否已通过认证在线。
        username: 在线时为准入账号（学工号），离线时为 ``None``。
        service: 在线时使用的网络服务名（如 ``"校园网"`` / ``"中国联通"``）。
        user_ip / user_mac: 在线时服务端记录的本机地址。
        message: 服务端原始结果信息（离线时形如 ``"dx.failed.user.offline"``）。
        raw: 服务端返回的原始 ``portalOnlineUserInfo`` 字典，供调试。
    """

    online: bool
    username: str | None = None
    service: str | None = None
    user_ip: str | None = None
    user_mac: str | None = None
    message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
