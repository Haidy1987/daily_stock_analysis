# 多用户数据归属清单与迁移设计

> 状态：阶段 0 盘点完成，待审阅
> 基线：本地 HEAD `aa513135`（工作区另有未提交文档/提词改动，未覆盖）
> 总规划：[multi-user-system-plan.md](./multi-user-system-plan.md)
> 执行提词：[../cursor/multi-user/00-discovery-and-migration-inventory.md](../cursor/multi-user/00-discovery-and-migration-inventory.md)

本文档只记录**已用源码核对**的事实与迁移设计。不确定处标为 **待确认**。本阶段未改认证实现、未改业务表、未执行破坏性数据库操作。

## 0. 设计约束（阶段 0 锁定，阶段 1+ 遵守）

- 第一期仅 `admin` / `user` 两种角色；关闭开放注册，由管理员创建用户。
- 继续使用 HttpOnly Cookie；Cookie 名可保留 `dsa_session`，阶段 1 将 Cookie 值改为不透明 token，服务端在 `user_sessions` 存 token hash（见 §5）。
- `user_id` 只能来自服务端认证上下文，禁止信任请求体或查询参数。
- 公共行情、新闻缓存、股票基础数据、系统配置不得误加用户隔离。
- 不做组织租户、支付、OAuth、用户自定义 AI Key。

---

## 1. 当前认证链路

### 1.1 架构（单管理员门禁）

```text
浏览器 (axios withCredentials)
  -> POST /api/v1/auth/login
  -> src/auth.py 校验 {DATA_DIR}/.admin_password_hash
  -> Set-Cookie: dsa_session = nonce.ts.hmac
  -> 后续 /api/v1/* 经 AuthMiddleware -> verify_session()
```

| 项 | 现状 | 源码路径 |
| --- | --- | --- |
| 开关 | `ADMIN_AUTH_ENABLED`（`.env`，默认关闭） | `src/auth.py` `is_auth_enabled()` / `_is_auth_enabled_from_env()` |
| 密码文件 | `{DATABASE_PATH 父目录}/.admin_password_hash`，格式 `salt_b64:hash_b64` | `src/auth.py` `_get_credential_path()` |
| 哈希 | PBKDF2-HMAC-SHA256，`PBKDF2_ITERATIONS=100_000` | `src/auth.py` |
| Session secret | `{DATA_DIR}/.session_secret`（32 字节） | `src/auth.py` `_load_session_secret()` |
| Cookie 名 | `dsa_session` | `src/auth.py` `COOKIE_NAME` |
| Session 格式 | `{nonce}.{unix_ts}.{hmac_hex}`，**无 user_id** | `create_session()` / `verify_session()` |
| 过期 | `ADMIN_SESSION_MAX_AGE_HOURS`（默认 24） | `verify_session()` |
| Cookie 属性 | `HttpOnly`、`SameSite=Lax`、`path=/`；`Secure` 在 `TRUST_X_FORWARDED_FOR`+HTTPS 或直连 HTTPS 时启用 | `api/v1/endpoints/auth.py` |
| 登出 | `rotate_session_secret()` **全局**使所有 Cookie 失效 | `auth_logout()` |
| 限流 | 按 IP，5 次失败 / 300 秒 | `check_rate_limit()` / `get_client_ip()` |
| 身份注入 | **无** `get_current_user`；中间件不写 `request.state.user` | `api/deps.py`（仅 DB/config 依赖） |

### 1.2 API 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/auth/status` | 认证状态；豁免登录 |
| POST | `/api/v1/auth/login` | 登录或首次设密 |
| POST | `/api/v1/auth/settings` | 开关 `ADMIN_AUTH_ENABLED`（需 session） |
| POST | `/api/v1/auth/change-password` | 改密（需 session） |
| POST | `/api/v1/auth/logout` | 轮换 secret + 清 Cookie |

路由：`api/v1/endpoints/auth.py`，挂载于 `api/v1/router.py` `prefix="/auth"`。

