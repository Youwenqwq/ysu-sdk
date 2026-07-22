# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project

A Python SDK for Yanshan University's unified identity authentication (CAS) gateway at `cer.ysu.edu.cn` and the educational administration system (教务系统, `jwxt.ysu.edu.cn`).

- `ysu_sdk.cas`: CAS login, MFA, credential persistence, and cross-`service` Service-Ticket issuance.
- `ysu_sdk.jwxt`: Information queries for the educational administration system — grades, grade statistics/distribution/ranking (per teaching class or whole course), GPA stats, schedule (theory & experimental), unscheduled/adjusted courses, courses-on-date, exams, student info, training plan, academic completion, academic warnings, and student evaluation. **写操作仅有三个**：`submit_evaluation`（评教提交）、`signup_makeup_exam`（补考报名）与 `recalculate_academic_completion`（学业完成度重算）——其余公开方法均为只读。 Don't add other write surfaces (course selection, applications) without an explicit ask; this SDK is intentionally narrow.
- `ysu_sdk.xgxt`: Read-only queries for the student-affairs system's 综合测评 app — evaluation terms, scores with class/grade rankings, indicator details, radar comparison, year score overview, and academic report.

The README is in Simplified Chinese; user-facing docstrings and exception messages should match.

## Environment & commands

- Python ≥ 3.12, managed via `uv` (see `.python-version` and `pyproject.toml`).
- Install editable: `uv pip install -e .`
- Runtime deps: `requests`, `pycryptodome`, `beautifulsoup4`. Build backend: `hatchling`.
- There is **no** test suite, lint config, or CI in the repo. Don't claim to have run tests that don't exist; if you need to verify behavior, write a one-off script and say so. For smoke checks, prefer `uv run python -c "..."` so the project venv (with `pycryptodome` etc.) is on the path — bare `python` will likely fail with `ModuleNotFoundError: No module named 'Crypto'`.

## Architecture

Package `ysu_sdk` contains two subpackages:

- `ysu_sdk.cas` — Public API is re-exported from `ysu_sdk.cas.__init__`.
- `ysu_sdk.jwxt` — Public API is re-exported from `ysu_sdk.jwxt.__init__`.

### CAS (`ysu_sdk.cas`)

#### Two flow styles for login

Both live on `CASClient`:

1. **High-level / interactive** — `CASClient.login(username, password, mfa_handler=..., captcha_solver=...)`. Callbacks are *blocking*: they're invoked synchronously and must return the captcha/MFA string.
2. **Step-wise / programmatic** — `fetch_captcha` → `login_step1` → (if `Step1Result.needs_mfa`) `request_mfa_code` → `submit_mfa_code`. Use this when you can't block (e.g. a web frontend).

`Step1Result` is the bridge: `login_step1` classifies the response into `authenticated` / `needs_mfa` and never raises on the MFA path.

#### Credential model — what's a CAS cookie

`CASCredential` is the serializable bag of cookies that proves you have a valid TGC. The filter is enforced in `CASCredential.from_session` and is load-bearing:

- `domain == cer.ysu.edu.cn` (constant `CAS_COOKIE_DOMAIN`), and
- `path == "/"` or `path.startswith("/authserver")`.

Per-service cookies (e.g. paths like `/personalInfo`) are explicitly **not** part of CAS credential — they belong to the target service's session. Don't loosen this filter without understanding why: same-named cookies on different paths (notably `JSESSIONID` on `/` vs `/personalInfo`) would otherwise clobber each other when round-tripped through JSON.

Persistence keeps full `name/value/domain/path/secure/expires` per cookie — never use `session.cookies.get_dict()`, which loses path info. Files are chmod 0o600 on POSIX (best-effort on Windows / NTFS-mounted WSL).

#### authorize() — the cookie sync invariant

