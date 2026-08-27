# ysu-sdk

> [English](README.md) | [中文](README.zh-CN.md)

燕山大学统一身份认证（CAS）与教务系统的 Python SDK。

- `ysu_sdk.cas`：负责 `cer.ysu.edu.cn` 网关上的登录、MFA、凭据持久化以及跨 service 出票。
- `ysu_sdk.jwxt`：基于已认证的 CAS 会话，查询教务系统（`jwxt.ysu.edu.cn`）的成绩、课表、全校班级课表、考试、学生信息、培养方案、学业完成与预警，以及学生评教（含提交答卷）。
- `ysu_sdk.xgxt`：查询学工系统（`xgxt.ysu.edu.cn`）「综合测评」应用的综测成绩、班级/年级排名、指标明细、雷达对比与学业成绩报告（全部只读）。
- `ysu_sdk.jwmobile`：移动教务课程签到——当前课程活动、签到详情/状态查询，以及 `sign()` 签到（本包唯一写操作）。
- `ysu_sdk.ldxt`：劳动教育实践课程管理平台（ASP.NET 服务端渲染）——劳动时长记录、学分汇总、活动报名列表，全部只读。
- `ysu_sdk.scxt`：创新创业学分认定系统（同厂商）——学分申报记录、分批次的认定记录、学分总表、竞赛库/活动库目录，全部只读。
- `ysu_sdk.eportal`：锐捷校园网认证（`auth1.ysu.edu.cn`）——登录、登出、在线状态查询。仅在校园网内可用，不经过 CAS 网关。

## 安装

```bash
uv pip install -e .
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

# 2. 创建教务系统客户端
#    - 所有公开业务方法都带有「懒回退」装饰器：默认信任已有的 jwxt cookie，
#      仅在服务端返回 401/403 或将请求重定向到 CAS 登录页时，才回退到
#      CAS authorize 重新拿 ST。避免每次调用都访问 cer.ysu.edu.cn。
#    - 若你已有 JWXTSession 快照（如上一次的请求结果），可通过 jwxt_session
#      传入，连第一次 authorize 都能跳过。
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

### JWXTSession — 持久化 per-service cookie

`CASCredential` 保存长寿命的 CAS 网关 cookie（`cer.ysu.edu.cn`）。
`JWXTSession` 保存短寿命的 per-service cookie（`jwxt.ysu.edu.cn`：
`JSESSIONID`、`_WEU`、`route` 等）。传入 `JWXTSession` 可以完全跳过初始的
CAS `authorize` 冷路径。

```python
from ysu_sdk.jwxt import JWXTSession

# 任意业务调用后，捕获旋转过的会话快照
snapshot: JWXTSession = jwxt.session_snapshot()
json_str = snapshot.to_json()          # → 运输 / 存储

# 下次运行时（或在无状态服务端）回传
session = JWXTSession.from_json(json_str)
jwxt = JWXTClient(cas, jwxt_session=session)
```

即使传了过期的 `JWXTSession` 也是安全的——懒回退装饰器会捕获
`NotLoggedInError`，清掉过期的 jwxt cookie，重新走 CAS authorize，
并重试业务方法一次。

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
- `JWXTSession`：可序列化的教务系统域 cookie 集合

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

## 学工系统（XGXT）用法

学工系统「综合测评」应用的只读查询，认证模式与 JWXT 相同：

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.xgxt import XGXTClient

cas = CASClient(credential=CASCredential.load())
xgxt = XGXTClient(cas)

# 可查询的测评学年学期（最新在前）
terms = xgxt.query_evaluation_terms()

# 综测成绩与班级/年级排名（默认最新测评批次）
result = xgxt.query_evaluation_result()            # 或 ("2024", "2")
print(result.total_score, result.class_rank, result.grade_rank)

# 指标得分明细 / 雷达对比 / 各学年分数总览
details = xgxt.query_evaluation_indicators()
radar = xgxt.query_evaluation_radar()
statics = xgxt.query_year_score_statics()

# 学业成绩报告（同页「学业成绩」弹窗）
years = xgxt.query_academic_report_years()
page = xgxt.query_academic_report()                # 默认服务端默认学年
```