### 1.3 中间件豁免路径

`api/middlewares/auth.py` `EXEMPT_PATHS`：

```text
/api/v1/auth/login
/api/v1/auth/status
/api/health
/api/v1/health
/health
/docs
/redoc
/openapi.json
```

规则摘要：

- `ADMIN_AUTH_ENABLED=false`：全部 `/api/v1/*` 放行。
- 非 `/api/v1/` 前缀（静态资源、SPA、部分根级 health）不受该中间件保护。
- 桌面旁路：`DSA_DESKTOP_MODE=true` 时，`.env` 导入/导出与 AlphaSift install 可免 admin session（`api/v1/endpoints/system_config.py`、`src/services/alphasift_service.py`）。

### 1.4 旧管理员凭据 → 初始管理员（阶段 1 迁移草案）

| 步骤 | 说明 |
| --- | --- |
| 1 | 若存在 `.admin_password_hash`，创建 `users` 行：`username=admin`（或可配置名）、`role=admin`、`status=active`，`password_hash` **直接复用**现有 salt:hash 格式（避免强制用户立刻改密）。 |
| 2 | 若无密码文件且认证曾关闭：阶段 1 需在首次启用多用户时走“设初始管理员密码”流程（与现有首次设密类似）。 |
| 3 | 迁移成功后保留 `.admin_password_hash` 只读备份一段时间，或明确删除时机；**待确认**是否保留 dual-read 兼容窗口。 |
| 4 | 旧无状态 HMAC session：切换到 `user_sessions` 后应 `rotate_session_secret` 或使旧 Cookie 校验失败，强制重新登录。 |

验证命令（只读）：

```bash
# 是否已设管理员密码（不打印哈希）
python3 -c "from src.auth import is_password_set, is_auth_enabled; print('password_set=', is_password_set()); print('auth_enabled=', is_auth_enabled())"
```

---

## 2. 当前数据库技术与迁移方式

| 项 | 现状 |
| --- | --- |
| 引擎 | SQLite only |
| ORM | SQLAlchemy；模型集中在 `src/storage.py` |
| URL | `Config.get_db_url()` → `sqlite:///{absolute DATABASE_PATH}` |
| 默认路径 | `./data/stock_analysis.db`（env `DATABASE_PATH`） |
| Docker | `DATABASE_PATH=/app/data/stock_analysis.db`；volume `../data:/app/data`（`docker/docker-compose.yml`） |
| 初始化 | `DatabaseManager.__init__` → `Base.metadata.create_all` + `_ensure_*` 补丁 |
| Schema 版本 | `CURRENT_SCHEMA_VERSION = "2026-06-05-create-all-baseline"`，表 `schema_migrations` |
| Alembic | **无** |
| WAL | `SQLITE_WAL_ENABLED`（默认 true）+ `busy_timeout` + 写事务重试 |
| 专用 DB 备份脚本 | **无**；文档要求备份时同时拷贝 `.db` / `.db-wal` / `.db-shm`（见 `docs/desktop-package.md`） |
| `.env.example` | **未列出** `DATABASE_PATH` / `SQLITE_*` / `ADMIN_AUTH_*`（与代码默认值存在文档缺口；**待确认**是否刻意隐藏） |

表数量（ORM metadata）：**28**。

只读核对命令：

```bash
python3 -c "from src.storage import Base; print(len(Base.metadata.tables)); print('\\n'.join(sorted(Base.metadata.tables)))"
```

---

## 3. 数据归属表（表级）

归属标签：

- **public**：全实例共享，不加 `user_id`
- **user-owned**：应属登录用户；当前多数尚未有列
- **admin-only**：仅管理员观测/治理
- **system**：内部元数据
- **待确认**：需产品/阶段 2 再定

