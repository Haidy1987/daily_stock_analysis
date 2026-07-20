# Cursor 提词 01：核心技术指标时间序列引擎

## 前置条件

必须完成并评审[阶段 00：口径冻结与契约设计](00-contract-and-baseline.md)，且 `technical-chart-calculation-contract.md` 已明确公式、空值和兼容规则。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、docs/plans/technical-chart-calculation-contract.md、技术图表相关规划、进度表和阶段 00 交付记录。

本阶段目标：建立可复用的技术指标时间序列计算基础，完成数据标准化、MA、MACD、RSI、BIAS、量比和量价状态。暂不实现 API、前端、BOLL、KDJ、CCI 和完整支撑压力；这些属于下一阶段。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 复核 src/stock_analyzer.py 中 _calculate_mas、_calculate_macd、_calculate_rsi、_calculate_bias、_analyze_volume 的调用方和测试。
3. 核对 DataFetcherManager 返回 DataFrame 的真实字段、排序、索引、NaN、0 值和日期类型。
4. 优先抽取共享逻辑，不在 API、报告和前端各维护一套公式。

建议实现边界：

- 新建或按现有服务层规范命名一个纯计算模块，例如 src/services/technical_indicators.py。
- 输入为标准化、日期升序的 pandas DataFrame；不得在计算函数内部重新访问网络或数据库。
- 输出为新的 DataFrame 或明确的数据对象，保留原始 OHLCV，并追加指标列。
- 计算函数应尽量无副作用，不修改调用方传入的 DataFrame。
- 将列名到 API 字段的 snake_case 映射集中管理，避免散落字符串。

建议公开接口，若实际项目结构需要调整必须在交付中说明：

- `normalize_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame`：只负责字段、排序、重复日期和非有限值标准化。
- `calculate_technical_indicators(df: pd.DataFrame, indicators: Optional[Set[str]] = None) -> pd.DataFrame`：返回原始 OHLCV 加请求指标列，不访问网络和数据库。
- `build_support_resistance_summary(df: pd.DataFrame) -> Dict[str, Any]`：由阶段 02 实现，阶段 01 仅预留边界。
- 公式级辅助函数可保持私有；API/报告/告警不得直接依赖内部 rolling 临时列。

本阶段必须实现：

1. 输入标准化
   - 校验 date/open/high/low/close。
   - volume/amount/change_percent 可以为空。
   - 按日期升序、去除或明确处理重复日期。
   - 非有限数值转为缺失值；不要把缺失价格静默变为 0。

2. MA
   - MA5、MA10、MA20。
   - 使用完整 rolling window，min_periods 等于周期。
   - 窗口不足输出 null/NaN，序列化时转 null。

3. MACD
   - EMA12、EMA26、DEA9，adjust=False。
   - DIF、DEA、BAR=(DIF-DEA)*2。
   - 按阶段 00 契约固定预热和首个可展示点。

4. RSI
   - RSI6、RSI12、RSI24，使用 Wilder EMA/SMMA。
   - 图表序列在有效窗口前输出 null，不用 50 填充。
   - 处理全涨、全跌、无涨跌和分母为 0。
   - 不直接破坏现有报告行为；通过共享底层函数和兼容适配层保持已有测试，或者按契约同步调整并说明影响。

5. BIAS
   - BIAS5、BIAS10、BIAS20。
   - 复用对应 MA 序列，不重复计算不同口径均线。
   - MA 为 0 或为空时输出 null。

6. 量比与量价状态
   - volume_ratio 使用前 5 根完整 K 线平均量，不包含当前 K 线。
   - 分母为空或 0 时输出 null。
   - 量比 <=0.7 为缩量，>=1.5 为放量，其余正常；阈值从单一常量来源读取。
   - 根据当前 close 与前一 close 形成量价枚举；枚举和值保持稳定，显示文案留给报告或前端。

兼容集成：

- 让 StockTrendAnalyzer 的 MA、MACD、RSI、BIAS、量比尽量消费共享计算结果。
- TrendAnalysisResult 仍只保留报告需要的最新值和状态，不把完整序列塞进报告对象。
- 不改变报告评分、买卖建议、Prompt 或通知结构，除非共享口径修复确实导致差异；出现差异必须记录并补回归测试。
- 不增加 BOLL、KDJ、CCI、API、前端或数据库修改。

测试要求：

- 新增 tests/test_technical_indicators.py 或符合项目规范的等价测试文件。
- 固定样本覆盖 MA、MACD、RSI、BIAS、量比和量价状态。
- 覆盖数据不足、空 DataFrame、缺失列、重复日期、NaN、volume=0、close 不变、全涨和全跌。
- MACD 和 RSI 与现有 StockTrendAnalyzer 固定样本保持一致。
- 至少保留并运行 tests/test_stock_analyzer_rsi.py 等受影响现有测试。
- 测试必须验证真实计算函数，不得 mock 掉计算层。

建议验证命令，按实际文件名调整：

python -m py_compile src/services/technical_indicators.py src/stock_analyzer.py
python -m pytest tests/test_technical_indicators.py tests/test_stock_analyzer_rsi.py -q

如改动影响面较大，再执行：

./scripts/ci_gate.sh

文档和进度：

- 更新计算契约中最终采用的函数/字段名。
- 更新 docs/CHANGELOG.md [Unreleased] 扁平条目。
- 更新 technical-chart-implementation-progress.html：P1 标记为进行中，记录已完成核心指标、测试结果和阶段 02 前置条件；不得提前将 P1 标记为完成。

交付时输出：改动文件、计算口径、兼容方式、测试命令和结果、未验证项、风险、回滚方式。完成后停止，不执行阶段 02。
```

## 阶段验收

- 核心指标形成按日期输出的共享时间序列。
- 数据不足使用 null，不生成伪造的 0 或 50 曲线。
- StockTrendAnalyzer 兼容路径和已有测试仍成立。
- P1 只标记为进行中，未越界实现 API 或前端。