`CASClient.authorize(service_url, session=None)` issues an ST and lands per-service cookies on the *target* session (defaults to a fresh `requests.Session` so each business system stays isolated). Before returning, it calls `CASCredential.from_session(target).apply(self.session)` to **sync back** any rotated CAS-domain cookies (e.g. `happyVoyage`) to the client's own session. If you change `authorize()`, preserve this round-trip — otherwise long-lived `CASClient` instances drift out of sync with the gateway after a few authorizations.

`get_service_ticket()` is the lower-level variant that just parses the ST out of the 302 `Location`. Most callers should use `authorize()`.

#### MFA

Only two methods, both verified against the live gateway: `sms` (code `"3"`, `reAuthDynamicCodeType`) and `cpdaily` (code `"5"`, `reAuthCpdailyDynamicCodeType`). Mappings are in `constants.py`. Don't add a method to `MFA_METHOD_TO_CODE` without confirming it works on the real server — the auth-code-type string is server-side enum and easy to get wrong.

`submit_mfa_code` is deliberately defensive: it accepts a 3xx redirect chain *or* a 200 with success markers, and falls back to `is_authenticated()` before declaring failure. Multiple branches are intentional, not redundant — different gateway versions return different shapes.

#### Crypto (`_crypto.py`)

Mirrors the gateway's frontend AES-CBC: `pwdEncryptSalt` is the key (UTF-8 bytes, must be 16/24/32), random 16-char IV, and a random 64-char prefix is prepended to the password before encryption. Output is Base64. We use `secrets` (not `random`) — the frontend uses `Math.random()`, but there's no reason to copy weak randomness into our implementation.

#### Parsing (`_parser.py`)

Uses BeautifulSoup (`html.parser`) to handle the CAS login page's multiple `<form>` clusters. Each login mode (userNameLogin / dynamicLogin / fidoLogin / qrLogin) lives in its own `<form>`, and field names like `execution` or `lt` repeat across forms. `extract_hidden_fields` scopes extraction by the `cllt` hidden field to avoid cross-form collisions, and falls back to `id` when `name` is absent (required for `pwdEncryptSalt`, which has no `name` attribute). `extract_error_message` uses CSS selectors rather than multiple compiled regexes. `is_reauth_page` and `is_ip_frozen` remain simple substring checks — no parsing needed.

### JWXT (`ysu_sdk.jwxt`)

#### Dependency on CAS

`JWXTClient` takes a `CASClient` instance in its constructor. On initialization, it calls `CASClient.authorize()` against the JWXT portal URL to establish per-service cookies (`JSESSIONID`, `_WEU`, etc.) on `jwxt.ysu.edu.cn`. The `JWXTClient` holds its own `requests.Session` — CAS and JWXT sessions are separate.

#### `_WEU` per-app refresh — `_ensure_weu` invariant

EMAP gates each *application* (成绩查询, 课表, 评教, …) behind its own `_WEU` cookie, served by `appShow.do?id=<APP_ID>`. The cookie is single-app: switching apps without refreshing leaves stale `_WEU` and the next API call returns `code=1`/redirects.

Every public query method **must** call `self._ensure_weu(APP_IDS[<app>])` before its first POST. The helper unconditionally GETs `appShow.do?id=<APP_ID>` to make the gateway re-issue `_WEU` for the target app — it does **not** check the current cookie. That's intentional: the cookie's app-binding is opaque from the client side, so we can't tell whether the existing `_WEU` matches without paying the round-trip anyway. When adding a new query, mirror this pattern — a missing `_ensure_weu` is the most common bug shape on this codebase.

#### EMAP platform — multiple request formats

The 教务系统 is built on the 金智教育 EMAP platform. Different functional modules use different API request patterns:

