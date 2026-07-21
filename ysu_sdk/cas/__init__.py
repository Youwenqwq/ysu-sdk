"""CAS 子包的公开 API。"""

from ysu_sdk.cas.client import CASClient
from ysu_sdk.cas.credential import CASCredential
from ysu_sdk.cas.exceptions import (
    CASError,
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

__all__ = [
    # Client
    "CASClient",
    "CASCredential",
    # Types
    "CaptchaChallenge",
    "MFAChallenge",
    "MFAMethod",
    "Step1Result",
    # Exceptions
    "CASError",
    "CASProtocolError",
    "IPBlockedError",
    "LoginFailedError",
    "MFAFailedError",
    "MFARequiredError",
    "NeedCaptchaError",
    "NotAuthenticatedError",
    "CASNetworkError",
]
