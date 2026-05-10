"""教务系统子包公开 API。"""

from ysu_sdk.jwxt.client import JWXTClient
from ysu_sdk.jwxt.exceptions import (
    JWXTError,
    NotLoggedInError,
    JWXTProtocolError,
    JWXTBusinessError,
)
from ysu_sdk.jwxt.types import (
    AcademicCompletion,
    AcademicWarning,
    Course,
    EvaluationAnswer,
    EvaluationDetail,
    EvaluationTask,
    EvaluationType,
    Exam,
    GPAStats,
    Grade,
    Question,
    QuestionOption,
    StudentInfo,
    TrainingPlan,
)

__all__ = [
    "JWXTClient",
    "JWXTError",
    "NotLoggedInError",
    "JWXTProtocolError",
    "JWXTBusinessError",
    "AcademicCompletion",
    "AcademicWarning",
    "Course",
    "EvaluationAnswer",
    "EvaluationDetail",
    "EvaluationTask",
    "EvaluationType",
    "Exam",
    "GPAStats",
    "Grade",
    "Question",
    "QuestionOption",
    "StudentInfo",
    "TrainingPlan",
]
