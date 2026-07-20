# 技术指标图表 Cursor 提词

本目录把技术图表改造拆成 11 个可独立执行和验收的步骤。总体需求、页面结构、后端差距和进度基线分别见：

- [技术指标图表第一版需求](../../plans/technical-chart-v1-requirements.md)
- [技术图表页面导航入口规划](../../plans/technical-chart-navigation-plan.md)
- [技术图表页面结构设计](../../plans/technical-chart-page-structure-design.md)
- [技术图表后端能力评估与补全计划](../../plans/technical-chart-backend-gap-analysis.md)
- [技术图表改造进度表](../../plans/technical-chart-implementation-progress.html)

## 执行顺序

| 步骤 | 文件 | 对应进度阶段 | 完成结果 |
| --- | --- | --- | --- |
| 00 | [口径冻结与契约设计](00-contract-and-baseline.md) | P0 | 指标公式、字段和边界完成评审 |
| 01 | [核心指标引擎](01-core-indicator-engine.md) | P1 进行中 | 核心指标形成可复用时间序列 |
| 02 | [完整指标与支撑压力](02-full-indicators-and-levels.md) | P1 完成 | 全部指标计算和回归测试完成 |
| 03 | [技术图表 API](03-technical-chart-api.md) | P2 | 日线完整指标接口可联调 |
| 04a | [页面骨架与股票上下文](04a-page-shell-and-stock-context.md) | P3 进行中 | 路由、导航、API client 和页面状态可用 |
| 04b | [K 线、BOLL 与成交量](04b-price-volume-chart.md) | P3 进行中 | 价格主图和成交量副图可用 |
| 04c | [完整指标副图](04c-indicator-panels.md) | P3 进行中 | MACD、RSI、KDJ、CCI、BIAS 可用 |
| 04d | [响应式、国际化与 Web 验收](04d-responsive-i18n-tests.md) | P3 完成 | Web、手机浏览器和主题验收完成 |
| 05a | [周线与月线](05a-weekly-monthly-aggregation.md) | P4 进行中 | 后端日/周/月线完整指标接口可用 |
| 05b | [跨页面与多端联动](05b-cross-page-and-multi-end.md) | P4 进行中 | 页面周期和 Web/Desktop 入口联动完成 |
| 05c | [性能、发布与最终验收](05c-performance-release-acceptance.md) | P4 完成 | 性能、全量回归、Docker 和回滚验收完成 |

## 执行规则

- 每次只把一份提词完整交给 Cursor。
- 当前步骤未通过验收时，不执行下一份提词。
- 每个步骤开始前读取 `AGENTS.md`、本 README、相关规划和上一步交付记录。
- 每个步骤完成后更新 `technical-chart-implementation-progress.html`，记录状态、日期、验证结果、风险和下一节点。
- 不执行 `git commit`、`git push`、`git tag`，除非用户另行明确授权。
- 不覆盖工作区中的多用户改造或其他已有修改。
- 不把真实 API Key、Cookie、数据库、服务器地址或临时截图提交到仓库。

## 进度回填刻度

以下百分比只用于里程碑记录，不代表工作量线性分布：

| 步骤完成后 | 总体进度 |
| --- | --- |
| 00 | 20% |
| 01 | 30%，P1 仍进行中 |
| 02 | 40%，P1 完成 |
| 03 | 60%，P2 完成 |
| 04a | 65% |
| 04b | 70% |
| 04c | 75% |
| 04d | 80%，P3 完成 |
| 05a | 87% |
| 05b | 94% |
| 05c | 100%，P4 完成 |

## 完成定义

技术图表项目只有在步骤 00～05c 全部通过后才算完成。所有指标均需具备后端计算、API 字段、前端展示、空值处理和固定样本测试：

- K 线 OHLCV
- MA5、MA10、MA20
- MACD DIF、DEA、柱
- RSI6、RSI12、RSI24
- BOLL 上轨、中轨、下轨、带宽、价格位置
- KDJ K、D、J
- CCI
- BIAS5、BIAS10、BIAS20
- 量比、放量/缩量和量价状态
- 支撑位、压力位、近期高点、近期低点

## 生产故障恢复（2026-07）

- 动态路由 chunk 404：全站 lazy 路由带一次 session 内自动刷新；RouteErrorBoundary 区分 chunk/render/unknown 并提供脱敏复制信息。
- ECharts 渲染失败：仅图表区域降级，股票摘要与数据说明继续可用，可点击「重新渲染图表」。
- 主题色：Canvas 使用 Safari 兼容的 legacy HSL/RGB 格式，避免 CSS Color 4 空格语法。
