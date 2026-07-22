"""学工系统（综合测评）数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationTerm:
    """可查询的测评学年学期。

    Attributes:
        year: 测评学年代码（``CPXN``，如 ``"2025"`` 表示 2025-2026 学年）
        term: 测评学期代码（``CPXQ``，``"1"`` / ``"2"``）
        year_display: 学年显示文本（如 ``"2025-2026学年"``）
        term_display: 学期显示文本（如 ``"第一学期"``）
        wid: 该学年学期记录的内部 ID
    """

    year: str = ""
    term: str = ""
    year_display: str = ""
    term_display: str = ""
    wid: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationIndicator:
    """综测成绩中的单项指标得分（来自成绩接口的 ``ZBLIST``）。

    Attributes:
        name: 指标名称（``ZBMC``，如 ``"学业表现"``）
        score: 得分（``FS``）
        rank: 年级排名（``RK``）
        max_score: 分值上限（``ZDZ``）
        category: 指标类别代码（``ZBLB``）
        description: 指标说明（``ZBSM``）
    """

    name: str = ""
    score: str = ""
    rank: int = 0
    max_score: str = ""
    category: str = ""
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """指定学年学期的综测成绩与排名。

    Attributes:
        total_score: 综测总分（``ZCJ``）
        class_rank: 班级排名（``BJPM``）
        class_size: 班级人数（``BJRS``）
        grade_rank: 年级排名（``ZYNJPM``）
        grade_size: 年级人数（``ZYNJRS``）
        year: 测评学年代码（``CPXN``）
        term: 测评学期代码（``CPXQ``）
        year_display: 学年显示文本
        term_display: 学期显示文本
        show_major_rank: 是否展示专业排名（``showZypm``）
        indicators: 各指标得分列表
    """

    total_score: str = ""
    class_rank: int = 0
    class_size: int = 0
    grade_rank: int = 0
    grade_size: int = 0
    year: str = ""
    term: str = ""
    year_display: str = ""
    term_display: str = ""
    show_major_rank: bool = False
    indicators: list[EvaluationIndicator] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationIndicatorDetail:
    """指标得分明细（综测成绩页的指标表格，分页接口）。

    Attributes:
        name: 指标名称（``ZBMC``）
        score: 得分（``FS``）
        max_score: 分值上限（``ZDZ``）
        range_text: 分值范围描述（``FZFW``，如 ``"分值：0-30.00"``）
        proportion: 占比百分比（``BL``）
        category_display: 指标类别显示文本（``ZBLB_DISPLAY``，如 ``"附加项"``）
        description: 指标说明（``ZBSM``）
    """

    name: str = ""
    score: str = ""
    max_score: str = ""
    range_text: str = ""
    proportion: str = ""
    category_display: str = ""
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationRadarItem:
    """雷达对比单项（「我和别人比一比」）：个人得分 vs 平均值 vs 满分。

    Attributes:
        name: 指标名称（``ZBMC``）
        personal: 个人得分（``GR``）
        average: 平均得分（``AVG``）
        max_score: 满分（``MAX``）
    """

    name: str = ""
    personal: str = ""
    average: str = ""
    max_score: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class YearScoreStatic:
    """各学年学期综测分数总览项（「我和自己比一比」）。

    Attributes:
        year: 学年代码（``XNZ``）
        term: 学期代码（``XQZ``）
        year_display: 学年显示文本（``XNXSZ``）
        term_display: 学期显示文本（``XQXSZ``）
        score: 综测分数（``FS``，未出分时为空串）
    """

    year: str = ""
    term: str = ""
    year_display: str = ""
    term_display: str = ""
    score: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicReportYear:
    """学业成绩报告的可选学年。

    Attributes:
        year: 学年代码（``XNZ``，如 ``"2025"``）
        year_display: 学年显示文本（``XNXSZ``）
    """

    year: str = ""
    year_display: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicReportYears:
    """学业成绩报告的学年选项与默认学年。

    Attributes:
        years: 可选学年列表
        default_year: 默认学年代码（``DQXN``）
    """

    years: list[AcademicReportYear] = field(default_factory=list)
    default_year: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicReportEntry:
    """学业成绩报告的单条课程成绩。

    Attributes:
        course_name: 科目名称（``KCMC``）
        score: 成绩（``ZCJ``）
        credit: 学分（``XF``）
        course_nature: 课程性质代码（``KCXZDM``）
        year: 学年（``XN``）
        term: 学期（``XQ``）
    """

    course_name: str = ""
    score: str = ""
    credit: str = ""
    course_nature: str = ""
    year: str = ""
    term: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicReportPage:
    """学业成绩报告的一页结果。

    Attributes:
        entries: 本页课程成绩列表
        total_size: 总记录数
        page_number: 当前页码
        page_size: 每页条数
    """

    entries: list[AcademicReportEntry] = field(default_factory=list)
    total_size: int = 0
    page_number: int = 1
    page_size: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
