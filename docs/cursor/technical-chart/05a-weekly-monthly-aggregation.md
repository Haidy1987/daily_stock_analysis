# Cursor 提词 05a：周线与月线聚合

## 前置条件

P3 已完成，daily 完整指标 API 和页面经过验收。计算契约已经固定周线/月线聚合口径。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、计算契约、阶段 03 API、P3 交付记录和现有 StockService/DataFetcherManager。

本阶段目标：只在后端实现 weekly/monthly K 线聚合、完整指标重新计算和 API 支持。不要修改 Web 页面、跨页面入口、Desktop 或缓存策略。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 核对不同市场日线日期、时区、复权和字段标准化，避免跨周/月错误分组。
3. 确认现有 `/history` 的 weekly/monthly 契约漂移；技术图表 API 与旧 history 的修复范围必须分别说明。

必须实现：

1. 聚合函数
   - 在服务层或共享行情处理模块实现纯 DataFrame 聚合，不访问前端。
   - weekly 按计算契约的交易周分组，date 取该周最后一个实际交易日。
   - monthly date 取该月最后一个实际交易日。
   - open=首根，high=max，low=min，close=末根。
   - volume/amount 对有效值求和；全部缺失时保持 null。
   - change_percent 基于前一聚合周期 close 重新计算。
   - 输出日期升序，不生成没有实际交易的周期。

2. 指标计算顺序
   - 先聚合 OHLCV，再调用共享指标引擎。
   - 禁止对日线 MA、MACD、RSI、BOLL、KDJ、CCI、BIAS 做平均或抽样。
   - 支撑压力和近期高低点基于聚合后的 K 线重新计算。

3. 取数和预热
   - 为返回 60/120/250 根周/月线读取足够日线历史。
   - 如果数据源最大历史范围不足，返回 partial 和明确 warning，不能重复日线或伪造周期。
   - 预热数据不出现在返回 items 中。

4. API
   - technical-chart period 放开 daily、weekly、monthly。
   - Schema 不因周期新增另一套字段。
   - calculation_version 如聚合口径影响结果，按契约决定是否升级并同步文档。
   - 不在本阶段修改 Web 周/月按钮。

5. 旧 history
   - 评估是否让旧 history 同步复用聚合函数；只有兼容性测试充分时才修复。
   - 如果不修复，明确记录旧 history 仍只支持 daily，不能让技术图表 API 依赖旧 endpoint。

测试要求：

- 固定跨周、跨月、节假日缺口和月末数据样本。
- 断言 OHLC、volume/amount、date、change_percent 聚合结果。
- 断言指标在聚合后重新计算，并与手工聚合 DataFrame 调用共享引擎一致。
- 覆盖数据不足、全部 volume 缺失、单交易日周/月和预热截断。
- API 覆盖 daily/weekly/monthly、非法 period、60/120/250 和 partial。
- 运行完整指标、API 和旧 history 回归测试。

建议验证命令：

python -m py_compile <本阶段变更 Python 文件>
python -m pytest tests/test_technical_indicators.py tests/test_technical_chart_service.py tests/test_technical_chart_api.py -q
./scripts/ci_gate.sh

文档和进度：

- 更新计算契约、API 文档和 docs/CHANGELOG.md。
- 更新进度表：P4 标记为进行中，记录 05a 聚合测试、未验证市场和下一节点 05b；不得标记 P4 完成。

交付时输出聚合路径、口径、测试、旧 history 决策、风险和回滚方式。完成后停止。
```

## 阶段验收

- 后端 daily/weekly/monthly 返回统一完整指标契约。
- 周/月线先聚合 OHLCV，再重新计算指标。
- 聚合、预热、partial 和旧接口兼容有测试。
- P4 仅标记为进行中。