| 表名 | ORM 类 | 归属 | 依据 |
| --- | --- | --- | --- |
| `schema_migrations` | `DatabaseSchemaMigration` | system | schema 版本标记 |
| `stock_daily` | `StockDaily` | public | 行情/指标缓存，按 code+date |
| `news_intel` | `NewsIntel` | public（元数据例外） | URL 全局唯一；`requester_user_id` 仅为 Bot/查询审计，不参与隔离 |
| `intelligence_sources` | `IntelligenceSource` | public / admin 配置 | 系统资讯源 |
| `intelligence_items` | `IntelligenceItem` | public | 沉淀资讯 |
| `fundamental_snapshot` | `FundamentalSnapshot` | public（按 query） | 基本面快照；与分析 query 关联 |
| `analysis_history` | `AnalysisHistory` | user-owned | 分析报告主表；无 user 列，现全局可见 |
| `backtest_results` | `BacktestResult` | user-owned（随分析） | FK → `analysis_history` |
| `backtest_summaries` | `BacktestSummary` | **待确认** | 按 scope/code 聚合；可能跨用户共享统计 |
| `portfolio_accounts` | `PortfolioAccount` | user-owned | 有 `owner_id` 但非认证用户且 list 不过滤 |
| `portfolio_trades` | `PortfolioTrade` | user-owned（经 account） | `account_id` FK |
| `portfolio_cash_ledger` | `PortfolioCashLedger` | user-owned（经 account） | 同上 |
| `portfolio_corporate_actions` | `PortfolioCorporateAction` | user-owned（经 account） | 同上 |
| `portfolio_positions` | `PortfolioPosition` | user-owned（经 account） | 同上 |
| `portfolio_position_lots` | `PortfolioPositionLot` | user-owned（经 account） | 同上 |
| `portfolio_daily_snapshots` | `PortfolioDailySnapshot` | user-owned（经 account） | 同上 |
| `portfolio_fx_rates` | `PortfolioFxRate` | public | 汇率参考缓存 |
| `conversation_messages` | `ConversationMessage` | user-owned | 靠 `session_id` 字符串；Web 未绑登录用户 |
| `conversation_summaries` | `ConversationSummary` | user-owned | 同上 |
| `agent_provider_turns` | `AgentProviderTurn` | user-owned | 同上；`anchor_user_message_id` 是消息 FK，不是账号 ID |
| `llm_usage` | `LLMUsage` | admin-only（观测）/ **待确认**是否兼 user 限额 | 无 user_id；`user_message_hmac` 非登录用户 |
| `alert_rules` | `AlertRuleRecord` | user-owned | 全局规则列表，无 user 列 |
| `alert_triggers` | `AlertTriggerRecord` | user-owned（经 rule） | 触发历史 |
| `alert_notifications` | `AlertNotificationRecord` | user-owned（经 rule） | 通知尝试 |
| `alert_cooldowns` | `AlertCooldownRecord` | user-owned（经 rule） | 冷却状态 |
| `decision_signals` | `DecisionSignalRecord` | **待确认** → 倾向 user-owned | 全局信号池；与 analysis 关联；含 `holding_only` 等组合过滤 |
| `decision_signal_outcomes` | `DecisionSignalOutcomeRecord` | 随 signal | 前向结果 |
| `decision_signal_feedback` | `DecisionSignalFeedbackRecord` | **待确认** | 无反馈者 ID，每 signal 一条最新反馈 |

### 3.1 非表存储（同等重要）

| 存储 | 归属 | 说明 |
| --- | --- | --- |
| `.env` / `STOCK_LIST` | **待确认** → 倾向拆成 user-owned | 自选股 API 读写全局配置（`api/v1/endpoints/stocks.py`）；系统级定时任务仍可能用全局列表 |
| `{DATA_DIR}/.admin_password_hash` | admin 凭据 | 阶段 1 迁入 `users` |
| `{DATA_DIR}/.session_secret` | 会话签名 | 阶段 1 改为 per-session token hash 后可弱化 |
| `reports/*.md` | **待确认** → 倾向 user-owned | `src/notification.py` `save_report_to_file`；文件名按日期，无用户目录 |
| 内存 `TaskQueue` | **待确认** → 需带 user 上下文 | `src/services/task_queue.py` 单例；SSE `/api/v1/analysis/tasks/stream` |
| Bot 平台 `user_id` | 外部平台身份 | **不得**当作本地 `users.id` |

