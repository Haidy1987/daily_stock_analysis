# 文档中心

这里是项目文档入口。README 负责项目概览和快速开始；更完整的配置、部署、功能说明和排障内容从这里进入。

## 按场景选择

| 我想要 | 先看 | 继续看 |
| --- | --- | --- |
| 快速了解项目能做什么 | [README](../README.md) | [完整配置与部署指南](full-guide.md) |
| 第一次把项目跑起来 | [小白客户端安装与配置](beginner-client-setup.md) | [完整配置与部署指南](full-guide.md) |
| 配置大模型渠道 | [LLM 配置指南](LLM_CONFIG_GUIDE.md) | [LLM 服务商配置指南](llm-providers.md) |
| 配置推送通知 | [通知能力基线](notifications.md) | [完整配置与部署指南](full-guide.md) |
| 部署到服务器或云平台 | [部署指南](DEPLOY.md) | [云端 WebUI 部署](deploy-webui-cloud.md)、[Zeabur 部署](docker/zeabur-deployment.md) |
| 使用 Bot / IM 接入 | [Bot 命令与接入](bot-command.md) | [Bot 平台配置](bot/) |
| 排查运行问题 | [FAQ](FAQ.md) | [更新日志](CHANGELOG.md) |
| 处理数据源失败或降级 | [数据源稳定性与故障处理图示](data-source-stability.md) | [FAQ](FAQ.md) |
| 参与开发或提交 PR | [贡献指南](CONTRIBUTING.md) | [固定开发与交付流程](development-workflow.md)、[API 规格](architecture/api_spec.json) |

## 快速开始

| 文档 | 内容 |
| --- | --- |
| [README](../README.md) | 项目定位、核心能力、快速开始、推送效果 |
| [小白客户端安装与配置](beginner-client-setup.md) | 面向不会代码用户的客户端下载、Anspire Open / AIHubMix 模型配置、新闻源配置和常见问题 |
| [完整配置与部署指南](full-guide.md) | 环境准备、运行方式、配置说明、部署路径和常见问题 |
| [FAQ](FAQ.md) | 常见配置、模型、通知、部署和运行问题 |
| [数据源稳定性与故障处理图示](data-source-stability.md) | Tushare、TickFlow、AkShare、Efinance、YFinance、Longbridge 等已接入源的使用场景、fallback 链路和推荐配置 |
| [更新日志](CHANGELOG.md) | 版本变化、能力调整和迁移说明 |

## 配置

| 文档 | 内容 |
| --- | --- |
| [LLM 配置指南](LLM_CONFIG_GUIDE.md) | 大模型渠道、三层配置、Web 设置页和常见模型配置 |
| [LLM 服务商配置指南](llm-providers.md) | Provider 预设、Actions 映射、错误分类和诊断建议 |
| [LiteLLM YAML 示例](examples/litellm_config.example.yaml) | LiteLLM 多渠道配置示例 |
| [通知能力基线](notifications.md) | 企业微信、飞书、Telegram、Discord、Slack、邮件等通知渠道配置 |
| [Tushare 股票列表指南](TUSHARE_STOCK_LIST_GUIDE.md) | Tushare 股票列表相关配置和使用说明 |
| [A 股全量主数据同步](a-share-universe-sync.md) | A 股全量主数据/快照表结构、配置项与分阶段计划 |

## 使用专题

