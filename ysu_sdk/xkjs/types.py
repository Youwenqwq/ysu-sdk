"""ysu_sdk.xkjs 的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """一页搜索结果（学生/教师共用分页结构）。"""

    items: list[T]
    page_count: int = 0
    total_records: int = 0
    page_index: int = 1


@dataclass(frozen=True, slots=True)
class Student:
    """一名学生（竞赛报名「添加学生」搜索结果行）。"""

    user_id: str  # 服务端内部 ID（行的 data-value / UserID 列）
    name: str
    account: str  # 学号
    college: str  # 学院
    major: str  # 专业
    # 是否已在当前竞赛申请名单中（操作列为「移除」即已选中）
    selected: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Teacher:
    """一名教师（竞赛报名「添加指导教师」搜索结果行）。"""

    user_id: str  # 服务端内部 ID（行的 data-value / UserID 列）
    name: str
    account: str  # 工号
    college: str  # 学院/部门
    # 是否已在当前竞赛申请名单中（操作列为「移除」即已选中）
    selected: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