所有方法均为只读。`XGXTClient` 与 `JWXTClient` 模式一致：懒回退重认证、
会话快照（`XGXTSession`）、异常分层（`XGXTProtocolError` /
`XGXTBusinessError` / `NotLoggedInError`）。

## 移动教务（jwmobile）用法

与桌面端 EMAP 会话相互独立：移动端客户端完成 CAS SSO 后从跳转链捕获
JWT，并以 cookie 携带调用移动 biz 接口。

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.jwxt import JWXTClient
from ysu_sdk.jwmobile import MobileClient

cas = CASClient(credential=CASCredential.load())
mobile = MobileClient(cas)

# 经 jwxt 发现今日课程，再在移动端查询活动
jwxt = JWXTClient(cas)
week = jwxt.query_current_week().week
for course in jwxt.query_courses_on_date():
    lesson = mobile.query_current_lesson_for_course(course, week)
    for activity in lesson.activities:
        detail = mobile.query_signin_detail(activity.activity_id)
        status = mobile.query_signin_status(activity.activity_id)
        # mobile.sign(activity.activity_id)  # 写操作：实际完成签到
```

`sign()` 是写操作（本人考勤签到），也是本包唯一写操作。
`query_current_lesson_for_course` 接受任何满足 `CourseLike` 字段的对象
（jwxt 的 `Course` 即满足）；两个包互不 import。

## 劳动教育（ldxt）用法

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.ldxt import LdxtClient

ldxt = LdxtClient(CASClient(credential=CASCredential.load()))

for record in ldxt.query_labor_records():
    print(record.term, record.name, record.hours, record.status)

summary = ldxt.query_labor_summary()          # 累计时长/总学分
activities = ldxt.query_enrollable_activities()  # 报名是写操作，未封装
```

劳动教育系统是 ASP.NET 服务端渲染（无 JSON 信封），SDK 用标准库解析器
抽取 HTML 表格，零额外依赖。

## 双创学分（scxt）用法

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.scxt import ScxtClient

scxt = ScxtClient(CASClient(credential=CASCredential.load()))

for d in scxt.query_credit_declarations():
    print(d.item_name, d.score, d.status)

summary = scxt.query_credit_summary()       # 总学分/成绩
records = scxt.query_all_credit_records()   # 遍历全部批次
comps = scxt.query_competitions(item_name="挑战杯")  # 分页目录
```

本系统不是直接注册的 CAS 服务，认证经 `ysu_pt` 平台桥中转，客户端已封装
完整握手。注意学分汇总服务端默认只给当前批次，全量请用
`query_all_credit_records()`。

## 校园网认证（ePortal）用法

独立子包：不经过 CAS——锐捷门户使用内嵌的 cas-sso 登录页（AES-ECB
加密，密钥内嵌于页面），目前所有账号登录均强制图形验证码。
仅在校园网内可用。

```python
from ysu_sdk.eportal import EPortalClient

portal = EPortalClient()

status = portal.get_status()            # 无需凭据，按本机 IP 判定
if not status.online:
    status = portal.login(
        "<学工号>",
        "<密码>",
        service="校园网",                # 或英文别名 campus/unicom/telecom/mobile
        captcha_solver=lambda png: solve(png),  # png 为 PNG 字节流，返回识别文本
    )
    print(status.username, status.service, status.user_ip)

portal.logout()
```

持有有效 CAS 凭据时，可以走 portal 的「统一身份认证」委托通道，
完全免密、免验证码：

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.eportal import EPortalClient

portal = EPortalClient()
portal.login_via_cas(CASClient(credential=CASCredential.load()))
```

登录被拒时抛 `EPortalAuthError`，可通过 `code` 区分原因
（`1030027`/`1030031` 用户名或密码错误、`1030028` 账号锁定、
`1410040`/`1410041` 用户名无效）；需要验证码但未提供回调时抛
`NeedCaptchaError`；验证码连续识别失败抛 `CaptchaFailedError`。

