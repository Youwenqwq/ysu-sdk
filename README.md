# ysu-sdk

> [English](README.md) | [中文](README.zh-CN.md)

Python SDK for Yanshan University's unified identity authentication (CAS)
gateway (`cer.ysu.edu.cn`) and educational administration system
(`jwxt.ysu.edu.cn`).

- `ysu_sdk.cas` — login, MFA, credential persistence, and cross-service
  Service-Ticket issuance on the CAS gateway.
- `ysu_sdk.jwxt` — read-only queries (grades, schedule, exams, student info,
  training plan, academic completion, warnings) and student evaluation
  (write-once) against the educational administration system.

## Install

Requires Python ≥ 3.12.

```bash
uv pip install -e .
```

Runtime dependencies: `requests`, `pycryptodome`, `beautifulsoup4`.

## CAS usage

```python
from ysu_sdk.cas import CASClient, CASCredential

# First login (interactive — callbacks read user input)
cas = CASClient()
cred = cas.login(
    "<student id>",
    "<password>",
    mfa_handler=lambda c: input(f"Enter {c.method} code ({c.mobile_hint}): "),
)
cred.save()

# Reuse credential to issue tickets for any service
cas = CASClient(credential=CASCredential.load())
sess = cas.authorize("https://jwxt.ysu.edu.cn/jwapp/sys/emaphome/portal/index.do")
resp = sess.get("https://jwxt.ysu.edu.cn/jwapp/sys/emaphome/portal/index.do")
```

Supported MFA methods: `sms`, `cpdaily`.

## Educational administration (JWXT) usage

```python
from ysu_sdk.cas import CASClient, CASCredential
from ysu_sdk.jwxt import JWXTClient

# 1. Authenticate via CAS
cas = CASClient(credential=CASCredential.load())

# 2. Create JWXT client
#    - Business methods are decorated with lazy re-auth: the client trusts
#      existing jwxt cookies by default and falls back to CAS authorize
#      only when the server returns 401/403 or redirects to the CAS login
#      page. This avoids hammering cer.ysu.edu.cn on every call.
#    - If you already have a JWXTSession snapshot (e.g. from a previous
#      request), pass it via jwxt_session to skip even the first authorize.
jwxt = JWXTClient(cas)

# 3. Query information
grades = jwxt.query_grades()                   # grades
gpa = jwxt.query_gpa_stats()                   # GPA stats
schedule = jwxt.query_schedule()               # lecture schedule (current term)
exp_schedule = jwxt.query_schedule_experimental()  # experiment schedule
unscheduled = jwxt.query_unscheduled_courses() # unscheduled courses
exams = jwxt.query_exams()                     # exam arrangements
info = jwxt.query_student_info()               # student profile
plan = jwxt.query_training_plan()              # training plan
completion = jwxt.query_academic_completion()  # academic completion
warnings = jwxt.query_academic_warnings()      # academic warnings

# Query by term
grades = jwxt.query_grades(term="2024-2025-1")
schedule = jwxt.query_schedule(term="2024-2025-2")
exams = jwxt.query_exams(term="2024-2025-2")
```

### JWXTSession — persisting per-service cookies

`CASCredential` holds long-lived CAS-gateway cookies (`cer.ysu.edu.cn`).
`JWXTSession` holds short-lived per-service cookies (`jwxt.ysu.edu.cn`:
`JSESSIONID`, `_WEU`, `route`, etc.). Passing a `JWXTSession` avoids the
initial CAS `authorize` cold path entirely.

```python
from ysu_sdk.jwxt import JWXTSession

# After any business call, capture the rotated session
snapshot: JWXTSession = jwxt.session_snapshot()
json_str = snapshot.to_json()          # → transport / store

# On the next run (or in a stateless server), feed it back
session = JWXTSession.from_json(json_str)
jwxt = JWXTClient(cas, jwxt_session=session)
```

A stale `JWXTSession` is safe — the lazy re-auth decorator catches
`NotLoggedInError`, clears expired jwxt cookies, re-authorizes via CAS, and
retries the business method once.

### Grade statistics / distribution / ranking

Each `Grade` returned by `query_grades` carries a `class_id` (teaching-class
ID) that can be fed into the three statistics APIs. Each supports two scopes:

- **Teaching class** (`TJLX=01`): pass `class_id`, results limited to that
  teaching class.
- **Whole course** (`TJLX=02`): pass `course_code`, aggregating all teaching
  classes of that course in the given term. The returned `class_id` is `"*"`.

Exactly one of `class_id` or `course_code` must be provided; passing both or
neither raises `ValueError`.

```python
g = jwxt.query_grades(term="2025-2026-2")[0]

# 1) max / min / average
class_stat = jwxt.query_grade_statistics(class_id=g.class_id)
course_stat = jwxt.query_grade_statistics(course_code=g.course_code)

# 2) bucketed distribution (excellent / good / average / pass / fail)
class_dist = jwxt.query_grade_distribution(class_id=g.class_id)
course_dist = jwxt.query_grade_distribution(course_code=g.course_code)

# 3) personal ranking (defaults to the logged-in student)
class_rank = jwxt.query_grade_ranking(class_id=g.class_id)
course_rank = jwxt.query_grade_ranking(course_code=g.course_code)
# class_rank.rank / class_rank.total / class_rank.score
```

### Student evaluation