1. **Standard EMAP `querySetting`** — JSON array of filter conditions sent as form data. Used by: 成绩查询 (`cjcx`), 学生基本信息 (`xsjbxx`), 待评问卷列表 (`dpwj`).
2. **`requestParamStr`** — JSON object (or array) sent as a single form field. Used by: 考试安排 (`wdksap`), 评教提交/预检 (`commit_answer`, `calculate_score`).
3. **Direct form parameters** — Plain key-value pairs like `XNXQDM=2025-2026-2`. Used by: 课表查询 (`wdkb`, `wdkb_sy`), 学业完成 (`xywc`), 评教类型/题目 (`pjlx`, `wjtxxx`).
4. **Multi-step chained APIs** — Some features require calling one API to get an identifier (e.g. `PYFADM`), then a second API with that identifier. Used by: 培养方案 (`pyfa` → `pyfa_courses`), 评教 (`dpwj` → `wjtxxx` → `calculate_score` → `commit_answer`).

`JWXTClient` methods handle these differences internally. Each query method constructs the correct request format for its target API.

#### `_post` is the choke point

All API calls go through `self._post(path, data)`, which (a) builds the URL via `_build_api_url`, (b) sends the form POST, (c) detects login expiry (HTTP 401/403 or redirect to CAS login → `NotLoggedInError`), (d) decodes the EMAP envelope, (e) raises `JWXTProtocolError` on malformed JSON / missing `datas`, and (f) raises `JWXTBusinessError(code, msg, url)` on non-zero `code`. **Never call `self.session.post` directly from query methods** — bypassing `_post` skips all five checks. The current code routes every public POST through `_post`; preserve this when adding new methods.

#### Response parsing

All EMAP APIs return a standard envelope:
```json
{"code": "0", "datas": {"apiName": {"rows": [...], "totalSize": N}}}
```

`_extract_rows(datas, key)` normalizes extraction of the `rows` array. Parser functions (`_parse_grade`, `_parse_course`, …) map API field names to structured dataclass instances. Each dataclass carries a `raw` field with the original response dict for forward compatibility.

Module-level helpers reduce parsing duplication:

- `_to_bool(val)` — converts EMAP truthy tokens (`"1"`, `"是"`, `"true"`, `"True"`) to `bool`. Use this for any boolean field; don't reinvent `str(...) in (...)` chains in new parsers.
- `_COURSE_CATEGORY_TO_KBLB` — maps the public `"all"/"theory"/"experiment"` enum to EMAP's `KBLB` values (`"0"/"1"/"2"`).
- `_TJLX_TO_SCOPE` — maps EMAP's `TJLX` (`"01"`/`"02"`) to the public `scope` (`"class"`/`"course"`) used on the grade-statistics dataclasses.
- `_evaluation_form_data(...)` — builds the `requestParamStr` payload shared by `calculate_evaluation_score` and `submit_evaluation`. The two endpoints take the same body shape; this helper is the single source of truth.
- `_build_grade_stats_request(...)` — builds the `JXBID`/`KCH`/`XNXQDM`/`TJLX` form body shared by `query_grade_statistics` / `query_grade_distribution` / `query_grade_ranking`. Enforces the `class_id` vs `course_code` mutex (exactly one must be provided) and substitutes `JXBID="*"` for the course-overall (`TJLX=02`) path.

#### Schedule/unscheduled-courses share a private impl

`query_schedule_experimental` and `query_unscheduled_courses` differ only in API path and `_extract_rows` key — both POST `XNXQDM/XH/KBLB` against the same `wdkb_sy` `_WEU`. The shared body lives in `_query_courses_by_kblb(*, path_key, row_key, term, student_id, course_category)`. If you add another `KBLB`-driven endpoint, route it through this helper.

#### Week bitmap — `SKZC` is shape-shifting

In schedule rows (`cxxszhxqkb`, `querybjkb`) `SKZC` is a 0/1 **bitmap** (char N = week N); in `xswpkc` rows it's **text** (`"15-17周"`). Never parse it blindly: `_weeks_bitmap()` normalizes to bitmap-or-empty, and `_week_active(bitmap, week)` does the bounds-checked lookup. `Course.weeks_bitmap` is populated by the former; `UnscheduledCourse.weeks_text` keeps the latter. `query_courses_on_date(date)` chains `query_current_week` + `query_schedule` and filters on `week_day` + bitmap — no new endpoint involved.

