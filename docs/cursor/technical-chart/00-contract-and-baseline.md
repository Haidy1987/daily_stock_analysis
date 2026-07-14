# Cursor 提词 00：技术指标口径冻结与契约设计

## 使用方式

将本文件完整交给 Cursor。本阶段以只读盘点和设计收敛为主，不实现指标计算、API 或页面。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。请先完整读取根目录 AGENTS.md，再读取：

- docs/plans/technical-chart-v1-requirements.md
- docs/plans/technical-chart-page-structure-design.md
- docs/plans/technical-chart-backend-gap-analysis.md
- docs/plans/technical-chart-implementation-progress.html
- docs/cursor/technical-chart/README.md

本阶段目标：基于真实代码冻结技术图表的完整指标口径、输入输出契约、预热窗口、错误状态和兼容边界。不要进入业务代码实现。

实施前必须：

1. 检查工作区状态，保留所有已有改动；不执行 reset、checkout、stash、commit、push 或 tag。
2. 阅读 api/v1/endpoints/stocks.py、api/v1/schemas/stocks.py、src/services/stock_service.py、src/stock_analyzer.py、data_provider/base.py 及相关测试。
3. 核对现有 history 接口、StockTrendAnalyzer、日线数据字段、数据排序、缺失值和异常 fallback 的真实行为。
4. 确认 weekly/monthly 虽在 API 枚举中出现但服务层当前是否实际支持，禁止只根据文档判断。
5. 搜索是否已有 BOLL、KDJ、CCI、BIAS 或通用技术指标模块，避免创建平行实现。

必须形成并冻结以下口径：

- 输入数据：date、open、high、low、close、volume、amount、change_percent；日期升序；数值清洗和重复日期处理。
- MA：SMA 5/10/20，完整窗口不足时返回 null。
- MACD：EMA12、EMA26、DEA9，adjust=False；柱值沿用 (DIF - DEA) * 2。
- RSI：6/12/24，Wilder EMA / SMMA；明确首个有效点和现有 fillna(50) 的兼容处理。图表不得用 50 伪造数据不足区间。
- BOLL：周期 20、标准差倍数 2、ddof=0；bandwidth=(upper-lower)/mid*100；position=(close-lower)/(upper-lower)*100，不裁剪到 0～100；分母为 0 时返回 null。
- KDJ：RSV 9、K/D 平滑 3/3；K、D 初始值 50；high==low 时的除零处理；J=3K-2D。
- CCI：周期 14；typical price=(high+low+close)/3；常数 0.015；平均偏差为 0 时返回 null。
- BIAS：基于 MA5/10/20，公式 (close-MA)/MA*100；MA 为 0 或不足时返回 null。
- 量比：当前量 / 前 5 根完整 K 线平均量，明确不把当前量放入分母；0.7/1.5 阈值沿用现有约定。
- 量价状态：上涨/下跌与放量/缩量组合的枚举值和显示文案分离。
- 支撑压力：默认最近 20 根聚合后 K 线；当前 close 以下的有效 MA5/10/20 和近期低点作为支撑候选，当前 close 以上的有效 MA5/10/20 和近期高点作为压力候选；相对价差不超过 0.5% 的水平位合并并保留来源；recent_high/recent_low 返回价格和实际日期；只使用请求结束日前的数据，禁止 look-ahead bias。
- 周线/月线：先冻结聚合口径，后续阶段实现。OHLC 取首/最高/最低/末，volume/amount 求和，日期取该周期最后一个交易日，指标在聚合后的 K 线上重新计算。

必须设计新的独立契约：

GET /api/v1/stocks/{stock_code}/technical-chart

查询参数至少包含：period、days、indicators。第一阶段只开放 daily；days 默认 120，首版允许 60～250，最终扩展到 500；indicators 支持 ma、volume、macd、rsi、boll、kdj、cci、bias、support_resistance。

响应必须包含：

- stock_code、stock_name、period、range_days。
- calculation_version，初始建议 technical-v1。
- data_status：available、partial、empty、source_unavailable。
- data_source、updated_at 等低敏元数据；不得暴露内部密钥或异常堆栈。
- items：按日期升序的 OHLCV 和完整指标字段。
- summary：最新价、涨跌、量价状态、支撑压力、近期高低点。
- warnings：数据不足、降级、部分字段缺失等可展示提示。

错误语义必须区分：

- 股票代码格式错误或参数非法：400/422。
- 合法请求但没有历史记录：返回 HTTP 200、data_status=empty、items=[] 和可展示 warning。
- 所有数据源不可用：503 或项目统一的 upstream unavailable 错误，不能伪装为空数组。
- 部分指标无法计算：200 + partial + null 字段和 warnings。

兼容约束：

- 不修改现有 GET /stocks/{stock_code}/history 的响应结构。
- 不在前端计算技术指标。
- 不为技术指标新增数据库表，第一版优先复用行情缓存和按请求计算。
- 公共行情和指标不绑定 user_id；全局认证仍沿用现有 AuthContext/中间件。
- 抽取共享指标引擎时，不能破坏报告分析现有 TrendAnalysisResult 语义；如语义冲突，设计兼容适配层并记录测试要求。

产物要求：

1. 新增 docs/plans/technical-chart-calculation-contract.md，包含公式、参数、首个有效点、null/除零规则、字段类型、示例响应和兼容风险。
2. 在该文档中列出建议新增/修改的源码文件和测试文件，但本阶段不要创建业务代码。
3. 更新 docs/plans/technical-chart-implementation-progress.html：P0 标记为已完成或明确阻塞；记录完成日期、验证证据和下一节点。不要把尚未完成的代码阶段标记为完成。
4. 更新 docs/INDEX.md 和 docs/CHANGELOG.md 的 [Unreleased] 扁平条目。

验证：

- 核对所有文档中的指标列表、字段名、周期支持和阶段范围没有互相矛盾。
- 执行 git diff --check。
- Docs only, tests not run；交付中说明未运行代码测试的原因。

完成后停止，等待用户评审计算契约，不要继续实现 P1。
```

## 阶段验收

- 全部指标的公式、参数和空值规则已固定。
- API 请求、响应、状态和错误语义已固定。
- 已明确现有报告计算的兼容策略。
- P0 进度已回填，且没有修改业务代码。