---

## 4. 既有 owner_id / user_id 语义与兼容风险

| 标识 | 位置 | 实际含义 | 兼容风险 |
| --- | --- | --- | --- |
| `portfolio_accounts.owner_id` | DB 列 `String(64)` | API 请求体可选业务标签；`list_accounts()` **不过滤**；Web 创建常不传 | **不能**直接当本地 user_id；空值/任意字符串不可自动映射 |
| `news_intel.requester_user_id` / `requester_user_name` | DB 列 | Bot/CLI 查询发起者平台 ID（pipeline `query_context`） | 仅审计；过滤读写会误伤公共新闻缓存 |
| Bot `message.user_id` | `bot/models.py` | 钉钉/飞书/Telegram 等平台发送者 | 会话键用 `{platform}_{user_id}`，与 Web 账号无关 |
| Agent API `user_id` 查询参数 | `api/v1/endpoints/agent.py` `list_chat_sessions` | 用作 `session_id` **前缀**过滤 | 客户端可控；多用户后必须改为服务端 `current_user` |
| Web `dsa_chat_session_id` | localStorage | 随机 UUID | 与登录无关；列表接口可看到全部会话（认证仅门禁） |
| DeepSeek / LLM `user_id` hint | `src/llm/provider_cache.py` | provider 侧提示 | 不落本地用户表 |
| `agent_provider_turns.anchor_user_message_id` | DB 列 | 指向 conversation message 行 | 命名易混，不是账号 ID |
| `llm_usage.user_message_hmac` | DB 列 | 消息指纹 | 不是登录用户 |

**硬规则**：本地认证 `user_id` 与上述任一字段默认不自动合并；若未来要做 Bot↔Web 绑定，需单独映射表（超出第一期）。

---

## 5. 建议新增表字段（阶段 1，本阶段不实现）

与总规划对齐，并补充与现有 Cookie 的兼容方案。

### 5.1 `users`

```text
id              INTEGER PK
username        TEXT UNIQUE NOT NULL
email           TEXT NULL          # 第一期可不启用邮箱登录
password_hash   TEXT NOT NULL      # 复用 salt_b64:hash_b64 + PBKDF2
role            TEXT NOT NULL      # admin | user
status          TEXT NOT NULL      # active | disabled
created_at      DATETIME
updated_at      DATETIME
last_login_at   DATETIME NULL
```

### 5.2 `user_sessions`

```text
id              INTEGER PK
user_id         INTEGER NOT NULL  FK -> users.id
token_hash      TEXT NOT NULL      # Cookie 明文 token 的哈希
expires_at      DATETIME NOT NULL
last_seen_at    DATETIME
revoked_at      DATETIME NULL
ip_address      TEXT
user_agent      TEXT
created_at      DATETIME
```

索引建议：`user_id`、`token_hash`、`expires_at`。

**与 `dsa_session` 兼容**：

- Cookie 名继续 `dsa_session`，减少前端改动。
- Cookie 值从 `nonce.ts.hmac` 改为高熵随机 token；校验改为查 `user_sessions`（未过期、未 revoke）。
- 登出/改密/禁用：revoke 该用户会话（可单会话或全部），不再依赖全局 `rotate_session_secret()` 作为唯一手段（secret 文件可保留作过渡或废弃）。

### 5.3 `user_preferences`

```text
id, user_id UNIQUE
language, theme, default_market, default_report_language
# 其他 UI 偏好 JSON 可选
created_at, updated_at
```

禁止存放系统 API Key / 模型密钥。

### 5.4 `audit_logs`

```text
id, actor_user_id, action, target_type, target_id
ip_address, user_agent, detail_json, created_at
```