#### 补考办理（bkbl）

读面为批次 + 可报名/已报名课程；写面仅 `signup_makeup_exam`（报名），取消报名有意不接。注意点：

- 补考学期**不等于**当前学期：取系统参数 `cxxtcs.do`（`CSDM=KW&ZCSDM=BKBMXNXQ`）的 `CSZA`，`_get_makeup_term()` 是 `term=None` 时的默认来源。
- `cxbkbmmx.do` 两个口径只差 `querySetting` 尾句：可报名 = `SFKBM=1 + KSBMZTDM notEqual 02`；已报名 = `KSBMZTDM m_value_equal 02`。
- 报名写接口 `xgksrwxs.do` 收 `param=<JSON数组>`（`XH/KSRWID/KSBMZTDM/KSDM`，报名="02"，取消="01"）。**外层信封恒为 `code=0`**，真实结果在 `datas.xgksrwxs.extParams`：`code=="1"` 成功，其余为业务拒绝（`msg` 含原因，如「学生不在报名时间范围内」）——SDK 据此抛 `JWXTBusinessError`，不能只信外层 code。

#### 全校课表（kcbcx）— Referer-gated code tables

- `/jwapp/code/*.do` dictionary endpoints validate the **`Referer` header**: missing → `code=404` *business envelope* (HTTP 200, not HTTP 404). Diagnosed by cookie-swap: the browser's own cookies replayed through `requests` still 404'd until `Referer` was added. `_emap_post`/`_post` take `referer=`; kcbcx methods pass `KCBCX_INDEX_URL`.
- Code tables return the standard `code` envelope. 专业 cascade is **client-side** (`otherFields.YXDM`); 班级 discovery is `bjcx.do` with server-side filters (`NJ/YXDM/ZYDM/SFYPK` as direct form params).
- `querybjkb` / `querybjkbtk` / `querybjkbwpk` / `queryjaskb` / `queryjaskbtk` are `requestParamStr` style and share `_query_bjkb` (`id_param` switches between `BJDM` and `JASDM`).
- 教室列表 `jscx.do` uses **`querySetting` JSON filters** (fuzzy `include` for `JASMC`, `equal` for the rest) while `XNXQDM` stays a direct form param.
- `API_PATHS` entries starting with `/` are site-absolute and bypass `JWXT_APP_BASE` in `_build_api_url`.

#### 学业完成（xywccx）—— 重算与计算时间

- 完成记录行（`cxxsscfa`，按 `-CZSJ` 倒序取首行）的 `CZSJ` 即页面显示的「本数据上次计算时间」，解析为 `AcademicCompletion.last_calculated_at`（RFC3339）；`query_academic_completion_time()` 是其便捷封装。
- 重算是**两段式写路径**：`bysc.do`（`PYFADM/BYNJDM/SCLBDM` 均取自完成记录行）触发计算，envelope 的 `datas.bysc.code==0` 才算受理（注意 `datas.bysc` 是对象不是 rows）；随后以前端同款 `byscjd.do`（`ZXJDKEY=BYSC_<XH>`）轮询进度，行内 `YWCS>=ZS` 为完成。`recalculate_academic_completion(wait=True)` 完成后会重新查询返回最新结果。

#### Grade statistics/distribution/ranking — `JXBID` vs `KCH` dispatch

