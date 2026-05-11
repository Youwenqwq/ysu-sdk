# ysu-sdk

燕山大学统一身份认证（CAS）与教务系统的 Python SDK。

- `ysu_sdk.cas`：负责 `cer.ysu.edu.cn` 网关上的登录、MFA、凭据持久化以及跨 service 出票。
- `ysu_sdk.jwxt`：基于已认证的 CAS 会话，查询教务系统（`jwxt.ysu.edu.cn`）的成绩、课表、考试、学生信息、培养方案、学业完成与预警，以及学生评教（含提交答卷）。

## 安装

```bash
uv pip install -e ./ysu-sdk
```

需要 Python ≥ 3.12，依赖 `requests`、`pycryptodome`、`beautifulsoup4`。

## CAS 认证用法

```python
from ysu_sdk.cas import CASClient, CASCredential

# 首次登录（交互式，回调里读用户输入）
cas = CASClient()
cred = cas.login(
    "<学号>",
    "<密码>",
    mfa_handler=lambda c: input(f"输入{c.method}验证码 ({c.mobile_hint}): "),
)
cred.save()

# 复用凭据，给任意 service 出票
cas = CASClient(credential=CASCredential.load())
sess = cas.authorize("https://jwxt.ysu.edu.cn/jwapp/sys/emaphome/portal/index.do")
resp = sess.get("https://jwxt.ysu.edu.cn/jwapp/sys/emaphome/portal/index.do")
```

支持的 MFA 类型：`sms`、`cpdaily`。

## 教务系统查询用法

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.jwxt import JWXTClient

# 1. 先完成 CAS 认证
cas = CASClient(credential=CASCredential.load())

# 2. 创建教务系统客户端（自动完成对 jwxt 的 authorize）
jwxt = JWXTClient(cas)

# 3. 查询各类信息
grades = jwxt.query_grades()                   # 成绩
gpa = jwxt.query_gpa_stats()                   # 学分绩点统计
schedule = jwxt.query_schedule()               # 理论课表（当前学期）
exp_schedule = jwxt.query_schedule_experimental()  # 实验选课课表
unscheduled = jwxt.query_unscheduled_courses() # 未排课程
exams = jwxt.query_exams()                     # 考试安排
info = jwxt.query_student_info()               # 学生基本信息
plan = jwxt.query_training_plan()              # 培养方案
completion = jwxt.query_academic_completion()  # 学业完成
warnings = jwxt.query_academic_warnings()      # 学业预警

# 按学期查询
grades = jwxt.query_grades(term="2024-2025-1")
schedule = jwxt.query_schedule(term="2024-2025-2")
exams = jwxt.query_exams(term="2024-2025-2")
```

### 成绩统计 / 分布 / 排名

`query_grades` 返回的每条 `Grade` 携带 `class_id`（教学班 ID），可直接喂给下面三个接口
进一步查询该课程的统计数据。每个接口都支持两种统计口径：

- **教学班**（`TJLX=01`）：传 `class_id`，结果限定在该教学班；
- **课程总体**（`TJLX=02`）：传 `course_code`，聚合该课程在指定学期的所有教学班，
  返回值中 `class_id` 为 `"*"`。

`class_id` 与 `course_code` 必须**仅提供其一**，否则抛 `ValueError`。

```python
g = jwxt.query_grades(term="2025-2026-2")[0]

# 1) 最高 / 最低 / 平均分
class_stat = jwxt.query_grade_statistics(class_id=g.class_id)        # 教学班
course_stat = jwxt.query_grade_statistics(course_code=g.course_code) # 课程总体

# 2) 等级分布（优秀 / 良好 / 中等 / 及格 / 不及格 的人数）
class_dist = jwxt.query_grade_distribution(class_id=g.class_id)
course_dist = jwxt.query_grade_distribution(course_code=g.course_code)

# 3) 个人排名（默认查当前登录学生）
class_rank = jwxt.query_grade_ranking(class_id=g.class_id)
course_rank = jwxt.query_grade_ranking(course_code=g.course_code)
# class_rank.rank / class_rank.total / class_rank.score
```

### 学生评教

`ysu_sdk.jwxt` 是 SDK 中**唯一的写操作场景**。提交评教不可撤回，请先用
`calculate_evaluation_score` 预检答案，再用 `submit_evaluation` 正式提交。

```python
from ysu_sdk.jwxt import EvaluationAnswer, JWXTBusinessError

# 1. 查询当前学期可参与的评教类型与待评数量
types = jwxt.query_evaluation_types()
# [EvaluationType(name="学生评教", code="01", count=3), ...]

