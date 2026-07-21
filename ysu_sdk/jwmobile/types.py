"""移动教务（jwmobile）数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LessonActivity:
    """课程活动（签到、投票等，来自 ``queryCurrentLesson``）。

    Attributes:
        activity_id: 活动 ID（签到相关接口的主键）
        type: 活动类型代码
        status: 活动状态代码
        title: 活动标题
        icon: 活动图标标识
        sign_type: 签到方式（如扫码、手势、位置）
        sign_clazz: 签到分类
        is_end: 活动是否已结束
        is_creator: 当前学生是否为活动创建者
        create_time: 活动创建时间（RFC3339，归一后）
    """

    activity_id: str = ""
    type: int | None = None
    status: int | None = None
    title: str | None = None
    icon: str | None = None
    sign_type: str = ""
    sign_clazz: str = ""
    is_end: bool = False
    is_creator: bool = False
    create_time: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class CurrentLesson:
    """当前课程及其活动列表。

    Attributes:
        lesson_id: 课程 ID
        activities: 该课程下的活动列表
    """

    lesson_id: str | None = None
    activities: list[LessonActivity] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class SigninActivityDetail:
    """签到活动详情（``signin/detail``）。

    Attributes:
        activity_id: 活动 ID
        duration: 签到时长（分钟）
        start_time: 签到开始时间（RFC3339，归一后）
        end_time: 签到结束时间（RFC3339，归一后）
        left_seconds: 剩余可签到秒数
        signin_type: 签到方式代码
    """

    activity_id: str = ""
    duration: int = 0
    start_time: str = ""
    end_time: str = ""
    left_seconds: int = 0
    signin_type: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class MobileUserInfo:
    """移动端用户信息（``biz/user/info``）。

    与 jwxt 的 :class:`ysu_sdk.jwxt.StudentInfo` 互补：字段更少，
    但独有头像 URL。

    Attributes:
        name: 姓名（``xm``）
        student_id: 学号（``xh``）
        class_name: 班级（``className``）
        major: 专业（``zymc``）
        department: 学院（``yxmc``）
        grade: 年级（``xznj``）
        avatar_url: 头像 URL（``avatar``）
    """

    name: str = ""
    student_id: str = ""
    class_name: str = ""
    major: str = ""
    department: str = ""
    grade: str = ""
    avatar_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class SigninStatus:
    """学生签到状态（``querySigninDetail`` 与 ``sign`` 同构返回）。

    Attributes:
        sign_status: 签到状态代码
        attendance_status: 考勤状态代码
        sign_order: 签到序号
        signin_type: 签到方式代码
    """

    sign_status: int = 0
    attendance_status: int = 0
    sign_order: int = 0
    signin_type: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class CourseLike(Protocol):
    """移动端课程查询所需的课程结构（结构化鸭子类型）。

    jwxt 的 :class:`ysu_sdk.jwxt.Course` 天然满足本协议，但 jwmobile
    不依赖 jwxt——任何携带同名属性的对象都可传入
    :meth:`MobileClient.query_current_lesson_for_course`。
    """

    class_id: str
    schedule_id: str
    class_type: str
    experiment_type_code: str
    week_day: int
    start_section: int
    end_section: int
