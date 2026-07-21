"""学工系统（综合测评）子包公开 API。"""

from ysu_sdk.xgxt.client import XGXTClient
from ysu_sdk.xgxt.exceptions import (
    NotLoggedInError,
    XGXTBusinessError,
    XGXTError,
    XGXTProtocolError,
)
from ysu_sdk.xgxt.session import XGXTSession
from ysu_sdk.xgxt.types import (
    AcademicReportEntry,
    AcademicReportPage,
    AcademicReportYear,
    AcademicReportYears,
    EvaluationIndicator,
    EvaluationIndicatorDetail,
    EvaluationRadarItem,
    EvaluationResult,
    EvaluationTerm,
    YearScoreStatic,
)

__all__ = [
    "XGXTClient",
    "XGXTSession",
    "XGXTError",
    "NotLoggedInError",
    "XGXTProtocolError",
    "XGXTBusinessError",
    "AcademicReportEntry",
    "AcademicReportPage",
    "AcademicReportYear",
    "AcademicReportYears",
    "EvaluationIndicator",
    "EvaluationIndicatorDetail",
    "EvaluationRadarItem",
    "EvaluationResult",
    "EvaluationTerm",
    "YearScoreStatic",
]