`ysu_sdk.jwxt` contains the **only write path** in this SDK. Submissions are
irreversible — use `calculate_evaluation_score` to pre-check answers before
`submit_evaluation`.

```python
from ysu_sdk.jwxt import EvaluationAnswer, JWXTBusinessError

# 1. Query evaluation types and pending counts for the current term
types = jwxt.query_evaluation_types()
# [EvaluationType(name="Student evaluation", code="01", count=3), ...]

# 2. Pull pending tasks for a given type
tasks = jwxt.query_pending_evaluations(eval_type="01")
# [EvaluationTask(wid=..., wjid=..., course_name=..., teacher_name=..., group_no=...), ...]

# 3. Pull questionnaire details
detail = jwxt.get_evaluation_detail(
    group_no=tasks[0].group_no,
    eval_type=tasks[0].eval_type,
    sequence=tasks[0].sequence,
)

# 4. Build answers (single/multi choice → option_ids, fill-in → text)
answers = [
    EvaluationAnswer(tmid=q.tmid, question_type=q.question_type, option_ids=[q.options[0].wid])
    for q in detail.questions if q.question_type in ("01", "07")
]

# 5. Pre-check (strongly recommended) — server validates completeness and score
try:
    jwxt.calculate_evaluation_score(
        group_no=tasks[0].group_no,
        wjid=detail.wjid,
        eval_type=tasks[0].eval_type,
        answers=answers,
    )
except JWXTBusinessError as e:
    print(f"Invalid answers: {e.msg}")
    raise

# 6. Submit (irreversible)
jwxt.submit_evaluation(
    group_no=tasks[0].group_no,
    wjid=detail.wjid,
    eval_type=tasks[0].eval_type,
    answers=answers,
)
```

### Data types

All query methods return structured dataclasses (`@dataclass(frozen=True, slots=True)`):

- `Grade` — course name, course code, class ID, score, GPA points, credits, term, etc.
- `GPAStats` — credit and GPA summary (required / elective / degree-course credits,
  various average GPAs, etc.)
- `GradeStatistics` — max / min / average score (teaching class or whole course)
- `GradeDistribution` — bucketed counts by letter grade (teaching class or whole course)
- `GradeRanking` — student rank within teaching class or whole course
- `Course` — course name, teacher, classroom, weekday, period, weeks, etc.
- `Exam` — course name, exam time, location, seat number, etc.
- `StudentInfo` — name, student ID, department, major, class, etc.
- `TrainingPlan` — course name, credits, required flag, suggested term, course group, etc.
- `AcademicCompletion` — training plan, required/earned credits, pass status, etc.
- `AcademicWarning` — warning type, level, description, term, etc.
- `EvaluationType` / `EvaluationTask` / `EvaluationDetail` / `Question` /
  `QuestionOption` — evaluation-related structures
- `EvaluationAnswer` — user-constructed answer (single question, with type and
  options / text)
- `JWXTSession` — serializable bag of jwxt-domain cookies

Every type carries a `raw` field preserving the original server response dict
for forward compatibility.

### Exception handling

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
    # CAS cookie expired or kicked offline — re-login required
    ...
except JWXTBusinessError as e:
    # Server returned a non-zero business code (e.g. "evaluation window not open",
    # "incomplete answers"). Inspect e.code / e.msg / e.url programmatically.
    if "evaluation window not open" in (e.msg or ""):
        ...
except JWXTProtocolError:
    # Response is not JSON, envelope is malformed, or network/HTTP error
    ...
except JWXTError:
    # Catch-all base for everything under the jwxt package
    ...
```

`JWXTBusinessError` and `JWXTProtocolError` are siblings under `JWXTError`:
the former means the server responded correctly but rejected on business rules;
the latter means the response itself violated the protocol. Do **not** catch
`JWXTProtocolError` to handle business errors.

## Architecture notes

- `JWXTClient` depends on `CASClient` for authentication. Every public business
  method is decorated with `_with_lazy_reauth`: on first call it checks whether
  jwxt-domain cookies already exist on the session; if not, it performs one
  `CASClient.authorize()` (cold start). If the server returns 401/403 or
  redirects to the CAS login page, the decorator clears expired jwxt cookies,
  re-authorizes, and retries the method once.

- `JWXTClient` holds its own `requests.Session`, separate from the CAS session.
  You can optionally seed it with a `JWXTSession` snapshot to skip the initial
  authorize.

- After any business call, `session_snapshot()` extracts the latest jwxt cookies
  from the session. External callers (e.g. `ysu-api`) can serialize and persist
  this snapshot so the next request avoids another CAS round-trip.

- The educational administration system is built on the 金智教育 EMAP platform.
  Different modules use different request formats (`querySetting` arrays,
  `requestParamStr` single-field JSON, direct form parameters, multi-step
  chained APIs). `JWXTClient` abstracts these internally.

- Every public query method calls `_ensure_weu(APP_ID)` before its first POST.
  EMAP gates each application behind its own `_WEU` cookie, so switching apps
  without refreshing leaves a stale token. The helper unconditionally hits
  `appShow.do?id=<APP_ID>` to re-issue `_WEU` — no short-circuit check, because
  the cookie's app-binding is opaque from the client side.

- All API posts go through `_post(path, data)`, which builds the URL, sends the
  form POST, detects login expiry, decodes the EMAP envelope, and raises
  `JWXTProtocolError` on malformed responses or `JWXTBusinessError` on non-zero
  `code`. Query methods should never call `self.session.post` directly.
