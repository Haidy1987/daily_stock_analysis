# Cursor 提词 01：多用户认证核心

## 前置条件

必须先完成 [阶段 0：盘点与迁移设计](00-discovery-and-migration-inventory.md)，并确认数据库迁移方式、旧数据归属和会话兼容策略。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、docs/plans/multi-user-system-plan.md，以及阶段 0 形成的实际数据盘点文档。

本阶段目标：在不改造业务数据隔离的前提下，建立可复用的多用户认证核心：users、user_sessions、admin/user 角色、账号状态、当前用户依赖和审计日志。

实施前：

1. 检查工作区状态，保留用户改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 复核现有 src/auth.py、api/v1/endpoints/auth.py、api/middlewares/auth.py、前端 AuthContext 和 LoginPage。
3. 按阶段 0 确认的实际数据库初始化和迁移机制实现新增表；禁止凭空引入第二套 ORM 或平行数据库。

必须实现：

- users 表：唯一 username，password_hash，role，status，创建/更新时间，最后登录时间。
- user_sessions 表：只保存 session token 哈希，包含 user_id、过期时间、撤销时间、IP、User-Agent 和最后访问时间。
- audit_logs 表：至少记录登录成功、登录失败、退出、改密、创建/禁用/启用用户和重置密码。
- current_user 依赖：从服务端 session 解析 user_id 和 role，供 API 和服务层复用。
- admin/user 角色校验：系统配置、用户管理和敏感配置仅 admin 可访问。
- 禁用用户立即不能登录，已有会话不能继续调用受保护 API。
- 修改密码或 logout-all 后，相关已有会话失效。
- 保留现有管理员认证兼容能力：现有 .admin_password_hash 必须能迁移为初始 admin 用户，不能静默丢失管理员访问能力。
- 保留现有登录限流、密码最小长度和错误码语义；如需改变，补充兼容说明。

建议新增或兼容的 API：

- GET /api/v1/auth/me
- POST /api/v1/auth/logout-all
- 现有 login、logout、change-password、status 保持兼容。

安全边界：

- 不开放公开注册。
- 不把 password、password_hash、session token、API Key 放进响应或日志。
- Cookie 使用 HttpOnly、SameSite=Lax，并按实际 Traefik forwarded headers 正确设置 Secure。
- 不信任前端传入的 user_id、role 或 owner_id。
- 不使用静默返回 None/False/[] 来掩盖认证失败；认证失败返回明确的 401/403。

前端只做认证基础适配：

- AuthContext 增加当前用户和角色状态。
- 登录后获取 /auth/me。
- 401 时清理本地状态并回到登录页。
- 暂不实现管理员用户管理页面和用户私有数据页面，那些属于后续阶段。

测试要求：

- 登录成功、错误密码、限流、禁用用户、会话过期、logout-all、修改密码后的旧会话失效。
- admin 可以访问管理依赖，user 不能访问。
- 不泄漏密码和 token。
- 如现有认证测试覆盖单管理员模式，必须保留并补充多用户测试。

完成后更新：

- .env.example 中的认证配置和注释。
- 与认证行为直接相关的 docs 文档。
- docs/CHANGELOG.md 的 [Unreleased] 扁平条目。

本阶段不要：

- 给现有业务表批量增加 user_id。
- 修改报告、行情、新闻和数据源业务逻辑。
- 添加公开注册、邮箱验证、OAuth、组织租户或支付。
- 修改桌面端登录流程，除非认证契约变化确实要求，并且同时补测试。

交付时输出：修改文件、数据库迁移方式、API 契约、测试结果、未验证项、风险、回滚命令和下一阶段前置条件。
```

## 阶段验收

- admin 和 user 可以独立建立会话。
- 禁用用户、改密、logout-all 能使旧会话失效。
- 当前用户身份由服务端会话提供。
- 现有单管理员兼容路径仍可用。
- 认证测试通过，未引入业务数据隔离改动。
