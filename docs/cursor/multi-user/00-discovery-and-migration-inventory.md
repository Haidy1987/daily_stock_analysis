# Cursor 提词 00：多用户盘点与迁移设计

## 使用方式

将本文件完整交给 Cursor。此阶段以只读分析和设计产物为主，不直接改造认证和业务代码。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。请先完整读取根目录 AGENTS.md，再执行本阶段任务。

目标：为多用户系统改造建立真实代码和数据库依据，输出可评审的数据归属清单、认证现状说明、迁移设计和风险清单。不要直接进入用户表、会话或业务隔离实现。

必须先检查：

1. 当前工作区状态，保留所有已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. src/auth.py、api/v1/endpoints/auth.py、api/middlewares/auth.py、api/deps.py 和启动入口。
3. 实际数据库初始化、连接、表结构、Repository 和事务管理代码。不要假设项目一定使用 Alembic 或某个 ORM。
4. src/repositories/、api/v1/endpoints/、api/v1/schemas/ 和 apps/dsa-web/src/ 中的用户私有数据入口。
5. analysis、history、stocks/watchlist、portfolio、alerts、decision_signals、agent/chat、usage 相关的表、字段和调用链。
6. docker/docker-compose.yml、.env.example、部署文档和桌面端启动链路。

输出以下内容：

- 当前认证链路：登录、密码存储、Cookie/session、认证开关、认证豁免路径。
- 当前数据库技术和迁移方式：初始化入口、数据库文件、表清单、索引、备份方式。
- 数据归属表：每张表标记 public、user-owned、admin-only 或需要进一步确认，并说明依据。
- 现有 owner_id/user_id/platform user_id 的实际含义和兼容风险。
- 需要新增的 users、user_sessions、user_preferences、audit_logs 字段建议。
- 每张 user-owned 表增加 user_id 的迁移策略，包括旧数据归属、默认管理员归属和不可自动判断的数据。
- API、后台任务、流式任务、报告文件和通知链路中需要传递用户上下文的位置。
- SQLite 锁、WAL、备份、Docker volume 和回滚风险。
- 阶段 1 至阶段 4 的前置条件、阻塞项和建议顺序。

设计约束：

- 第一阶段只支持 admin/user 两种角色。
- 第一阶段关闭开放注册，由管理员创建用户。
- 推荐继续使用 HttpOnly Cookie；如建议改为服务端 Session，必须说明与现有 dsa_session 的兼容方案。
- user_id 必须来自服务端认证上下文，不能信任请求体或查询参数。
- 公共行情、新闻缓存、股票基础数据和系统配置不能误加用户隔离。
- 不要为了“完整”新增组织租户、支付、OAuth 或用户自定义 AI Key。

产物要求：

- 优先输出到 docs/plans/multi-user-data-inventory.md；如果用户已有同名文件，先更新而不是覆盖无关内容。
- 文档必须包含源码路径、表名、字段名、验证命令和不确定项。
- 如果无法确认某张表或调用链，明确标记“待确认”，禁止猜测。
- 只运行与盘点有关的安全、只读检查；不要启动迁移、删除数据或重建数据库。

完成后停止，等待用户审阅盘点和迁移设计，再执行认证核心阶段。
```

## 阶段验收

- 已形成表级数据归属清单。
- 已明确旧管理员凭据如何迁移为初始管理员用户。
- 已识别所有会产生用户私有数据的 API、Repository 和后台任务。
- 没有执行破坏性数据库操作。