`query_grade_statistics` (`jxbcjtjcx`), `query_grade_distribution` (`jxbcjfbcx`), and `query_grade_ranking` (`jxbxspmcx`) are three sibling APIs that all live behind the `cjcx` `_WEU` and share the same dispatch shape: the caller picks **either** `class_id` (teaching-class scope, `TJLX=01`) or `course_code` (whole-course scope, `TJLX=02`), and the body is `JXBID/KCH/XNXQDM/TJLX`. The mutex is enforced in `_build_grade_stats_request` — providing both or neither raises `ValueError`. The two scopes are surfaced to callers as `scope="class"` / `scope="course"` on the returned dataclass via `_TJLX_TO_SCOPE`. For `TJLX=02`, the server expects `JXBID="*"` (a sentinel, not a wildcard pattern); the helper substitutes that automatically — don't ask callers to pass `"*"` themselves. `query_grade_ranking` additionally takes `student_id` (defaults to the logged-in user) and adds `XH` to the body; the other two don't.

#### Evaluation — multi-step, write-once

The evaluation flow is the only multi-step *write* path:

```
query_evaluation_types  →  query_pending_evaluations  →  get_evaluation_detail
                        →  calculate_evaluation_score (predicate)
                        →  submit_evaluation (write — irreversible)
```

`calculate_evaluation_score` and `submit_evaluation` accept `group_no` and `eval_type` for forward compatibility, but the current server payload doesn't use them — both methods `del group_no, eval_type` and rely on `_evaluation_form_data`. Don't drop these parameters from the signatures: removing them is a breaking API change, and the EMAP server is known to revisit fields between releases.

#### Exception hierarchy

`JWXTError` is the base. Three concrete subclasses:

- `NotLoggedInError` — session expired (HTTP 401/403, or redirect to CAS login). Raised by `_post`.
- `JWXTProtocolError` — response format violates the EMAP envelope (non-JSON, missing `datas`, network/HTTP error). Raised by `_post` and a few callers when `_extract_rows` returns nothing where rows are required.
- `JWXTBusinessError(code, msg, url)` — server returned a structurally valid envelope with non-zero `code`. The original motivation was the evaluation system's `code=1 msg=未到评教时间` rejection: that's a *business-rule* refusal, not a protocol failure, and callers need to programmatically distinguish it (e.g. surfacing the message to the user vs. retrying).

`JWXTBusinessError` is **not** a subclass of `JWXTProtocolError` — they're siblings under `JWXTError`. Code that previously caught `JWXTProtocolError` to handle "any server-side rejection" needs updating: catch `JWXTBusinessError` for business rejections, leave `JWXTProtocolError` for actual protocol corruption. When raising new exceptions, pick the layer that matches: malformed JSON → protocol; valid JSON, server says "no" → business.

#### Constants layout

`constants.py` groups `APP_IDS` and `API_PATHS` by feature with `# —— … ——` headers (成绩查询 / 课表 / 学籍 / 考试 / 学生评教). Entries marked `（未使用）` are kept as references for future work but not wired through `JWXTClient`. When adding a new endpoint, place it under the matching header and add a one-line Chinese comment describing the API.

### Scxt (`ysu_sdk.scxt`)

创新创业学分认定系统（裸 IP `202.206.247.49/ysu_xf`，与 ldxt 同厂商）。**认证完全不同**：本系统未注册为 CAS service（服务端 CAS 配置残留 `cas.example.com` 占位符，直连流程是坏的），必须经双创平台（`/ysu_pt`）中转：

1. `cas.authorize(/ysu_pt/UnifiedAuth/CASLogin)` —— 平台 `.loginAuth`；
2. GET `/ysu_pt/System/Platform/AccessSubsystem/{固定guid}`（**必须带平台主页 Referer**，否则 302 回平台根）；
3. GET 302 给出的 `authserver/access?access=…` 票据（同样带 Referer）→ 302 LoginRole；
4. **预热**：跟随落地链后再 GET 一次 `/ysu_xf/System/Home/Index`——服务端会话状态经主页初始化，否则列表页**少渲染列**（实测「成绩」列在预热前不存在于 HTML，与视口/UA 无关）。

