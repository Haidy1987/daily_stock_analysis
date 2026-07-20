# Cursor 提词 05c：性能、发布准备与最终验收

## 前置条件

阶段 00～05b 全部完成，所有指标、日/周/月线、Web 页面、跨页面入口和适用 Desktop 验证均有实际证据。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、全部技术图表规划、计算契约、进度表和阶段 00～05b 的交付记录。

本阶段目标：基于测量结果决定是否增加技术结果缓存，完成性能、后端/Web/Desktop/Docker 全量回归、文档、视觉证据和回滚验收。只有所有必达项通过后才能把总体进度更新为 100%。本阶段不部署服务器。

实施前：

1. 检查工作区状态，保留所有已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 汇总阶段 03 记录的 120/250 点未命中性能、阶段 04b 记录的 bundle 体积和阶段 05a 的周/月线耗时。
3. 不因“可能更快”增加缓存；只有测量结果超过已定目标时才实施。

缓存决策：

- 性能满足目标：记录“不新增结果缓存”，继续复用行情缓存。
- 性能不满足目标：优先复用项目现有缓存抽象，禁止新增数据库表或无边界全局字典。
- 如增加结果缓存，键必须包含 normalized stock_code、period、days、排序后的 indicators、calculation_version 和数据截止日期。
- 设置容量/TTL/失效规则；不同股票、周期和指标集合不能串数据。
- 缓存异常降级为重新计算，但不得把 source_unavailable 缓存成长期 empty。
- 增加命中、未命中、失效、隔离和 calculation_version 变化测试。

性能验收：

- 记录 daily/weekly/monthly 的 120/250 数据点耗时，区分缓存命中和未命中。
- 记录 Web build 产物和 ECharts 路由 chunk；确认首页初始 chunk 未无条件包含 ECharts。
- 检查技术图表页面快速切换股票、周期和指标时没有明显请求竞态、事件泄漏或持续增长的图表实例。
- 500 数据点只有在后端和前端测量通过后才开放；否则保持 250 上限并记录后续事项。

最终测试矩阵：

1. 后端
   - MA、MACD、RSI、BOLL、KDJ、CCI、BIAS、量价、支撑压力。
   - no-look-ahead、null、NaN/inf、预热、partial、empty、source_unavailable。
   - daily、weekly、monthly 和 60/120/250。
   - 旧 history、StockTrendAnalyzer、alerts KDJ/CCI、报告和 Agent 回归。

2. Web
   - 导航、路由、StockAutocomplete、URL、完整指标、日/周/月、主题、i18n、手机和错误状态。
   - 首页、选股、持仓、历史入口。
   - 普通用户、管理员和认证关闭模式。

3. 多端和构建
   - Web lint/test/build。
   - Desktop 适用 build 或明确平台缺口。
   - 如 package.json、lockfile、Docker 或依赖变化，执行仓库 CI 对应 Docker build 和关键模块 import smoke。
   - 不修改部署架构，不连接或更新生产服务器。

最低验证命令，按实际文件调整：

python -m py_compile <全部变更 Python 文件>
python -m pytest tests/test_technical_indicators.py tests/test_alert_worker.py tests/test_technical_chart_service.py tests/test_technical_chart_api.py -q
./scripts/ci_gate.sh

cd apps/dsa-web
npm ci
npm run lint
npm run test
npm run build

cd ../dsa-desktop
npm install
npm run build

如涉及 Docker，执行 `.github/workflows/ci.yml` 中最接近的构建与 import smoke，并记录准确命令和结果。

真实数据 smoke：

- 尽量覆盖 A 股、港股、美股各一个代码和日/周/月。
- 网络或数据源不可用时记录未验证项，不使用伪数据声称真实联调通过。
- 截图放在 PR 描述、评论或 Actions artifact，不提交一次性截图。

文档和回滚：

- 更新技术图表需求、计算契约、页面结构、导航、API 文档、部署/桌面说明和 docs/CHANGELOG.md。
- 评估英文文档；未同步需说明原因。
- 回滚方案至少包括：移除导航/路由、停用技术 API、恢复旧 history、回退共享计算适配、移除 ECharts 依赖和清理可选缓存。
- 不删除用户数据；本项目原则上不新增技术指标数据库表。

进度表：

- 只有所有必达指标、日/周/月、Web、适用 Desktop、测试、视觉证据和回滚说明通过后，才把 P4 标记完成、总体进度更新为 100%。
- 记录完成日期、准确命令、性能数据、bundle 数据、证据位置、未验证项和风险。
- 任一必达项缺失时保持进行中或部分完成，禁止只因 CI 通过标记 100%。

交付最终验收报告：改动文件、架构结果、完整指标矩阵、周期矩阵、测试和构建结果、性能、视觉证据、未验证项、风险、回滚方式。完成后停止，不执行 commit、push、tag 或服务器部署，除非用户另行明确授权。
```

## 阶段验收

- 缓存决策基于测量，并有隔离和失效测试。
- 全部指标、周期、页面、多端和旧功能回归通过。
- Web/Desktop/Docker 适用验证和视觉证据完整。
- 进度表有证据地更新为 100%，并具备可执行回滚方案。
