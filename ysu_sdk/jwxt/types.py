"""教务系统数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Course:
    """课程信息。

    Attributes:
        name: 课程名称
        code: 课程号
        teacher: 任课教师
        classroom: 上课地点
        week_day: 星期几 (1-7)
        start_section: 起始节次
        end_section: 结束节次
        weeks: 上课周次描述
        credit: 学分
        course_type: 课程性质
    """

    name: str
    code: str = ""
    teacher: str = ""
    classroom: str = ""
    week_day: int = 0
    start_section: int = 0
    end_section: int = 0
    weeks: str = ""
    credit: str = ""
    course_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class ClassPeriod:
    """课表节次配置。

    描述教务系统全局的节次时刻表，可与 :class:`Course` 的
    ``start_section``/``end_section`` 字段联用，把节次序号映射到具体的
    上下课时间。

    Attributes:
        name: 节次名称（如 "第1节"）
        section: 节次序号（对应 :attr:`Course.start_section`）
        start_time: 开始时间（``HH:MM``）
        end_time: 结束时间（``HH:MM``）
        is_in_use: 该节次是否启用
    """

    name: str = ""
    section: int = 0
    start_time: str = ""
    end_time: str = ""
    is_in_use: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class TermCalendar:
    """学期校历配置。

    描述一个学年学期的周次结构（总周次、正常教学周次、起始日期等），可以
    与 :class:`CurrentWeek` 配合使用，把日期换算为教学周次。

    Attributes:
        term: 学年学期（``"YYYY-YYYY-N"``，如 ``"2025-2026-2"``）
        start_date: 学期开始日期（``YYYY-MM-DD``）
        total_weeks: 学期总周次（含考试 / 节假日等）
        teaching_weeks: 正常教学周次
        is_in_use: 该学期校历是否启用
    """

    term: str = ""
    start_date: str = ""
    total_weeks: int = 0
    teaching_weeks: int = 0
    is_in_use: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CurrentWeek:
    """指定日期所属的教学周次与星期。

    Attributes:
        week: 教学周次（学期第几周）
        weekday: 星期几（``1`` = 周一、…、``7`` = 周日）
        term: 学年学期
        date: 查询的日期（``YYYY-MM-DD``）
    """

    week: int = 0
    weekday: int = 0
    term: str = ""
    date: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Exam:
    """考试安排信息。

    Attributes:
        name: 课程名称
        exam_name: 考试名称（如"期末考试"）
        exam_date: 考试日期（YYYY-MM-DD）
        exam_time: 考试时间描述
        exam_location: 考试地点
        seat_number: 座位号
    """

    name: str
    exam_name: str = ""
    exam_date: str = ""
    exam_time: str = ""
    exam_location: str = ""
    seat_number: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Grade:
    """成绩信息。

    Attributes:
        course_name: 课程名称
        course_code: 课程号
        score: 百分制成绩
        grade_level: 等级制成绩
        grade_point: 绩点
        credit: 学分
        hours: 学时
        term: 学年学期
        course_type: 课程性质
        course_category: 课程类别
        exam_type: 考试类型
        study_mode: 修读方式
        is_major: 是否主修
        is_retake: 是否重修重考
        grade_level_type: 显示等级成绩类型
        department: 开课单位
        is_pass: 是否及格
        is_valid: 是否有效
        special_reason: 特殊原因
        is_degree_course: 是否学位课
        project_name: 项目名称
    """

    course_name: str
    course_code: str = ""
    score: str = ""
    grade_level: str = ""
    grade_point: str = ""
    credit: str = ""
    hours: str = ""
    term: str = ""
    course_type: str = ""
    course_category: str = ""
    exam_type: str = ""
    study_mode: str = ""
    is_major: bool = False
    is_retake: str = ""
    grade_level_type: str = ""
    department: str = ""
    is_pass: bool = False
    is_valid: bool = True
    special_reason: str = ""
    is_degree_course: bool = False
    project_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class GPAStats:
    """学分绩点统计信息。

    Attributes:
        plan_name: 培养方案名称
        study_type: 方案修读类型（如"主修"）
        required_credit_earned: 必修课获得学分
        elective_credit_earned: 选修课获得学分
        degree_credit_earned: 学位课获得学分
        required_credit_failed: 必修课不及格学分
        gpa_initial: 平均绩点（初修含选修）
        gpa_highest: 平均绩点（最高含选修）
        required_gpa_highest: 必修课平均绩点（最高仅必修）
        degree_gpa_initial: 学位课平均绩点（初修）
        degree_gpa_highest: 学位课平均绩点（最高）
        weighted_avg: 加权平均分
        arithmetic_avg: 算术平均分
        degree_weighted_avg: 学位课加权平均分
    """

    plan_name: str = ""
    study_type: str = ""
    required_credit_earned: str = ""
    elective_credit_earned: str = ""
    degree_credit_earned: str = ""
    required_credit_failed: str = ""
    gpa_initial: str = ""
    gpa_highest: str = ""
    required_gpa_highest: str = ""
    degree_gpa_initial: str = ""
    degree_gpa_highest: str = ""
    weighted_avg: str = ""
    arithmetic_avg: str = ""
    degree_weighted_avg: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class StudentInfo:
    """学生基本信息。

    Attributes:
        name: 姓名
        name_pinyin: 姓名拼音
        student_id: 学号
        gender: 性别
        nation: 民族
        nationality: 国籍
        department: 院系
        major: 专业
        class_name: 班级
        grade_level: 年级
        enrollment_date: 入学年月
        expected_graduation: 预计毕业日期
        education_level: 培养层次
        campus: 校区
        student_status: 学籍状态
        discipline: 学科门类
        study_duration: 学制
        foreign_language: 外语语种
    """

    name: str = ""
    name_pinyin: str = ""
    student_id: str = ""
    gender: str = ""
    nation: str = ""
    nationality: str = ""
    department: str = ""
    major: str = ""
    class_name: str = ""
    grade_level: str = ""
    enrollment_date: str = ""
    expected_graduation: str = ""
    education_level: str = ""
    campus: str = ""
    student_status: str = ""
    discipline: str = ""
    study_duration: str = ""
    foreign_language: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class TrainingPlan:
    """培养方案课程信息。

    Attributes:
        course_name: 课程名称
        course_code: 课程号
        credit: 学分
        course_type: 课程类别
        required: 是否必修
        term: 建议修读学期
        course_group: 课组名称
    """

    course_name: str
    course_code: str = ""
    credit: str = ""
    course_type: str = ""
    required: bool = False
    term: str = ""
    course_group: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicWarning:
    """学业预警信息。

    Attributes:
        warning_type: 预警类型
        warning_level: 预警级别
        description: 预警描述
        term: 学年学期
    """

    warning_type: str
    warning_level: str = ""
    description: str = ""
    term: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class AcademicCompletion:
    """学业完成查询信息。

    Attributes:
        plan_name: 培养方案名称
        total_required: 总要求学分
        completed: 已获得学分
        elective: 选修学分
        passed: 是否审查通过
    """

    plan_name: str = ""
    total_required: str = ""
    completed: str = ""
    elective: str = ""
    passed: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationType:
    """评教类型信息。

    Attributes:
        name: 评教类型名称（如"学生评教"、"随堂调查"）
        code: 评教类型代码（如"01"、"07"）
        count: 待评数量
    """

    name: str
    code: str = ""
    count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationTask:
    """待评教任务信息。

    Attributes:
        wid: 任务唯一标识
        wjid: 问卷ID
        name: 评教名称
        course_name: 课程名称
        teacher_name: 教师姓名
        teacher_id: 教师号
        term: 学年学期代码
        term_name: 学年学期名称
        eval_type: 评教类型代码
        eval_type_name: 评教类型名称
        category: 评教类别代码
        category_name: 评教类别名称
        start_time: 开始时间
        end_time: 结束时间
        sequence: 评教次序
        class_name: 班级名称
        group_no: 分组标识
    """

    wid: str
    wjid: str = ""
    name: str = ""
    course_name: str = ""
    teacher_name: str = ""
    teacher_id: str = ""
    term: str = ""
    term_name: str = ""
    eval_type: str = ""
    eval_type_name: str = ""
    category: str = ""
    category_name: str = ""
    start_time: str = ""
    end_time: str = ""
    sequence: int = 1
    class_name: str = ""
    group_no: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class QuestionOption:
    """问卷选项信息。

    Attributes:
        wid: 选项唯一标识
        text: 选项文本
        score: 分值
        score_ratio: 分值比例（百分比）
        question_id: 所属题目ID
    """

    wid: str
    text: str = ""
    score: float = 0.0
    score_ratio: float = 0.0
    question_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Question:
    """问卷题目信息。

    Attributes:
        tmid: 题目唯一标识
        wjid: 问卷ID
        text: 题目文本
        question_type: 题目类型（"01"单选、"02"填空、"07"多选等）
        max_score: 满分
        order: 排序号
        options: 选项列表
    """

    tmid: str
    wjid: str = ""
    text: str = ""
    question_type: str = ""
    max_score: float = 0.0
    order: int = 0
    options: list[QuestionOption] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationDetail:
    """问卷详情信息。

    Attributes:
        wjid: 问卷ID
        name: 问卷名称
        deadline: 截止日期
        questions: 题目列表
        teachers: 待评教师列表
    """

    wjid: str = ""
    name: str = ""
    deadline: str = ""
    questions: list[Question] = field(default_factory=list)
    teachers: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class EvaluationAnswer:
    """单题答案。

    Attributes:
        tmid: 题目ID
        question_type: 题目类型（如"01"单选、"02"填空、"07"多选）
        option_ids: 选中的选项ID列表（单选/多选）
        text: 文本答案（填空题）
    """

    tmid: str
    question_type: str = ""
    option_ids: list[str] = field(default_factory=list)
    text: str = ""