- 表格解析与 ldxt 共享 `ysu_sdk/_table.py`（从 ldxt 包内提升）。
- 批次陷阱：学分汇总 `BatchID=""` ≠ 全部，服务端默认只给当前批次；全量 = 解析申报页 `BatchID` 下拉框 → 逐批次查询（`query_all_credit_records`）。
- 竞赛库 1448 条 / 活动库 132 条，固定每页 20，`pageIndex=N` 翻页，`PageSize` 参数被忽略；分页信息从「共N页M条记录」文本正则提取。

### JWMobile (`ysu_sdk.jwmobile`)

移动教务（课程签到）。**与 jwxt 子包完全解耦**：不共用 session、不 import jwxt；唯一的组合点是 `CourseLike` Protocol（结构化鸭子类型），jwxt 的 `Course` 天然满足但编译期互不相识。

- **认证流与 EMAP 不同**：CAS `authorize(/jwmobile/auth/index)` 落地 JSESSIONID 后，再 GET 认证入口并**手动跟随跳转链**，从重定向 `Location` 里正则提取 `token=`——注意 token 在 **fragment**（`#/…?token=…`，SPA 路由）而非 query 里，解析时必须匹配整串。JWT 以 `Authorization` cookie（path `/jwmobile`）携带。
- **Envelope 是 `code:200`**（不是 EMAP 的 `code:"0"`；200/0 均算成功，401 触发懒重认证），业务调用为 JSON POST 到 `/jwmobile/biz/v410`。
- `sign()` 是全包唯一写操作（本人签到）。已结束的活动会返回 `code=404 msg=Sign-in Expired` 的业务拒绝——可用于安全验证写路径。
- `query_current_lesson_for_course` 封装 teachClassId 解析规则（`class_type=="1"` 取 JXBID，否则取 SYXZDM）；`Course` 上的 `class_id/schedule_id/class_type/experiment_type_code` 字段为此而补。

### Ldxt (`ysu_sdk.ldxt`)

劳动教育实践课程管理平台（ldxt.ysu.edu.cn，南京先极科技）。**非 EMAP**：ASP.NET MVC 服务端渲染，无 JSON 信封，数据靠标准库 `html.parser` 抽 HTML 表格（`ysu_sdk/_table.py`，与 scxt 共享）。

- **SSO 三步握手**：`cas.authorize(/About/UnifiedAuthenticationLogin)` 出票种 `.DotNetCasClientAuth` → `POST` 同端点确认（JSON `Success`+`Data.Url`）→ GET 角色落地 URL（通常 `/System/User/LoginRole`）。只 authorize 主页不够——票据消费端点是 UnifiedAuthenticationLogin。
- 登录页判定用**精确路径相等**（`/System/User/Login`），子串匹配会误杀 `LoginRole`。
- 表格解析：只收顶层 `<table>`（主表单元格内嵌详情小表，嵌套表内容必须忽略）；`m-badge` 徽标文本单独收集——活动名单元格的「教师选择」是徽标（剥离），而状态列整体就是一个徽标（回退为单元格文本）。
- 时间区间形如 `2024-09-28 08:00 至 2024-09-28 12:00`，按「至」拆分后走 `_datetime` 归一。
- 导出端点是旧版 OLE2 `.xls`（magic `d0cf11e0`），不解析、不使用。

### XGXT (`ysu_sdk.xgxt`)

学工系统（`xgxt.ysu.edu.cn`）「综合测评」应用的只读查询。Scope is deliberately limited to the 综测成绩 tab: evaluation terms, score+ranking, indicator details, radar comparison, year overview, and the academic report popup. 测评公示 / 综测打分 are intentionally not implemented (the latter is a write surface).

#### Differences from JWXT