| 文档 | 内容 |
| --- | --- |
| [Bot 命令与接入](bot-command.md) | Bot 命令、Webhook、平台接入和回调说明 |
| [Bot 平台配置](bot/) | 飞书、钉钉、Discord 等 Bot 配置截图和补充说明 |
| [实时告警中心](alerts.md) | EventMonitor 基线、Web 规则管理、通知结果、冷却状态和 Phase 边界 |
| [DecisionSignal 决策信号专题](decision-signals.md) | AI 建议池字段语义、API、Web 展示、告警/通知/组合风险联动、后验评估、脱敏、迁移与回滚 |
| [资讯 / 情报源](intelligence-sources.md) | RSS/Atom 合规资讯源配置、测试、拉取、去重、存储、查询与安全边界 |
| [分析上下文包契约、运行态消费与可见性](analysis-context-pack.md) | AnalysisContextPack 首版范围、字段质量状态、P1/P2 内部契约、P3 Prompt 摘要消费、P4 历史/API/Web 低敏可见性、P5 数据质量评分、P6 迁移回滚与源码锚点；完整指南补充 #1386 阶段感知分析、迁移与回滚入口 |
| [图片识别 Prompt](image-extract-prompt.md) | 图片识别股票信息的 Prompt 与使用边界 |
| [OpenClaw Skill 集成](openclaw-skill-integration.md) | OpenClaw / Skill 外部集成说明 |

## 部署与打包

| 文档 | 内容 |
| --- | --- |
| [部署指南](DEPLOY.md) | 服务器部署、Docker、systemd、Supervisor 等部署方式 |
| [云端 WebUI 部署](deploy-webui-cloud.md) | 云服务器访问 WebUI 的部署说明 |
| [Zeabur 部署](docker/zeabur-deployment.md) | Zeabur 平台部署说明 |
| [桌面端打包说明](desktop-package.md) | Electron 桌面端和 Web 构建产物打包说明 |

## 参考与开发

| 文档 | 内容 |
| --- | --- |
| [API 规格](architecture/api_spec.json) | FastAPI OpenAPI 规格产物 |
| [贡献指南](CONTRIBUTING.md) | Issue、PR、测试、文档同步和协作要求 |
| [固定开发与交付流程](development-workflow.md) | 从接任务、影响面判断、实现、验证、PR 到发布和回滚的统一 SOP |
| [项目瘦身规划](plans/project-slimming-plan.md) | 仓库资源、前端依赖、Python 依赖、代码复杂度和 Git 历史的分阶段瘦身方案 |
| [多用户系统改造规划](plans/multi-user-system-plan.md) | 用户认证、角色权限、数据隔离、数据库迁移、部署和回滚方案 |
| [多用户数据归属清单](plans/multi-user-data-inventory.md) | 阶段 0 盘点：认证现状、28 表归属、伪 user_id 语义、迁移策略与阶段前置条件 |
| [多用户数据隔离迁移说明](plans/multi-user-isolation-migration.md) | 阶段 2：user_id 回填、自选股表、备份校验与回滚 |
| [多用户切换与验收说明](plans/multi-user-cutover.md) | 阶段 4：AUTH_MODE 切换、备份恢复、Docker 要点与验收矩阵 |
| [技术指标图表第一版需求](plans/technical-chart-v1-requirements.md) | K 线、均线、成交量、MACD、RSI、支撑压力图表的第一版需求与验收范围 |
| [技术图表页面导航入口规划](plans/technical-chart-navigation-plan.md) | 技术图表一级导航、路由、股票上下文、权限边界和实施拆分 |
| [技术图表页面结构设计](plans/technical-chart-page-structure-design.md) | 页面骨架、股票上下文、主图/副图布局、响应式结构和页面状态 |
| [技术图表后端能力评估与补全计划](plans/technical-chart-backend-gap-analysis.md) | 当前 API、指标实现、周期能力差距及后端 P0/P1/P2 补全任务 |
| [技术图表计算与 API 契约](plans/technical-chart-calculation-contract.md) | technical-v1 指标公式、空值规则、API 字段、错误语义与兼容边界（P0 冻结） |
| [技术图表改造进度表](plans/technical-chart-implementation-progress.html) | 技术图表改造起点、阶段任务、指标清单、状态和验收记录 |
| [Cursor 提词文档](cursor/README.md) | 多用户系统与技术指标图表按阶段拆分的 Cursor 执行提词、前置条件、验收标准和交接规则 |

## 多语言

| 文档 | 内容 |
| --- | --- |
| [英文文档索引](INDEX_EN.md) | English documentation index |
| [英文 README](README_EN.md) | English project overview and quick start |
| [繁中 README](README_CHT.md) | 繁體中文項目概覽與快速開始 |