覆盖：登录成功/失败、创建/禁用用户、重置密码、revoke sessions、删除用户数据等。

---

## 6. user-owned 表增加 `user_id` 的迁移策略

### 6.1 通用原则

1. 新增可空 `user_id` → 回填 → 再改为 NOT NULL（SQLite 可用表重建或分步 `_ensure_*`）。
2. **旧数据默认归属初始管理员**（迁移自 `.admin_password_hash` 的那个 admin 用户）。
3. `user_id` 写入路径一律取自服务端会话；Repository 的 list/get/update/delete 必须带 `user_id` 条件。
4. 访问他人资源建议返回 **404**（总规划约定）。
5. 不可自动判断的数据标 **待确认**，不要静默猜测归属。

### 6.2 分表策略

| 对象 | 迁移策略 |
| --- | --- |
| `analysis_history` | 加 `user_id`；历史行 → 初始 admin；`query_id` 仍为运行链路 ID |
| `backtest_results` | 经 `analysis_history_id` 继承 owner；或冗余 `user_id` 便于过滤 |
| `backtest_summaries` | **待确认**：若为全局聚合可保持 public；若含用户策略则按 user 拆分 |
| Portfolio 子表 | 优先在 `portfolio_accounts` 加真实 `user_id`；子表经 `account_id` 间接隔离。现有 `owner_id`：空/非数字 **不**自动映射；若值恰好等于未来 username，**待确认**是否人工映射工具 |
| `alert_*` | `alert_rules` 加 `user_id`；triggers/notifications/cooldowns 经 `rule_id` |
| `decision_signals*` | **待确认**：若信号视为用户私有建议池则加 `user_id`（或经 `source_report_id`→analysis）；feedback 需记录 `user_id` |
| `conversation_*` / `agent_provider_turns` | 加 `user_id`；现有 Web 随机 `session_id` 历史行 → 初始 admin 或标“孤儿会话”只读归档（**待确认**） |
| Bot 会话 | 第一期可继续用 platform session 前缀；与 Web 用户映射 **待确认**（可不做） |
| `llm_usage` | 建议加可空 `user_id` 便于 admin 分用户观测；配额系统第一期可不做 |
| Watchlist | **新建**用户级存储（表或 `user_preferences` JSON）；全局 `STOCK_LIST` 保留给 CLI/schedule 系统任务（**待确认**产品语义） |
| `reports/` 文件 | 阶段 2：按 `user_id` 子目录或文件名嵌入 user；旧文件归 admin 或只读归档 |

### 6.3 不可自动判断的数据

- `portfolio_accounts.owner_id` 已有任意字符串的生产数据含义。
- Web Agent 历史会话与“哪个真人”的对应关系。
- `decision_signal_feedback` 无作者时的历史反馈归属。
- 系统定时任务 / GitHub Actions / CLI 产生的 `analysis_history`：建议固定 `user_id=admin` 或 `system` 伪用户（**待确认**；若引入 system 用户需在阶段 1 角色模型中显式设计，当前规划仅 admin/user）。

---

## 7. 需要传递用户上下文的调用链