## 故障排查：校外网络与 WAF

所有 `*.ysu.edu.cn` 网关都在同一道安全 WAF 之后。当同一 IP 的**非浏览器流量突发**时，它会分两级升级：

1. **渐进限速（tarpit）**——响应被量化延迟（30s → 40s → 50s）。延迟池按 TLS 指纹区分：浏览器和 curl/libcurl 全速通过，python-requests/urllib3 被拖慢。用被标记的指纹重试只会加码。
2. **全 IP 封锁**——该 IP 的所有客户端（含浏览器）都被拒绝。换 IP（或等待冷却）后恢复。

使用建议：

- 控制请求节奏（`scripts/smoke.py --pace` 默认 1s），避免对网关并发突发。
- 如果请求突然变成几十秒才返回，**立即停手**——不要顶着限速重试，等冷却或换 IP。
- 作为恢复手段，可以注入 `curl_cffi` session（其 TLS 指纹不在延迟池内）——客户端构造函数接受任何 duck-typed session：

```python
from curl_cffi import requests as creq

class CookiesAdapter:
    def __init__(self, jar): self._jar = jar
    def set_cookie(self, c):
        self._jar.set(c.name, c.value, domain=c.domain,
                      path=c.path, secure=bool(c.secure))
    def clear(self, domain=None, path=None, name=None):
        if domain is None:
            self._jar.clear(); return
        for c in list(self):
            if domain in (c.domain or ""):
                self._jar.clear(domain=c.domain, path=c.path, name=c.name)
    def __iter__(self):
        yield from self._jar.jar

class SessionAdapter:
    def __init__(self, inner): self._inner = inner
    @property
    def cookies(self): return CookiesAdapter(self._inner.cookies)
    def get(self, url, **kw): return self._inner.get(url, **kw)
    def post(self, url, data=None, **kw): return self._inner.post(url, data=data, **kw)

session = SessionAdapter(creq.Session(impersonate="chrome", timeout=30))
jwxt = JWXTClient(cas, session=session)
```

## 架构说明

- `JWXTClient` 依赖 `CASClient` 完成认证。所有公开业务方法都带有「懒回退」
  装饰器：首次调用时检查 session 上是否已有 jwxt 域 cookie；没有则执行一次
  `CASClient.authorize()`（冷启动）。若服务端返回 401/403 或将请求重定向到
  CAS 登录页，装饰器会清掉过期的 jwxt cookie，重新 authorize，并重试业务方法
  一次。
- `JWXTClient` 持有自己的 `requests.Session`，与 CAS 会话相互独立。可通过
  `jwxt_session` 参数传入已有快照，跳过初始 authorize。
- 任意业务调用后，`session_snapshot()` 可从 session 中提取最新的 jwxt cookie。
  外部调用方（如 `ysu-api`）可将其序列化并持久化，使下次请求避免再次 CAS 往返。
- 教务系统基于金智教育 EMAP 平台，不同模块使用不同的请求格式
  （`querySetting` 数组、`requestParamStr` 单字段、直接 form 参数、多步 API），
  `JWXTClient` 内部已封装。
- 每个查询方法在调用前会按需调用 `_ensure_weu(APP_ID)`，刷新该应用的 `_WEU`
  令牌，避免跨应用调用时 cookie 错位。
- `XGXTClient` 与 `JWXTClient` 模式相同（懒回退、独立 session、
  `session_snapshot()`），但与 jwxt 的按应用 `_WEU` 刷新不同，学工平台要求
  在 authorize 之后做一次**角色握手**（`getAppConfig` → `setXgCommonAppRole`
  → `changeAppRole`）；未完成握手前模块 API 一律返回 404。该握手由
  `_ensure_app_role()` 在首次业务调用时自动完成。接口存在两种报文形态并存：
  controller 风格（请求体为 `data=<JSON>`，响应载荷在 `data` 字段）与 EMAP
  列表风格（纯 form 表单，响应载荷在 `datas.<key>.rows`），分别由
  `_post_controller` / `_post_rows` 收口。
