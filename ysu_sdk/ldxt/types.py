"""ysu_sdk.ldxt 的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LaborRecord:
    """一条劳动记录（时长汇总页的「劳动列表」）。

    Attributes:
        term: 学期（如 ``2024-2025第一学期``）
        name: 活动名称（不含报名来源徽标）
        enroll_type: 报名来源徽标（如 ``教师选择``，无则为空串）
        category: 活动大类（如 ``服务性实践劳动``）
        department: 所属学院
        time_start: 活动开始时间（RFC3339，未识别则原样）
        time_end: 活动结束时间
        teacher: 组织老师（如 ``王老师 (100000)``）
        hours: 劳动时长（小时）
        student: 学生展示串（如 ``某同学 (200000000001)``）
        status: 审核状态（如 ``学院审核通过``）
    """

    term: str = ""
    name: str = ""
    enroll_type: str = ""
    category: str = ""
    department: str = ""
    time_start: str = ""
    time_end: str = ""
    teacher: str = ""
    hours: float | None = None
    student: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class LaborSummary:
    """学生学分汇总（``学生学分汇总`` 页，学生视角只有本人一行）。

    Attributes:
        student_id: 学号
        name: 姓名
        department: 学院
        major: 专业
        class_name: 班级
        grade: 年级
        schooling: 学制（如 ``四年制``）
        total_hours: 累计劳动时长
        total_credits: 总学分
    """

    student_id: str = ""
    name: str = ""
    department: str = ""
    major: str = ""
    class_name: str = ""
    grade: str = ""
    schooling: str = ""
    total_hours: float | None = None
    total_credits: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EnrollableActivity:
    """一条可报名活动（活动报名列表）。

    Attributes:
        name: 活动名称
        category: 活动大类
        time_start: 活动开始时间（RFC3339，未识别则原样）
        time_end: 活动结束时间
        location: 活动地点
        hours: 劳动时长
        description: 活动说明
        department: 所属学院/部门
        enroll_start: 报名开始时间
        enroll_end: 报名结束时间
        is_enrolled: 是否已报名
        operation: 操作列状态（如 ``不在报名时间``）
    """

    name: str = ""
    category: str = ""
    time_start: str = ""
    time_end: str = ""
    location: str = ""
    hours: float | None = None
    description: str = ""
    department: str = ""
    enroll_start: str = ""
    enroll_end: str = ""
    is_enrolled: bool = False
    operation: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
