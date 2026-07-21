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
        weeks_bitmap: 上课周次位图（``SKZC``，第 N 个字符为 ``"1"`` 表示第 N 周有课；
            非位图形态时为空串）
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
    weeks_bitmap: str = ""
    credit: str = ""
    course_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class UnscheduledCourse:
    """未排课程（理论课表口径，对应 ``xswpkc``）。

    与 :class:`Course` 的区别：这些课程尚未安排具体时间地点，
    因此没有星期/节次，只有周次范围文本与合班上课的行政班列表。

    Attributes:
        name: 课程名称（``KCM``）
        code: 课程号（``KCH``）
        teacher: 任课教师（``SKJS``）
        credit: 学分（``XF``）
        class_id: 教学班 ID（``JXBID``）
        course_seq: 课序号（``KXH``）
        weeks_text: 周次范围文本（``SKZC``，如 ``"15-17周"``）
        attending_classes: 合班上课的行政班列表（``SKBJ``，逗号分隔）
    """

    name: str = ""
    code: str = ""
    teacher: str = ""
    credit: str = ""
    class_id: str = ""
    course_seq: str = ""
    weeks_text: str = ""
    attending_classes: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CourseAdjustment:
    """调课课程记录（对应 ``xsdkkc``，模型 ``Tkjg``）。

    记录一次调课调整前后的上课安排。字段以 ``new_`` 前缀表示调整后。

    Attributes:
        name: 课程名称（``KCM``）
        class_id: 教学班 ID（``JXBID``）
        old_week_day: 原上课星期（``SKXQ``）
        new_week_day: 新上课星期（``XSKXQ``）
        old_start_section: 原开始节次（``KSJC``）
        new_start_section: 新开始节次（``XKSJC``）
        old_end_section: 原结束节次（``JSJC``）
        new_end_section: 新结束节次（``XJSJC``）
        old_weeks: 原周次名称（``ZCMC``）
        new_weeks: 新周次名称（``XZCMC``）
        new_classroom: 新教室（``XJASDM``）
        apply_time: 调课申请时间（``SQSJ``）
    """

    name: str = ""
    class_id: str = ""
    old_week_day: int = 0
    new_week_day: int = 0
    old_start_section: int = 0
    new_start_section: int = 0
    old_end_section: int = 0
    new_end_section: int = 0
    old_weeks: str = ""
    new_weeks: str = ""
    new_classroom: str = ""
    apply_time: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class OverallAdjustment:
    """整体调课记录（对应 ``cxztdkjl``）。

    全校性/批次性的调课安排（如节假日整体调课）。

    Attributes:
        batch_name: 批次名称（``PCMC``）
        adjustment_type: 调课类型（``TKLXDM``）
        time_range: 调课时间段（``TKSJDDM``）
    """

    batch_name: str = ""
    adjustment_type: str = ""
    time_range: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CodeItem:
    """代码表条目（年级、院系等字典数据）。

    Attributes:
        id: 代码值（如 ``"2025"`` / ``"301"``）
        name: 显示名称（如 ``"2025级"`` / ``"机械工程学院"``）
    """

    id: str = ""
    name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class MajorInfo:
    """专业代码表条目。

    Attributes:
        id: 专业代码（``ZYDM``）
        name: 专业名称
        department: 所属院系代码（``otherFields.YXDM``）
    """

    id: str = ""
    name: str = ""
    department: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class ClassInfo:
    """全校班级列表条目（对应 ``bjcx``）。

    Attributes:
        class_id: 班级代码（``BJDM``，如 ``"01AA25001"``）
        class_name: 班级名称（``BJMC``，如 ``"机械类25-1"``）
        grade: 年级代码（``NJ``）
        grade_display: 年级显示文本（如 ``"2025级"``）
        department: 院系代码（``YXDM``）
        department_display: 院系名称
        major: 专业代码（``ZYDM``）
        major_display: 专业名称
        is_scheduled: 是否已排课（``SFYPK``）
        student_count: 实际人数（``SJRS``）
        initial_count: 初始人数（``CSRS``）
    """

    class_id: str = ""
    class_name: str = ""
    grade: str = ""
    grade_display: str = ""
    department: str = ""
    department_display: str = ""
    major: str = ""
    major_display: str = ""
    is_scheduled: bool = False
    student_count: int = 0
    initial_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class ClassroomInfo:
    """全校教室列表条目（对应 ``jscx``）。

    Attributes:
        name: 教室名称（``JASMC``）
        code: 教室代码（``JASDM``，课表查询的主键）
        campus: 校区代码（``XXXQDM``）
        campus_display: 校区名称
        building: 教学楼代码（``JXLDM``）
        building_display: 教学楼名称
        exam_seats: 考试座位数（``KSZWS``）
        class_seats: 上课座位数（``SKZWS``）
        type_display: 教室类型（``JASLXDM_DISPLAY``，如多媒体教室）
        floor: 楼层（``LC``）
        is_scheduled: 是否已排课（``SFYPK``）
    """

    name: str = ""
    code: str = ""
    campus: str = ""
    campus_display: str = ""
    building: str = ""
    building_display: str = ""
    exam_seats: int = 0
    class_seats: int = 0
    type_display: str = ""
    floor: int = 0
    is_scheduled: bool = False
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
        course_code: 课程号（``KCH``）
        invigilator: 主考/监考教师姓名（``ZJJSXM``）
        term: 学年学期代码（``XNXQDM``）
    """

    name: str
    exam_name: str = ""
    exam_date: str = ""
    exam_time: str = ""
    exam_location: str = ""
    seat_number: str = ""
    course_code: str = ""
    invigilator: str = ""
    term: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Grade:
    """成绩信息。

    Attributes:
        course_name: 课程名称
        course_code: 课程号
        class_id: 教学班ID
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
        usual_score: 平时成绩（``PSCJ``）
        midterm_score: 期中成绩（``QZCJ``）
        final_score: 期末成绩（``QMCJ``）
        practice_score: 实践成绩（``SJCJ``）
        exam_time: 考试时间（``KSSJ``）
    """

    course_name: str
    course_code: str = ""
    class_id: str = ""
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
    usual_score: str = ""
    midterm_score: str = ""
    final_score: str = ""
    practice_score: str = ""
    exam_time: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class GradeStatistics:
    """成绩统计信息（最高分 / 最低分 / 平均分）。

    对应原始接口 ``jxbcjtjcx``。``scope`` 区分两种统计口径：

    - ``"class"`` 教学班统计（``TJLX=01``）：针对单个 ``class_id`` 的统计；
    - ``"course"`` 课程总体统计（``TJLX=02``）：针对单个 ``course_code``、
      聚合所有教学班，此时服务端返回的 ``class_id`` 为 ``"*"``。

    Attributes:
        scope: 统计口径，``"class"`` 或 ``"course"``
        term: 学年学期
        class_id: 教学班ID（课程总体统计下为 ``"*"``）
        course_code: 课程号
        highest_score: 最高分
        lowest_score: 最低分
        average_score: 平均分
    """

    scope: str = ""
    term: str = ""
    class_id: str = ""
    course_code: str = ""
    highest_score: float = 0.0
    lowest_score: float = 0.0
    average_score: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class GradeDistribution:
    """成绩分布信息（按等级分桶的人数）。

    对应原始接口 ``jxbcjfbcx``。每条记录代表一个等级及该等级的人数。
    ``scope`` 区分教学班统计（``TJLX=01``）与课程总体统计（``TJLX=02``），
    后者下 ``class_id`` 为 ``"*"``。

    Attributes:
        scope: 统计口径，``"class"`` 或 ``"course"``
        term: 学年学期
        class_id: 教学班ID（课程总体统计下为 ``"*"``）
        course_code: 课程号
        level_code: 等级代码（``"01"`` 优秀、``"02"`` 良好、``"03"`` 中等、
            ``"04"`` 及格、``"05"`` 不及格）
        level_name: 等级名称
        count: 该等级人数
    """

    scope: str = ""
    term: str = ""
    class_id: str = ""
    course_code: str = ""
    level_code: str = ""
    level_name: str = ""
    count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class GradeRanking:
    """学生成绩排名信息。

    对应原始接口 ``jxbxspmcx``。``scope`` 区分排名口径：

    - ``"class"`` 教学班内排名（``TJLX=01``）：在指定 ``class_id`` 中的名次；
    - ``"course"`` 课程总体排名（``TJLX=02``）：在指定 ``course_code`` 所有
      教学班的合并名次，此时 ``class_id`` 为 ``"*"``。

    Attributes:
        scope: 排名口径，``"class"`` 或 ``"course"``
        term: 学年学期
        student_id: 学号
        class_id: 教学班ID（课程总体排名下为 ``"*"``）
        course_code: 课程号
        score: 学生本人成绩
        rank: 当前名次
        total: 参与排名的总人数
        ranking_type: 服务端 ``PMLX`` 字段（如 ``"JXB"``），用于调试
    """

    scope: str = ""
    term: str = ""
    student_id: str = ""
    class_id: str = ""
    course_code: str = ""
    score: float = 0.0
    rank: int = 0
    total: int = 0
    ranking_type: str = ""
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
        start_date: 预警开始日期（``YJKSSJ``，YYYY-MM-DD）
        end_date: 预警结束日期（``YJJSSJ``，YYYY-MM-DD）
    """

    warning_type: str
    warning_level: str = ""
    description: str = ""
    term: str = ""
    start_date: str = ""
    end_date: str = ""
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