| 链路 | 关键路径 | 阶段 2 要点 |
| --- | --- | --- |
| 分析提交 | `api/v1/endpoints/analysis.py` → `TaskQueue.submit_*` | 任务对象携带 `user_id` |
| 任务 SSE | `analysis` tasks stream | 只推送当前用户任务；禁止枚举他人 task_id |
| 历史/报告 API | `api/v1/endpoints/history.py`、`src/services/history_service.py` | 查询加 `user_id` |
| Pipeline 落库 | `src/core/pipeline.py`、`DatabaseManager.save_analysis_history` | 写入 `user_id` |
| 通知与文件 | `src/notification.py` | 渠道仍可为系统级；文件归属按 user |
| 自选股 | `api/v1/endpoints/stocks.py` watchlist* | 离开全局 `STOCK_LIST` 或双写策略 |
| 持仓 | `api/v1/endpoints/portfolio.py`、`portfolio_service.py` | 强制 account.user_id；废弃请求体信任 |
| 预警 | `alert_service.py`、`alert_worker.py` | Worker 按规则所属用户解析 watchlist/portfolio |
| 决策信号 | `decision_signal_service.py`、`task_queue` 抽取 | 抽取结果归属触发用户 |
| Agent | `api/v1/endpoints/agent.py` chat/stream/research | session 绑定 `current_user.id`；忽略客户端 `user_id` 参数作授权依据 |
| Usage | `api/v1/endpoints/usage.py` | admin 看全局；user 仅看自己（若开放） |
| 系统配置 | `system_config.py` | 保持 admin-only |
| CLI / schedule | `main.py`、`RuntimeSchedulerService` | **待确认**归属：建议 admin/system |
| 桌面端 | `DSA_DESKTOP_MODE` 旁路 | 单用户桌面可默认本地 admin；需文档说明 |

---

## 8. SQLite 锁、WAL、备份、Docker 与回滚风险

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| WAL 三件套 | 只拷 `.db` 可能丢最近写入 | 备份/还原同时处理 `.db`、`.db-wal`、`.db-shm`，或先安全 checkpoint |
| 写锁 | 多用户并发分析加重 `database is locked` | 保持 WAL、`busy_timeout`、写重试；评估长事务 |
| `create_all` | 只加表不加列语义演进 | 新列继续 `_ensure_*` 或引入正式迁移链（**待确认**是否上 Alembic） |
| Docker volume | `../data:/app/data` 持久化 DB 与凭据文件 | 迁移前备份整个 `data/` 与 `.env` |
| 回滚 | 代码回退后新表仍残留 | 文档说明：保留表无害；若需干净回滚则恢复 DB 文件快照 |
| 认证切换窗口 | HMAC Cookie → DB session | 强制全员重新登录；准备管理员密码文件回退路径 |
| 无专用备份 CLI | 运维靠手工/卷快照 | 阶段 4 补充备份与恢复说明（提词 04） |

回滚基本动作（部署态）：

```text
1. 停服务
2. 还原 data/stock_analysis.db(+wal/shm)、.env、.admin_password_hash（若仍需要）
3. 部署上一版本镜像/代码
4. 启动并验证 /api/v1/auth/status 与关键业务读路径
```

---

## 9. 阶段 1–4 前置条件、阻塞项与建议顺序

### 9.1 阶段 1 认证核心 — 前置

- [ ] 本清单审阅通过（尤其是 admin 密码复用与 session 模型）。
- [ ] 确认初始管理员 username 默认值（建议 `admin`）。
- [ ] 确认是否保留 `ADMIN_AUTH_ENABLED` 总开关作为“多用户认证总开关”兼容桌面/本地。
- [ ] 确认关闭开放注册、仅 admin/user。

阻塞项：

- 无 `current_user` 依赖前，不要改业务表 `user_id`。
- `.env.example` 与 Web 设置页对 auth/session 配置的暴露范围需产品确认。

### 9.2 阶段 2 数据隔离 — 前置

- [ ] 阶段 1：`users` / `user_sessions` / `get_current_user` / 密码迁移已上线可测。
- [ ] Watchlist 存储方案选定（新表 vs preferences）。
- [ ] 系统任务（schedule/CLI/Actions）的 `user_id` 归属策略选定。
- [ ] `decision_signals` 与 `backtest_summaries` 归属评审结论。

阻塞项：

- `TaskQueue` 与 SSE 若无 user 作用域，存在跨用户任务窥探风险。
- `portfolio.owner_id` 与真实 `user_id` 双字段并存时的 API 兼容期。

### 9.3 阶段 3 管理员 Web — 前置

- [ ] 阶段 1 API：`/auth/me`、admin users CRUD、reset-password、logout-all。
- [ ] `audit_logs` 可查询。
- [ ] 系统配置页继续 admin-only 的回归范围。

