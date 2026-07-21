"""ysu_sdk.scxt 的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CatalogPage(Generic[T]):
    """分页目录页（竞赛库/活动库）。

    Attributes:
        items: 当前页条目
        page_index: 当前页码（1 起）
        total_pages: 总页数
        total_records: 总记录数
    """

    items: list[T] = field(default_factory=list)
    page_index: int = 1
    total_pages: int = 1
    total_records: int = 0


@dataclass(frozen=True, slots=True)
class CreditBatch:
    """一个学分认定批次（如 ``2026年创新创业教育学分认定``）。

    Attributes:
        batch_id: 批次 GUID
        name: 批次名称
    """

    batch_id: str = ""
    name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CreditDeclaration:
    """一条我的学分申报记录（申报学分页）。

    Attributes:
        item_name: 项目名称
        category_major: 认定大类（如 ``技能与素质（技能考试）``）
        category_minor: 认定小类（如 ``全国大学生外语四六级``）
        award_level: 获奖等级或排名
        score: 分值
        applicant: 学分申请人展示串
        batch: 所属批次
        status: 审核状态（如 ``学校审核学分通过``）
        operation: 操作列状态
    """

    item_name: str = ""
    category_major: str = ""
    category_minor: str = ""
    award_level: str = ""
    score: float | None = None
    applicant: str = ""
    batch: str = ""
    status: str = ""
    operation: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CreditRecord:
    """一条已认定学分记录（学分汇总页，按批次过滤）。

    Attributes:
        item_name: 项目名称
        year: 取得成果年份
        category_major: 认定大类
        category_minor: 认定小类
        award_level: 获奖等级或排名
        reference_score: 参照分值
        actual_score: 实际分值
        grade: 成绩（如 ``C``）
        applicant: 学分申请人展示串
        class_name: 所属班级
        department: 所属学院
        batch: 所属批次
        status: 状态
    """

    item_name: str = ""
    year: str = ""
    category_major: str = ""
    category_minor: str = ""
    award_level: str = ""
    reference_score: float | None = None
    actual_score: float | None = None
    grade: str = ""
    applicant: str = ""
    class_name: str = ""
    department: str = ""
    batch: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CreditSummary:
    """学生学分汇总（学生视角只有本人一行）。

    Attributes:
        student_id: 账号（学号）
        name: 用户名（姓名）
        department: 学院
        major: 专业
        class_name: 班级
        grade_year: 年级
        grade: 成绩（如 ``C``）
        total_credits: 总学分
    """

    student_id: str = ""
    name: str = ""
    department: str = ""
    major: str = ""
    class_name: str = ""
    grade_year: str = ""
    grade: str = ""
    total_credits: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Competition:
    """竞赛库条目。

    Attributes:
        code: 竞赛编码（如 ``1-1``）
        name: 竞赛名称
        category_major: 认定大类
        category_minor: 认定小类
        is_enabled: 是否启用
        status: 状态
    """

    code: str = ""
    name: str = ""
    category_major: str = ""
    category_minor: str = ""
    is_enabled: bool = False
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class LibraryActivity:
    """活动库条目。

    Attributes:
        name: 活动名称
        organizer: 举办单位
        category: 活动类别
        detail: 详情
    """

    name: str = ""
    organizer: str = ""
    category: str = ""
    detail: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
