# Cursor 提词 02：完整指标与支撑压力

## 前置条件

阶段 01 已完成，核心指标引擎测试通过，P1 在进度表中处于“进行中”。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、计算契约、技术图表规划、进度表、阶段 01 交付记录和共享指标模块。

本阶段目标：在同一计算引擎中补齐 BOLL、KDJ、CCI 和支撑压力，完成全部指标的计算层验收，并将 P1 标记为完成。不要实现 API 或前端。

实施前：

1. 检查工作区状态，保留用户改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 复查阶段 01 的输入标准化、空值处理和列命名，新增指标必须复用这些基础能力。
3. 必须阅读 src/services/alert_indicators.py 中现有 `_evaluate_kdj`、`_evaluate_cci` 及 tests/test_alert_worker.py。KDJ/CCI 已存在告警计算，禁止忽略后重新创建平行公式；同时搜索 report、agent 或其他模块中的指标实现并记录差异。

必须实现：

1. BOLL
   - 中轨为 MA20。
   - 标准差和倍数严格使用计算契约，默认 period=20、std=2、ddof=0。
   - 输出 boll_upper、boll_mid、boll_lower、boll_bandwidth、boll_position。
   - bandwidth 分母为 0、upper==lower 或窗口不足时按契约输出 null。
   - 不重复计算与 MA20 不同口径的中轨。

2. KDJ
   - 9 周期最高/最低计算 RSV。
   - K、D 初始值 50，按 3/3 平滑递推，J=3K-2D。
   - high==low 时使用契约规定的中性 RSV 或 null 处理，不允许出现 inf。
   - 明确 K/D/J 是否限制在 0～100；按契约实现，不自行裁剪。
   - 把 KDJ 序列公式抽取到共享计算层，让 alert_indicators 的边缘穿越判断消费共享 K/D 序列；保留告警方向、消息和状态语义。

3. CCI
   - typical price=(high+low+close)/3。
   - 周期 14，常数 0.015。
   - 平均偏差为 0 或窗口不足时输出 null。
   - 输出有限数值，不允许 inf。
   - 把 CCI 序列公式抽取到共享计算层，让 alert_indicators 的阈值穿越判断消费共享 CCI 序列；不得在告警和图表各保留一套 rolling 公式。

4. 支撑压力与近期高低点
   - 第一版 summary 以请求结束日为基准，不要求给每个历史点生成交易信号。
   - 候选至少覆盖 MA5/10/20、近期 20 根 K 线低点和高点。
   - 每个 level 包含 price、label、source，能确定时附 date。
   - 按契约执行相近价格去重和排序。
   - 所有计算只允许使用结束日及以前数据；测试必须包含截断数据集，证明增加未来 K 线不会改变过去时点结果。

5. 完整序列输出
   - 单次调用能输出 OHLCV、MA、MACD、RSI、BOLL、KDJ、CCI、BIAS、量比和量价状态。
   - 指标列名、类型和 null 规则与计算契约一致。
   - 允许调用方按 indicators 集合选择计算内容，但默认完整指标集；不要让选择逻辑造成依赖缺失，例如 BIAS 仍需 MA。

测试要求：

- 扩展 tests/test_technical_indicators.py，或按模块拆分 BOLL/KDJ/CCI/levels 测试。
- 运行并补充 tests/test_alert_worker.py，证明 KDJ/CCI 告警在重构后仍保持原边缘穿越和错误语义。
- 为每个指标提供可人工复算的小样本或可信固定结果，不使用“结果不是空”作为唯一断言。
- 覆盖窗口不足、常量价格、high==low、缺失 volume、NaN、极端值和非有限值。
- 支撑压力测试覆盖 no-look-ahead、相近水平位去重、近期高低点日期。
- 完整调用测试断言所有必达列存在，并验证日期和原始 OHLCV 未错位。
- 运行阶段 01 和受影响 StockTrendAnalyzer 测试，避免新增指标破坏核心口径。

建议验证命令：

python -m py_compile src/services/technical_indicators.py src/stock_analyzer.py
python -m pytest tests/test_technical_indicators.py tests/test_stock_analyzer_rsi.py tests/test_alert_worker.py -q
./scripts/ci_gate.sh

如果 ci_gate 因与本任务无关的既有问题失败，记录准确命令、失败项和证据，不要篡改无关代码绕过门禁。

文档和进度：

- 更新计算契约中的最终实现路径、字段名和测试锚点。
- 更新 docs/CHANGELOG.md。
- 更新 technical-chart-implementation-progress.html：只有全部指标测试通过后才把 P1 标记为已完成；记录完成日期、测试结果、风险和下一节点 P2 API。

本阶段不要：

- 新增 FastAPI endpoint 或 Schema。
- 修改 Web 依赖、页面、导航或图表组件。
- 引入 TA-Lib 等需要系统级原生依赖的库；优先使用现有 pandas/numpy，避免 Docker 和桌面端打包复杂化。
- 增加用户指标模板、回测、交易信号或数据库表。

交付时输出：改动文件、全部指标状态、固定公式、测试结果、兼容风险、未验证项和回滚方式。完成后停止。
```

## 阶段验收

- BOLL、KDJ、CCI、BIAS 和核心指标均已形成可靠序列。
- 支撑压力无未来数据泄漏。
- 完整指标测试和既有回归通过。
- P1 已按证据更新为完成，尚未修改 API 或 Web。