### 9.4 阶段 4 测试与切换 — 前置

- [ ] 在**副本库**跑完整迁移。
- [ ] 用户 A/B 隔离验收用例（分析/自选/持仓/预警/问股）。
- [ ] 备份与回滚演练（含 WAL）。
- [ ] 文档与 `CHANGELOG` 用户可见说明。

### 9.5 建议顺序（不变）

```text
0 盘点（本文） -> 1 认证核心 -> 2 数据隔离 -> 3 管理员 Web -> 4 测试切换
```

禁止在阶段 0/1 未完成时直接改业务表隔离逻辑。

---

## 10. 用户私有数据入口清单（API / Repository / 任务）

便于阶段 2 逐项打勾（路径均为仓库内相对路径）。

| 域 | API | Repository / Service | 后台/流式 |
| --- | --- | --- | --- |
| 分析 | `api/v1/endpoints/analysis.py` | `src/repositories/analysis_repo.py`、`task_queue.py`、`pipeline.py` | TaskQueue、SSE |
| 历史 | `api/v1/endpoints/history.py` | `history_service.py`、`analysis_repo.py` | 报告 Markdown 生成 |
| 自选 | `api/v1/endpoints/stocks.py`（watchlist*） | `system_config_service.py`（`STOCK_LIST`） | AlertWorker watchlist scope；schedule |
| 持仓 | `api/v1/endpoints/portfolio.py` | `portfolio_repo.py`、`portfolio_service.py` | 持仓触发分析；组合风险 |
| 预警 | `api/v1/endpoints/alerts.py` | `alert_repo.py`、`alert_service.py` | `alert_worker.py` |
| 决策信号 | `api/v1/endpoints/decision_signals.py` | `decision_signal_*` | task_queue 抽取；outcomes run |
| 问股 | `api/v1/endpoints/agent.py` | `src/agent/*`、`storage` chat helpers | chat/stream SSE；Bot chat |
| 用量 | `api/v1/endpoints/usage.py` | `storage` llm_usage helpers | pipeline/agent 写入 |
| 认证（阶段 1） | `api/v1/endpoints/auth.py` | 将扩展 `src/auth.py` + 新表 | 限流、审计 |

Web 入口参考：`apps/dsa-web/src/api/{analysis,history,systemConfig,portfolio,alerts,decisionSignals,agent,usage}.ts` 及对应 pages/stores。

---

## 11. 待确认汇总

1. `ADMIN_SESSION_MAX_AGE_HOURS` 未进 `.env.example` / config_registry 是否刻意。
2. `.env.example` 是否应补 `DATABASE_PATH` / `SQLITE_*` / auth 相关项。
3. 是否引入 Alembic，或继续 `_ensure_*` 补丁风格。
4. `portfolio_accounts.owner_id` 生产环境实际取值约定。
5. `backtest_summaries`、`decision_signals`、feedback 的最终归属。
6. 全局 `STOCK_LIST` 与用户自选并存时，schedule/AlertWorker 读哪一份。
7. CLI / GitHub Actions / schedule 产物挂 admin 还是引入 `system` 主体。
8. Bot 会话是否要在第一期绑定本地 Web 用户。
9. `reports/` 目录隔离粒度与旧文件处理。
10. 密码文件迁移后 dual-read 兼容窗口时长。

---

## 12. 阶段 0 验收对照

| 验收项 | 结果 |
| --- | --- |
| 表级数据归属清单 | 已完成（§3，28 表 + 非表存储） |
| 旧管理员凭据迁移说明 | 已完成（§1.4） |
| 用户私有数据 API/Repo/任务入口 | 已完成（§7、§10） |
| 未执行破坏性数据库操作 | 是；仅只读 `Base.metadata` 导入 |

**下一步**：审阅本清单后，再执行 [../cursor/multi-user/01-auth-core.md](../cursor/multi-user/01-auth-core.md)。