# 2. 拉取指定类型下的待评任务
tasks = jwxt.query_pending_evaluations(eval_type="01")
# [EvaluationTask(wid=..., wjid=..., course_name=..., teacher_name=..., group_no=...), ...]

# 3. 拉取问卷题目
detail = jwxt.get_evaluation_detail(
    group_no=tasks[0].group_no,
    eval_type=tasks[0].eval_type,
    sequence=tasks[0].sequence,
)

# 4. 构造答案（单选/多选传 option_ids，填空题传 text）
answers = [
    EvaluationAnswer(tmid=q.tmid, question_type=q.question_type, option_ids=[q.options[0].wid])
    for q in detail.questions if q.question_type in ("01", "07")
]

# 5. 预检（强烈建议）—— 服务端校验答案完整性与得分
try:
    jwxt.calculate_evaluation_score(
        group_no=tasks[0].group_no,
        wjid=detail.wjid,
        eval_type=tasks[0].eval_type,
        answers=answers,
    )
except JWXTBusinessError as e:
    print(f"答卷不合法：{e.msg}")
    raise

# 6. 提交（不可撤回）
jwxt.submit_evaluation(
    group_no=tasks[0].group_no,
    wjid=detail.wjid,
    eval_type=tasks[0].eval_type,
    answers=answers,
)
```

### 数据类型

所有查询方法返回结构化数据类型（`@dataclass(frozen=True, slots=True)`）：

- `Grade`：成绩信息（课程名、课程号、教学班ID、成绩、绩点、学分、学期等）
- `GPAStats`：学分绩点统计（必修/选修/学位课学分、各类平均绩点等）
- `GradeStatistics`：成绩统计（最高分 / 最低分 / 平均分；教学班或课程总体）
- `GradeDistribution`：成绩分布（按等级分桶的人数；教学班或课程总体）
- `GradeRanking`：学生成绩排名（教学班内或课程总体）
- `Course`：课程信息（课程名、教师、教室、星期、节次、周次等）
- `Exam`：考试安排（课程名、考试时间、地点、座位号等）
- `StudentInfo`：学生基本信息（姓名、学号、院系、专业、班级等）
- `TrainingPlan`：培养方案课程（课程名、学分、是否必修、建议学期、课组等）
- `AcademicCompletion`：学业完成情况（培养方案、要求/已得学分、是否通过等）
- `AcademicWarning`：学业预警（预警类型、级别、描述、学期等）
- `EvaluationType` / `EvaluationTask` / `EvaluationDetail` / `Question` / `QuestionOption`：评教相关结构
- `EvaluationAnswer`：用户构造的答案（单题，包含题目类型与选项/文本）

每个类型均携带 `raw` 字段，保留服务端原始 dict 响应，便于读取未封装的字段。

### 异常处理

```python
from ysu_sdk.jwxt import (
    JWXTError,
    NotLoggedInError,
    JWXTProtocolError,
    JWXTBusinessError,
)

try:
    jwxt.submit_evaluation(...)
except NotLoggedInError:
    # CAS cookie 过期或被踢下线，需要重新登录
    ...
except JWXTBusinessError as e:
    # 服务端按协议返回了非零业务码（如「未到评教时间」「答卷不完整」）
    # 通过 e.code / e.msg / e.url 编程区分具体原因
    if "未到评教时间" in (e.msg or ""):
        ...
except JWXTProtocolError:
    # 响应不是 JSON、envelope 残缺、或网络/HTTP 异常等协议层问题
    ...
except JWXTError:
    # 兜底：教务子包所有异常的基类
    ...
```

`JWXTBusinessError` 与 `JWXTProtocolError` 是平级的：前者表示**服务端
正确返回但业务规则拒绝**（响应结构合法），后者表示**响应本身不符合协议
预期**。两者都继承自 `JWXTError`，但 `JWXTBusinessError` **不是**
`JWXTProtocolError` 的子类——不要用 `except JWXTProtocolError` 捕获业务错误。

## 架构说明

- `JWXTClient` 依赖 `CASClient` 完成认证，在初始化时自动调用 `CASClient.authorize()`
  获取教务系统 cookie。`JWXTClient` 持有自己的 `requests.Session`，与 CAS
  会话相互独立。
- 教务系统基于金智教育 EMAP 平台，不同模块使用不同的请求格式
  （`querySetting` 数组、`requestParamStr` 单字段、直接 form 参数、多步 API），
  `JWXTClient` 内部已封装。
- 每个查询方法在调用前会按需调用 `_ensure_weu(APP_ID)`，刷新该应用的 `_WEU`
  令牌，避免跨应用调用时 cookie 错位。