- **Role handshake instead of `_WEU` per-app gating.** Module APIs 404 until the session binds an app role (e.g. 「学生组」). `_ensure_app_role()` replicates the frontend's handshake once per client instance: `getAppConfig.do` (appId `5275772372599202`) → pick the `active` entry in `HEADER.dropMenu` → `setXgCommonAppRole.do` + `changeAppRole/<app>/<roleId>.do`. These three endpoints do NOT use the `code` envelope (raw config JSON / `returnCode` / `success`), so they go through `_raw_post`, not `_post`. The flag resets in `_reauthorize`.
- **Two envelope shapes side by side.** Controller style (`evaluationApplyController` / `evaluationBjhpController`): request body is `data=<JSON>`, response payload under `data` — handled by `_post_controller`. EMAP list style (`tjsqhqxqzbxx`, `xycjbg`): plain form params, payload under `datas.<key>.rows` — handled by `_post_rows`. Both are keyed on `code == "0"` and share `_post` as the choke point (same expiry detection and exception layering as jwxt).
- **Term model.** `CPXN` (e.g. `"2025"` = 2025-2026学年) + `CPXQ` (`"1"`/`"2"`) come in pairs from `getCpxnxq.do` (`XNXX` list, newest first). `_resolve_term(None, None)` defaults to the newest pair.
- Lazy re-auth decorator and `XGXTSession` mirror the jwxt pattern one-for-one.

### WAF / live-testing notes (learned 2026-07)

`cer` / `xgxt` / `ehall` / `res` subdomains sit behind a WAF that issues `nS_*` cookies (`jwxt` is notably NOT behind it). From off-campus IPs, bursts of non-browser traffic (python-requests/curl) get connections RST'd after the TLS handshake and escalate to a **full IP block** within minutes — the block then affects browsers too. When probing live endpoints: keep volume low, sequential, browser-paced; prefer capturing traffic from a real browser session.

Related design point: `CASClient.is_authenticated()` raises `CASNetworkError` on transport failure (connection refused, timeout, WAF reset) instead of returning `False`, so a WAF-blocked/unreachable gateway is never confused with an expired TGC. Callers using it as a health signal should catch `CASNetworkError` separately.

The same WAF also **tarpits progressively**: after enough burst traffic, requests from the flagged client fingerprint succeed only after quantized delays that escalate per offense (observed 30 s → 40 s → 50 s, capping at ~50 s). It looks like a hang but is throttling — and crucially, retrying feeds the escalation. Counterintuitively the delay pool is **fingerprint-selective, not IP-wide**: at the same moment from the same IP, Chrome (~150 ms) and curl/libcurl (~340 ms) pass at full speed while python-requests/urllib3 is delayed. Two lessons: (a) stop the flagged fingerprint's traffic immediately rather than retrying; (b) curl_cffi (libcurl, any impersonation) escapes the pool and can serve as a recovery transport for smoke tests. Whether the pool is armed globally for urllib3 or only after behavioral bursts is undetermined — treat paced, normal SDK use as safe by default.

## Conventions

- Docstrings and user-facing strings (exceptions, README) are in Simplified Chinese; identifiers and code comments default to English.
- **日期/时间字段约定**：日期统一 `YYYY-MM-DD`，日期时间统一 RFC3339（`YYYY-MM-DDTHH:MM:SS`）。归一由 `_to_iso_date` / `_to_iso_datetime` 在解析层完成——只改写已知格式（空格分隔、点号分隔等），未识别格式**原样透传**（字符串契约下不完美不等于数据丢失）。展示型时间串（如 `Exam.exam_time` 的 `"2026-06-29 13:30-15:05(星期一)"`）不改写原字段，需要结构化时加解析伴随字段（`exam_start_time` / `exam_end_time`）。
- `from __future__ import annotations` everywhere. Dataclasses use `slots=True`; immutable ones use `frozen=True`.
- Module-private modules are prefixed with `_` (`_crypto.py`, `_parser.py`) and not re-exported from `__init__.py`.
- Exception hierarchy lives in `exceptions.py`; everything inherits from `CASError` (for `cas/`) or `JWXTError` (for `jwxt/`). Add new exception types there rather than raising `Exception` / `ValueError`.
