# Cursor 提词文档

本目录用于存放可直接交给 Cursor 执行的工程提词。总体规划仍以 `docs/plans/` 中的专题文档为准，本目录只负责把规划拆解为可执行阶段。

## 多用户系统

| 顺序 | 提词 | 目标 |
| --- | --- | --- |
| 0 | [盘点与迁移设计](multi-user/00-discovery-and-migration-inventory.md) | 识别现有数据库、认证、业务数据和迁移边界 |
| 1 | [认证核心](multi-user/01-auth-core.md) | 建立用户、会话、角色和审计基础 |
| 2 | [用户数据隔离](multi-user/02-data-isolation.md) | 为用户私有业务接入 `user_id` 并防止越权 |
| 3 | [管理员后台与 Web](multi-user/03-admin-web.md) | 提供用户管理和个人账户页面 |
| 4 | [测试、部署与切换](multi-user/04-testing-cutover.md) | 完成回归测试、文档、备份和灰度上线 |

必须按顺序执行。第 0 阶段没有形成数据归属清单和迁移方案时，不得直接修改业务表或认证链路。

## 技术指标图表

| 顺序 | 提词 | 目标 |
| --- | --- | --- |
| 0 | [口径冻结与契约设计](technical-chart/00-contract-and-baseline.md) | 固定完整指标公式、API 契约、空值和预热规则 |
| 1 | [核心指标引擎](technical-chart/01-core-indicator-engine.md) | 建立 MA、MACD、RSI、BIAS 和量价时间序列引擎 |
| 2 | [完整指标与支撑压力](technical-chart/02-full-indicators-and-levels.md) | 补齐 BOLL、KDJ、CCI、支撑压力并完成计算层回归 |
| 3 | [技术图表 API](technical-chart/03-technical-chart-api.md) | 提供完整日线指标接口、状态语义和缓存边界 |
| 4a | [页面骨架与股票上下文](technical-chart/04a-page-shell-and-stock-context.md) | 实现路由、导航、API client、股票选择和页面状态 |
| 4b | [K 线、BOLL 与成交量](technical-chart/04b-price-volume-chart.md) | 固定 ECharts 方案并完成价格主图和成交量副图 |
| 4c | [完整指标副图](technical-chart/04c-indicator-panels.md) | 完成 MACD、RSI、KDJ、CCI、BIAS 和联动交互 |
| 4d | [响应式、国际化与 Web 验收](technical-chart/04d-responsive-i18n-tests.md) | 完成移动端、主题、i18n、可访问性、测试和截图 |
| 5a | [周线与月线](technical-chart/05a-weekly-monthly-aggregation.md) | 实现后端周期聚合及完整指标重新计算 |
| 5b | [跨页面与多端联动](technical-chart/05b-cross-page-and-multi-end.md) | 开放周期切换并联动首页、选股、持仓和 Desktop |
| 5c | [性能、发布与最终验收](technical-chart/05c-performance-release-acceptance.md) | 完成缓存决策、全量回归、Docker、证据和回滚验收 |

技术图表提词必须按顺序执行。BOLL、KDJ、CCI、BIAS 属于本期必达范围；拆分阶段只表示执行顺序，不代表可以取消或延期。

## 通用执行约束

将本目录任一提词交给 Cursor 时，同时要求它：

- 先读取根目录 `AGENTS.md`，遵循仓库现有目录边界和验证矩阵。
- 先检查工作区状态，保留用户已有改动，不覆盖、不重置、不自动提交。
- 先阅读实际代码、测试、配置和文档，再实现；不得根据文件名猜测不存在的 ORM、迁移框架或 API。
- 不写入任何真实密钥、密码、Token、服务器地址或个人路径。
- 不执行 `git commit`、`git push`、`git tag`，除非用户另行明确授权。
- 改动配置、API、Web、部署或用户可见行为时同步更新 `.env.example`、相关专题文档和 `docs/CHANGELOG.md`。
- 每个阶段只完成当前阶段范围；发现跨阶段问题时记录阻塞项，不顺手扩展功能。
- 交付时说明改动、原因、验证、未验证项、风险和回滚方式。

## 阶段交接规则

每个阶段完成后，Cursor 必须输出：

1. 实际修改文件清单。
2. 数据库或 API 契约变化。
3. 已执行的测试和结果。
4. 未解决问题和下一阶段前置条件。
5. 回滚方式。

上一阶段的验收未通过时，停止后续阶段，不要使用静默 fallback 或 mock 绕过真实风险路径。
