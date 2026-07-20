# Cursor 提词 03：技术图表 API

## 前置条件

阶段 01～02 已完成，完整指标引擎和固定样本测试通过，P1 已标记为完成。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、技术图表计算契约、后端能力补全计划、进度表和阶段 01～02 交付记录。

本阶段目标：新增独立的日线技术图表 API，向前端提供完整指标时间序列、支撑压力 summary、数据状态和明确错误语义。不要实现 Web 页面或周线/月线。

实施前：

1. 检查工作区状态，保留用户已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 阅读 api/v1/endpoints/stocks.py、api/v1/schemas/stocks.py、api/v1/router.py、src/services/stock_service.py、数据源异常类型和 API 错误处理规范。
3. 检查现有 API 测试如何覆盖依赖、数据源和认证；沿用真实项目方式，不凭空引入第二套错误框架。
4. 确认技术指标属于公共行情数据，不给请求体或查询参数增加 user_id。

建议代码边界：

- Schema 优先放在 api/v1/schemas/technical_chart.py，或按现有 stocks schema 边界最小扩展。
- 如果新增独立 Schema 文件，同步更新 api/v1/schemas/__init__.py 的导出和项目实际 OpenAPI 规格生成/校验入口。
- 服务层新增 src/services/technical_chart_service.py，负责取数、预热、调用指标引擎、截取展示窗口和组装 summary。
- endpoint 可放在现有 stocks router 下；如文件已过大，可建立独立 endpoint 并在 router 中注册。不要同时维护两条实现。
- 旧 GET /api/v1/stocks/{stock_code}/history 保持原样。

必须实现的接口：

GET /api/v1/stocks/{stock_code}/technical-chart

查询参数：

- period：本阶段只支持 daily；weekly/monthly 明确返回 unsupported_period，不返回日线冒充。
- days：默认 120，允许 60～250。
- indicators：逗号分隔，支持 ma、volume、macd、rsi、boll、kdj、cci、bias、support_resistance；默认完整指标集；未知指标返回 422。

取数和预热：

- display_days 与 calculation_days 分开。
- 按计算契约为最长指标和稳定 EMA 读取额外预热数据，建议至少 display_days+60；不要把预热数据返回给页面。
- 如果数据源实际返回不足，返回可用数据并设置 partial/warnings；完全无数据和数据源失败必须区分。
- 日期排序、重复日期和缺失值交给共享标准化逻辑，服务层不要复制公式。

响应至少包含：

- stock_code、stock_name、period、range_days。
- calculation_version、data_status、data_source、updated_at、warnings。
- items：date、open、high、low、close、volume、amount、change_percent、ma5、ma10、ma20、macd_dif、macd_dea、macd_bar、rsi6、rsi12、rsi24、boll_upper、boll_mid、boll_lower、boll_bandwidth、boll_position、kdj_k、kdj_d、kdj_j、cci、bias5、bias10、bias20、volume_ratio、volume_status。
- summary：latest_close、latest_change_percent、support_levels、resistance_levels、recent_high、recent_low、latest_volume_status。
- 所有数值必须可 JSON 序列化；NaN、Infinity 转为 null，禁止输出非标准 JSON。

状态和错误：

- available：核心行情和请求指标可用。
- partial：有行情，但部分指标因历史不足或字段缺失为 null，并附 warnings。
- empty：合法请求没有历史记录，固定返回 HTTP 200、data_status=empty、items=[] 和 warning。
- source_unavailable：所有数据源失败，映射为 503 或项目统一上游错误。
- 股票代码格式错误复用现有标准化和校验逻辑。
- 不把底层异常 str(e)、密钥、URL 查询凭据或堆栈返回给用户。
- 修正 StockService 当前把所有异常吞成空数组的问题时，保持旧 history 兼容；可为新服务使用明确异常，不要无意改变旧接口。

缓存：

- 本阶段不新增数据库表，也不新增独立技术指标结果缓存。
- 只复用 DataFetcherManager 或项目现有行情数据缓存，确保先建立正确性和未命中性能基线。
- 在测试或交付记录中测量 120/250 点完整指标接口耗时，作为阶段 05c 是否增加结果缓存的依据。
- 如果现有缓存抽象已自动覆盖行情取数，记录实际缓存键和失效条件，不创建平行缓存。
- 缓存优化推迟到阶段 05c；没有测量证据时不得提前增加全局字典或新的持久化缓存。

测试要求：

- 新增 API Schema 和 service 单元测试、endpoint 集成测试。
- 覆盖默认请求、选择指标、未知指标、days 边界、daily、unsupported weekly/monthly、空数据、partial、数据源失败和非有限值。
- 验证 items 日期升序、长度等于展示窗口、预热数据不泄漏、完整指标字段存在。
- 验证旧 history API 响应结构和已有测试未改变。
- 测试必须调用真实共享计算引擎；只允许 mock 外部数据源边界，不 mock 指标结果。
- 若认证开启，沿用项目测试认证上下文，不能绕过全局中间件造成虚假通过。

建议验证命令，按实际测试文件调整：

python -m py_compile api/v1/schemas/technical_chart.py src/services/technical_chart_service.py api/v1/endpoints/stocks.py
python -m pytest tests/test_technical_indicators.py tests/test_technical_chart_service.py tests/test_technical_chart_api.py -q
./scripts/ci_gate.sh

文档和进度：

- 更新 API 专题文档或 OpenAPI 规格生成方式，确保字段与真实 Schema 一致。
- 更新技术图表需求/计算契约中的最终 endpoint 和状态语义。
- 更新 docs/CHANGELOG.md。
- 更新 technical-chart-implementation-progress.html：测试通过后将 P2 标记为完成，记录接口、日期、测试、风险和 P3 前置条件。

本阶段不要修改 apps/dsa-web、桌面端、导航、用户偏好或数据库表。交付后停止，等待 API 契约评审和真实日线 smoke，再进入 Web。
```

## 阶段验收

- 日线技术图表 API 返回完整指标集。
- 预热、null、partial、empty 和 source_unavailable 语义明确。
- 旧 history API 保持兼容。
- 后端测试和 CI 门禁通过，P2 已回填。
