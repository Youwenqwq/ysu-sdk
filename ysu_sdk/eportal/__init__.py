"""ePortal（锐捷校园网认证）子包的公开 API。"""

from ysu_sdk.eportal.client import EPortalClient
from ysu_sdk.eportal.exceptions import (
    CaptchaFailedError,
    EPortalAuthError,
    EPortalBusinessError,
    EPortalError,
    EPortalNetworkError,
    EPortalProtocolError,
    NeedCaptchaError,
)
from ysu_sdk.eportal.types import OnlineStatus

__all__ = [
    # Client
    "EPortalClient",
    # Types
    "OnlineStatus",
    # Exceptions
    "CaptchaFailedError",
    "EPortalAuthError",
    "EPortalBusinessError",
    "EPortalError",
    "EPortalNetworkError",
    "EPortalProtocolError",
    "NeedCaptchaError",
]
